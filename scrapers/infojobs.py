import urllib.parse
import unicodedata
import random
import json
from playwright.sync_api import sync_playwright
from utils.navegador import iniciar_navegador_blindado

def remover_acentos(texto: str):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def buscar_vagas_infojobs(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
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
                termo_formatado = urllib.parse.quote(termo_sem_acento)
                
                print(f"\n🔍 [InfoJobs] Iniciando varredura para a tag: '{termo_alvo}'")

                for pagina in range(1, max_paginas + 1):
                    if pagina == 1:
                        url = f"https://www.infojobs.com.br/empregos.aspx?palabra={termo_formatado}"
                    else:
                        url = f"https://www.infojobs.com.br/empregos.aspx?palabra={termo_formatado}&page={pagina}"
                    
                    print(f"🤖 [InfoJobs - Pág {pagina}] Acessando: {url}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(random.randint(2000, 4000))
                        
                        for _ in range(4):
                            page.mouse.wheel(0, random.randint(500, 800))
                            page.wait_for_timeout(random.randint(700, 1200))
                            
                        js_extrator = r"""
                        (function() {
                            var enc = [];
                            var cards = document.querySelectorAll('div.card.grid-row, .card');
                            var termosAlvo = REPLACE_TERMOS;
                            var proibidas = REPLACE_PROIBIDAS;
                            var locaisAlvo = REPLACE_LOCAIS;
                            var termosGringos = ["eua", "usa", "latam", "global", "worldwide", "abroad", "internacional", "exterior"];
                            
                            for (var i = 0; i < cards.length; i++) {
                                try {
                                    var el = cards[i];
                                    var textFull = el.innerText.toLowerCase();
                                    
                                    var titleEl = el.querySelector('h2.js_vacancyTitle');
                                    if(!titleEl) continue;
                                    
                                    var titulo = titleEl.innerText.trim();
                                    if(titulo.length < 3) continue;
                                    
                                    var tituloBaixo = titulo.toLowerCase();
                                    
                                    if (termosAlvo.length > 0) {
                                        var match = termosAlvo.some(t => tituloBaixo.includes(t));
                                        if (!match) continue;
                                    }
                                    
                                    if (proibidas.length > 0) {
                                        var temProibida = proibidas.some(p => tituloBaixo.includes(p));
                                        if (temProibida) continue;
                                    }

                                    var aTag = el.querySelector('a.text-decoration-none[href*="/vaga-de-"]') || titleEl.parentElement;
                                    var link = aTag ? aTag.getAttribute('href') : '';
                                    
                                    if (!link || link === '') {
                                        var fallbackLink = el.querySelector('a[href*="/vaga-de-"]');
                                        if (fallbackLink) link = fallbackLink.getAttribute('href');
                                    }
                                    if (link && link.startsWith('/')) link = 'https://www.infojobs.com.br' + link;
                                    if (!link) continue;
                                    
                                    var empTag = el.querySelector('.text-body a') || el.querySelector('.text-body');
                                    var empresa = 'Confidencial';
                                    if (empTag) {
                                        var cloneEmp = empTag.cloneNode(true);
                                        var spansToRemove = cloneEmp.querySelectorAll('span');
                                        spansToRemove.forEach(t => t.remove());
                                        
                                        empresa = cloneEmp.innerText.replace(/\n/g, ' ').replace(/VERIFICADA/gi, '').trim();
                                        if (empresa.toLowerCase().includes('confidencial') || empresa.length < 2) {
                                            empresa = 'Confidencial';
                                        }
                                    }
                                    
                                    var localTag = el.querySelector('.mb-8') || el.querySelector('.text-medium');
                                    var localStr = 'Brasil';
                                    if (localTag) {
                                        var cloneLoc = localTag.cloneNode(true);
                                        var distTag = cloneLoc.querySelector('.js_divUserVagaDistance');
                                        if (distTag) distTag.remove();
                                        localStr = cloneLoc.innerText.trim().split(',')[0]; 
                                    }
                                    
                                    var localStrBaixo = localStr.toLowerCase();
                                    var formatoStr = "Presencial";
                                    
                                    if (textFull.includes('remoto') || textFull.includes('home office') || textFull.includes('qualquer lugar')) {
                                        formatoStr = "Remoto";
                                    } else if (textFull.includes('híbrido') || textFull.includes('hibrido')) {
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
                                        if (termosGringos.some(t => tituloBaixo.includes(t) || localStrBaixo.includes(t))) {
                                            continue; 
                                        }
                                    }
                                    
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
                                    
                                    enc.push([titulo, link, empresa, localStr, dataStr, formatoStr].join('|||'));
                                } catch(err) { continue; }
                            }
                            return enc;
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
                        print(f"❌ Erro na pág {pagina}: {e}")
                        break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} resultados extraídos do InfoJobs.")
        
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
                    "scraper": "Infojobs"
                })
                
    return resultados