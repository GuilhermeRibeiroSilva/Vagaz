from fastapi import FastAPI, Request, Depends, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import func
import asyncio
import bcrypt
import re
import urllib.request
import urllib.error
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

from scrapers.gupy import buscar_vagas_gupy
from scrapers.linkedin import buscar_vagas_linkedin
from scrapers.remotar import buscar_vagas_remotar
from scrapers.pci import buscar_concursos_pci 
from scrapers.concursos_brasil import buscar_concursos_brasil
from scrapers.empregos import buscar_vagas_empregos
from scrapers.infojobs import buscar_vagas_infojobs

from db.database import SessionLocal, User, SearchFilter, SavedJob, AppConfig, UserConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("vagaz")
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserRegister(BaseModel):
    nome: str
    email: str
    senha: str

class UserLogin(BaseModel):
    email: str
    senha: str
    lembrar: bool = False

class NovoFiltro(BaseModel):
    tipo_busca: str
    nome_filtro: str
    termos: str
    palavras_proibidas: str
    localizacao: str
    formato: str
    scrapers: str
    max_dias: int
    timer_ativo: bool
    intervalo_timer: int

class ConfigPayload(BaseModel):
    headless: bool

class UserEdit(BaseModel):
    nome: str
    email: str
    senha: Optional[str] = None

class PerfilEdit(BaseModel):
    nome: str
    email: str
    senha: Optional[str] = None

class ConfigUsuario(BaseModel):
    ativa: bool
    dias: int
    receber_emails: bool

@app.post("/api/register")
def registrar_usuario(user: UserRegister, db = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")
    
    senha_cripto = bcrypt.hashpw(user.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    novo_usuario = User(nome=user.nome, email=user.email, senha_hash=senha_cripto)
    db.add(novo_usuario)
    db.commit()
    logger.info(f"Novo usuário registrado: {user.email}")
    return {"mensagem": "Conta criada com sucesso!"}

@app.post("/api/login")
async def login_usuario(request: Request, response: Response, db = Depends(get_db)):
    try:
        dados = await request.json()
    except Exception as e:
        logger.error(f"Erro no login (Formato inválido): {e}")
        raise HTTPException(status_code=400, detail="Formato de dados inválido.")

    email_fornecido = dados.get('email', '')
    senha_fornecida = dados.get('senha') or dados.get('password', '')
    lembrar_me = dados.get('lembrar', False)

    if not email_fornecido or not senha_fornecida:
        raise HTTPException(status_code=422, detail="E-mail e senha são obrigatórios.")

    try:
        usuario = db.query(User).filter(User.email == email_fornecido).first()
        if not usuario or not bcrypt.checkpw(senha_fornecida.encode('utf-8'), usuario.senha_hash.encode('utf-8')):
            logger.warning(f"Tentativa de login falha para o email: {email_fornecido}")
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
        
        tempo_expiracao = 604800 if lembrar_me else 86400
        response.set_cookie(key="vagaz_user_id", value=str(usuario.id), max_age=tempo_expiracao, httponly=True)
        
        logger.info(f"Login aprovado: {usuario.nome} (Admin: {usuario.is_admin})")
        return {
            "mensagem": f"Bem-vindo(a), {usuario.nome}!", 
            "user_id": usuario.id, 
            "is_admin": usuario.is_admin
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro interno no login: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor.")

@app.get("/logout")
def logout(response: Response):
    from fastapi.responses import RedirectResponse
    res = RedirectResponse(url="/")
    res.delete_cookie("vagaz_user_id")
    return res

@app.get("/", response_class=HTMLResponse)
async def pagina_inicial(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def pagina_dashboard(request: Request, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: 
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    usuario = db.query(User).filter(User.id == int(vagaz_user_id)).first()
    if not usuario:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": usuario})

@app.get("/api/filtros")
def listar_filtros(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    return db.query(SearchFilter).filter(SearchFilter.user_id == int(vagaz_user_id)).all()

@app.post("/api/filtros")
def criar_editar_filtro(filtro: NovoFiltro, id: Optional[int] = None, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    
    if id: 
        f_db = db.query(SearchFilter).filter(SearchFilter.id == id, SearchFilter.user_id == int(vagaz_user_id)).first()
        if f_db:
            f_db.tipo_busca = filtro.tipo_busca
            f_db.nome_filtro = filtro.nome_filtro
            f_db.termos = filtro.termos
            f_db.palavras_proibidas = filtro.palavras_proibidas
            f_db.localizacao = filtro.localizacao
            f_db.formato = filtro.formato
            f_db.scrapers = filtro.scrapers
            f_db.max_dias = filtro.max_dias
            f_db.timer_ativo = filtro.timer_ativo
            f_db.intervalo_timer = filtro.intervalo_timer
            db.commit()
            return {"mensagem": "Rastreador atualizado!"}
            
    novo = SearchFilter(user_id=int(vagaz_user_id), **filtro.dict())
    db.add(novo)
    db.commit()
    return {"mensagem": "Rastreador criado com sucesso!"}

@app.delete("/api/filtros/{filtro_id}")
def excluir_filtro(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if f_db:
        db.query(SavedJob).filter(SavedJob.filtro_id == filtro_id).delete()
        db.delete(f_db)
        db.commit()
        return {"mensagem": "Excluído!"}
    raise HTTPException(status_code=404)

@app.delete("/api/filtros/{filtro_id}/vagas")
def limpar_vagas_do_filtro(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if not f_db: raise HTTPException(status_code=404, detail="Radar não encontrado")
    
    db.query(SavedJob).filter(SavedJob.filtro_id == filtro_id).delete()
    db.commit()
    return {"mensagem": "Vagas limpas com sucesso!"}

@app.delete("/api/resultados/{vaga_id}")
def deletar_resultado_individual(vaga_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    vaga = db.query(SavedJob).filter(SavedJob.id == vaga_id, SavedJob.user_id == int(vagaz_user_id)).first()
    if not vaga: raise HTTPException(status_code=404, detail="Vaga não encontrada")
    db.delete(vaga)
    db.commit()
    return {"mensagem": "Vaga excluída com sucesso!"}

@app.get("/api/resultados")
def listar_resultados(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    return db.query(SavedJob).filter(SavedJob.user_id == int(vagaz_user_id)).order_by(SavedJob.id.desc()).all()

def enviar_email_alerta(email_destino: str, nome_usuario: str, nome_radar: str, vagas_top: list):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")

    if not SMTP_USER or not SMTP_PASS:
        logger.warning("⚠️ E-mail não enviado: Faltam credenciais no arquivo .env")
        return

    if not vagas_top: return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 Vagaz: Encontramos {len(vagas_top)} novas vagas em '{nome_radar}'!"
    msg["From"] = SMTP_USER
    msg["To"] = email_destino

    linhas_vagas = ""
    for v in vagas_top:
        linhas_vagas += f"""
        <li style="margin-bottom: 15px; padding: 15px; border-left: 4px solid #0d9488; background-color: #f8fafc; border-radius: 4px;">
            <strong style="color: #0f172a; font-size: 16px;">{v['titulo']}</strong><br>
            <span style="color: #64748b; font-size: 13px;">🏢 {v['empresa']} | 📍 {v['local']} | 🤖 {v['scraper']}</span><br>
            <a href="{v['link']}" target="_blank" style="color: #0d9488; font-weight: bold; font-size: 13px; text-decoration: none; display: inline-block; margin-top: 8px;">Ver Oportunidade ➔</a>
        </li>
        """

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
        <h2 style="color: #0d9488; margin-top: 0;">Olá, {nome_usuario}!</h2>
        <p>O seu rastreador terminou a varredura e separou oportunidades fresquinhas.</p>
        <p>Aqui estão os destaques do seu radar <strong>{nome_radar}</strong>:</p>
        <ul style="list-style-type: none; padding: 0;">
            {linhas_vagas}
        </ul>
        <div style="text-align: center; margin-top: 30px;">
            <a href="http://localhost:8000/dashboard" style="background-color: #0f172a; color: #ffffff; padding: 14px 28px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block;">Acessar Painel Vagaz</a>
        </div>
        <p style="margin-top: 30px; font-size: 12px; color: #94a3b8; text-align: center;">Este é um alerta automático do Vagaz.</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, email_destino, msg.as_string())
        server.quit()
        logger.info(f"📧 E-mail enviado com sucesso para {email_destino}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar e-mail para {email_destino}: {e}")

task_queue = asyncio.Queue()
fila_espera = [] 
status_varreduras = {}
timers_memoria = {} 

@app.get("/api/varredura/{filtro_id}/status")
def status_varredura(filtro_id: int):
    if filtro_id in status_varreduras:
        status_varreduras[filtro_id]["last_poll"] = datetime.now()

    if filtro_id in fila_espera:
        pos = fila_espera.index(filtro_id) + 1
        return {
            "etapa": f"⏳ Aguardando na fila (Sua posição: {pos})",
            "progresso": 0
        }
    return status_varreduras.get(filtro_id, {"etapa": "Iniciando motor...", "progresso": 0})

@app.post("/api/varredura/{filtro_id}/cancelar")
def cancelar_varredura_real(filtro_id: int):
    if filtro_id in status_varreduras:
        status_varreduras[filtro_id]["cancelado"] = True
    if filtro_id in fila_espera:
        fila_espera.remove(filtro_id)
    logger.warning(f"[RADAR-{filtro_id}] Cancelamento solicitado pelo usuário.")
    return {"mensagem": "Cancelamento confirmado."}

async def executar_varredura_async(filtro_id: int, is_auto: bool = False):
    status_varreduras[filtro_id] = {
        "etapa": "Preparando os robôs invisíveis...", 
        "cancelado": False, 
        "progresso": 5,
        "last_poll": datetime.now()
    }
    db = SessionLocal()
    try:
        f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id).first()
        if not f_db: return 0
        
        user_db = db.query(User).filter(User.id == f_db.user_id).first()
        config_headless = db.query(AppConfig).filter(AppConfig.chave == "headless_mode").first()
        is_headless = config_headless.valor == 'true' if config_headless else True
        
        scrapers_escolhidos = [s.strip() for s in f_db.scrapers.split(',') if s.strip()]
        palavras_proibidas = [p.strip().lower() for p in f_db.palavras_proibidas.split(',') if p.strip()]
        resultados_totais = []
        total_sites = len(scrapers_escolhidos)
        
        logger.info(f"[RADAR-{filtro_id}] Iniciando. Termos: '{f_db.termos}', Sites: {total_sites}")
        
        for i, scraper in enumerate(scrapers_escolhidos):
            if status_varreduras.get(filtro_id, {}).get("cancelado"):
                logger.warning(f"[RADAR-{filtro_id}] Abortado internamente.")
                break
                
            status_varreduras[filtro_id]["progresso"] = int(((i) / total_sites) * 80) + 5
            status_varreduras[filtro_id]["etapa"] = f"🔎 Vasculhando {scraper} ({i+1}/{total_sites})..."
            logger.info(f"[RADAR-{filtro_id}] [{scraper}] Raspando dados...")
            
            cfg_ind = db.query(AppConfig).filter(AppConfig.chave == f"headless_{scraper}").first()
            scraper_headless = cfg_ind.valor == 'true' if cfg_ind else is_headless
            
            funcoes_map = {
                "Empregos": lambda: buscar_vagas_empregos(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, 3, headless=scraper_headless),
                "InfoJobs": lambda: buscar_vagas_infojobs(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, 2, headless=scraper_headless),
                "Gupy": lambda: buscar_vagas_gupy(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, 4, headless=scraper_headless),
                "LinkedIn": lambda: buscar_vagas_linkedin(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, 4, headless=scraper_headless),
                "Remotar": lambda: buscar_vagas_remotar(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, 3, headless=scraper_headless),
                "PCI Concursos": lambda: buscar_concursos_pci(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, headless=scraper_headless),
                "Concursos Brasil": lambda: buscar_concursos_brasil(f_db.termos, f_db.localizacao, f_db.palavras_proibidas, headless=scraper_headless),
            }
            
            func_scraper = funcoes_map.get(scraper)
            if not func_scraper: continue

            tentativas = 2
            resultados_scraper = []
            
            for tentativa in range(tentativas):
                try:
                    resultados_scraper = await asyncio.wait_for(run_in_threadpool(func_scraper), timeout=300.0)
                    break 
                except asyncio.TimeoutError:
                    logger.error(f"[RADAR-{filtro_id}] [{scraper}] TIMEOUT: O site demorou mais de 60s.")
                    if tentativa == 0: logger.info(f"[RADAR-{filtro_id}] [{scraper}] Retentando...")
                except Exception as e:
                    logger.error(f"[RADAR-{filtro_id}] [{scraper}] Falha: {str(e)[:50]}...")
                    if tentativa == 0: logger.info(f"[RADAR-{filtro_id}] [{scraper}] Retentando...")
            
            if resultados_scraper:
                for res in resultados_scraper:
                    res['scraper'] = scraper
                    if 'local' not in res: res['local'] = 'Não informado'
                    if 'data' not in res: res['data'] = 'Recente'
                logger.info(f"[RADAR-{filtro_id}] [{scraper}] Sucesso: {len(resultados_scraper)} vagas.")
                resultados_totais.extend(resultados_scraper)

        if status_varreduras.get(filtro_id, {}).get("cancelado"):
            logger.info(f"🛑 [RADAR-{filtro_id}] Processamento cancelado. Nenhuma vaga será salva.")
            if filtro_id in status_varreduras:
                del status_varreduras[filtro_id]
            return 0

        status_varreduras[filtro_id]["progresso"] = 90
        status_varreduras[filtro_id]["etapa"] = "💾 Aplicando regras de negócio..."
        
        novas_vagas = 0
        links_vistos = set()
        titulos_vistos = set()
        vagas_alert_email = []
        links_vistos_email = set()
        titulos_vistos_email = set()
        
        agora_relogio = datetime.now()
        agora_calendario = agora_relogio.replace(hour=23, minute=59, second=59, microsecond=0)
        
        for vaga in resultados_totais:
            titulo = vaga.get('titulo', '')
            link = vaga.get('link', '')
            scraper_nome = vaga.get('scraper', 'Desconhecido')
            formato = vaga.get('formato', 'Padrão')
            
            empresa_bruta = vaga.get('empresa', '')
            empresa_padronizada = "Confidencial" if not empresa_bruta or str(empresa_bruta).strip() == "" else str(empresa_bruta).strip()
            
            local_bruto = str(vaga.get('local', '')).strip()
            local_lower = local_bruto.lower()
            if scraper_nome == "Remotar" or "qualquer lugar" in local_lower: local_padronizado = "Remoto"
            elif not local_bruto: local_padronizado = "Brasil"
            else: local_padronizado = local_bruto

            data_bruta = str(vaga.get('data', 'hoje')).strip().lower()
            tempo_subtrair_relogio, tempo_subtrair_calendario, data_v = None, None, None
            
            if 'hoje' in data_bruta or 'recente' in data_bruta or 'agora' in data_bruta or 'minuto' in data_bruta: tempo_subtrair_calendario = timedelta(days=0)
            elif 'ontem' in data_bruta: tempo_subtrair_calendario = timedelta(days=1)
            elif '/' in data_bruta or '-' in data_bruta: 
                try:
                    match_full = re.search(r'(\d{2})/(\d{2})/(\d{4})', data_bruta)
                    match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', data_bruta)
                    match_short = re.search(r'(\d{2})/(\d{2})', data_bruta)
                    if match_full: data_v = datetime(int(match_full.group(3)), int(match_full.group(2)), int(match_full.group(1)))
                    elif match_iso: data_v = datetime(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
                    elif match_short:
                        data_v = datetime(agora_relogio.year, int(match_short.group(2)), int(match_short.group(1)))
                        if data_v > agora_relogio: data_v = datetime(agora_relogio.year - 1, int(match_short.group(2)), int(match_short.group(1)))
                except: pass
            else:
                numeros = re.findall(r'\d+', data_bruta)
                if numeros:
                    valor = int(numeros[0])
                    if 'hora' in data_bruta or re.search(r'\d+h', data_bruta): tempo_subtrair_relogio = timedelta(hours=valor)
                    elif 'dia' in data_bruta or re.search(r'\d+d', data_bruta): tempo_subtrair_calendario = timedelta(days=valor)
                    elif 'semana' in data_bruta: tempo_subtrair_calendario = timedelta(days=valor * 7)
                    elif 'mês' in data_bruta or 'mes' in data_bruta: tempo_subtrair_calendario = timedelta(days=valor * 30)
                    elif 'ano' in data_bruta: tempo_subtrair_calendario = timedelta(days=valor * 365)

            if data_v: data_exata_calculada = data_v; dias_vaga = (agora_relogio - data_v).days 
            elif tempo_subtrair_relogio is not None: data_exata_calculada = agora_relogio - tempo_subtrair_relogio; dias_vaga = tempo_subtrair_relogio.days
            elif tempo_subtrair_calendario is not None: data_exata_calculada = agora_calendario - tempo_subtrair_calendario; dias_vaga = (agora_relogio - data_exata_calculada).days
            else: data_exata_calculada = agora_relogio; dias_vaga = 0

            if dias_vaga < 0: dias_vaga = 0
            data_padronizada = data_exata_calculada.strftime("%d/%m/%Y")

            chave_duplicidade = (titulo.lower().strip(), empresa_padronizada.lower().strip())

            if not link or link in links_vistos or chave_duplicidade in titulos_vistos: 
                continue
                
            texto_analise = (titulo + " " + local_padronizado).lower()
            if any(p and p in texto_analise for p in palavras_proibidas): continue
            if dias_vaga > f_db.max_dias: continue
            
            links_vistos.add(link)
            titulos_vistos.add(chave_duplicidade)
            
            existe_link = db.query(SavedJob).filter(SavedJob.link == link, SavedJob.user_id == f_db.user_id).first()
            existe_titulo = db.query(SavedJob).filter(
                SavedJob.user_id == f_db.user_id, 
                func.lower(SavedJob.titulo) == titulo.lower().strip(), 
                func.lower(SavedJob.empresa) == empresa_padronizada.lower().strip()
            ).first()
            
            if not existe_link and not existe_titulo:
                db.add(SavedJob(
                    user_id=f_db.user_id, filtro_id=f_db.id, tipo_busca=f_db.tipo_busca,
                    scraper=scraper_nome, empresa=empresa_padronizada, titulo=titulo, 
                    link=link, data_publicacao=data_padronizada, local=local_padronizado, formato=formato
                ))
                novas_vagas += 1
                
                if link not in links_vistos_email and chave_duplicidade not in titulos_vistos_email:
                    vagas_alert_email.append({"titulo": titulo, "empresa": empresa_padronizada, "link": link, "local": local_padronizado, "scraper": scraper_nome})
                    links_vistos_email.add(link)
                    titulos_vistos_email.add(chave_duplicidade)
        
        f_db.ultima_varredura = datetime.now()
        db.commit()
        
        last_poll = status_varreduras.get(filtro_id, {}).get("last_poll")
        is_offline = not last_poll or (datetime.now() - last_poll).total_seconds() > 10

        user_cfg = db.query(UserConfig).filter(UserConfig.user_id == f_db.user_id).first()
        pode_enviar_email = user_cfg.receber_emails if user_cfg else True

        if novas_vagas > 0 and user_db and vagas_alert_email and pode_enviar_email:
            if is_auto or is_offline:
                vagas_por_site = {}
                for v in vagas_alert_email:
                    site = v['scraper']
                    if site not in vagas_por_site: vagas_por_site[site] = []
                    vagas_por_site[site].append(v)
                
                top4_diversificado = []
                while len(top4_diversificado) < 4 and vagas_por_site:
                    sites_vazios = []
                    for site, lista_vagas in vagas_por_site.items():
                        if len(top4_diversificado) >= 4: break
                        if lista_vagas: top4_diversificado.append(lista_vagas.pop(0))
                        else: sites_vazios.append(site)
                    for site in sites_vazios: del vagas_por_site[site]

                enviar_email_alerta(user_db.email, user_db.nome, f_db.nome_filtro, top4_diversificado)
            else:
                logger.info(f"🔇 E-mail não enviado: O usuário já está com o painel aberto.")

        status_varreduras[filtro_id]["progresso"] = 100
        status_varreduras[filtro_id]["etapa"] = "Processo Concluído!"
        
        logger.info(f"✅ [RADAR-{filtro_id}] Finalizado! {novas_vagas} oportunidades novas entregues.")
        
        await asyncio.sleep(2)
        if filtro_id in status_varreduras:
            del status_varreduras[filtro_id]
            
        return novas_vagas
    finally:
        db.close()

async def radar_worker():
    while True:
        tarefa = await task_queue.get()
        filtro_id = tarefa["id"]
        is_auto = tarefa["is_auto"]
        try:
            if filtro_id in fila_espera:
                fila_espera.remove(filtro_id)
            if status_varreduras.get(filtro_id, {}).get("cancelado"):
                continue
            await executar_varredura_async(filtro_id, is_auto)
        except Exception as e:
            logger.error(f"❌ [WORKER] Erro crítico: {e}")
        finally:
            task_queue.task_done()

@app.post("/api/filtros/{filtro_id}/rodar")
async def rodar_filtro_manual(filtro_id: int):
    fila_espera.append(filtro_id)
    await task_queue.put({"id": filtro_id, "is_auto": False})
    return {"mensagem": "Busca enviada para processamento!"}

@app.patch("/api/filtros/{filtro_id}/toggle")
def toggle_timer(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if f_db:
        f_db.timer_ativo = not f_db.timer_ativo
        db.commit()
        estado = "ATIVADA" if f_db.timer_ativo else "DESATIVADA"
        return {"mensagem": f"Automação {estado} com sucesso!"}
    raise HTTPException(status_code=404)

@app.on_event("startup")
async def iniciar_automacao():
    asyncio.create_task(radar_worker())
    asyncio.create_task(radar_worker())
    asyncio.create_task(loop_de_automacao())

async def loop_de_automacao():
    while True:
        await asyncio.sleep(60) 
        db = SessionLocal()
        try:
            agora = datetime.now()
            limite_global = agora - timedelta(days=60)
            db.query(SavedJob).filter(SavedJob.data_salva < limite_global).delete()

            configs_limpeza = db.query(UserConfig).filter(UserConfig.auto_limpeza_ativa == True).all()
            for cfg in configs_limpeza:
                limite_data = agora - timedelta(days=cfg.auto_limpeza_dias)
                db.query(SavedJob).filter(SavedJob.user_id == cfg.user_id, SavedJob.data_salva < limite_data).delete()

            filtros_ativos = db.query(SearchFilter).filter(SearchFilter.timer_ativo == True).all()
            for f in filtros_ativos:
                ultima_vez = timers_memoria.get(f.id)
                if not ultima_vez or (agora - ultima_vez).total_seconds() >= (f.intervalo_timer * 60):
                    timers_memoria[f.id] = agora
                    if f.id not in fila_espera:
                        fila_espera.append(f.id)
                        await task_queue.put({"id": f.id, "is_auto": True})
            db.commit()
        except Exception as e:
            logger.error(f"Erro no Cronjob: {e}")
        finally:
            db.close()

@app.get("/admin", response_class=HTMLResponse)
async def pagina_admin(request: Request, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    usuario = db.query(User).filter(User.id == int(vagaz_user_id)).first()
    if not usuario or not usuario.is_admin:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("admin.html", {"request": request, "user": usuario})

@app.get("/api/admin/stats")
def get_admin_stats(db = Depends(get_db)):
    hoje_inicio = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    vagas_hoje = db.query(SavedJob).filter(SavedJob.data_salva >= hoje_inicio).count()
    filtros_ativos = db.query(SearchFilter).filter(SearchFilter.timer_ativo == True).count()
    
    top_scrapers_query = db.query(SavedJob.scraper, func.count(SavedJob.id).label('total')).group_by(SavedJob.scraper).order_by(func.count(SavedJob.id).desc()).limit(3).all()
    top_scrapers = [{"nome": s.scraper, "total": s.total} for s in top_scrapers_query]
    
    stats = {
        'total_usuarios': db.query(User).count(),
        'total_filtros': db.query(SearchFilter).count(),
        'filtros_ativos': filtros_ativos,
        'total_vagas': db.query(SavedJob).count(),
        'vagas_hoje': vagas_hoje,
        'top_scrapers': top_scrapers
    }
    return stats

@app.get("/api/admin/fila")
def get_fila_status():
    ativas = []
    for f_id, status in status_varreduras.items():
        if not status.get("cancelado") and "finalizado" not in status.get("etapa", "").lower():
            ativas.append({"id": f_id, "etapa": status.get("etapa")})
    
    return {
        "tamanho_fila": len(fila_espera),
        "fila": fila_espera,
        "varreduras_ativas": ativas
    }

@app.post("/api/admin/qa/ping")
def ping_scraper(payload: dict):
    url = payload.get("url")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'})
        response = urllib.request.urlopen(req, timeout=8)
        return {"status": "ok", "code": response.getcode(), "message": "Site Operante"}
    except urllib.error.HTTPError as e:
        status = "warning" if e.code in [403, 401] else "error"
        return {"status": status, "code": e.code, "message": f"Retornou {e.code} (Proteção Anti-Bot?)"}
    except Exception as e:
        return {"status": "error", "code": 500, "message": "Timeout ou Fora do Ar"}

@app.get("/api/admin/config")
def get_config(db = Depends(get_db)):
    headless = db.query(AppConfig).filter(AppConfig.chave == 'headless_mode').first()
    is_headless = headless.valor == 'true' if headless else True
    return {"headless_mode": is_headless}

@app.post("/api/admin/config/headless")
def toggle_headless(payload: ConfigPayload, db = Depends(get_db)):
    valor_str = 'true' if payload.headless else 'false'
    config = db.query(AppConfig).filter(AppConfig.chave == 'headless_mode').first()
    if config: config.valor = valor_str
    else: db.add(AppConfig(chave="headless_mode", valor=valor_str))
    db.commit()
    return {"message": "Configuração atualizada", "headless_mode": payload.headless}

@app.get("/api/admin/scrapers")
def get_scrapers(db = Depends(get_db)):
    configs = db.query(AppConfig).filter(AppConfig.chave.like("headless_%")).all()
    return [{"nome": c.chave.replace("headless_", ""), "headless": c.valor == "true"} for c in configs]

@app.post("/api/admin/scrapers/{nome}/toggle")
def toggle_scraper_individual(nome: str, db = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.chave == f"headless_{nome}").first()
    if config:
        config.valor = "false" if config.valor == "true" else "true"
        db.commit()
        logger.info(f"Modo Fantasma do scraper {nome} alterado para: {config.valor.upper()}")
        return {"mensagem": f"Scraper {nome} atualizado!", "headless": config.valor == "true"}
    raise HTTPException(status_code=404)

@app.get("/api/admin/usuarios")
def get_all_users(db = Depends(get_db)):
    usuarios = db.query(User).all()
    users_data = []
    for u in usuarios:
        total_vagas = db.query(SavedJob).filter(SavedJob.user_id == u.id).count()
        filtros = db.query(SearchFilter).filter(SearchFilter.user_id == u.id).all()
        users_data.append({
            "id": u.id, "nome": u.nome, "email": u.email, "is_admin": u.is_admin,
            "total_vagas": total_vagas, "filtros": [{"id": f.id, "termo": f.termos} for f in filtros]
        })
    return users_data

@app.post("/api/admin/usuarios")
def create_user_admin(user: UserRegister, db = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="E-mail já existe.")
    senha_cripto = bcrypt.hashpw(user.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    novo = User(nome=user.nome, email=user.email, senha_hash=senha_cripto)
    db.add(novo)
    db.commit()
    logger.info(f"Novo usuário criado via Admin: {user.nome}")
    return {"mensagem": "Usuário criado com sucesso!"}

@app.put("/api/admin/usuarios/{user_id}")
def edit_user_admin(user_id: int, dados: UserEdit, db = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if dados.email != user.email:
        if db.query(User).filter(User.email == dados.email).first():
            raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado em outra conta.")
            
    user.nome = dados.nome
    user.email = dados.email
    if dados.senha and len(dados.senha) >= 6:
        user.senha_hash = bcrypt.hashpw(dados.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
    db.commit()
    logger.info(f"Usuário ID {user_id} ({user.nome}) editado com sucesso.")
    return {"mensagem": "Usuário atualizado com sucesso!"}

@app.delete("/api/admin/usuarios/{user_id}")
def delete_user_admin(user_id: int, db = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    if user.is_admin: raise HTTPException(status_code=403, detail="Não pode deletar o Admin!")
    
    db.query(SavedJob).filter(SavedJob.user_id == user_id).delete()
    db.query(SearchFilter).filter(SearchFilter.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    logger.info(f"Usuário ID {user_id} excluído.")
    return {"mensagem": "Usuário deletado."}

@app.get("/api/admin/usuarios/{user_id}/detalhes")
def get_user_details(user_id: int, db = Depends(get_db)):
    filtros = db.query(SearchFilter).filter(SearchFilter.user_id == user_id).all()
    dados_filtros = []
    for f in filtros:
        vagas = db.query(SavedJob).filter(SavedJob.filtro_id == f.id).order_by(SavedJob.id.desc()).all()
        dados_filtros.append({
            "id": f.id, "nome": f.nome_filtro, "termos": f.termos, "palavras_proibidas": f.palavras_proibidas,
            "localizacao": f.localizacao, "scrapers": f.scrapers, "timer_ativo": f.timer_ativo,
            "vagas": [{"titulo": v.titulo, "empresa": v.empresa, "link": v.link, "data": v.data_publicacao, "local": v.local, "scraper": v.scraper} for v in vagas]
        })
    return {"filtros": dados_filtros}

@app.get("/api/admin/db/tables")
def get_tables_info(db = Depends(get_db)):
    return [
        {"nome": "users", "linhas": db.query(User).count()},
        {"nome": "search_filters", "linhas": db.query(SearchFilter).count()},
        {"nome": "saved_jobs", "linhas": db.query(SavedJob).count()},
        {"nome": "app_configs", "linhas": db.query(AppConfig).count()}
    ]

@app.get("/api/admin/db/tables/{tabela}/dados")
def ver_dados_tabela(tabela: str, db = Depends(get_db)):
    if tabela == "users":
        rows = db.query(User).limit(50).all()
        return [{"id": r.id, "nome": r.nome, "email": r.email, "admin": r.is_admin} for r in rows]
    elif tabela == "search_filters":
        rows = db.query(SearchFilter).limit(50).all()
        return [{"id": r.id, "user_id": r.user_id, "termos": r.termos, "ativo": r.ativo} for r in rows]
    elif tabela == "saved_jobs":
        rows = db.query(SavedJob).order_by(SavedJob.id.desc()).limit(50).all()
        return [{"id": r.id, "titulo": r.titulo, "scraper": r.scraper} for r in rows]
    elif tabela == "app_configs":
        rows = db.query(AppConfig).all()
        return [{"chave": r.chave, "valor": r.valor} for r in rows]
    raise HTTPException(status_code=400)

@app.delete("/api/admin/db/clear/{tabela}")
def clear_table(tabela: str, db = Depends(get_db)):
    tabelas_map = { 'users': User, 'search_filters': SearchFilter, 'saved_jobs': SavedJob, 'app_configs': AppConfig }
    if tabela not in tabelas_map: raise HTTPException(status_code=400, detail="Tabela inválida")
    
    if tabela == "users": db.query(User).filter(User.is_admin == False).delete()
    else: db.query(tabelas_map[tabela]).delete()
    db.commit()
    return {"message": f"Tabela {tabela} limpa com sucesso!"}

@app.delete("/api/admin/db/nuke")
def limpar_banco_total(db = Depends(get_db)):
    db.query(SavedJob).delete()
    db.query(SearchFilter).delete()
    db.query(AppConfig).delete()
    db.query(User).filter(User.is_admin == False).delete()
    db.commit()
    logger.warning("☢️ LIMPEZA TOTAL REALIZADA. O sistema foi resetado à estaca zero.")
    return {"mensagem": "Tudo foi varrido. Apenas a sua conta de Admin sobreviveu."}

@app.delete("/api/admin/filtros/{filtro_id}/vagas")
def limpar_vagas_filtro_admin(filtro_id: int, db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id).first()
    if not f_db: raise HTTPException(status_code=404, detail="Radar não encontrado")
    apagadas = db.query(SavedJob).filter(SavedJob.filtro_id == filtro_id).delete()
    db.commit()
    logger.info(f"Admin esvaziou {apagadas} vagas do radar ID {filtro_id}.")
    return {"mensagem": f"Vagas do radar limpas com sucesso!"}

@app.get("/api/usuario/dados")
def get_user_dados(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == int(vagaz_user_id)).first()
    cfg = db.query(UserConfig).filter(UserConfig.user_id == int(vagaz_user_id)).first()
    
    if not cfg:
        cfg = UserConfig(auto_limpeza_ativa=False, auto_limpeza_dias=30, receber_emails=True)
        
    return {
        "perfil": {"nome": user.nome, "email": user.email},
        "config": {"ativa": cfg.auto_limpeza_ativa, "dias": cfg.auto_limpeza_dias, "receber_emails": cfg.receber_emails}
    }

@app.put("/api/usuario/perfil")
def update_user_perfil(payload: PerfilEdit, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == int(vagaz_user_id)).first()
    
    if payload.email != user.email:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Este e-mail já está em uso.")
            
    user.nome = payload.nome
    user.email = payload.email
    if payload.senha and len(payload.senha) >= 6:
        user.senha_hash = bcrypt.hashpw(payload.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
    db.commit()
    return {"mensagem": "Perfil atualizado com sucesso!"}

@app.post("/api/usuario/config")
def save_user_config(payload: ConfigUsuario, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    cfg = db.query(UserConfig).filter(UserConfig.user_id == int(vagaz_user_id)).first()
    if cfg:
        cfg.auto_limpeza_ativa = payload.ativa
        cfg.auto_limpeza_dias = payload.dias
        cfg.receber_emails = payload.receber_emails
    else:
        db.add(UserConfig(user_id=int(vagaz_user_id), auto_limpeza_ativa=payload.ativa, auto_limpeza_dias=payload.dias, receber_emails=payload.receber_emails))
    db.commit()
    return {"mensagem": "Preferências salvas!"}

@app.post("/api/filtros/pausar_todos")
def pausar_todos_rastreadores(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    filtros = db.query(SearchFilter).filter(SearchFilter.user_id == int(vagaz_user_id)).all()
    for f in filtros:
        f.timer_ativo = False
    db.commit()
    return {"mensagem": "Modo Férias ativado! Todos os rastreadores foram pausados."}

@app.delete("/api/usuario/conta")
def excluir_minha_conta(response: Response, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    user_id = int(vagaz_user_id)
    
    db.query(SavedJob).filter(SavedJob.user_id == user_id).delete()
    db.query(SearchFilter).filter(SearchFilter.user_id == user_id).delete()
    db.query(UserConfig).filter(UserConfig.user_id == user_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    
    response.delete_cookie("vagaz_user_id")
    return {"mensagem": "Sua conta foi excluída para sempre. Adeus!"}