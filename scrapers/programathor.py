import urllib.parse
import random
from playwright.sync_api import sync_playwright
# O Stealth foi removido daqui pois o motor blindado já faz isso
from navegador import iniciar_navegador_blindado

def buscar_vagas_programathor(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    # O ProgramaThor usa hífens em vez de espaços na URL
    termo_formatado = urllib.parse.quote(termo.replace(' ', '-').lower())
    
    vagas_brutas_totais = set()
    links_capturados = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(1, max_paginas + 1):
            if pagina == 1:
                url = f"https://programathor.com.br/jobs-{termo_formatado}"
            else:
                url = f"https://programathor.com.br/jobs-{termo_formatado}?page={pagina}"
            
            print(f"🤖 [ProgramaThor - Pág {pagina}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                
                # Simula o humano lendo a tela
                page.wait_for_timeout(random.randint(2000, 3500))
                
                # Se cair em uma página 404
                if "404" in page.title() or "não encontrada" in page.title().lower():
                    print("⚠️ [ProgramaThor] Nenhuma vaga encontrada para esse termo exato.")
                    break
                
                for _ in range(3):
                    page.mouse.wheel(0, random.randint(500, 700))
                    page.wait_for_timeout(random.randint(700, 1200))
                
                # EXTRATOR PADRONIZADO (5 Chaves)
                js_extrator = r"""
                (function() {
                    var encontrados = [];
                    var links = document.querySelectorAll('a[href*="/jobs/"]');
                    
                    for (var i = 0; i < links.length; i++) {
                        try {
                            var el = links[i];
                            
                            // 1. TÍTULO E LINK
                            var titleEl = el.querySelector('h2, h3');
                            if (!titleEl) continue;
                            
                            var tituloLimpo = titleEl.innerText.trim();
                            if (tituloLimpo.length < 3) continue;

                            var textoCompleto = el.innerText.toLowerCase();
                            
                            if (textoCompleto.includes('encerrada') || 
                                textoCompleto.includes('pausada') || 
                                textoCompleto.includes('cancelada') || 
                                textoCompleto.includes('fechada') ||
                                textoCompleto.includes('vencida')) {
                                continue;
                            }

                            var href = el.getAttribute('href');
                            if (href && href.startsWith('/')) href = 'https://programathor.com.br' + href;
                            
                            // 2. EMPRESA (Lendo o ícone da maleta)
                            var empresa = "Confidencial";
                            var iconBriefcase = el.querySelector('i.fa-briefcase');
                            if (iconBriefcase && iconBriefcase.parentElement) {
                                empresa = iconBriefcase.parentElement.innerText.trim();
                            }
                            
                            // 3. LOCALIZAÇÃO (Lendo o ícone do mapa)
                            var localStr = "Brasil"; // Fallback
                            var iconMarker = el.querySelector('i.fa-map-marker, i.fa-map-marker-alt');
                            if (iconMarker && iconMarker.parentElement) {
                                localStr = iconMarker.parentElement.innerText.trim();
                            }
                            
                            // Regra de Ouro do Remoto: Se disser remoto em qualquer lugar do card ou título
                            if (textoCompleto.includes('remoto') || textoCompleto.includes('home office')) {
                                localStr = "Remoto";
                            }
                            
                            // 4. DATA (O site não fornece, fixamos como Recente)
                            var dataStr = 'Recente';
                            
                            encontrados.push([tituloLimpo, href, empresa, localStr, dataStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return encontrados;
                })();
                """
                
                vagas_desta_pagina = page.evaluate(js_extrator)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [ProgramaThor] Fim das vagas. Encerrando na pág {pagina}.")
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
                    
                print(f"✅ [ProgramaThor] {novas_vagas} vagas capturadas na pág {pagina}.")

            except Exception as e:
                print(f"❌ Erro na página {pagina}: {e}")
                break
            
        browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas extraídas do ProgramaThor.")
        
        # 5. RETORNO NO DICIONÁRIO DE OURO (Com o carimbo do scraper)
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "Programathor"
                })
                
    return resultados