from fastapi import FastAPI
from scrapers.gupy import buscar_vagas_gupy
from scrapers.linkedin import buscar_vagas_linkedin
from scrapers.solides import buscar_vagas_solides
from scrapers.programathor import buscar_vagas_programathor
from scrapers.remotar import buscar_vagas_remotar
from scrapers.pci import buscar_concursos_pci 
from scrapers.concursos_brasil import buscar_concursos_brasil
from scrapers.gran_cursos import buscar_concursos_gran
from scrapers.folha_qc import buscar_concursos_folha 
from scrapers.empregos import buscar_vagas_empregos
from scrapers.infojobs import buscar_vagas_infojobs
#----------------------#
from fastapi import FastAPI, Request, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import bcrypt
# Adicionado importação do AppConfig
from database import SessionLocal, User, SearchFilter, SavedJob, AppConfig, UserConfig
from fastapi import Cookie 
from typing import Optional
import asyncio
import re
from datetime import datetime
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Função para abrir e fechar a conexão com o banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- MODELOS DE DADOS PARA A API ---
class UserRegister(BaseModel):
    nome: str
    email: str
    senha: str

class UserLogin(BaseModel):
    email: str
    senha: str
    lembrar: bool = False  # <-- O segredo está aqui

# --- ROTAS DE AUTENTICAÇÃO ---

@app.post("/api/register")
def registrar_usuario(user: UserRegister, db = Depends(get_db)):
    usuario_existente = db.query(User).filter(User.email == user.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")
    
    senha_criptografada = bcrypt.hashpw(user.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    novo_usuario = User(nome=user.nome, email=user.email, senha_hash=senha_criptografada)
    db.add(novo_usuario)
    db.commit()
    
    return {"mensagem": "Conta criada com sucesso!"}

@app.post("/api/login")
async def login_usuario(request: Request, response: Response, db = Depends(get_db)):
    # 1. CAPTURA BRUTA: Pega tudo que veio do site antes de qualquer validação
    try:
        dados = await request.json()
        log_admin(f"\n📦 [RAIO-X] DADOS RECEBIDOS DO SITE: {dados}")
    except Exception as e:
        log_admin(f"\n❌ [RAIO-X] ERRO: O site não enviou um JSON válido. Erro: {e}")
        raise HTTPException(status_code=400, detail="Formato de dados inválido.")

    # 2. Extrai os campos flexibilizando os nomes (aceita 'senha' ou 'password')
    email_fornecido = dados.get('email', '')
    senha_fornecida = dados.get('senha') or dados.get('password', '')
    lembrar_me = dados.get('lembrar', False)

    if not email_fornecido or not senha_fornecida:
        log_admin("❌ [RAIO-X] Faltou e-mail ou senha!")
        raise HTTPException(status_code=422, detail="E-mail e senha são obrigatórios.")

    try:
        # 3. Busca no banco de dados
        usuario = db.query(User).filter(User.email == email_fornecido).first()
        if not usuario:
            log_admin(f"❌ [RAIO-X] E-mail '{email_fornecido}' não existe no banco.")
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
        
        # 4. Verifica a criptografia
        senha_fornecida_bytes = senha_fornecida.encode('utf-8')
        senha_banco_bytes = usuario.senha_hash.encode('utf-8')
        
        if not bcrypt.checkpw(senha_fornecida_bytes, senha_banco_bytes):
            log_admin("❌ [RAIO-X] Senha não bateu com a criptografia do banco.")
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
        
        # 5. Sucesso e Cookie
        tempo_expiracao = 604800 if lembrar_me else 86400
        response.set_cookie(key="vagaz_user_id", value=str(usuario.id), max_age=tempo_expiracao, httponly=True)
        
        log_admin(f"✅ [RAIO-X] LOGIN APROVADO! Usuário: {usuario.nome} (Admin: {usuario.is_admin})")
        
        return {
            "mensagem": f"Bem-vindo(a), {usuario.nome}!", 
            "user_id": usuario.id, 
            "is_admin": usuario.is_admin
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_admin(f"\n❌ ERRO INTERNO NO BANCO/SERVIDOR: {e}\n")
        raise HTTPException(status_code=500, detail="Erro interno no servidor.")

# --- ROTAS DO DASHBOARD E FILTROS ---

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

@app.get("/logout")
def logout(response: Response):
    from fastapi.responses import RedirectResponse
    res = RedirectResponse(url="/")
    res.delete_cookie("vagaz_user_id")
    return res

# MODELOS PYDANTIC
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

@app.get("/api/filtros")
def listar_filtros(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
    filtros = db.query(SearchFilter).filter(SearchFilter.user_id == int(vagaz_user_id)).all()
    return filtros

@app.post("/api/filtros")
def criar_editar_filtro(filtro: NovoFiltro, id: Optional[int] = None, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
    
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
            return {"mensagem": "Filtro atualizado!"}
            
    novo = SearchFilter(
        user_id=int(vagaz_user_id),
        tipo_busca=filtro.tipo_busca,
        nome_filtro=filtro.nome_filtro,
        termos=filtro.termos,
        palavras_proibidas=filtro.palavras_proibidas,
        localizacao=filtro.localizacao,
        formato=filtro.formato,
        scrapers=filtro.scrapers,
        max_dias=filtro.max_dias,
        timer_ativo=filtro.timer_ativo,
        intervalo_timer=filtro.intervalo_timer
    )
    db.add(novo)
    db.commit()
    return {"mensagem": "Filtro criado com sucesso!"}

@app.delete("/api/filtros/{filtro_id}")
def excluir_filtro(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if f_db:
        db.delete(f_db)
        db.commit()
        return {"mensagem": "Excluído!"}
    raise HTTPException(status_code=404)

# 4. LIMPAR APENAS AS VAGAS DE UM FILTRO ESPECÍFICO
@app.delete("/api/filtros/{filtro_id}/vagas")
def limpar_vagas_do_filtro(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
        
    # Verifica se o radar existe e pertence a este usuário
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if not f_db:
        raise HTTPException(status_code=404, detail="Radar não encontrado")
    
    # Deleta todas as vagas atreladas a este radar
    db.query(SavedJob).filter(SavedJob.filtro_id == filtro_id).delete()
    db.commit()
    
    return {"mensagem": "Todas as vagas deste radar foram limpas com sucesso!"}

# 6. EXCLUIR VAGA INDIVIDUALMENTE
@app.delete("/api/resultados/{vaga_id}")
def deletar_resultado_individual(vaga_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
        
    # Busca a vaga garantindo que ela pertence ao usuário logado
    vaga = db.query(SavedJob).filter(SavedJob.id == vaga_id, SavedJob.user_id == int(vagaz_user_id)).first()
    
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
        
    db.delete(vaga)
    db.commit()
    
    return {"mensagem": "Vaga excluída com sucesso!"}

scan_lock = asyncio.Lock()
timers_memoria = {} 

# ==========================================
# O MOTOR DE VARREDURA ISOLADO (Com Logs Injetados)
# ==========================================
def executar_varredura(filtro_id: int):
    db = SessionLocal()
    try:
        f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id).first()
        if not f_db: return 0
        
        config_headless = db.query(AppConfig).filter(AppConfig.chave == "headless_mode").first()
        is_headless = config_headless.valor == 'true' if config_headless else True
        
        scrapers_escolhidos = [s.strip() for s in f_db.scrapers.split(',') if s.strip()]
        palavras_proibidas = [p.strip().lower() for p in f_db.palavras_proibidas.split(',') if p.strip()]
        resultados_totais = []
        
        log_admin(f"Iniciando Radar '{f_db.nome_filtro}' (ID: {filtro_id}). Termos: '{f_db.termos}'.", "SISTEMA")
        
        for scraper in scrapers_escolhidos:
            try:
                # Checa controle individual do scraper
                cfg_ind = db.query(AppConfig).filter(AppConfig.chave == f"headless_{scraper}").first()
                scraper_headless = cfg_ind.valor == 'true' if cfg_ind else is_headless

                log_admin(f"Buscando '{f_db.termos}' em {f_db.localizacao}...", scraper)
                
                resultados_scraper = []
                if scraper == "Empregos": resultados_scraper = buscar_vagas_empregos(f_db.termos, 3, headless=scraper_headless)
                elif scraper == "InfoJobs": resultados_scraper = buscar_vagas_infojobs(f_db.termos + " " + f_db.localizacao, 2, headless=scraper_headless)
                elif scraper == "Gupy": resultados_scraper = buscar_vagas_gupy(f_db.termos, 4, headless=scraper_headless)
                elif scraper == "LinkedIn": resultados_scraper = buscar_vagas_linkedin(f_db.termos, f_db.localizacao, 4, headless=scraper_headless)
                elif scraper == "Solides": resultados_scraper = buscar_vagas_solides(f_db.termos, f_db.localizacao, 4, headless=scraper_headless)
                elif scraper == "Programathor": resultados_scraper = buscar_vagas_programathor(f_db.termos, 2, headless=scraper_headless)
                elif scraper == "Remotar": resultados_scraper = buscar_vagas_remotar(f_db.termos, 3, headless=scraper_headless)
                elif scraper == "PCI Concursos": resultados_scraper = buscar_concursos_pci(f_db.termos, headless=scraper_headless)
                elif scraper == "Concursos Brasil": resultados_scraper = buscar_concursos_brasil(f_db.termos, headless=scraper_headless)
                elif scraper == "Gran Concursos": resultados_scraper = buscar_concursos_gran(f_db.termos, headless=scraper_headless)
                elif scraper == "Folha QC": resultados_scraper = buscar_concursos_folha(f_db.termos, headless=scraper_headless)

                # --- FORÇA A ASSINATURA E A GARANTIA DE DADOS ---
                for res in resultados_scraper:
                    res['scraper'] = scraper # Obriga a ter o nome do site
                    if 'local' not in res: res['local'] = 'Não informado'
                    if 'data' not in res: res['data'] = 'Recente'
                # ------------------------------------------------
                
                log_admin(f"Devolveu {len(resultados_scraper)} vagas brutas.", scraper)
                resultados_totais.extend(resultados_scraper)
                
            except Exception as e:
                log_admin(f"Erro fatal: {e}", scraper)

        novas_vagas = 0
        links_vistos = set()
        
        from datetime import datetime, timedelta
        # Pegamos o dia de hoje, mas "empurramos" o relógio para 23:59:59
        # Isso compensa o arredondamento de horas que os sites fazem (ex: "há 20 horas" ou "há 2 dias").
        hoje = datetime.now()
        agora = hoje.replace(hour=23, minute=59, second=59, microsecond=0)
        
        for vaga in resultados_totais:
            titulo = vaga.get('titulo', '')
            link = vaga.get('link', '')
            scraper_nome = vaga.get('scraper', 'Desconhecido')
            formato = vaga.get('formato', 'Padrão')
            
            # --- 1. PADRONIZAÇÃO DE EMPRESA E LOCAL ---
            empresa_bruta = vaga.get('empresa', '')
            if not empresa_bruta or str(empresa_bruta).strip() == "":
                empresa_padronizada = "Confidencial"
            else:
                empresa_padronizada = str(empresa_bruta).strip()

            local_bruto = str(vaga.get('local', '')).strip()
            local_lower = local_bruto.lower()

            # REGRAS INTELIGENTES DE LOCALIZAÇÃO (Evita buracos nos cards)
            if scraper_nome == "Remotar":
                local_padronizado = "Remoto"
            elif "qualquer lugar" in local_lower:
                local_padronizado = "Remoto"
            elif not local_bruto:
                local_padronizado = "Brasil"
            else:
                local_padronizado = local_bruto

           # --- 2. TRADUÇÃO E PADRONIZAÇÃO DE DATA (CALIBRAÇÃO DEFINITIVA) ---
            data_bruta = str(vaga.get('data', 'hoje')).strip()
            s = data_bruta.lower()
            
            import re
            from datetime import datetime, timedelta
            
            # Os Dois Relógios
            agora_relogio = datetime.now()
            agora_calendario = agora_relogio.replace(hour=23, minute=59, second=59, microsecond=0)
            
            tempo_subtrair_relogio = None
            tempo_subtrair_calendario = None
            data_v = None
            
            # 1. Regras Imediatas
            if 'hoje' in s or 'recente' in s or 'agora' in s or 'minuto' in s:
                tempo_subtrair_calendario = timedelta(days=0)
            elif 'ontem' in s:
                tempo_subtrair_calendario = timedelta(days=1)
                
            # 2. Regras de Data Exata (DD/MM/YYYY)
            elif '/' in s or '-' in s: 
                try:
                    match_full = re.search(r'(\d{2})/(\d{2})/(\d{4})', s)
                    match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
                    match_short = re.search(r'(\d{2})/(\d{2})', s)
                    
                    if match_full:
                        data_v = datetime(int(match_full.group(3)), int(match_full.group(2)), int(match_full.group(1)))
                    elif match_iso:
                        data_v = datetime(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
                    elif match_short:
                        data_v = datetime(agora_relogio.year, int(match_short.group(2)), int(match_short.group(1)))
                        if data_v > agora_relogio: 
                            data_v = datetime(agora_relogio.year - 1, int(match_short.group(2)), int(match_short.group(1)))
                except:
                    pass
                    
            # 3. Regras Matemáticas Dinâmicas
            else:
                numeros = re.findall(r'\d+', s)
                if numeros:
                    valor = int(numeros[0])
                    
                    # Se for HORAS -> Usa o Relógio exato
                    if 'hora' in s or 'horas' in s or re.search(r'\d+h', s): 
                        tempo_subtrair_relogio = timedelta(hours=valor)
                        
                    # Se for DIAS/MESES -> Usa o Calendário (Sem o +1 agressivo)
                    elif 'dia' in s or 'dias' in s or re.search(r'\d+d', s): 
                        tempo_subtrair_calendario = timedelta(days=valor)
                    elif 'semana' in s or 'semanas' in s: 
                        tempo_subtrair_calendario = timedelta(days=valor * 7)
                    elif 'mês' in s or 'meses' in s or 'mes' in s: 
                        tempo_subtrair_calendario = timedelta(days=valor * 30)
                    elif 'ano' in s or 'anos' in s: 
                        tempo_subtrair_calendario = timedelta(days=valor * 365)

            # --- A FÓRMULA FINAL CALIBRADA ---
            if data_v:
                data_exata_calculada = data_v
                dias_vaga = (agora_relogio - data_v).days 
            elif tempo_subtrair_relogio is not None:
                data_exata_calculada = agora_relogio - tempo_subtrair_relogio
                dias_vaga = tempo_subtrair_relogio.days
            elif tempo_subtrair_calendario is not None:
                data_exata_calculada = agora_calendario - tempo_subtrair_calendario
                dias_vaga = (agora_relogio - data_exata_calculada).days
            else:
                # Se tudo falhar, garante que não vai quebrar
                data_exata_calculada = agora_relogio
                dias_vaga = 0

            if dias_vaga < 0: dias_vaga = 0
            
            data_padronizada = data_exata_calculada.strftime("%d/%m/%Y")
            
            print(f"🔎 [DATA] Site: {scraper_nome.ljust(12)} | Chegou: '{data_bruta}' | Virou: {data_padronizada}")
            # -----------------------------------------------------------------

            if not link or link in links_vistos: continue
            
            # Repare que agora ele usa o 'local_padronizado' para buscar palavras proibidas
            texto_analise = (titulo + " " + local_padronizado).lower()
            if any(p and p in texto_analise for p in palavras_proibidas): continue
            
            # --- 3. BARRANDO A VAGA SE FOR MUITO VELHA ---
            if dias_vaga > f_db.max_dias:
                continue

            links_vistos.add(link)

            existe = db.query(SavedJob).filter(SavedJob.link == link, SavedJob.user_id == f_db.user_id).first()
            if not existe:
                nova_vaga = SavedJob(
                    user_id=f_db.user_id, 
                    filtro_id=f_db.id, 
                    tipo_busca=f_db.tipo_busca,
                    scraper=scraper_nome,
                    empresa=empresa_padronizada,     
                    titulo=titulo, 
                    link=link, 
                    data_publicacao=data_padronizada, # Data Padrão DD/MM/YYYY
                    local=local_padronizado,          # Regras de Local Aplicadas
                    formato=formato
                )
                db.add(nova_vaga)
                novas_vagas += 1
        
        f_db.ultima_varredura = datetime.now()
        db.commit()
        log_admin(f"Radar '{f_db.nome_filtro}' finalizado. {novas_vagas} oportunidades 100% novas entregues.", "SISTEMA")
        return novas_vagas
    finally:
        db.close()


@app.post("/api/filtros/{filtro_id}/rodar")
async def rodar_filtro_manual(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None)):
    async with scan_lock:
        log_admin(f"▶️ [Manual] Iniciando Radar ID {filtro_id}...")
        novas = await run_in_threadpool(executar_varredura, filtro_id)
        log_admin(f"✅ [Manual] Finalizado! {novas} encontradas.")
    return {"mensagem": f"Busca concluída! {novas} novas oportunidades."}

@app.on_event("startup")
async def iniciar_automacao():
    asyncio.create_task(loop_de_automacao())

async def loop_de_automacao():
    print("🤖 Robô de automação iniciado com sistema de Fila e Faxina Automática!")
    from datetime import timedelta
    
    while True:
        await asyncio.sleep(60) 
        db = SessionLocal()
        filtros_para_rodar = []
        try:
            agora = datetime.now()
            
            # --- 1. A FAXINA GLOBAL OBRIGATÓRIA (Vagas com mais de 4 meses / 120 dias) ---
            limite_global = agora - timedelta(days=120)
            apagados_globais = db.query(SavedJob).filter(SavedJob.data_salva < limite_global).delete()
            if apagados_globais > 0:
                log_admin(f"🧹 FAXINA GLOBAL: {apagados_globais} vagas extintas (mais de 4 meses no banco).", "SISTEMA")

            # --- 2. A FAXINA INDIVIDUAL (A que o usuário escolhe na tela: 1, 2 ou 3 meses) ---
            configs_limpeza = db.query(UserConfig).filter(UserConfig.auto_limpeza_ativa == True).all()
            for cfg in configs_limpeza:
                limite_data = agora - timedelta(days=cfg.auto_limpeza_meses * 30)
                apagados = db.query(SavedJob).filter(SavedJob.user_id == cfg.user_id, SavedJob.data_salva < limite_data).delete()
                if apagados > 0:
                    log_admin(f"🧹 Faxina Local: {apagados} vagas excluídas do usuário ID {cfg.user_id} (Regra: {cfg.auto_limpeza_meses} meses).", "SISTEMA")

            # --- 3. A VARREDURA NORMAL DOS RADARES ---
            filtros_ativos = db.query(SearchFilter).filter(SearchFilter.timer_ativo == True).all()
            for f in filtros_ativos:
                ultima_vez = timers_memoria.get(f.id)
                if not ultima_vez or (agora - ultima_vez).total_seconds() >= (f.intervalo_timer * 60):
                    timers_memoria[f.id] = agora
                    filtros_para_rodar.append(f.id)
            
            db.commit()
        except Exception as e:
            print(f"Erro no loop de automação: {e}")
        finally:
            db.close()
            
        for f_id in filtros_para_rodar:
            print(f"⏰ [Auto] Radar ID {f_id} entrou na fila de varredura.")
            async with scan_lock:
                await run_in_threadpool(executar_varredura, f_id)
                print(f"✅ [Auto] Radar ID {f_id} finalizado!")

@app.patch("/api/filtros/{filtro_id}/toggle")
def toggle_timer(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if f_db:
        f_db.timer_ativo = not f_db.timer_ativo
        db.commit()
        estado = "ATIVADA" if f_db.timer_ativo else "DESATIVADA"
        return {"mensagem": f"Automação {estado} com sucesso!"}
    raise HTTPException(status_code=404)                

@app.get("/api/resultados")
def listar_resultados(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
    vagas = db.query(SavedJob).filter(SavedJob.user_id == int(vagaz_user_id)).order_by(SavedJob.id.desc()).all()
    return vagas

@app.get("/", response_class=HTMLResponse)
async def pagina_inicial(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ==========================================
# PAINEL DE ADMINISTRAÇÃO - ROTAS
# ==========================================

# 1. Rota para carregar a TELA do Admin (HTML)
@app.get("/admin", response_class=HTMLResponse)
async def pagina_admin(request: Request, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
        
    usuario = db.query(User).filter(User.id == int(vagaz_user_id)).first()
    # Proteção: Apenas o Admin Supremo pode ver essa tela
    if not usuario or not usuario.is_admin:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")
        
    return templates.TemplateResponse("admin.html", {"request": request, "user": usuario})


@app.get("/api/admin/stats")
def get_admin_stats(db = Depends(get_db)):
    stats = {
        'total_usuarios': db.query(User).count(),
        'total_filtros': db.query(SearchFilter).count(),
        'total_vagas': db.query(SavedJob).count()
    }
    return stats

@app.get("/api/admin/config")
def get_config(db = Depends(get_db)):
    headless = db.query(AppConfig).filter(AppConfig.chave == 'headless_mode').first()
    # Se não existir, por padrão é True (Escondido)
    is_headless = headless.valor == 'true' if headless else True
    return {"headless_mode": is_headless}

class ConfigPayload(BaseModel):
    headless: bool

@app.post("/api/admin/config/headless")
def toggle_headless(payload: ConfigPayload, db = Depends(get_db)):
    valor_str = 'true' if payload.headless else 'false'
    config = db.query(AppConfig).filter(AppConfig.chave == 'headless_mode').first()
    
    if config:
        config.valor = valor_str
    else:
        nova_config = AppConfig(chave="headless_mode", valor=valor_str)
        db.add(nova_config)
        
    db.commit()
    return {"message": "Configuração atualizada", "headless_mode": payload.headless}

@app.get("/api/admin/usuarios")
def get_all_users(db = Depends(get_db)):
    usuarios = db.query(User).all()
    users_data = []
    
    for u in usuarios:
        # Conta as vagas deste usuário
        total_vagas = db.query(SavedJob).filter(SavedJob.user_id == u.id).count()
        # Busca os filtros dele
        filtros = db.query(SearchFilter).filter(SearchFilter.user_id == u.id).all()
        
        users_data.append({
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "is_admin": u.is_admin,
            "total_filtros": len(filtros),
            "total_vagas": total_vagas,
            "filtros": [{"id": f.id, "termo": f.termos} for f in filtros]
        })
    return users_data

class UserEdit(BaseModel):
    nome: str
    email: str
    senha: Optional[str] = None # Opcional, caso o admin só queira mudar o nome/email

@app.put("/api/admin/usuarios/{user_id}")
def edit_user_admin(user_id: int, dados: UserEdit, db = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Verifica se o e-mail novo já pertence a outra pessoa
    if dados.email != user.email:
        email_em_uso = db.query(User).filter(User.email == dados.email).first()
        if email_em_uso:
            raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado em outra conta.")
            
    user.nome = dados.nome
    user.email = dados.email
    
    # Só atualiza a senha se o admin digitou algo no campo
    if dados.senha and len(dados.senha) >= 6:
        user.senha_hash = bcrypt.hashpw(dados.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
    db.commit()
    log_admin(f"Usuário ID {user_id} ({user.nome}) editado com sucesso.", "SISTEMA")
    return {"mensagem": "Usuário atualizado com sucesso!"}

@app.get("/api/admin/db/tables")
def get_tables_info(db = Depends(get_db)):
    # Contagem de linhas por tabela no SQLAlchemy
    tables_data = [
        {"nome": "users", "linhas": db.query(User).count()},
        {"nome": "search_filters", "linhas": db.query(SearchFilter).count()},
        {"nome": "saved_jobs", "linhas": db.query(SavedJob).count()},
        {"nome": "app_configs", "linhas": db.query(AppConfig).count()}
    ]
    return tables_data

@app.delete("/api/admin/db/clear/{tabela}")
def clear_table(tabela: str, db = Depends(get_db)):
    tabelas_map = {
        'users': User,
        'search_filters': SearchFilter,
        'saved_jobs': SavedJob,
        'app_configs': AppConfig
    }
    
    if tabela not in tabelas_map:
        raise HTTPException(status_code=400, detail="Tabela inválida")
        
    modelo = tabelas_map[tabela]
    
    # ATENÇÃO: Deletar a tabela "users" vai quebrar a relação com as outras tabelas 
    # e você perderá o acesso de admin. Recomendo limpar apenas vagas e filtros nos testes.
    if tabela == "users":
        # Apaga todo mundo que não for admin
        db.query(User).filter(User.is_admin == False).delete()
    else:
        db.query(modelo).delete()
        
    db.commit()
    return {"message": f"Tabela {tabela} limpa com sucesso!"}

# 1. SISTEMA DE LOGS EM TEMPO REAL
admin_logs = []

def log_admin(mensagem: str, scraper: str = "SISTEMA"):
    hora = datetime.now().strftime("%H:%M:%S")
    admin_logs.append({"time": hora, "scraper": scraper, "msg": mensagem})
    if len(admin_logs) > 200: # Guarda as últimas 200 ações
        admin_logs.pop(0)
    print(f"[{hora}] [{scraper}] {mensagem}")


# --- MODELOS E ROTAS DE CONFIGURAÇÃO DO USUÁRIO ---
class ConfigUsuario(BaseModel):
    ativa: bool
    meses: int

@app.get("/api/usuario/config")
def get_user_config(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    cfg = db.query(UserConfig).filter(UserConfig.user_id == int(vagaz_user_id)).first()
    if not cfg:
        return {"ativa": False, "meses": 3}
    return {"ativa": cfg.auto_limpeza_ativa, "meses": cfg.auto_limpeza_meses}

@app.post("/api/usuario/config")
def save_user_config(payload: ConfigUsuario, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: raise HTTPException(status_code=401)
    cfg = db.query(UserConfig).filter(UserConfig.user_id == int(vagaz_user_id)).first()
    if cfg:
        cfg.auto_limpeza_ativa = payload.ativa
        cfg.auto_limpeza_meses = payload.meses
    else:
        nova_cfg = UserConfig(user_id=int(vagaz_user_id), auto_limpeza_ativa=payload.ativa, auto_limpeza_meses=payload.meses)
        db.add(nova_cfg)
    db.commit()
    return {"mensagem": "Configurações salvas com sucesso!"}    

# ==========================================
# PAINEL DE ADMINISTRAÇÃO - ROTAS
# ==========================================

@app.get("/api/admin/logs")
def get_logs(vagaz_user_id: Optional[str] = Cookie(None)):
    return {"logs": admin_logs}

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
    from sqlalchemy import func
    hoje = datetime.utcnow().date()
    vagas_hoje = db.query(SavedJob).filter(func.date(SavedJob.data_salva) == hoje).count()
    filtros_ativos = db.query(SearchFilter).filter(SearchFilter.timer_ativo == True).count()
    
    # Faz um Top 3 dos Scrapers que mais trouxeram resultados no banco inteiro
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
        log_admin(f"Modo Fantasma do scraper {nome} alterado para: {config.valor.upper()}", "SISTEMA")
        return {"mensagem": f"Scraper {nome} atualizado!", "headless": config.valor == "true"}
    raise HTTPException(status_code=404)

@app.get("/api/admin/usuarios")
def get_all_users(db = Depends(get_db)):
    usuarios = db.query(User).all()
    dados = []
    for u in usuarios:
        total_vagas = db.query(SavedJob).filter(SavedJob.user_id == u.id).count()
        filtros = db.query(SearchFilter).filter(SearchFilter.user_id == u.id).all()
        dados.append({
            "id": u.id, "nome": u.nome, "email": u.email, "is_admin": u.is_admin,
            "total_vagas": total_vagas, "filtros": [{"id": f.id, "termo": f.termos} for f in filtros]
        })
    return dados

@app.post("/api/admin/usuarios")
def create_user_admin(user: UserRegister, db = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="E-mail já existe.")
    senha_cripto = bcrypt.hashpw(user.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    novo = User(nome=user.nome, email=user.email, senha_hash=senha_cripto)
    db.add(novo)
    db.commit()
    log_admin(f"Novo usuário criado via Admin: {user.nome}", "SISTEMA")
    return {"mensagem": "Usuário criado com sucesso!"}

@app.delete("/api/admin/usuarios/{user_id}")
def delete_user_admin(user_id: int, db = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    if user.is_admin: raise HTTPException(status_code=403, detail="Não pode deletar o Admin!")
    
    db.query(SavedJob).filter(SavedJob.user_id == user_id).delete()
    db.query(SearchFilter).filter(SearchFilter.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    log_admin(f"Usuário ID {user_id} excluído.", "SISTEMA")
    return {"mensagem": "Usuário deletado."}

@app.get("/api/admin/usuarios/{user_id}/detalhes")
def get_user_details(user_id: int, db = Depends(get_db)):
    filtros = db.query(SearchFilter).filter(SearchFilter.user_id == user_id).all()
    dados_filtros = []
    for f in filtros:
        vagas = db.query(SavedJob).filter(SavedJob.filtro_id == f.id).all()
        dados_filtros.append({
            "nome": f.nome_filtro, "termos": f.termos,
            "vagas": [{"titulo": v.titulo, "empresa": v.empresa, "link": v.link} for v in vagas]
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

@app.delete("/api/admin/db/nuke")
def limpar_banco_total(db = Depends(get_db)):
    # Limpa Vagas, Radares, Configurações e Todos os Usuários (Exceto o Admin)
    db.query(SavedJob).delete()
    db.query(SearchFilter).delete()
    db.query(AppConfig).delete()
    db.query(User).filter(User.is_admin == False).delete()
    db.commit()
    log_admin("☢️ LIMPEZA TOTAL REALIZADA. O sistema foi resetado à estaca zero.", "SISTEMA")
    return {"mensagem": "Tudo foi varrido. Apenas a sua conta de Admin sobreviveu."}