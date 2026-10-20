import urllib.parse
import unicodedata
import random
import json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth 
from utils.navegador import iniciar_navegador_blindado

def remover_acentos(texto: str):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def buscar_vagas_gupy(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
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
                
                print(f"\n🔍 [Gupy] Iniciando varredura para a tag: '{termo_alvo}'")

                for pagina in range(1, max_paginas + 1):
                    url = f"https://portal.gupy.io/job-search/term={termo_formatado}" if pagina == 1 else f"https://portal.gupy.io/job-search/term={termo_formatado}?page={pagina}"
                    print(f"🤖 [Gupy - Pág {pagina}] Acessando: {url}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(3000)
                        
                        for _ in range(3):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                            page.wait_for_timeout(1500)
                        
                        js_extrator = r"""
                        (function() {
                            var enc = [];
                            var elementos = document.querySelectorAll('li a, a[data-testid="job-list-item"]');
                            if(elementos.length === 0) elementos = document.querySelectorAll('a'); 
                            
                            var proibidas = REPLACE_PROIBIDAS;
                            var locaisAlvo = REPLACE_LOCAIS;
                            var termosGringos = ["eua", "usa", "latam", "global", "worldwide", "abroad", "internacional", "exterior"];
                            
                            for (var i = 0; i < elementos.length; i++) {
                                try {
                                    var el = elementos[i];
                                    var tagTitulo = el.querySelector('h2, h3, h4');
                                    if (!tagTitulo) continue; 
                                    
                                    var tituloLimpo = tagTitulo.innerText.trim();
                                    if (tituloLimpo.length < 5 || tituloLimpo.includes("Gupy")) continue;
                                    
                                    var tituloBaixo = tituloLimpo.toLowerCase();
                                    if (proibidas.length > 0 && proibidas.some(p => tituloBaixo.includes(p))) continue;
                                    
                                    var href = el.getAttribute('href') || "";
                                    if(href.startsWith('/')) href = 'https://portal.gupy.io' + href;
                                    if(!href.includes('gupy.io')) continue; 
                                    
                                    var link = href.split('?')[0]; 
                                    var empresa = "Confidencial";
                                    
                                    try {
                                        var dominio = new URL(link).hostname;
                                        var partesDominio = dominio.split('.');
                                        if (partesDominio.length > 2) {
                                            empresa = partesDominio[0];
                                            empresa = empresa.charAt(0).toUpperCase() + empresa.slice(1);
                                        }
                                    } catch(e) {}
                                    
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
                                        if (termosGringos.some(t => tituloBaixo.includes(t) || localStrBaixo.includes(t))) {
                                            continue; 
                                        }
                                    }
                                    
                                    if (formatoStr === 'Remoto' && localStr === 'Brasil') localStr = 'Qualquer lugar';
                                    
                                    enc.push([tituloLimpo, link, empresa, localStr, dataStr, formatoStr].join('|||'));
                                } catch(err) { continue; }
                            }
                            return enc;
                        })();
                        """
                        
                        js_final = js_extrator.replace('REPLACE_PROIBIDAS', json.dumps(lista_proibidas)).replace('REPLACE_LOCAIS', json.dumps(lista_locais))
                        vagas_desta_pagina = page.evaluate(js_final)
                        
                        if not vagas_desta_pagina:
                            print(f"⚠️ [Gupy] Fim das vagas para a tag '{termo_alvo}'.")
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
                            
                        print(f"✅ [Gupy] {novas_vagas} vagas capturadas na página {pagina}.")

                    except Exception as e:
                        print(f"❌ Erro na página {pagina}: {e}")
                        break
        
        finally:
            page.close()
            browser.close()

    print(f"📊 RELATÓRIO GUPY: {len(vagas_brutas_totais)} vagas extraídas globais.")
    
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
                "scraper": "Gupy"
            })
            
    return resultados