from fastapi import FastAPI
from scrapers.gupy import buscar_vagas_gupy
from scrapers.linkedin import buscar_vagas_linkedin
from scrapers.indeed import buscar_vagas_indeed
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
# Importa o banco de dados que criamos
from database import SessionLocal, User
from fastapi import Cookie # Adicione o Cookie aqui
from typing import Optional
from database import SearchFilter, SavedJob # Não esqueça de importar
import asyncio # Para rodar tarefas em segundo plano se necessário
import re
import asyncio
from datetime import datetime
from fastapi.concurrency import run_in_threadpool

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
    lembrar: bool

# --- ROTAS DE AUTENTICAÇÃO ---

@app.post("/api/register")
def registrar_usuario(user: UserRegister, db = Depends(get_db)):
    # 1. Verifica se o e-mail já existe
    usuario_existente = db.query(User).filter(User.email == user.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")
    
    # 2. Criptografa a senha
    senha_criptografada = bcrypt.hashpw(user.senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # 3. Salva no banco de dados
    novo_usuario = User(nome=user.nome, email=user.email, senha_hash=senha_criptografada)
    db.add(novo_usuario)
    db.commit()
    
    return {"mensagem": "Conta criada com sucesso!"}

@app.post("/api/login")
def login_usuario(user: UserLogin, response: Response, db = Depends(get_db)):
    # 1. Busca o usuário no banco
    usuario = db.query(User).filter(User.email == user.email).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    
    # 2. Verifica se a senha bate com a criptografia
    if not bcrypt.checkpw(user.senha.encode('utf-8'), usuario.senha_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    
    # 3. Regra do "Lembrar de mim" (Configura um cookie de sessão)
    tempo_expiracao = 2592000 if user.lembrar else 86400 # 30 dias ou 1 dia
    
    # No futuro usaremos JWT aqui, por enquanto um cookie básico com o ID resolve o teste
    response.set_cookie(key="vagaz_user_id", value=str(usuario.id), max_age=tempo_expiracao, httponly=True)
    
    return {"mensagem": f"Bem-vindo(a), {usuario.nome}!", "user_id": usuario.id}

# --- ROTAS DO DASHBOARD E FILTROS ---

# 1. Rota para carregar a página do Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def pagina_dashboard(request: Request, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id: # Se não tem cookie, manda pro login
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    
    usuario = db.query(User).filter(User.id == int(vagaz_user_id)).first()
    if not usuario:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
        
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": usuario})

# 3. Rota de Logout
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

# 1. LISTAR FILTROS DO USUÁRIO
@app.get("/api/filtros")
def listar_filtros(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
    filtros = db.query(SearchFilter).filter(SearchFilter.user_id == int(vagaz_user_id)).all()
    return filtros

# 2. SALVAR OU EDITAR FILTRO
@app.post("/api/filtros")
def criar_editar_filtro(filtro: NovoFiltro, id: Optional[int] = None, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
    
    if id: # Edição
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
            
    # Criação
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

# 3. EXCLUIR FILTRO
@app.delete("/api/filtros/{filtro_id}")
def excluir_filtro(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if f_db:
        db.delete(f_db)
        db.commit()
        return {"mensagem": "Excluído!"}
    raise HTTPException(status_code=404)

# O NOSSO SEGURANÇA DA FILA (Garante 1 scraper por vez)
scan_lock = asyncio.Lock()
timers_memoria = {} 

# --- O MOTOR DE VARREDURA ISOLADO ---
def executar_varredura(filtro_id: int):
    db = SessionLocal()
    try:
        f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id).first()
        if not f_db: return 0
        
        scrapers_escolhidos = [s.strip() for s in f_db.scrapers.split(',') if s.strip()]
        palavras_proibidas = [p.strip().lower() for p in f_db.palavras_proibidas.split(',') if p.strip()]
        resultados_totais = []
        
        # ... (SEUS SCRAPERS CONTINUAM AQUI EXATAMENTE IGUAIS) ...
        for scraper in scrapers_escolhidos:
            try:
                if scraper == "Empregos": resultados_totais.extend(buscar_vagas_empregos(f_db.termos, 2))
                elif scraper == "InfoJobs": resultados_totais.extend(buscar_vagas_infojobs(f_db.termos + " " + f_db.localizacao, 2))
                elif scraper == "Gupy": resultados_totais.extend(buscar_vagas_gupy(f_db.termos, 2))
                elif scraper == "LinkedIn": resultados_totais.extend(buscar_vagas_linkedin(f_db.termos, f_db.localizacao, 2))
                elif scraper == "Indeed": resultados_totais.extend(buscar_vagas_indeed(f_db.termos, f_db.localizacao, 2))
                elif scraper == "Programathor": resultados_totais.extend(buscar_vagas_programathor(f_db.termos, 2))
                elif scraper == "Remotar": resultados_totais.extend(buscar_vagas_remotar(f_db.termos, 2))
                elif scraper == "PCI": resultados_totais.extend(buscar_concursos_pci(f_db.termos))
                elif scraper == "C_Brasil": resultados_totais.extend(buscar_concursos_brasil(f_db.termos))
                elif scraper == "Gran": resultados_totais.extend(buscar_concursos_gran(f_db.termos))
                elif scraper == "Folha_QC": resultados_totais.extend(buscar_concursos_folha(f_db.termos))
            except Exception as e:
                print(f"❌ Erro no {scraper}: {e}")

        novas_vagas = 0
        links_vistos = set()
        
        for vaga in resultados_totais:
            titulo = vaga.get('titulo', '')
            link = vaga.get('link', '')
            local = vaga.get('local', '')
            data_pub = vaga.get('data', 'Recente')
            
            if not link or link in links_vistos: continue
            
            texto_analise = (titulo + " " + local).lower()
            if any(p and p in texto_analise for p in palavras_proibidas): continue
                
            import re
            numeros_na_data = re.findall(r'\d+', data_pub)
            if numeros_na_data:
                dias_vaga = int(numeros_na_data[0])
                if 'mês' in data_pub.lower() or 'meses' in data_pub.lower(): dias_vaga *= 30
                if dias_vaga > f_db.max_dias: continue

            links_vistos.add(link)

            existe = db.query(SavedJob).filter(SavedJob.link == link, SavedJob.user_id == f_db.user_id).first()
            if not existe:
                nova_vaga = SavedJob(
                    user_id=f_db.user_id, filtro_id=f_db.id, tipo_busca=f_db.tipo_busca,
                    scraper=scraper, empresa=vaga.get('empresa', 'Confidencial'),
                    titulo=titulo, link=link, data_publicacao=data_pub,
                    local=local, formato=vaga.get('formato', 'Padrão')
                )
                db.add(nova_vaga)
                novas_vagas += 1
        
        # ATUALIZA A DATA DA ÚLTIMA VARREDURA NO BANCO
        f_db.ultima_varredura = datetime.now()
        db.commit()
        return novas_vagas
    finally:
        db.close()


# --- ROTA MANUAL (Com Fila) ---
@app.post("/api/filtros/{filtro_id}/rodar")
async def rodar_filtro_manual(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None)):
    # O 'async with scan_lock' faz o código esperar aqui até o outro terminar!
    async with scan_lock:
        print(f"▶️ [Manual] Iniciando Radar ID {filtro_id}...")
        novas = await run_in_threadpool(executar_varredura, filtro_id)
        print(f"✅ [Manual] Finalizado! {novas} encontradas.")
    return {"mensagem": f"Busca concluída! {novas} novas oportunidades."}


# --- O DESPERTADOR (Com Fila) ---
@app.on_event("startup")
async def iniciar_automacao():
    asyncio.create_task(loop_de_automacao())

async def loop_de_automacao():
    print("🤖 Robô de automação iniciado em segundo plano com sistema de Fila!")
    while True:
        await asyncio.sleep(60) # Checa a cada 1 minuto
        db = SessionLocal()
        filtros_para_rodar = []
        try:
            filtros_ativos = db.query(SearchFilter).filter(SearchFilter.timer_ativo == True).all()
            agora = datetime.now()
            
            for f in filtros_ativos:
                ultima_vez = timers_memoria.get(f.id)
                if not ultima_vez or (agora - ultima_vez).total_seconds() >= (f.intervalo_timer * 60):
                    timers_memoria[f.id] = agora
                    filtros_para_rodar.append(f.id)
        finally:
            db.close()
            
        # Para cada filtro que precisa rodar, ele entra na Fila do Cadeado (scan_lock)
        for f_id in filtros_para_rodar:
            print(f"⏰ [Auto] Radar ID {f_id} entrou na fila de varredura.")
            async with scan_lock:
                await run_in_threadpool(executar_varredura, f_id)
                print(f"✅ [Auto] Radar ID {f_id} finalizado!")

# 3.5 TOGGLE RÁPIDO DO TIMER
@app.patch("/api/filtros/{filtro_id}/toggle")
def toggle_timer(filtro_id: int, vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    f_db = db.query(SearchFilter).filter(SearchFilter.id == filtro_id, SearchFilter.user_id == int(vagaz_user_id)).first()
    if f_db:
        f_db.timer_ativo = not f_db.timer_ativo
        db.commit()
        estado = "ATIVADA" if f_db.timer_ativo else "DESATIVADA"
        return {"mensagem": f"Automação {estado} com sucesso!"}
    raise HTTPException(status_code=404)                

# 5. LISTAR RESULTADOS NA ABA DE VAGAS
@app.get("/api/resultados")
def listar_resultados(vagaz_user_id: Optional[str] = Cookie(None), db = Depends(get_db)):
    if not vagaz_user_id:
        raise HTTPException(status_code=401)
    # Traz as mais recentes primeiro
    vagas = db.query(SavedJob).filter(SavedJob.user_id == int(vagaz_user_id)).order_by(SavedJob.id.desc()).all()
    return vagas

# --- ROTA DA PÁGINA INICIAL ---
@app.get("/", response_class=HTMLResponse)
async def pagina_inicial(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/api/buscar")
def buscar_vagas(termo: str, site: str):
    print(f"\n📡 RECEBIDO PEDIDO DO CELULAR: Buscar '{termo}' no site '{site}'")
    
    resultados = []
    
    if site.lower() == "gupy":
        resultados = buscar_vagas_gupy(termo, max_paginas=4)
    elif site.lower() == "linkedin":
        resultados = buscar_vagas_linkedin(termo, max_paginas=4)
    elif site.lower() == "indeed":
        resultados = buscar_vagas_indeed(termo, max_paginas=4)
    elif site.lower() == "programathor":
        resultados = buscar_vagas_programathor(termo, max_paginas=4)
    elif site.lower() == "remotar":
        resultados = buscar_vagas_remotar(termo, max_paginas=4)
    elif site.lower() == "pci": 
        resultados = buscar_concursos_pci(termo, max_paginas=4)
    elif site.lower() == "c_brasil": 
        resultados = buscar_concursos_brasil(termo, max_paginas=4)
    elif site.lower() == "gran": 
        resultados = buscar_concursos_gran(termo, max_paginas=1) 
    elif site.lower() == "folha_qc": 
        resultados = buscar_concursos_folha(termo, max_paginas=3)
    elif site.lower() == "empregos": 
        resultados = buscar_vagas_empregos(termo, max_paginas=4)
    elif site.lower() == "infojobs": 
        resultados = buscar_vagas_infojobs(termo, max_paginas=4)    
        
    print(f"🚀 DEVOLVENDO {len(resultados)} RESULTADOS PARA O CELULAR!")
    return resultados