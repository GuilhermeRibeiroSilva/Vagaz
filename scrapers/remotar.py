import urllib.parse
import random
import json
from playwright.sync_api import sync_playwright
from utils.navegador import iniciar_navegador_blindado

def buscar_vagas_remotar(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    lista_termos = [t.strip().lower() for t in termo.split(',') if t.strip()]
    if not lista_termos:
        return resultados

    lista_proibidas = [p.strip().lower() for p in palavras_proibidas.split(',') if p.strip()]
    lista_locais = [l.strip().lower() for l in local.split(',') if l.strip()]
    
    if not lista_locais:
        lista_locais = ["brasil"]
    
    links_capturados = set()
    vagas_brutas_totais = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)
        try:
            for termo_alvo in lista_termos:
                termo_formatado = urllib.parse.quote(termo_alvo)
                print(f"\n🔍 [Remotar] Iniciando varredura para a tag: '{termo_alvo}'")

                for pagina in range(1, max_paginas + 1):
                    url = f"https://remotar.com.br/search/jobs?q={termo_formatado}&page={pagina}"
                    print(f"🤖 [Remotar - Pág {pagina}] Acessando: {url}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(random.randint(2000, 4000))
                        
                        for _ in range(4):
                            page.mouse.wheel(0, random.randint(500, 800))
                            page.wait_for_timeout(random.randint(700, 1200))
                        
                        js_extrator = r"""
                        (function() {
                            var encontrados = [];
                            var cards = document.querySelectorAll('.box-content, .css-e36j8y, .job-card, [class*="job-list"]');
                            var termosAlvo = REPLACE_TERMOS;
                            var proibidas = REPLACE_PROIBIDAS;
                            var locaisAlvo = REPLACE_LOCAIS;
                            var termosGringos = ["eua", "usa", "latam", "global", "worldwide", "abroad", "internacional", "exterior"];
                            
                            for (var i = 0; i < cards.length; i++) {
                                try {
                                    var el = cards[i];
                                    
                                    var titleEl = el.querySelector('a.job-title') || el.querySelector('h2 a') || el.querySelector('h3 a') || el.querySelector('h2');
                                    if (!titleEl) continue;
                                    
                                    var tituloLimpo = titleEl.innerText.trim();
                                    if (tituloLimpo.length < 3) continue;
                                    
                                    var tituloBaixo = tituloLimpo.toLowerCase();
                                    
                                    if (termosAlvo.length > 0) {
                                        var match = termosAlvo.some(t => tituloBaixo.includes(t));
                                        if (!match) continue;
                                    }
                                    if (proibidas.length > 0 && proibidas.some(p => tituloBaixo.includes(p))) continue;
                                    
                                    var href = "";
                                    if (titleEl.tagName.toLowerCase() === 'a') {
                                        href = titleEl.getAttribute('href');
                                    } else if (titleEl.parentElement && titleEl.parentElement.tagName.toLowerCase() === 'a') {
                                        href = titleEl.parentElement.getAttribute('href');
                                    }
                                    
                                    if (!href || href === "") {
                                        var todosLinks = el.querySelectorAll('a');
                                        for (var k = 0; k < todosLinks.length; k++) {
                                            var linkTemp = todosLinks[k].getAttribute('href') || '';
                                            if (linkTemp && !linkTemp.includes('/company/')) {
                                                href = linkTemp;
                                                break;
                                            }
                                        }
                                    }
                                    if (href && href.startsWith('/')) href = 'https://remotar.com.br' + href;

                                    var textoCompleto = el.innerText.toLowerCase();
                                    if (textoCompleto.includes('encerrada') || textoCompleto.includes('vencida') || textoCompleto.includes('fechada')) {
                                        continue;
                                    }

                                    var empresa = "Confidencial";
                                    var companyEl = el.querySelector('a.company, .company-name');
                                    if (companyEl) {
                                        empresa = companyEl.innerText.trim();
                                    }

                                    var dataStr = "Recente";
                                    var metaEl = el.querySelector('.info-meta');
                                    if (metaEl) {
                                        var primeiroP = metaEl.querySelector('p'); 
                                        if (primeiroP) {
                                            dataStr = primeiroP.innerText.trim();
                                        }
                                    }
                                    
                                    var localStr = "Remoto"; 
                                    var svgs = el.querySelectorAll('svg');
                                    for (var s = 0; s < svgs.length; s++) {
                                        var path = svgs[s].querySelector('path');
                                        if (path && path.getAttribute('d') && path.getAttribute('d').startsWith('M12 2C8.13')) {
                                            var locParent = svgs[s].parentElement;
                                            if (locParent) {
                                                var locText = locParent.innerText.replace(svgs[s].innerText, '').trim();
                                                if (locText.length > 2) {
                                                    localStr = locText;
                                                }
                                            }
                                        }
                                    }
                                    
                                    var tags = el.querySelectorAll('a[href*="/search/jobs"]');
                                    for (var t = 0; t < tags.length; t++) {
                                        if (tags[t].innerText.toLowerCase().includes('remoto')) {
                                            localStr = "Remoto";
                                        }
                                    }
                                    
                                    var formatoStr = "Remoto"; 
                                    if (textoCompleto.includes('híbrido') || textoCompleto.includes('hibrido')) formatoStr = "Híbrido";

                                    var localStrBaixo = localStr.toLowerCase();
                                    var localAprovado = false;
                                    var eRemotoBr = false;
                                    var eRemotoIntl = false;

                                    if (locaisAlvo.includes("brasil")) {
                                        localAprovado = true;
                                    } else {
                                        for (var l = 0; l < locaisAlvo.length; l++) {
                                            var alvo = locaisAlvo[l];
                                            if (alvo === "remoto (brasil)") {
                                                if (formatoStr === "Remoto") { localAprovado = true; eRemotoBr = true; }
                                            } else if (alvo === "remoto (internacional)") {
                                                if (formatoStr === "Remoto") { localAprovado = true; eRemotoIntl = true; }
                                            } else {
                                                var cidadeEstado = alvo.split(',')[0].trim();
                                                if (localStrBaixo.includes(cidadeEstado)) { localAprovado = true; }
                                            }
                                        }
                                    }
                                    
                                    if (!localAprovado) continue; 
                                    
                                    if (eRemotoBr && !eRemotoIntl) {
                                        if (termosGringos.some(t => tituloBaixo.includes(t) || localStrBaixo.includes(t) || textoCompleto.includes(t))) {
                                            continue; 
                                        }
                                    }

                                    encontrados.push([tituloLimpo, href, empresa, localStr, dataStr, formatoStr].join('|||'));
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
                            link_da_vaga = vaga_str.split('|||')[1]
                            if link_da_vaga not in links_capturados:
                                links_capturados.add(link_da_vaga)
                                vagas_brutas_totais.add(vaga_str)
                                novas_vagas += 1
                        
                        if novas_vagas == 0:
                            break

                    except Exception as e:
                        print(f"❌ Erro na pág {pagina}: {e}")
                        break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas extraídas do Remotar.")
        
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
                    "scraper": "Remotar"
                })
                
    return resultados