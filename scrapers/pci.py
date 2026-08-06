import urllib.parse
from playwright.sync_api import sync_playwright
from navegador import iniciar_navegador_blindado

# O "CÉREBRO GEOGRÁFICO" DO SCRAPER
MAPA_ESTADOS = {
    'ac': 'norte', 'acre': 'norte',
    'al': 'nordeste', 'alagoas': 'nordeste',
    'am': 'norte', 'amazonas': 'norte',
    'ap': 'norte', 'amapa': 'norte', 'amapá': 'norte',
    'ba': 'nordeste', 'bahia': 'nordeste',
    'ce': 'nordeste', 'ceara': 'nordeste', 'ceará': 'nordeste',
    'df': 'centrooeste', 'distrito federal': 'centrooeste',
    'es': 'sudeste', 'espirito santo': 'sudeste', 'espírito santo': 'sudeste',
    'go': 'centrooeste', 'goias': 'centrooeste', 'goiás': 'centrooeste',
    'ma': 'nordeste', 'maranhao': 'nordeste', 'maranhão': 'nordeste',
    'mg': 'sudeste', 'minas gerais': 'sudeste',
    'ms': 'centrooeste', 'mato grosso do sul': 'centrooeste',
    'mt': 'centrooeste', 'mato grosso': 'centrooeste',
    'pa': 'norte', 'para': 'norte', 'pará': 'norte',
    'pb': 'nordeste', 'paraiba': 'nordeste', 'paraíba': 'nordeste',
    'pe': 'nordeste', 'pernambuco': 'nordeste',
    'pi': 'nordeste', 'piaui': 'nordeste', 'piauí': 'nordeste',
    'pr': 'sul', 'parana': 'sul', 'paraná': 'sul',
    'rj': 'sudeste', 'rio de janeiro': 'sudeste',
    'rn': 'nordeste', 'rio grande do norte': 'nordeste',
    'ro': 'norte', 'rondonia': 'norte', 'rondônia': 'norte',
    'rr': 'norte', 'roraima': 'norte',
    'rs': 'sul', 'rio grande do sul': 'sul',
    'sc': 'sul', 'santa catarina': 'sul',
    'se': 'nordeste', 'sergipe': 'nordeste',
    'sp': 'sudeste', 'sao paulo': 'sudeste', 'são paulo': 'sudeste',
    'to': 'norte', 'tocantins': 'norte'
}

SIGLAS = {
    'acre': 'ac', 'alagoas': 'al', 'amazonas': 'am', 'amapa': 'ap', 'amapá': 'ap',
    'bahia': 'ba', 'ceara': 'ce', 'ceará': 'ce', 'distrito federal': 'df',
    'espirito santo': 'es', 'espírito santo': 'es', 'goias': 'go', 'goiás': 'go',
    'maranhao': 'ma', 'maranhão': 'ma', 'minas gerais': 'mg', 'mato grosso do sul': 'ms',
    'mato grosso': 'mt', 'para': 'pa', 'pará': 'pa', 'paraiba': 'pb', 'paraíba': 'pb',
    'pernambuco': 'pe', 'piaui': 'pi', 'piauí': 'pi', 'parana': 'pr', 'paraná': 'pr',
    'rio de janeiro': 'rj', 'rio grande do norte': 'rn', 'rondonia': 'ro', 'rondônia': 'ro',
    'roraima': 'rr', 'rio grande do sul': 'rs', 'santa catarina': 'sc', 'sergipe': 'se',
    'sao paulo': 'sp', 'são paulo': 'sp', 'tocantins': 'to'
}

def buscar_concursos_pci(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    termo_limpo = termo.lower().strip()
    termo_formatado = urllib.parse.quote(termo_limpo)
    
    links_capturados = set()
    vagas_brutas_totais = set()
    
    # 1. ROTEAMENTO DE URL
    url_base = ""
    is_categoria = False
    sigla_alvo = ""
    
    if termo_limpo in ['nacional', 'brasil']:
        url_base = "https://www.pciconcursos.com.br/concursos/nacional/"
        is_categoria = True
    elif termo_limpo in MAPA_ESTADOS:
        regiao = MAPA_ESTADOS[termo_limpo]
        sigla_alvo = SIGLAS.get(termo_limpo, termo_limpo).upper()
        # Formato exato que você pediu (Ex: /concursos/nordeste/#BA)
        url_base = f"https://www.pciconcursos.com.br/concursos/{regiao}/#{sigla_alvo}"
        is_categoria = True
    else:
        # Se for um cargo (ex: "professor"), mantém a pesquisa normal
        url_base = f"https://www.pciconcursos.com.br/pesquisa/{termo_formatado}"
    
    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        # Se for uma região ou nacional, não existe paginação. Tudo fica na página 1.
        paginas_a_buscar = 1 if is_categoria else max_paginas
        
        try:
            for pagina in range(1, paginas_a_buscar + 1):
                if is_categoria:
                    url = url_base
                else:
                    url = url_base if pagina == 1 else f"{url_base}/{pagina}"
                
                print(f"🤖 [PCI Concursos - Pág {pagina}] Acessando: {url}")
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    page.evaluate("window.stop();") # Trava anúncios chatos
                    page.wait_for_timeout(1000)
                    
                    for _ in range(2):
                        page.evaluate("window.scrollBy(0, 800);")
                        page.wait_for_timeout(500)
                    
                    # O CÓDIGO JAVASCRIPT AGORA RECEBE A "SIGLA ALVO" DO PYTHON
                    js_extrator = r"""
                    (async function() {
                        var siglaAlvo = "__SIGLA_ALVO__";
                        var cards = document.querySelectorAll('div.ca, div.na');
                        
                        var promises = Array.from(cards).map(async (el) => {
                            try {
                                var aTag = el.querySelector('a');
                                if (!aTag) return null;
                                
                                var localTag = el.querySelector('div.cc');
                                var localStr = localTag ? localTag.innerText.trim() : 'Brasil';
                                
                                // SE FOR BUSCA POR ESTADO, IGNORA OS OUTROS ESTADOS DA MESMA REGIÃO
                                if (siglaAlvo !== "" && localStr.toUpperCase() !== siglaAlvo) {
                                    return null;
                                }
                                
                                var orgao = aTag.innerText.trim(); 
                                var descricao = aTag.getAttribute('title') || ''; 
                                if (orgao.length < 2) return null;
                                
                                var empresa = orgao;
                                if (empresa.length > 40) empresa = empresa.substring(0, 37) + "...";

                                var tituloCompleto = descricao ? descricao : orgao;
                                if (descricao && !tituloCompleto.toLowerCase().includes(orgao.toLowerCase())) {
                                    tituloCompleto = orgao + " - " + descricao;
                                }

                                var href = aTag.getAttribute('href') || '';
                                if (href && href.startsWith('/')) href = 'https://www.pciconcursos.com.br' + href;

                                // LENDO O PRAZO FINAL
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

                                if (prazoStr) {
                                    tituloCompleto = tituloCompleto + " [Prazo: " + prazoStr + "]";
                                }

                                // FETCH INVISÍVEL PARA PEGAR A DATA REAL DA PUBLICAÇÃO
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

                                return [tituloCompleto, href, empresa, localStr, dataPublicacao].join('|||');
                            } catch(err) { return null; }
                        });
                        
                        var results = await Promise.all(promises);
                        return results.filter(r => r !== null);
                    })();
                    """
                    
                    # Injeta a sigla alvo de forma segura no script
                    js_extrator = js_extrator.replace("__SIGLA_ALVO__", sigla_alvo)
                    
                    vagas_desta_pagina = page.evaluate(js_extrator)
                    
                    if not vagas_desta_pagina:
                        print(f"⚠️ [PCI] Nenhum concurso válido encontrado na pág {pagina}.")
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

                    print(f"✅ [PCI] {novos_concursos} editais mapeados na pág {pagina}.")

                except Exception as e:
                    print(f"❌ Erro na pág {pagina}: {e}")
                    break

        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO FINAL: {len(vagas_brutas_totais)} concursos extraídos do PCI.")
        
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "PCI Concursos"
                })
                
    return resultados