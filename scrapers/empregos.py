import urllib.parse
import unicodedata
import random
import json
from playwright.sync_api import sync_playwright
from utils.navegador import iniciar_navegador_blindado

def remover_acentos(texto: str):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def buscar_vagas_empregos(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    lista_termos = [t.strip().lower() for t in termo.split(',') if t.strip()]
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
                termo_sem_acento = remover_acentos(termo_alvo)
                termo_slug = termo_sem_acento.replace(' ', '-')
                termo_formatado = urllib.parse.quote(termo_slug)
                
                print(f"\n🔍 [Empregos.com] Iniciando varredura para a tag: '{termo_alvo}'")

                for pagina in range(1, max_paginas + 1):
                    url = f"https://www.empregos.com.br/vagas/{termo_formatado}" if pagina == 1 else f"https://www.empregos.com.br/vagas/{termo_formatado}/{pagina}"
                    print(f"🤖 [Empregos.com - Pág {pagina}] Acessando: {url}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(random.randint(2000, 3500))
                        
                        if "404" in page.title() or "não encontrada" in page.title().lower():
                            break

                        for _ in range(3):
                            page.mouse.wheel(0, random.randint(500, 700))
                            page.wait_for_timeout(random.randint(800, 1200))
                            
                        js_extrator = r"""
                        (function() {
                            var enc = [];
                            var cards = document.querySelectorAll('.cmp-job-card-area-expand');
                            var proibidas = REPLACE_PROIBIDAS;
                            var locaisAlvo = REPLACE_LOCAIS; 
                            var termosGringos = ["eua", "usa", "latam", "global", "worldwide", "abroad", "internacional", "exterior"];
                            
                            for (var i = 0; i < cards.length; i++) {
                                try {
                                    var el = cards[i];
                                    var h2 = el.querySelector('h2');
                                    if(!h2) continue;
                                    var titulo = h2.innerText.trim();
                                    if(titulo.length < 3) continue;
                                    
                                    var tituloBaixo = titulo.toLowerCase();
                                    if (proibidas.length > 0 && proibidas.some(p => tituloBaixo.includes(p))) continue;
                                    
                                    var aTag = el.querySelector('a[href*="/vaga/"]');
                                    var link = aTag ? 'https://www.empregos.com.br' + aTag.getAttribute('href') : '';
                                    
                                    var empH3 = el.querySelector('h3');
                                    var empresa = empH3 ? empH3.innerText.trim() : 'Confidencial';
                                    if (empresa.toLowerCase().includes('salvador') || empresa.toLowerCase().includes('brasil')) {
                                        empresa = 'Confidencial';
                                    }
                                    
                                    var localTag = el.querySelector('h3[title]');
                                    var localStr = localTag ? localTag.getAttribute('title') : 'Brasil';
                                    var localStrBaixo = localStr.toLowerCase();
                                    
                                    var txtGeral = el.innerText.toLowerCase();
                                    var formatoStr = "Presencial";
                                    if (txtGeral.includes('remoto') || txtGeral.includes('home office')) {
                                        formatoStr = "Remoto";
                                    } else if (txtGeral.includes('híbrido') || txtGeral.includes('hibrido')) {
                                        formatoStr = "Híbrido";
                                    }
                                    
                                    var localAprovado = false;
                                    var eRemotoBr = false;
                                    var eRemotoIntl = false;

                                    if (locaisAlvo.includes("brasil")) {
                                        localAprovado = true;
                                    } else {
                                        for (var l = 0; l < locaisAlvo.length; l++) {
                                            var alvo = locaisAlvo[l];
                                            if (alvo === "remoto (brasil)") {
                                                if (formatoStr === "Remoto") {
                                                    localAprovado = true;
                                                    eRemotoBr = true;
                                                }
                                            } else if (alvo === "remoto (internacional)") {
                                                if (formatoStr === "Remoto") {
                                                    localAprovado = true;
                                                    eRemotoIntl = true;
                                                }
                                            } else {
                                                var cidadeEstado = alvo.split(',')[0].trim();
                                                if (localStrBaixo.includes(cidadeEstado)) {
                                                    localAprovado = true;
                                                }
                                            }
                                        }
                                    }
                                    
                                    if (!localAprovado) continue; 
                                    
                                    if (eRemotoBr && !eRemotoIntl) {
                                        if (termosGringos.some(t => tituloBaixo.includes(t) || localStrBaixo.includes(t))) {
                                            continue; 
                                        }
                                    }
                                    
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
                        
                        js_final = js_extrator.replace('REPLACE_PROIBIDAS', json.dumps(lista_proibidas)).replace('REPLACE_LOCAIS', json.dumps(lista_locais))
                        vagas_desta_pagina = page.evaluate(js_final)
                        
                        if not vagas_desta_pagina:
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

                    except Exception as e:
                        print(f"❌ Erro na página {pagina}: {e}")
                        break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} vagas validadas extraídas do Empregos.com.br.")
        
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
                    "scraper": "Empregos"
                })
                
    return resultados