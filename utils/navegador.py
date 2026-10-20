import random
from playwright.sync_api import sync_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
]

def interceptar_rota_dieta(route):
    if route.request.resource_type in ["image", "media", "font", "stylesheet", "other"]:
        route.abort()
    else:
        route.continue_()

def iniciar_navegador_blindado(p, headless=True, usar_proxy=False):
    ua = random.choice(USER_AGENTS)
    
    configs_navegador = {
        "headless": headless,
        "args": [
            "--no-sandbox", 
            "--disable-setuid-sandbox", 
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--mute-audio",
            "--js-flags=--max-old-space-size=500"
        ]
    }
    
    browser = p.chromium.launch(**configs_navegador)
    
    context = browser.new_context(
        user_agent=ua,
        viewport={'width': 1920, 'height': 1080},
        locale='pt-BR',
        timezone_id='America/Sao_Paulo'
    )
    
    page = context.new_page()
    
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except Exception:
        pass
    
    page.route("**/*", interceptar_rota_dieta)
    
    return browser, page