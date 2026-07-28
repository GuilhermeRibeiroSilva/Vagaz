import urllib.parse
import random
from playwright.sync_api import sync_playwright
# Removemos o Stealth daqui, pois o navegador.py já faz a blindagem!
from navegador import iniciar_navegador_blindado

def buscar_vagas_remotar(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    termo_formatado = urllib.parse.quote(termo)
    
    # MEMÓRIA ANTI-LOOP: Guarda os links para não repetir vagas
    links_capturados = set()
    vagas_brutas_totais = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(1, max_paginas + 1):
            url = f"https://remotar.com.br/search/jobs?q={termo_formatado}&page={pagina}"
            
            print(f"🤖 [Remotar - Pág {pagina}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                
                # Respiro humano
                page.wait_for_timeout(random.randint(2000, 4000))
                
                # Desce a página para carregar todos os cards
                for _ in range(4):
                    page.mouse.wheel(0, random.randint(500, 800))
                    page.wait_for_timeout(random.randint(700, 1200))
                
                # EXTRATOR CIRÚRGICO ATUALIZADO COM OS PADRÕES DO HTML
                js_extrator = r"""
                (function() {
                    var encontrados = [];
                    var cards = document.querySelectorAll('.box-content, .css-e36j8y, .job-card, [class*="job-list"]');
                    
                    for (var i = 0; i < cards.length; i++) {
                        try {
                            var el = cards[i];
                            
                            // 1. TÍTULO E LINK
                            var titleEl = el.querySelector('a.job-title') || el.querySelector('h2 a') || el.querySelector('h3 a') || el.querySelector('h2');
                            if (!titleEl) continue;
                            
                            var tituloLimpo = titleEl.innerText.trim();
                            if (tituloLimpo.length < 3) continue;
                            
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
                            if (href.startsWith('/')) href = 'https://remotar.com.br' + href;

                            var textoCompleto = el.innerText.toLowerCase();
                            if (textoCompleto.includes('encerrada') || textoCompleto.includes('vencida') || textoCompleto.includes('fechada')) {
                                continue;
                            }

                            // 2. EMPRESA
                            var empresa = "Confidencial";
                            var companyEl = el.querySelector('a.company, .company-name');
                            if (companyEl) {
                                empresa = companyEl.innerText.trim();
                            }

                            // 3. DATA (Agora caça no <div class="info-meta">)
                            var dataStr = "";
                            var metaEl = el.querySelector('.info-meta');
                            if (metaEl) {
                                var primeiroP = metaEl.querySelector('p'); // Pega o primeiro <p> que tem a data
                                if (primeiroP) {
                                    dataStr = primeiroP.innerText.trim();
                                }
                            }
                            
                            // 4. LOCALIZAÇÃO E FORMATO (Tratamento para Remoto)
                            var localStr = "Remoto"; // Regra padrão do usuário para o Remotar
                            
                            // Tenta caçar a cidade exata lendo o ícone de localização
                            var svgs = el.querySelectorAll('svg');
                            for (var s = 0; s < svgs.length; s++) {
                                var path = svgs[s].querySelector('path');
                                // Identifica o SVG do pino de mapa (M12 2C8.13...)
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
                            
                            // Se as tags de formato disserem que é remoto, garantimos o remoto
                            var tags = el.querySelectorAll('a[href*="/search/jobs"]');
                            for (var t = 0; t < tags.length; t++) {
                                if (tags[t].innerText.toLowerCase().includes('remoto')) {
                                    localStr = "Remoto";
                                }
                            }

                            encontrados.push([tituloLimpo, href, empresa, localStr, dataStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return encontrados;
                })();
                """
                
                vagas_desta_pagina = page.evaluate(js_extrator)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [Remotar] Nenhuma vaga nova carregou. Fim da linha na pág {pagina}.")
                    break
                
                novas_vagas = 0
                for vaga_str in vagas_desta_pagina:
                    link_da_vaga = vaga_str.split('|||')[1]
                    
                    if link_da_vaga not in links_capturados:
                        links_capturados.add(link_da_vaga)
                        vagas_brutas_totais.add(vaga_str)
                        novas_vagas += 1
                
                if novas_vagas == 0:
                    print(f"🛑 [Remotar] O site começou a repetir vagas na pág {pagina}. Abortando para evitar clones.")
                    break

                print(f"✅ [Remotar] {novas_vagas} vagas aprovadas na pág {pagina}.")

            except Exception as e:
                print(f"❌ Erro na pág {pagina}: {e}")
                break
            
        browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas extraídas do Remotar.")
        
        # 5. RETORNO NO DICIONÁRIO DE OURO PADRONIZADO
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "Remotar" # Garantia de assinatura do scraper
                })
                
    return resultados