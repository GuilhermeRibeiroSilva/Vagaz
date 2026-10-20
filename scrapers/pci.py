import urllib.parse
import json
from playwright.sync_api import sync_playwright
from utils.navegador import iniciar_navegador_blindado

ESTADOS_PCI = {
    "acre": ("norte", "AC"), "alagoas": ("nordeste", "AL"), "amapá": ("norte", "AP"),
    "amazonas": ("norte", "AM"), "bahia": ("nordeste", "BA"), "ceará": ("nordeste", "CE"),
    "distrito federal": ("centrooeste", "DF"), "espírito santo": ("sudeste", "ES"),
    "goiás": ("centrooeste", "GO"), "maranhão": ("nordeste", "MA"),
    "mato grosso": ("centrooeste", "MT"), "mato grosso do sul": ("centrooeste", "MS"),
    "minas gerais": ("sudeste", "MG"), "pará": ("norte", "PA"), "paraíba": ("nordeste", "PB"),
    "paraná": ("sul", "PR"), "pernambuco": ("nordeste", "PE"), "piauí": ("nordeste", "PI"),
    "rio de janeiro": ("sudeste", "RJ"), "rio grande do norte": ("nordeste", "RN"),
    "rio grande do sul": ("sul", "RS"), "rondônia": ("norte", "RO"), "roraima": ("norte", "RR"),
    "santa catarina": ("sul", "SC"), "são paulo": ("sudeste", "SP"), "sergipe": ("nordeste", "SE"),
    "tocantins": ("norte", "TO")
}

def buscar_concursos_pci(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    
    lista_termos = [t.strip().lower() for t in termo.split(',') if t.strip()]
    if not lista_termos:
        return resultados

    lista_proibidas = [p.strip().lower() for p in palavras_proibidas.split(',') if p.strip()]
    lista_locais = [l.strip().lower() for l in local.split(',') if l.strip()]
    
    if not lista_locais:
        lista_locais = ["brasil"]
    
    links_capturados = set()
    vagas_brutas_totais = set()
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        try:
            for local_alvo in lista_locais:
                print(f"\n🌍 [PCI Concursos] Processando rota para: '{local_alvo}'")
                
                url_base = ""
                sigla_alvo = ""
                is_categoria = False
                
                if local_alvo in ['nacional', 'brasil', 'remoto (brasil)', 'remoto (internacional)']:
                    url_base = "https://www.pciconcursos.com.br/concursos/nacional/"
                    is_categoria = True
                else:
                    for estado, (regiao, sigla) in ESTADOS_PCI.items():
                        if estado in local_alvo:
                            url_base = f"https://www.pciconcursos.com.br/concursos/{regiao}/#{sigla}"
                            sigla_alvo = sigla
                            is_categoria = True
                            break
                    
                    if not url_base:
                        query = urllib.parse.quote(" ".join(lista_termos))
                        url_base = f"https://www.pciconcursos.com.br/pesquisa/{query}"

                paginas_a_buscar = 1 if is_categoria else max_paginas
                
                for pagina in range(1, paginas_a_buscar + 1):
                    url = url_base if is_categoria or pagina == 1 else f"{url_base}/{pagina}"
                    print(f"🤖 [PCI Concursos - Pág {pagina}] Acessando: {url}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        page.evaluate("window.stop();")
                        page.wait_for_timeout(1000)
                        
                        for _ in range(2):
                            page.evaluate("window.scrollBy(0, 800);")
                            page.wait_for_timeout(500)
                        
                        js_extrator = r"""
                        (async function() {
                            var siglaAlvo = "__SIGLA_ALVO__";
                            var termosAlvo = REPLACE_TERMOS;
                            var proibidas = REPLACE_PROIBIDAS;
                            var cards = document.querySelectorAll('div.ca, div.na');
                            
                            var promises = Array.from(cards).map(async (el) => {
                                try {
                                    var aTag = el.querySelector('a');
                                    if (!aTag) return null;
                                    
                                    var localTag = el.querySelector('div.cc');
                                    var localStr = localTag ? localTag.innerText.trim() : 'Brasil';
                                    
                                    if (siglaAlvo !== "" && localStr.toUpperCase() !== siglaAlvo) {
                                        return null;
                                    }
                                    
                                    var orgao = aTag.innerText.trim(); 
                                    var descricao = aTag.getAttribute('title') || ''; 
                                    if (orgao.length < 2) return null;
                                    
                                    var tituloCompleto = descricao ? descricao : orgao;
                                    if (descricao && !tituloCompleto.toLowerCase().includes(orgao.toLowerCase())) {
                                        tituloCompleto = orgao + " - " + descricao;
                                    }
                                    
                                    var tituloLower = tituloCompleto.toLowerCase();
                                    
                                    if (termosAlvo.length > 0) {
                                        var match = termosAlvo.some(t => tituloLower.includes(t));
                                        if (!match) return null;
                                    }
                                    if (proibidas.length > 0 && proibidas.some(p => tituloLower.includes(p))) return null;

                                    var empresa = orgao;
                                    if (empresa.length > 40) empresa = empresa.substring(0, 37) + "...";

                                    var href = aTag.getAttribute('href') || '';
                                    if (href && href.startsWith('/')) href = 'https://www.pciconcursos.com.br' + href;

                                    var dataTag = el.querySelector('div.ce');
                                    var prazoStr = dataTag ? dataTag.innerText.trim() : '';
                                    var isExpired = false;

                                    if (prazoStr) {
                                        var m = prazoStr.match(/(\d{2})\/(\d{2})\/(\d{4})/);
                                        var today = new Date();
                                        today.setHours(0,0,0,0);
                                        
                                        if (m) {
                                            var dDate = new Date(m[3], m[2]-1, m[1]);
                                            if (dDate < today) isExpired = true;
                                        } else {
                                            var m2 = prazoStr.match(/(\d{2})\/(\d{2})/);
                                            if (m2) {
                                                var dDate2 = new Date(today.getFullYear(), m2[2]-1, m2[1]);
                                                if (dDate2 < today && (today.getMonth() - dDate2.getMonth() > 2)) {
                                                    isExpired = true;
                                                }
                                            }
                                        }
                                    }

                                    if (isExpired) return null; 
                                    if (prazoStr) tituloCompleto = tituloCompleto + " [Prazo: " + prazoStr + "]";

                                    var dataPublicacao = 'Recente';
                                    try {
                                        var resp = await fetch(href, { signal: AbortSignal.timeout(4000) });
                                        var html = await resp.text();
                                        
                                        var matchAbbr = html.match(/<abbr[^>]*class=["']published["'][^>]*>([^<]+)<\/abbr>/i);
                                        if (matchAbbr) {
                                            var dataExtensa = matchAbbr[1].toLowerCase();
                                            var meses = {"janeiro":"01","fevereiro":"02","março":"03","abril":"04","maio":"05","junho":"06","julho":"07","agosto":"08","setembro":"09","outubro":"10","novembro":"11","dezembro":"12"};
                                            
                                            for (var mes in meses) {
                                                if (dataExtensa.includes(mes)) {
                                                    var diaMatch = dataExtensa.match(/(\d{1,2})\s+de/);
                                                    var anoMatch = dataExtensa.match(/20\d{2}/);
                                                    if (diaMatch && anoMatch) {
                                                        var dia = diaMatch[1].padStart(2, '0');
                                                        dataPublicacao = dia + "/" + meses[mes] + "/" + anoMatch[0];
                                                    }
                                                    break;
                                                }
                                            }
                                        }
                                    } catch(e) {} 

                                    var formatoStr = "Presencial";
                                    return [tituloCompleto, href, empresa, localStr, dataPublicacao, formatoStr].join('|||');
                                } catch(err) { return null; }
                            });
                            
                            var results = await Promise.all(promises);
                            return results.filter(r => r !== null);
                        })();
                        """
                        
                        js_final = js_extrator.replace('__SIGLA_ALVO__', sigla_alvo).replace('REPLACE_TERMOS', json.dumps(lista_termos)).replace('REPLACE_PROIBIDAS', json.dumps(lista_proibidas))
                        vagas_desta_pagina = page.evaluate(js_final)
                        
                        if not vagas_desta_pagina:
                            break
                        
                        novos_concursos = 0
                        for vaga_str in vagas_desta_pagina:
                            link_da_vaga = vaga_str.split('|||')[1]
                            
                            if link_da_vaga not in links_capturados:
                                links_capturados.add(link_da_vaga)
                                vagas_brutas_totais.add(vaga_str)
                                novos_concursos += 1
                        
                        if novos_concursos == 0:
                            break

                    except Exception as e:
                        print(f"❌ Erro na pág {pagina}: {e}")
                        break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} concursos extraídos do PCI.")
        
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
                    "scraper": "PCI Concursos"
                })
                
    return resultados