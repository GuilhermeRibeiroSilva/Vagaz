import urllib.parse
import random
from playwright.sync_api import sync_playwright
# O Stealth foi removido daqui pois o motor blindado já faz isso
from navegador import iniciar_navegador_blindado

def buscar_vagas_linkedin(termo: str, local: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    termo_formatado = urllib.parse.quote(termo.strip())
    local_limpo = local.strip()
    
    # ROTEADOR DE LOCALIZAÇÃO DO LINKEDIN
    if local_limpo:
        # Se o usuário digitou um local, amarramos com "Brasil" para não vazar pros EUA
        local_formatado = urllib.parse.quote(f"{local_limpo}, Brasil")
        url_base = f"https://www.linkedin.com/jobs/search?keywords={termo_formatado}&location={local_formatado}"
    else:
        # Se vazio, busca no Brasil inteiro usando o geoId oficial
        url_base = f"https://www.linkedin.com/jobs/search?keywords={termo_formatado}&location=Brasil&geoId=106057199"
    
    vagas_brutas_totais = set()
    links_capturados = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)
        try:
            for pagina in range(max_paginas):
                # O LinkedIn avança de 25 em 25 vagas
                start_index = pagina * 25
                url = f"{url_base}&start={start_index}"
                
                print(f"🤖 [LinkedIn - Lote {pagina + 1}] Acessando: {url}")
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    
                    # Simula humano lendo a tela
                    page.wait_for_timeout(random.randint(2000, 4000)) 
                    
                    # RADAR DE BLOQUEIO: Se o LinkedIn forçar a tela de login, nós paramos o robô com elegância
                    if "authwall" in page.url or "login" in page.url or "session" in page.url:
                        print("🧱 [LinkedIn] Barreira de Login (Authwall) atingida. Parando captura deste scraper...")
                        break
                    
                    # Scroll aleatório (fundamental para carregar as imagens e datas no LinkedIn)
                    for _ in range(4):
                        page.mouse.wheel(0, random.randint(500, 900))
                        page.wait_for_timeout(random.randint(800, 1500))
                    
                    # EXTRATOR PADRONIZADO (5 Chaves)
                    js_extrator = r"""
                    (function() {
                        var encontrados = [];
                        // Pega tanto os cards tradicionais quanto o novo layout
                        var cards = document.querySelectorAll('ul.jobs-search__results-list > li, div.job-search-card, div.base-card');
                        
                        for (var i = 0; i < cards.length; i++) {
                            try {
                                var el = cards[i];
                                var textFull = el.innerText.toLowerCase();
                                
                                // 1. TÍTULO
                                var titleEl = el.querySelector('.base-search-card__title, h3, strong');
                                if (!titleEl) continue;
                                
                                var tituloLimpo = titleEl.innerText.replace(/<!---->/g, '').trim();
                                if (tituloLimpo.length < 3) continue;

                                // 2. LINK LIMPO
                                var linkEl = el.querySelector('a.base-search-card__full-link, a.base-card__full-link, a');
                                if (!linkEl) continue;
                                var rawLink = linkEl.getAttribute('href') || '';
                                
                                // Removemos os rastreadores gigantes do link (tudo depois do '?')
                                var link = rawLink;
                                if(rawLink.includes('?')) link = rawLink.split('?')[0]; 
                                if(link.startsWith('/')) link = 'https://www.linkedin.com' + link;

                                // 3. EMPRESA (Lidando com as classes obfuscadas que você mapeou)
                                var empresa = "Confidencial";
                                var empEl = el.querySelector('h4.base-search-card__subtitle, .hidden-nested-link');
                                if (empEl) {
                                    empresa = empEl.innerText.replace(/<!---->/g, '').trim();
                                } else {
                                    // Fallback: caça o primeiro span com dir="ltr" (novo padrão do LinkedIn)
                                    var spansLtr = el.querySelectorAll('span[dir="ltr"]');
                                    if (spansLtr.length > 0) {
                                        empresa = spansLtr[0].innerText.replace(/<!---->/g, '').trim();
                                    }
                                }

                                // 4. LOCALIZAÇÃO E REGRA DO REMOTO
                                var localStr = "";
                                var locationEl = el.querySelector('.job-search-card__location');
                                if (locationEl) {
                                    localStr = locationEl.innerText.replace(/<!---->/g, '').trim();
                                } else {
                                    // Fallback: Procura nas classes de baixa ênfase
                                    var tvmTexts = el.querySelectorAll('.tvm__text--low-emphasis');
                                    for (var t=0; t<tvmTexts.length; t++) {
                                        var txt = tvmTexts[t].innerText.replace(/<!---->/g, '').trim();
                                        if (txt && !txt.toLowerCase().includes('há') && !txt.toLowerCase().includes('dia')) {
                                            localStr = txt;
                                            break;
                                        }
                                    }
                                }
                                
                                // REGRA DE OURO: Se disser remoto em qualquer lugar, vira "Remoto"
                                if (textFull.includes('remoto') || textFull.includes('remote') || textFull.includes('home office') || textFull.includes('qualquer lugar')) {
                                    localStr = "Remoto";
                                } else if (!localStr) {
                                    localStr = "Brasil";
                                }
                                
                                // 5. DATA (Priorizando a tag <time> mapeada)
                                var dataStr = "Recente";
                                var dateEl = el.querySelector('time');
                                if (dateEl) {
                                    dataStr = dateEl.innerText.replace(/<!---->/g, '').trim();
                                } else {
                                    // Fallback para achar o "há X dias" escondido em spans
                                    var allSpans = el.querySelectorAll('span');
                                    for (var s=0; s<allSpans.length; s++) {
                                        var stxt = allSpans[s].innerText.toLowerCase();
                                        if (stxt.includes('há ') || stxt.includes('hoje') || stxt.includes('ontem') || stxt.includes('minuto') || stxt.includes('hora')) {
                                            dataStr = allSpans[s].innerText.replace(/<!---->/g, '').trim();
                                            break;
                                        }
                                    }
                                }
                                
                                encontrados.push([tituloLimpo, link, empresa, localStr, dataStr].join('|||'));
                            } catch(err) { continue; }
                        }
                        return encontrados;
                    })();
                    """
                    
                    vagas_desta_pagina = page.evaluate(js_extrator)
                    
                    if not vagas_desta_pagina:
                        print(f"⚠️ [LinkedIn] Nenhuma vaga nova carregou. Encerrando no lote {pagina + 1}.")
                        break
                        
                    novas_vagas = 0
                    for vaga_str in vagas_desta_pagina:
                        link_vaga = vaga_str.split('|||')[1]
                        if link_vaga not in links_capturados:
                            links_capturados.add(link_vaga)
                            vagas_brutas_totais.add(vaga_str)
                            novas_vagas += 1
                            
                    if novas_vagas == 0:
                        break
                        
                    print(f"✅ [LinkedIn] {novas_vagas} vagas capturadas no lote {pagina + 1}.")

                except Exception as e:
                    print(f"⚠️ [LinkedIn] Instabilidade detectada no lote {pagina + 1}. Salvando e saindo. Erro: {e}")
                    break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO LINKEDIN: {len(vagas_brutas_totais)} vagas extraídas.")
        
        # RETORNO NO DICIONÁRIO DE OURO
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "LinkedIn"
                })
                
    return resultados