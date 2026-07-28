import urllib.parse
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from navegador import iniciar_navegador_blindado

def buscar_concursos_folha(termo: str, max_paginas: int = 3, headless: bool = True):
    resultados = []
    termo_limpo = termo.lower().strip()
    termo_formatado = urllib.parse.quote(termo_limpo)
    
    # Roteador Inteligente: Mapeia estados e regiões para os links diretos da Folha
    mapa_rotas = {
        "ba": "https://folha.qconcursos.com/e/concursos-bahia-ba",
        "bahia": "https://folha.qconcursos.com/e/concursos-bahia-ba",
        "nordeste": "https://folha.qconcursos.com/e/concursos-nordeste",
        "br": "https://folha.qconcursos.com/e/concursos-federais",
        "brasil": "https://folha.qconcursos.com/e/concursos-federais",
        "nacional": "https://folha.qconcursos.com/e/concursos-federais",
        "federal": "https://folha.qconcursos.com/e/concursos-federais"
    }
    
    # Se o termo estiver no mapa, usa o link direto. Se não, usa o motor de busca.
    if termo_limpo in mapa_rotas:
        url_base = mapa_rotas[termo_limpo]
        local_padrao = termo_limpo.capitalize()
    else:
        url_base = f"https://folha.qconcursos.com/busca?q={termo_formatado}"
        local_padrao = "Nacional/Busca"

    vagas_brutas_totais = set()
    links_capturados = set()

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        for pagina in range(1, max_paginas + 1):
            # Lógica de paginação flexível: usa "&" se for busca, "?" se for página de estado
            separador = "&" if "?" in url_base else "?"
            url = url_base if pagina == 1 else f"{url_base}{separador}page={pagina}"
            
            print(f"🤖 [Folha/QC - Pág {pagina}] Acessando: {url}")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(3000) # Respiro vital para o React renderizar os cards
                
                # Desce a página em degraus para ativar o "Lazy Load" dos cards
                for _ in range(4):
                    page.evaluate("window.scrollBy(0, 600);")
                    page.wait_for_timeout(800)
                    
                js_extrator = r"""
                (function() {
                    var enc = [];
                    var cards = document.querySelectorAll('article');
                    
                    for (var i = 0; i < cards.length; i++) {
                        try {
                            var el = cards[i];
                            
                            // Garante que o link aponte para uma notícia de fato (/n/)
                            var aTag = el.querySelector('a[href*="/n/"]');
                            if(!aTag) continue;
                            
                            var link = aTag.getAttribute('href');
                            if (link && link.startsWith('/')) link = 'https://folha.qconcursos.com' + link;
                            
                            var h3 = el.querySelector('h3');
                            var titulo = h3 ? h3.innerText.trim() : '';
                            if (titulo.length < 5) continue;
                            
                            // Em concursos, a empresa costuma ser a primeira parte do título da notícia (Ex: "Concurso IBGE")
                            var empresa = titulo.split('-')[0].trim();
                            if(empresa.length > 40) empresa = "Órgão Público";
                            
                            // Caçador de Datas (Procura o padrão 00/00/0000 nos spans)
                            var spans = el.querySelectorAll('span');
                            var dataStr = 'Recente';
                            for(var s = 0; s < spans.length; s++) {
                                var txt = spans[s].innerText.trim();
                                var matchData = txt.match(/\d{2}\/\d{2}\/\d{4}/);
                                if(matchData) {
                                    dataStr = matchData[0]; // Pega a data limpa
                                    break;
                                }
                            }
                            
                            var formatoStr = "Presencial";
                            
                            enc.push([titulo, link, empresa, 'LOCAL_AQUI', dataStr, formatoStr].join('|||'));
                        } catch(err) { continue; }
                    }
                    return enc;
                })();
                """
                
                # Substitui a marcação "LOCAL_AQUI" pelo local que detectamos no Roteador
                js_final = js_extrator.replace('LOCAL_AQUI', local_padrao)
                
                vagas_desta_pagina = page.evaluate(js_final)
                
                if not vagas_desta_pagina:
                    print(f"⚠️ [Folha/QC] Sem resultados na pág {pagina}. Encerrando busca.")
                    break
                    
                novas_vagas = 0
                for vaga_str in vagas_desta_pagina:
                    link_vaga = vaga_str.split('|||')[1]
                    if link_vaga not in links_capturados:
                        links_capturados.add(link_vaga)
                        vagas_brutas_totais.add(vaga_str)
                        novas_vagas += 1
                
                if novas_vagas == 0:
                    print(f"🛑 [Folha/QC] O site começou a repetir os cards na pág {pagina}. Fim da linha.")
                    break
                    
                print(f"✅ [Folha/QC] {novas_vagas} notícias de editais mapeadas na pág {pagina}.")

            except Exception as e:
                print(f"❌ Erro na extração da pág {pagina}: {e}")
                break
        
        browser.close()
        
        print(f"📊 RELATÓRIO FOLHA_QC: {len(vagas_brutas_totais)} resultados extraídos.")
        
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