import urllib.parse
import unicodedata
import random
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from navegador import iniciar_navegador_blindado

def remover_acentos(texto: str):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def buscar_vagas_empregos(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    # Prepara o termo no formato do site: "Lider Tecnico" vira "lider-tecnico"
    termo_limpo = termo.lower().strip()
    termo_sem_acento = remover_acentos(termo_limpo)
    termo_slug = termo_sem_acento.replace(' ', '-')
    termo_formatado = urllib.parse.quote(termo_slug)
    
    vagas_brutas_totais = set()
    links_capturados = set()

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(1, max_paginas + 1):
            if pagina == 1:
                url = f"https://www.empregos.com.br/vagas/{termo_formatado}"
            else:
                # O Empregos.com.br usa paginação em formato de diretório /2, /3...
                url = f"https://www.empregos.com.br/vagas/{termo_formatado}/{pagina}"
            
            print(f"🤖 [Empregos.com - Pág {pagina}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                
                # Respiro humano
                page.wait_for_timeout(random.randint(2000, 3500))
                
                # Título 404 (caso não existam vagas para aquele termo exato)
                if "404" in page.title() or "não encontrada" in page.title().lower():
                    print("⚠️ [Empregos.com] Nenhuma vaga encontrada para esse termo.")
                    break

                # Scroll para garantir que a página carregou os cards
                for _ in range(3):
                    page.mouse.wheel(0, random.randint(500, 700))
                    page.wait_for_timeout(random.randint(800, 1200))
                    
                js_extrator = r"""
                (function() {
                    var enc = [];
                    // Pega exatamente o card de vagas do HTML fornecido
                    var cards = document.querySelectorAll('.cmp-job-card-area-expand');
                    
                    for (var i = 0; i < cards.length; i++) {
                        try {
                            var el = cards[i];
                            
                            // TÍTULO
                            var h2 = el.querySelector('h2');
                            if(!h2) continue;
                            var titulo = h2.innerText.trim();
                            if(titulo.length < 3) continue;
                            
                            // Filtro silencioso para evitar vagas fora do foco Junior/Estágio
                            var tituloBaixo = titulo.toLowerCase();
                            if (tituloBaixo.includes('senior') || tituloBaixo.includes('sênior') || tituloBaixo.includes('pleno') || tituloBaixo.includes('especialista')) {
                                continue;
                            }
                            
                            // LINK DIRETO
                            var aTag = el.querySelector('a[href*="/vaga/"]');
                            var link = aTag ? 'https://www.empregos.com.br' + aTag.getAttribute('href') : '';
                            
                            // EMPRESA (Geralmente na tag h3 abaixo do título ou no link da logo)
                            var empH3 = el.querySelector('h3');
                            var empresa = empH3 ? empH3.innerText.trim() : 'Confidencial';
                            if (empresa.toLowerCase().includes('salvador') || empresa.toLowerCase().includes('brasil')) {
                                empresa = 'Confidencial'; // Tratamento de falso positivo
                            }
                            
                            // LOCALIZAÇÃO (Tag h3 com atributo title)
                            var localTag = el.querySelector('h3[title]');
                            var localStr = localTag ? localTag.getAttribute('title') : 'Brasil';
                            
                            // FORMATO
                            var formatoStr = "Presencial";
                            var txtGeral = el.innerText.toLowerCase();
                            if (txtGeral.includes('remoto') || txtGeral.includes('home office')) {
                                formatoStr = "Remoto";
                            } else if (txtGeral.includes('híbrido') || txtGeral.includes('hibrido')) {
                                formatoStr = "Híbrido";
                            }
                            
                            // DATA
                            var dataStr = "Recente";
                            var todasH3 = el.querySelectorAll('h3');
                            for(var k=0; k<todasH3.length; k++) {
                                var txtData = todasH3[k].innerText.toLowerCase();
                                if(txtData.includes('publicada') || txtData.includes('hoje') || txtData.includes('há ')) {
                                    dataStr = todasH3[k].innerText.trim();
                                    break;
                                }
                            }
                            
                            enc.push([titulo, link, empresa, localStr, dataStr, formatoStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return enc;
                })();
                """
                
                vagas_desta_pagina = page.evaluate(js_extrator)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [Empregos.com] Fim das vagas. Encerrando na pág {pagina}.")
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
                    
                print(f"✅ [Empregos.com] {novas_vagas} vagas capturadas na pág {pagina}.")

            except Exception as e:
                print(f"❌ Erro na página {pagina}: {e}")
                break
            
        browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas extraídas do Empregos.com.br.")
        
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