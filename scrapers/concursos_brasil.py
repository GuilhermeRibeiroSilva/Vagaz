import urllib.parse
import json
import random
from playwright.sync_api import sync_playwright
from utils.navegador import iniciar_navegador_blindado

ESTADOS_UF = {
    "acre": "ac", "alagoas": "al", "amapá": "ap", "amazonas": "am",
    "bahia": "ba", "ceará": "ce", "distrito federal": "df",
    "espírito santo": "es", "goiás": "go", "maranhão": "ma",
    "mato grosso": "mt", "mato grosso do sul": "ms", "minas gerais": "mg",
    "pará": "pa", "paraíba": "pb", "paraná": "pr", "pernambuco": "pe",
    "piauí": "pi", "rio de janeiro": "rj", "rio grande do norte": "rn",
    "rio grande do sul": "rs", "rondônia": "ro", "roraima": "rr",
    "santa catarina": "sc", "são paulo": "sp", "sergipe": "se",
    "tocantins": "to",
    "rio branco": "ac", "maceió": "al", "macapá": "ap", "manaus": "am",
    "salvador": "ba", "fortaleza": "ce", "brasília": "df", "vitória": "es",
    "goiânia": "go", "são luís": "ma", "cuiabá": "mt", "campo grande": "ms",
    "belo horizonte": "mg", "belém": "pa", "joão pessoa": "pb", "curitiba": "pr",
    "recife": "pe", "teresina": "pi", "natal": "rn", "porto alegre": "rs",
    "porto velho": "ro", "boa vista": "rr", "florianópolis": "sc",
    "aracaju": "se", "palmas": "to"
}

def buscar_concursos_brasil(termo: str, local: str = "", palavras_proibidas: str = "", max_paginas: int = 4, headless: bool = True):
    resultados = []
    lista_termos = [t.strip().lower() for t in termo.split(',') if t.strip()]
    lista_proibidas = [p.strip().lower() for p in palavras_proibidas.split(',') if p.strip()]
    lista_locais = [l.strip().lower() for l in local.split(',') if l.strip()]
    
    if not lista_termos:
        return resultados

    if not lista_locais:
        lista_locais = ["brasil"]

    links_capturados = set()
    vagas_brutas_totais = set()

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)
        
        try:
            for local_alvo in lista_locais:
                print(f"\n🌍 [Concursos Brasil] Processando local: '{local_alvo}'")
                
                uf_alvo = ESTADOS_UF.get(local_alvo)
                usar_tabela_direta = False
                url_tabela = ""
                local_padrao = local_alvo.title()
                
                if uf_alvo:
                    usar_tabela_direta = True
                    url_tabela = f"https://concursosnobrasil.com/concursos/{uf_alvo}/"
                elif local_alvo in ["brasil", "nacional", "federal", "remoto (brasil)", "remoto (internacional)"]:
                    usar_tabela_direta = True
                    url_tabela = "https://concursosnobrasil.com/concursos/br/"
                    local_padrao = "Nacional" if "remoto" not in local_alvo else "Remoto"

                if usar_tabela_direta:
                    print(f"🤖 [Concursos Brasil] Modo Tabela Ativado. Acessando: {url_tabela}")
                    try:
                        page.goto(url_tabela, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(random.randint(2000, 3000))
                        
                        js_tabela = r"""
                        (async function() {
                            var enc = [];
                            var linhas = document.querySelectorAll('table tbody tr');
                            var termosAlvo = REPLACE_TERMOS;
                            var proibidas = REPLACE_PROIBIDAS;
                            
                            var promises = Array.from(linhas).map(async (linha) => {
                                try {
                                    var aTag = linha.querySelector('a');
                                    if(!aTag) return null;
                                    
                                    var titulo = aTag.innerText.trim();
                                    var tituloLower = titulo.toLowerCase();
                                    
                                    if (termosAlvo.length > 0) {
                                        var match = termosAlvo.some(t => tituloLower.includes(t));
                                        if (!match) return null;
                                    }
                                    
                                    if (proibidas.length > 0) {
                                        var temProibida = proibidas.some(p => tituloLower.includes(p));
                                        if (temProibida) return null;
                                    }
                                    
                                    var href = aTag.getAttribute('href') || '';
                                    if (href.startsWith('/')) href = 'https://concursosnobrasil.com' + href;
                                    
                                    var empresa = titulo.split('-')[0].trim();
                                    if(empresa.length > 35) empresa = "Órgão Público";
                                    
                                    var vagasTag = linha.querySelector('td.center');
                                    var vagas = vagasTag ? vagasTag.innerText.trim() : "N/A";
                                    var previsto = linha.querySelector('.label-previsto') ? " [PREVISTO]" : "";
                                    
                                    var tituloCompleto = titulo + previsto + " (" + vagas + " vagas)";
                                    var dataStr = "Edital Ativo"; 
                                    
                                    try {
                                        var resp = await fetch(href, { signal: AbortSignal.timeout(4000) });
                                        var html = await resp.text();
                                        var matchTime = html.match(/<time[^>]*>.*?(\d{2}\/\d{2}\/\d{4})/i);
                                        if (matchTime) {
                                            dataStr = matchTime[1];
                                        } else {
                                            var altMatch = html.match(/(\d{2}\/\d{2}\/\d{4})/);
                                            if (altMatch) dataStr = altMatch[1];
                                        }
                                    } catch(e) {}
                                    
                                    return [tituloCompleto, href, empresa, 'LOCAL_AQUI', dataStr].join('|||');
                                } catch(err) { return null; }
                            });
                            
                            var results = await Promise.all(promises);
                            return results.filter(r => r !== null);
                        })();
                        """
                        js_final = js_tabela.replace('REPLACE_TERMOS', json.dumps(lista_termos)).replace('REPLACE_PROIBIDAS', json.dumps(lista_proibidas)).replace('LOCAL_AQUI', local_padrao)
                        vagas_extraidas = page.evaluate(js_final)
                        
                        if vagas_extraidas:
                            for vaga in vagas_extraidas:
                                link = vaga.split('|||')[1]
                                if link not in links_capturados:
                                    links_capturados.add(link)
                                    vagas_brutas_totais.add(vaga)
                            print(f"✅ [Concursos Brasil] Editais validados na tabela.")
                    except Exception as e:
                        print(f"❌ Erro na tabela C_Brasil: {e}")

                else:
                    termo_query = " OR ".join([f'"{t}"' for t in lista_termos])
                    if local_alvo not in ["brasil", "remoto (brasil)", "remoto (internacional)"]:
                        termo_query += f" {local_alvo}"
                    termo_formatado = urllib.parse.quote(termo_query)

                    for pagina in range(1, max_paginas + 1):
                        url = f"https://concursosnobrasil.com/busca/?q={termo_formatado}#gsc.tab=0&gsc.q={termo_formatado}&gsc.page={pagina}"
                        print(f"🤖 [Concursos Brasil - Pág {pagina}] Buscando via CSE: {url}")
                        
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=45000)
                            page.wait_for_timeout(random.randint(3000, 5000))
                            
                            for _ in range(3):
                                page.mouse.wheel(0, 600)
                                page.wait_for_timeout(800)
                                
                            js_cse = r"""
                            (async function() {
                                var enc = [];
                                var resultados = document.querySelectorAll('.gsc-webResult.gsc-result');
                                var termosAlvo = REPLACE_TERMOS;
                                var proibidas = REPLACE_PROIBIDAS;
                                
                                var promises = Array.from(resultados).map(async (el) => {
                                    try {
                                        var aTag = el.querySelector('a.gs-title');
                                        if (!aTag) return null;
                                        
                                        var tituloLimpo = aTag.innerText.trim();
                                        var tituloLower = tituloLimpo.toLowerCase();
                                        var href = aTag.getAttribute('data-ctorig') || aTag.getAttribute('href') || '';
                                        if(!href) return null;

                                        if (href.includes('/artigo/') || href.includes('/cargos/')) return null;
                                        if (!href.includes('/concursos/')) return null; 
                                        
                                        if (termosAlvo.length > 0) {
                                            var match = termosAlvo.some(t => tituloLower.includes(t));
                                            if (!match) return null;
                                        }
                                        
                                        if (proibidas.length > 0) {
                                            var temProibida = proibidas.some(p => tituloLower.includes(p));
                                            if (temProibida) return null;
                                        }
                                        
                                        var empresa = tituloLimpo.split('-')[0].trim();
                                        if(empresa.length > 35) empresa = "Órgão Público";
                                        
                                        var snippetTag = el.querySelector('.gs-snippet');
                                        var detalhesStr = snippetTag ? snippetTag.innerText.trim() : '';
                                        
                                        var dataStr = 'Recente';
                                        var matchData = detalhesStr.match(/^\d{2}\/\d{2}\/\d{4}/);
                                        if (matchData) {
                                            dataStr = matchData[0];
                                        }
                                        
                                        try {
                                            var resp = await fetch(href, { signal: AbortSignal.timeout(4000) });
                                            var html = await resp.text();
                                            var matchTime = html.match(/<time[^>]*>.*?(\d{2}\/\d{2}\/\d{4})/i);
                                            if (matchTime) {
                                                dataStr = matchTime[1];
                                            }
                                        } catch(e) {}
                                        
                                        return [tituloLimpo, href, empresa, 'LOCAL_AQUI', dataStr].join('|||');
                                    } catch(err) { return null; }
                                });
                                
                                var results = await Promise.all(promises);
                                return results.filter(r => r !== null);
                            })();
                            """
                            js_cse_final = js_cse.replace('REPLACE_TERMOS', json.dumps(lista_termos)).replace('REPLACE_PROIBIDAS', json.dumps(lista_proibidas)).replace('LOCAL_AQUI', local_padrao)
                            vagas_desta_pagina = page.evaluate(js_cse_final)
                            
                            if not vagas_desta_pagina:
                                break
                                
                            novas_vagas = 0
                            for vaga_str in vagas_desta_pagina:
                                link = vaga_str.split('|||')[1]
                                if link not in links_capturados:
                                    links_capturados.add(link)
                                    vagas_brutas_totais.add(vaga_str)
                                    novas_vagas += 1
                                    
                            if novas_vagas == 0:
                                break
                        except Exception as e:
                            print(f"❌ Erro na pág {pagina} do CSE: {e}")
                            break

        except Exception as e_mestre:
            print(f"❌ Erro crítico no motor: {e_mestre}")
        finally:
            page.close()
            browser.close()
        
        print(f"📊 RELATÓRIO C_BRASIL: {len(vagas_brutas_totais)} resultados extraídos.")
        
        for vaga_str in vagas_brutas_totais:
            partes = vaga_str.split('|||')
            if len(partes) >= 5:
                resultados.append({
                    "titulo": partes[0],
                    "link": partes[1],
                    "empresa": partes[2],
                    "local": partes[3],
                    "data": partes[4],
                    "scraper": "Concursos no Brasil"
                })
                
    return resultados