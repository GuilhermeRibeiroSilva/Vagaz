import urllib.parse
import random
from playwright.sync_api import sync_playwright
from navegador import iniciar_navegador_blindado

def buscar_vagas_solides(termo: str, local: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    # Formatação do Termo (ex: "python junior" -> "python-junior")
    termo_limpo = termo.lower().strip()
    termo_formatado = urllib.parse.quote(termo_limpo.replace(' ', '-'))
    
    # Formatação do Local
    local_limpo = local.lower().strip()
    if local_limpo and local_limpo not in ["brasil", "nacional", "remoto"]:
        local_formatado = urllib.parse.quote(local_limpo.replace(' ', '-'))
    else:
        local_formatado = "brasil"
        
    vagas_brutas_totais = set()
    links_capturados = set()

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)
        try:
            for pagina in range(1, max_paginas + 1):
                url = f"https://vagas.solides.com.br/vagas/{local_formatado}/{termo_formatado}?page={pagina}"
                
                print(f"🤖 [Solides - Pág {pagina}] Acessando: {url}")
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(random.randint(2000, 3000))
                    
                    # A TRAVA DE SEGURANÇA COM FALLBACK DE F5
                    try:
                        page.wait_for_selector('[data-cy="vacancy-company-name"]', timeout=15000, state='attached')
                    except:
                        print(f"🔄 [Solides] SPA engasgou na pág {pagina}. Forçando reload...")
                        page.reload(wait_until="domcontentloaded")
                        page.wait_for_timeout(4000)
                        try:
                            page.wait_for_selector('[data-cy="vacancy-company-name"]', timeout=15000, state='attached')
                        except:
                            print(f"⚠️ [Solides] Nenhum card carregou na pág {pagina}. Fim da linha.")
                            break
                    
                    # Scroll para garantir carregamento
                    for _ in range(3):
                        page.mouse.wheel(0, random.randint(500, 700))
                        page.wait_for_timeout(random.randint(800, 1200))
                        
                    # EXTRATOR COM A DATA CALIBRADA PARA O MAIN.PY
                    js_extrator = r"""
                    (function() {
                        var enc = [];
                        var headers = document.querySelectorAll('h2');
                        
                        for (var i = 0; i < headers.length; i++) {
                            try {
                                var h2 = headers[i];
                                var titulo = h2.innerText.trim();
                                if(titulo.length < 3) continue;
                                
                                var card = h2;
                                for(var up = 0; up < 5; up++) {
                                    if(card.parentElement) card = card.parentElement;
                                }
                                
                                var aTag = h2.querySelector('a') || card.querySelector('a[href^="/vaga/"]');
                                var link = aTag ? aTag.getAttribute('href') : '';
                                if(link && link.startsWith('/')) link = 'https://vagas.solides.com.br' + link;
                                if(!link) continue;
                                
                                var compTag = card.querySelector('[data-cy="vacancy-company-name"]');
                                var empresa = compTag ? compTag.innerText.trim() : 'Confidencial';
                                
                                var locTag = card.querySelector('[data-icon="location_on"]');
                                var localStr = locTag && locTag.parentElement ? locTag.parentElement.innerText.trim() : 'Brasil';
                                localStr = localStr.replace('location_on', '').trim();
                                
                                var formatoStr = "Presencial";
                                var textFull = card.innerText.toLowerCase();
                                
                                if (textFull.includes('remoto') || textFull.includes('home office')) {
                                    formatoStr = "Remoto";
                                } else if (textFull.includes('híbrido') || textFull.includes('hibrido')) {
                                    formatoStr = "Híbrido";
                                }
                                
                                // A NOVA REGRA DA DATA: Prioriza textos como "há 10 dias" e "Postada em..."
                                var timeTag = card.querySelector('time');
                                var dataStr = 'Recente';
                                if (timeTag) {
                                    var textoVisivel = timeTag.innerText.trim();
                                    var textoTitulo = timeTag.getAttribute('title') || '';
                                    
                                    if (textoVisivel.toLowerCase().includes('há') || textoVisivel.toLowerCase().includes('hoje') || textoVisivel.toLowerCase().includes('ontem')) {
                                        dataStr = textoVisivel;
                                    } else if (textoTitulo) {
                                        dataStr = textoTitulo; // Pega o formato "Postada em 19 de julho de 2026"
                                    } else {
                                        dataStr = timeTag.getAttribute('datetime') || 'Recente';
                                    }
                                }
                                
                                enc.push([titulo, link, empresa, localStr, dataStr, formatoStr].join('|||'));
                            } catch(err) { continue; }
                        }
                        
                        var finalList = [];
                        var vistos = {};
                        for(var k=0; k < enc.length; k++){
                            var url = enc[k].split('|||')[1];
                            if(!vistos[url]){
                                vistos[url] = true;
                                finalList.push(enc[k]);
                            }
                        }
                        return finalList;
                    })();
                    """
                    
                    vagas_desta_pagina = page.evaluate(js_extrator)
                    
                    if not vagas_desta_pagina:
                        print(f"⚠️ [Solides] Nenhuma vaga extraída na pág {pagina}.")
                        break
                        
                    novas_vagas = 0
                    for vaga_str in vagas_desta_pagina:
                        link_vaga = vaga_str.split('|||')[1]
                        if link_vaga and link_vaga not in links_capturados:
                            links_capturados.add(link_vaga)
                            vagas_brutas_totais.add(vaga_str)
                            novas_vagas += 1
                            
                    if novas_vagas == 0:
                        break
                        
                    print(f"✅ [Solides] {novas_vagas} vagas capturadas na pág {pagina}.")

                except Exception as e:
                    print(f"❌ Erro na página {pagina}: {e}")
                    break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas extraídas da Solides.")
        
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 6:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "formato": partes[5],
                    "scraper": "Solides"
                })
                
    return resultados