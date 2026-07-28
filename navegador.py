import random
from playwright.sync_api import sync_playwright

# Roleta de disfarces reais
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
]

def iniciar_navegador_blindado(p, headless=True, usar_proxy=False):
    ua = random.choice(USER_AGENTS)
    
    configs_navegador = {
        "headless": headless,
        "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
    }
    
    # 1. Inicia o Navegador
    browser = p.chromium.launch(**configs_navegador)
    
    # 2. Inicia o Contexto aplicando o User-Agent Falso
    context = browser.new_context(
        user_agent=ua,
        viewport={'width': 1920, 'height': 1080},
        locale='pt-BR',
        timezone_id='America/Sao_Paulo'
    )
    
    # 3. Cria a página
    page = context.new_page()
    
    # 4. A MÁGICA SEGURA: Tenta injetar o Stealth. Se a sua versão não tiver a função,
    # ele passa reto sem travar o código. A proteção dos argumentos acima e do User-Agent 
    # já fazem 90% do trabalho sujo de camuflagem.
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except Exception:
        pass
    
    # 5. OTIMIZAÇÃO: Bloqueia imagens, vídeos e fontes em TODOS os scrapers
    page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
    
    return browser, page