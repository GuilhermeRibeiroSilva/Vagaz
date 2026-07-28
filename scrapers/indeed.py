import urllib.parse
import random
from playwright.sync_api import sync_playwright
# O Stealth foi removido daqui pois o motor blindado já faz isso
from navegador import iniciar_navegador_blindado

def buscar_vagas_indeed(termo: str, local: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    termo_formatado = urllib.parse.quote(termo.strip())
    local_formatado = urllib.parse.quote(local.strip()) if local.strip() else "Brasil"
    
    vagas_brutas_totais = set()
    links_capturados = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(max_paginas):
            start_index = pagina * 10
            url = f"https://br.indeed.com/jobs?q={termo_formatado}&l={local_formatado}&start={start_index}"
            
            print(f"🤖 [Indeed - Pág {pagina + 1}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Simula leitura humana inicial
                page.wait_for_timeout(random.randint(3000, 5000))
                
                # RADAR CLOUDFLARE: Se cair no desafio anti-robô, ele tenta esperar
                titulo_pagina = page.title().lower()
                if "cloudflare" in titulo_pagina or "moment" in titulo_pagina or "human" in titulo_pagina:
                    print("🧱 [ALERTA CLOUDFLARE] Bloqueio detectado! Tentando aguardar a resolução...")
                    page.wait_for_timeout(15000)
                
                # Scroll suave para carregar os cards ocultos
                for _ in range(4):
                    page.mouse.wheel(0, random.randint(400, 700))
                    page.wait_for_timeout(random.randint(800, 1500))
                
                # EXTRATOR INTELIGENTE (Padrão Ouro - 5 Chaves)
                js_extrator = r"""
                (function() {
                    var encontrados = [];
                    // Busca direto pela caixa mestre da vaga (Onde tudo fica dentro)
                    var cards = document.querySelectorAll('div.job_seen_beacon, div.cardOutline');
                    
                    for (var i = 0; i < cards.length; i++) {
                        try {
                            var el = cards[i];
                            var textFull = el.innerText.toLowerCase();
                            
                            // 1. TÍTULO E LINK
                            var aTag = el.querySelector('a.jcs-JobTitle, h2.jobTitle a');
                            if (!aTag) continue;
                            
                            var tituloLimpo = aTag.innerText.trim();
                            if (!tituloLimpo) {
                                // Fallback para achar o título dentro do span com atributo title
                                var spanT = aTag.querySelector('span[title]');
                                if (spanT) tituloLimpo = spanT.getAttribute('title').trim();
                            }
                            if (!tituloLimpo || tituloLimpo.length < 3) continue;

                            var rawLink = aTag.getAttribute('href') || '';
                            if(rawLink.startsWith('/')) rawLink = 'https://br.indeed.com' + rawLink;
                            
                            // Limpeza de rastreadores: Corta a URL no primeiro "&"
                            var link = rawLink;
                            if (rawLink.includes('&')) {
                                link = rawLink.split('&')[0];
                            }

                            // 2. EMPRESA
                            var empresa = "Confidencial";
                            var empEl = el.querySelector('[data-testid="company-name"], .companyName');
                            if (empEl) {
                                empresa = empEl.innerText.trim();
                            }

                            // 3. LOCALIZAÇÃO E REMOTO
                            var localStr = 'Local não informado';
                            var locEl = el.querySelector('[data-testid="text-location"], .companyLocation');
                            if (locEl) {
                                localStr = locEl.innerText.trim();
                            }
                            
                            if (textFull.includes('remoto') || textFull.includes('home office') || textFull.includes('qualquer lugar')) {
                                localStr = 'Remoto';
                            }
                            
                            // 4. DATA (Fixo em Recente como você observou)
                            var dataStr = 'Recente';
                            
                            encontrados.push([tituloLimpo, link, empresa, localStr, dataStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return encontrados;
                })();
                """
                
                vagas_desta_pagina = page.evaluate(js_extrator)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [Indeed] Fim das vagas atingido (ou bloqueado). Encerrando o ciclo.")
                    break
                    
                novas_vagas = 0
                for vaga_str in vagas_desta_pagina:
                    link_vaga = vaga_str.split('|||')[1]
                    if link_vaga not in links_capturados:
                        links_capturados.add(link_vaga)
                        vagas_brutas_totais.add(vaga_str)
                        novas_vagas += 1
                        
                if novas_vagas == 0:
                    print(f"🛑 [Indeed] Repetição detectada na pág {pagina + 1}. Fim da linha.")
                    break
                    
                print(f"✅ [Indeed] {novas_vagas} vagas capturadas na pág {pagina + 1}.")

            except Exception as e:
                print(f"❌ Erro na página {pagina + 1}: {e}")
                break
            
        browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas extraídas do Indeed.")
        
        # RETORNO NO DICIONÁRIO DE OURO PADRONIZADO
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "Indeed" # Assinatura adicionada
                })
                
    return resultados