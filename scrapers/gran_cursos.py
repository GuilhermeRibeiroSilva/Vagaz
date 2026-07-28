import urllib.parse
from playwright.sync_api import sync_playwright
# Stealth gerenciado pelo motor central
from navegador import iniciar_navegador_blindado

def buscar_concursos_gran(termo: str, max_paginas: int = 2, headless: bool = True):
    resultados = []
    termo_limpo = termo.lower().strip()
    
    # Dicionário de mapeamento para as URLs exatas regionais do Gran Cursos
    mapa_estados = {
        "ba": "https://blog.grancursosonline.com.br/concursos/nordeste/bahia/",
        "bahia": "https://blog.grancursosonline.com.br/concursos/nordeste/bahia/",
        "sp": "https://blog.grancursosonline.com.br/concursos/sudeste/sao-paulo/",
        "sao paulo": "https://blog.grancursosonline.com.br/concursos/sudeste/sao-paulo/",
        "são paulo": "https://blog.grancursosonline.com.br/concursos/sudeste/sao-paulo/"
    }
    
    is_regional = termo_limpo in mapa_estados
    url_alvo = mapa_estados.get(termo_limpo, "https://blog.grancursosonline.com.br/concursos-abertos/")
    local_padrao = termo_limpo.capitalize() if is_regional else "Brasil"
    
    vagas_brutas_totais = set()

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        print(f"🤖 [Gran Cursos] Acessando: {url_alvo}")
        
        try:
            page.goto(url_alvo, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)
            
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 800);")
                page.wait_for_timeout(500)
                
            if is_regional:
                # ==========================================
                # EXTRATOR 1: PÁGINAS REGIONAIS (Estrutura de Blog)
                # ==========================================
                js_extrator = r"""
                (function() {
                    var enc = [];
                    var cards = document.querySelectorAll('.row.list-post');
                    
                    for (var i = 0; i < cards.length; i++) {
                        try {
                            var el = cards[i];
                            var titleEl = el.querySelector('h2.heading-4 a, h2 a');
                            if(!titleEl) continue;
                            
                            var titulo = titleEl.innerText.trim();
                            var link = titleEl.href;
                            
                            // Empresa é o órgão. Pega o começo do título.
                            var empresa = titulo.split('-')[0].split(':')[0].trim();
                            if(empresa.length > 45) empresa = "Órgão Público";
                            
                            // === A CASCATA DE DATAS ===
                            var dataStr = 'Recente';
                            
                            // Tentativa 1: Tag <time>
                            var timeTag = el.querySelector('time');
                            if (timeTag) {
                                dataStr = timeTag.innerText.trim(); // Pega o "27/07/26" direto
                            } else {
                                // Tentativa 2 e 3: Classe autor-chamada
                                var dataEl = el.querySelector('.autor-chamada, .data-publicacao');
                                if (dataEl) {
                                    var txtRaw = dataEl.innerText;
                                    var partes = txtRaw.split('•');
                                    var txtData = partes.length > 1 ? partes[partes.length - 1].toLowerCase().trim() : txtRaw.toLowerCase().trim();
                                    
                                    if (txtData.includes('há') || txtData.includes('hora') || txtData.includes('dia') || txtData.includes('minuto')) {
                                        // Cenário "Há 4 horas" - Manda direto pro main.py fazer a conta
                                        dataStr = txtData;
                                    } else {
                                        // Cenário "23 de Julho"
                                        var meses = {"janeiro":"01","fevereiro":"02","março":"03","abril":"04","maio":"05","junho":"06","julho":"07","agosto":"08","setembro":"09","outubro":"10","novembro":"11","dezembro":"12"};
                                        var dataTraduzida = false;
                                        
                                        for (var mes in meses) {
                                            if (txtData.includes(mes)) {
                                                var diaMatch = txtData.match(/(\d{1,2})\s+de/);
                                                var anoMatch = txtData.match(/20\d{2}/);
                                                
                                                var dia = diaMatch ? diaMatch[1].padStart(2, '0') : '01';
                                                
                                                if (anoMatch) {
                                                    dataStr = dia + "/" + meses[mes] + "/" + anoMatch[0];
                                                } else {
                                                    dataStr = dia + "/" + meses[mes]; // Ex: 23/07
                                                }
                                                dataTraduzida = true;
                                                break;
                                            }
                                        }
                                        
                                        // Se falhou em tudo, busca apenas a data via Regex
                                        if (!dataTraduzida) {
                                            var matchNum = txtData.match(/(\d{2}\/\d{2}(\/\d{2,4})?)/);
                                            if (matchNum) dataStr = matchNum[1];
                                        }
                                    }
                                }
                            }
                            // ===========================
                            
                            // Ignora propagandas do cursinho
                            if (titulo.toLowerCase().includes('entrevista') && !titulo.toLowerCase().includes('concurso')) continue;
                            
                            enc.push([titulo, link, empresa, 'LOCAL_AQUI', dataStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return enc;
                })();
                """
                
                js_final = js_extrator.replace('LOCAL_AQUI', local_padrao)
                vagas_extraidas = page.evaluate(js_final)
                
                for vaga in vagas_extraidas:
                    vagas_brutas_totais.add(vaga)
                    
            else:
                # ==========================================
                # EXTRATOR 2: PÁGINA NACIONAL (Mega Artigo / Tabelas)
                # ==========================================
                js_extrator = r"""
                (function() {
                    var enc = [];
                    
                    var trs = document.querySelectorAll('article#content table tbody tr');
                    for (var t = 0; t < trs.length; t++) {
                        try {
                            var tds = trs[t].querySelectorAll('td');
                            if(tds.length >= 3) {
                                var aTagTabela = tds[0].querySelector('a');
                                if(aTagTabela) {
                                    var tituloTab = tds[0].innerText.trim();
                                    var linkTab = aTagTabela.href;
                                    var prazoTab = tds[2].innerText.trim().replace(/\n/g, ' ');

                                    var empresaTab = tituloTab.split('-')[0].trim();
                                    if(empresaTab.length > 40) empresaTab = "Órgão Público";

                                    if(tituloTab !== 'Concurso' && tituloTab.length > 2) {
                                        enc.push([tituloTab, linkTab, empresaTab, 'Brasil', prazoTab].join('|||'));
                                    }
                                }
                            }
                        } catch(e) {}
                    }

                    var headers = document.querySelectorAll('article#content h3');
                    for (var i = 0; i < headers.length; i++) {
                        try {
                            var h3 = headers[i];
                            var aTag = h3.querySelector('a');
                            var titulo = h3.innerText.trim();
                            var link = aTag ? aTag.href : '';

                            if(titulo.includes('?')) continue;

                            var empresa = titulo.split('-')[0].trim();
                            if(empresa.length > 40) empresa = "Órgão Público";

                            var nextEl = h3.nextElementSibling;
                            var inscricoes = '';

                            while(nextEl && nextEl.tagName !== 'H3' && nextEl.tagName !== 'H2') {
                                if (nextEl.tagName === 'UL') {
                                    var lis = nextEl.querySelectorAll('li');
                                    for(var j=0; j<lis.length; j++) {
                                        var text = lis[j].innerText;
                                        if(text.toLowerCase().includes('inscrições:')) {
                                            inscricoes = text.replace(/Período de inscrições:/i, '').trim();
                                        }
                                    }
                                }
                                nextEl = nextEl.nextElementSibling;
                            }

                            if(!inscricoes) inscricoes = 'Recente'; 

                            if(titulo.length > 3 && link) {
                                enc.push([titulo, link, empresa, 'Brasil', inscricoes].join('|||'));
                            }
                        } catch(e) {}
                    }
                    return enc;
                })();
                """
            
                vagas_extraidas = page.evaluate(js_extrator)
                
                for vaga_str in vagas_extraidas:
                    if not is_regional:
                        if termo_limpo not in vaga_str.lower():
                            continue 
                    vagas_brutas_totais.add(vaga_str)

            print(f"✅ [Gran Cursos] {len(vagas_brutas_totais)} editais encontrados e filtrados para '{termo}'.")

        except Exception as e:
            print(f"❌ Erro na extração do Gran Cursos: {e}")
        
        browser.close()
        
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "Gran Cursos"
                })
                
    return resultados