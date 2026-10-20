import urllib.parse
import random
import json
import time
from playwright.sync_api import sync_playwright
from utils.navegador import iniciar_navegador_blindado

def buscar_vagas_linkedin(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    lista_termos = [t.strip() for t in termo.split(',') if t.strip()]
    if not lista_termos:
        return resultados

    lista_proibidas = [p.strip().lower() for p in palavras_proibidas.split(',') if p.strip()]
    lista_locais = [l.strip().lower() for l in local.split(',') if l.strip()]
    
    if not lista_locais:
        lista_locais = ["brasil"]
    
    vagas_brutas_totais = set()
    links_capturados = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)
        try:
            for termo_alvo in lista_termos:
                termo_formatado = urllib.parse.quote(termo_alvo)
                print(f"\n🔍 [LinkedIn] Iniciando varredura para a tag: '{termo_alvo}'")

                for local_alvo in lista_locais:
                    
                    if local_alvo == "remoto (internacional)":
                        local_query = "Worldwide"
                        geo_param = ""
                    elif local_alvo == "remoto (brasil)" or local_alvo == "brasil":
                        local_query = "Brasil"
                        geo_param = "&geoId=106057199"
                    else:
                        cidade_limpa = local_alvo.split(',')[0].title()
                        local_query = f"{cidade_limpa}, Brasil"
                        geo_param = "&geoId=106057199"

                    local_formatado = urllib.parse.quote(local_query)
                    url_base = f"https://www.linkedin.com/jobs/search?keywords={termo_formatado}&location={local_formatado}{geo_param}"
                    
                    limite_paginas = min(max_paginas, 2)
                    
                    for pagina in range(limite_paginas):
                        start_index = pagina * 25
                        url = f"{url_base}&start={start_index}"
                        
                        print(f"🤖 [LinkedIn - {local_query} - Lote {pagina + 1}] Acessando: {url}")
                        
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=40000)
                            page.wait_for_timeout(random.randint(3000, 5000))
                            
                            if "authwall" in page.url or "login" in page.url or "session" in page.url:
                                try:
                                    page.close()
                                    browser.close()
                                except:
                                    pass
                                time.sleep(random.randint(4, 7))
                                browser, page = iniciar_navegador_blindado(p, headless=headless)
                                break
                            
                            for _ in range(4):
                                page.mouse.wheel(0, random.randint(500, 900))
                                page.wait_for_timeout(random.randint(800, 1500))
                            
                            js_extrator = r"""
                            (function() {
                                var encontrados = [];
                                var cards = document.querySelectorAll('ul.jobs-search__results-list > li, div.job-search-card, div.base-card');
                                
                                var termosAlvo = REPLACE_TERMOS;
                                var proibidas = REPLACE_PROIBIDAS;
                                var locaisAlvo = REPLACE_LOCAIS;
                                var termosGringos = ["eua", "usa", "latam", "global", "worldwide", "abroad", "internacional", "exterior", "estados unidos", "united states", "california", "califórnia", "texas", "new york", "georgia", "geórgia", "ohio", "illinois", "ilinois", "north carolina", "carolina do norte", "washington", "florida", "flórida"];
                                
                                for (var i = 0; i < cards.length; i++) {
                                    try {
                                        var el = cards[i];
                                        var textFull = el.innerText.toLowerCase();
                                        
                                        var titleEl = el.querySelector('.base-search-card__title, h3, strong');
                                        if (!titleEl) continue;
                                        
                                        var tituloLimpo = titleEl.innerText.replace(/<!---->/g, '').trim();
                                        if (tituloLimpo.length < 3) continue;
                                        
                                        var tituloBaixo = tituloLimpo.toLowerCase();
                                        
                                        if (termosAlvo.length > 0) {
                                            var match = termosAlvo.some(t => tituloBaixo.includes(t.toLowerCase()));
                                            if (!match) continue;
                                        }
                                        if (proibidas.length > 0 && proibidas.some(p => tituloBaixo.includes(p))) continue;

                                        var linkEl = el.querySelector('a.base-search-card__full-link, a.base-card__full-link, a');
                                        if (!linkEl) continue;
                                        var rawLink = linkEl.getAttribute('href') || '';
                                        
                                        var link = rawLink;
                                        if(rawLink.includes('?')) link = rawLink.split('?')[0]; 
                                        if(link.startsWith('/')) link = 'https://www.linkedin.com' + link;

                                        var empresa = "Confidencial";
                                        var empEl = el.querySelector('h4.base-search-card__subtitle, .hidden-nested-link');
                                        if (empEl) {
                                            empresa = empEl.innerText.replace(/<!---->/g, '').trim();
                                        } else {
                                            var spansLtr = el.querySelectorAll('span[dir="ltr"]');
                                            if (spansLtr.length > 0) {
                                                empresa = spansLtr[0].innerText.replace(/<!---->/g, '').trim();
                                            }
                                        }

                                        var localStr = "";
                                        var locationEl = el.querySelector('.job-search-card__location');
                                        if (locationEl) {
                                            localStr = locationEl.innerText.replace(/<!---->/g, '').trim();
                                        } else {
                                            var tvmTexts = el.querySelectorAll('.tvm__text--low-emphasis');
                                            for (var t=0; t<tvmTexts.length; t++) {
                                                var txt = tvmTexts[t].innerText.replace(/<!---->/g, '').trim();
                                                if (txt && !txt.toLowerCase().includes('há') && !txt.toLowerCase().includes('dia')) {
                                                    localStr = txt;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        var localStrBaixo = localStr.toLowerCase();
                                        var formatoStr = "Presencial";
                                        
                                        if (textFull.includes('remoto') || textFull.includes('remote') || textFull.includes('home office') || textFull.includes('qualquer lugar')) {
                                            formatoStr = "Remoto";
                                        } else if (textFull.includes('híbrido') || textFull.includes('hibrido')) {
                                            formatoStr = "Híbrido";
                                        }
                                        
                                        var localAprovado = false;
                                        var eRemotoIntl = locaisAlvo.includes("remoto (internacional)");

                                        if (locaisAlvo.includes("brasil")) {
                                            localAprovado = true;
                                        } else {
                                            for (var l = 0; l < locaisAlvo.length; l++) {
                                                var alvo = locaisAlvo[l];
                                                if (alvo === "remoto (brasil)") {
                                                    if (formatoStr === "Remoto") localAprovado = true;
                                                } else if (alvo === "remoto (internacional)") {
                                                    if (formatoStr === "Remoto") localAprovado = true;
                                                } else {
                                                    var cidadeEstado = alvo.split(',')[0].trim();
                                                    if (localStrBaixo.includes(cidadeEstado)) localAprovado = true;
                                                }
                                            }
                                        }
                                        
                                        if (!localAprovado) continue; 
                                        
                                        if (!eRemotoIntl) {
                                            if (termosGringos.some(t => tituloBaixo.includes(t) || localStrBaixo.includes(t))) {
                                                continue; 
                                            }
                                        }

                                        var dataStr = "Recente";
                                        var dateEl = el.querySelector('time');
                                        if (dateEl) {
                                            dataStr = dateEl.innerText.replace(/<!---->/g, '').trim();
                                        } else {
                                            var allSpans = el.querySelectorAll('span');
                                            for (var s=0; s<allSpans.length; s++) {
                                                var stxt = allSpans[s].innerText.toLowerCase();
                                                if (stxt.includes('há ') || stxt.includes('hoje') || stxt.includes('ontem') || stxt.includes('minuto') || stxt.includes('hora')) {
                                                    dataStr = allSpans[s].innerText.replace(/<!---->/g, '').trim();
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        if (formatoStr === 'Remoto' && localStr === '') localStr = 'Remoto';
                                        if (!localStr) localStr = 'Brasil';
                                        
                                        encontrados.push([tituloLimpo, link, empresa, localStr, dataStr, formatoStr].join('|||'));
                                    } catch(err) { continue; }
                                }
                                return encontrados;
                            })();
                            """
                            
                            js_final = js_extrator.replace('REPLACE_TERMOS', json.dumps(lista_termos)).replace('REPLACE_PROIBIDAS', json.dumps(lista_proibidas)).replace('REPLACE_LOCAIS', json.dumps(lista_locais))
                            vagas_desta_pagina = page.evaluate(js_final)
                            
                            if not vagas_desta_pagina:
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

                        except Exception as e:
                            print(f"⚠️ [LinkedIn] Instabilidade detectada. Erro: {e}")
                            break

        finally:
            try:
                page.close()
                browser.close()
            except:
                pass
        
        print(f"📊 RELATÓRIO LINKEDIN: {len(vagas_brutas_totais)} vagas validadas e extraídas.")
        
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
                    "scraper": "LinkedIn"
                })
                
    return resultados