import urllib.parse
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth # <--- IMPORT CORRETO (Usando a classe Stealth)
from navegador import iniciar_navegador_blindado

def buscar_vagas_gupy(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    termo_formatado = urllib.parse.quote(termo)
    vagas_brutas_totais = set()
    links_capturados = set()
    
    # <--- APLICAÇÃO CORRETA DO STEALTH NO CONTEXT MANAGER --->
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(1, max_paginas + 1):
            url = f"https://portal.gupy.io/job-search/term={termo_formatado}" if pagina == 1 else f"https://portal.gupy.io/job-search/term={termo_formatado}?page={pagina}"
            
            print(f"🤖 [Gupy - Pág {pagina}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(3000)
                
                # Desce a página para carregar o infinite scroll/lazy load
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    page.wait_for_timeout(1500)
                
                js_extrator = r"""
                (function() {
                    var enc = [];
                    // A Gupy costuma usar listas (ul > li) para os cards
                    var elementos = document.querySelectorAll('li a, a[data-testid="job-list-item"]');
                    
                    if(elementos.length === 0) {
                        elementos = document.querySelectorAll('a'); // Fallback brutal
                    }
                    
                    for (var i = 0; i < elementos.length; i++) {
                        try {
                            var el = elementos[i];
                            var tagTitulo = el.querySelector('h2, h3, h4');
                            if (!tagTitulo) continue; 
                            
                            var tituloLimpo = tagTitulo.innerText.trim();
                            if (tituloLimpo.length < 5 || tituloLimpo.includes("Gupy")) continue;
                            
                            var href = el.getAttribute('href') || "";
                            if(href.startsWith('/')) href = 'https://portal.gupy.io' + href;
                            if(!href.includes('gupy.io')) continue; // Garante que é link de vaga mesmo
                            
                            // LIMPEZA DO LINK E EXTRAÇÃO DA EMPRESA
                            var link = href.split('?')[0]; 
                            var empresa = "Confidencial";
                            
                            // Na Gupy, a empresa quase sempre está no subdomínio (ex: https://itau.gupy.io)
                            try {
                                var dominio = new URL(link).hostname;
                                var partesDominio = dominio.split('.');
                                if (partesDominio.length > 2) {
                                    empresa = partesDominio[0];
                                    // Capitaliza a primeira letra
                                    empresa = empresa.charAt(0).toUpperCase() + empresa.slice(1);
                                }
                            } catch(e) {}
                            
                            // O site da Gupy joga muita info em spans espalhados
                            var textoSujo = el.innerText.trim();
                            var dataStr = "Recente";
                            var localStr = "Brasil";
                            var formatoStr = "Presencial";
                            var linhas = textoSujo.split('\n');
                            
                            for (var j = 0; j < linhas.length; j++) {
                                var l = linhas[j].trim();
                                var lb = l.toLowerCase();
                                
                                if (lb === 'remoto' || lb === 'trabalho remoto') formatoStr = "Remoto";
                                else if (lb === 'presencial') formatoStr = "Presencial";
                                else if (lb === 'híbrido' || lb === 'hibrido') formatoStr = "Híbrido";
                                
                                if (l.match(/ - [A-Z]{2}$/) || l.includes('Estado de') || l.includes('Região')) localStr = l;
                                
                                if (lb.includes('publicada') || lb.includes('há ') || lb.includes('atrás') || l.match(/\d{2}\/\d{2}\/\d{4}/)) {
                                    dataStr = l.charAt(0).toUpperCase() + l.slice(1);
                                }
                            }
                            
                            if (formatoStr === 'Remoto' && localStr === 'Brasil') localStr = 'Qualquer lugar';
                            
                            enc.push([tituloLimpo, link, empresa, localStr, dataStr, formatoStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return enc;
                })();
                """
                
                vagas_desta_pagina = page.evaluate(js_extrator)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [Gupy] Fim das vagas. Parando o loop na página {pagina}.")
                    break
                    
                novas_vagas = 0
                for vaga_str in vagas_desta_pagina:
                    link_vaga = vaga_str.split('|||')[1]
                    if link_vaga not in links_capturados:
                        links_capturados.add(link_vaga)
                        vagas_brutas_totais.add(vaga_str)
                        novas_vagas += 1
                        
                if novas_vagas == 0:
                    print(f"🛑 [Gupy] Resultados repetidos na pág {pagina}. Fim da linha.")
                    break
                    
                print(f"✅ [Gupy] {novas_vagas} vagas capturadas na página {pagina}.")

            except Exception as e:
                print(f"❌ Erro na página {pagina}: {e}")
                break
            
        browser.close()
        
        print(f"📊 RELATÓRIO GUPY: {len(vagas_brutas_totais)} vagas extraídas.")
        
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 6:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "formato": partes[5]
                })
                
    return resultados