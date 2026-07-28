import urllib.parse
import unicodedata
import random
from playwright.sync_api import sync_playwright
# Removido o Stealth, já gerenciado pelo motor central
from navegador import iniciar_navegador_blindado

def remover_acentos(texto: str):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def buscar_vagas_infojobs(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    termo_limpo = termo.lower().strip()
    termo_sem_acento = remover_acentos(termo_limpo)
    termo_formatado = urllib.parse.quote(termo_sem_acento)
    
    vagas_brutas_totais = set()
    links_capturados = set()

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(1, max_paginas + 1):
            if pagina == 1:
                url = f"https://www.infojobs.com.br/empregos.aspx?palabra={termo_formatado}"
            else:
                url = f"https://www.infojobs.com.br/empregos.aspx?palabra={termo_formatado}&page={pagina}"
            
            print(f"🤖 [InfoJobs - Pág {pagina}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                
                # Simula o tempo humano lendo
                page.wait_for_timeout(random.randint(2000, 4000))
                
                # Desce a página em degraus suaves para forçar o carregamento
                for _ in range(4):
                    page.mouse.wheel(0, random.randint(500, 800))
                    page.wait_for_timeout(random.randint(700, 1200))
                    
                # EXTRATOR INTELIGENTE (Padrão Ouro - 5 Chaves)
                js_extrator = r"""
                (function() {
                    var enc = [];
                    var cards = document.querySelectorAll('div.card.grid-row, .card');
                    
                    for (var i = 0; i < cards.length; i++) {
                        try {
                            var el = cards[i];
                            var textFull = el.innerText.toLowerCase();
                            
                            // 1. TÍTULO E LINK
                            var titleEl = el.querySelector('h2.js_vacancyTitle');
                            if(!titleEl) continue;
                            
                            var titulo = titleEl.innerText.trim();
                            if(titulo.length < 3) continue;

                            var aTag = el.querySelector('a.text-decoration-none[href*="/vaga-de-"]') || titleEl.parentElement;
                            var link = aTag ? aTag.getAttribute('href') : '';
                            
                            if (!link || link === '') {
                                var fallbackLink = el.querySelector('a[href*="/vaga-de-"]');
                                if (fallbackLink) link = fallbackLink.getAttribute('href');
                            }
                            if (link && link.startsWith('/')) link = 'https://www.infojobs.com.br' + link;
                            if (!link) continue;
                            
                            // 2. EMPRESA (Limpando o lixo HTML do tooltip)
                            var empTag = el.querySelector('.text-body a') || el.querySelector('.text-body');
                            var empresa = 'Confidencial';
                            if (empTag) {
                                // Clonamos o elemento para deletar as tags internas (span tooltip, svg) sem quebrar o site
                                var cloneEmp = empTag.cloneNode(true);
                                var spansToRemove = cloneEmp.querySelectorAll('span');
                                spansToRemove.forEach(t => t.remove());
                                
                                empresa = cloneEmp.innerText.replace(/\n/g, ' ').replace(/VERIFICADA/gi, '').trim();
                                if (empresa.toLowerCase().includes('confidencial') || empresa.length < 2) {
                                    empresa = 'Confidencial';
                                }
                            }
                            
                            // 3. LOCALIZAÇÃO E REMOTO (Removendo a distância do usuário)
                            var localTag = el.querySelector('.mb-8') || el.querySelector('.text-medium');
                            var localStr = 'Brasil';
                            if (localTag) {
                                var cloneLoc = localTag.cloneNode(true);
                                var distTag = cloneLoc.querySelector('.js_divUserVagaDistance');
                                if (distTag) distTag.remove();
                                localStr = cloneLoc.innerText.trim().split(',')[0]; // Pega só o estado/cidade
                            }
                            
                            // REGRA DO REMOTO
                            if (textFull.includes('remoto') || textFull.includes('home office') || textFull.includes('qualquer lugar')) {
                                localStr = 'Remoto';
                            }
                            
                            // 4. DATA (Traduzindo "20 jul" para "20/07")
                            var dataTag = el.querySelector('.text-medium.small.text-nowrap') || el.querySelector('span.text-muted');
                            var dataStr = 'Recente';
                            if (dataTag) {
                                var txtData = dataTag.innerText.toLowerCase().trim();
                                if (txtData.includes('hoje') || txtData.includes('ontem')) {
                                    dataStr = txtData;
                                } else {
                                    var meses = {"jan":"01","fev":"02","mar":"03","abr":"04","mai":"05","jun":"06","jul":"07","ago":"08","set":"09","out":"10","nov":"11","dez":"12"};
                                    for (var mes in meses) {
                                        if (txtData.includes(mes)) {
                                            var diaMatch = txtData.match(/(\d{1,2})/);
                                            if (diaMatch) {
                                                var dia = diaMatch[1].padStart(2, '0');
                                                dataStr = dia + "/" + meses[mes];
                                            }
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            enc.push([titulo, link, empresa, localStr, dataStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return enc;
                })();
                """
                
                vagas_desta_pagina = page.evaluate(js_extrator)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [InfoJobs] Fim das vagas na pág {pagina}.")
                    break
                    
                novas_vagas = 0
                for vaga_str in vagas_desta_pagina:
                    link_vaga = vaga_str.split('|||')[1]
                    if link_vaga not in links_capturados:
                        links_capturados.add(link_vaga)
                        vagas_brutas_totais.add(vaga_str)
                        novas_vagas += 1
                
                if novas_vagas == 0:
                    print(f"🛑 [InfoJobs] Repetição detectada na pág {pagina}. Fim da linha.")
                    break
                    
                print(f"✅ [InfoJobs] {novas_vagas} vagas mapeadas na pág {pagina}.")

            except Exception as e:
                print(f"❌ Erro na pág {pagina}: {e}")
                break
        
        browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} resultados extraídos do InfoJobs.")
        
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
                    "scraper": "Infojobs" # Assinatura adicionada
                })
                
    return resultados