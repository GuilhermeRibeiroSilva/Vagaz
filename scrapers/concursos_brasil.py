import urllib.parse
import unicodedata
import random
from playwright.sync_api import sync_playwright
# O Stealth foi removido daqui pois o motor central já gerencia a blindagem
from navegador import iniciar_navegador_blindado

def buscar_concursos_brasil(termo: str, max_paginas: int = 4, headless: bool = True):
    resultados = []
    termo_limpo = termo.lower().strip()
    termo_formatado = urllib.parse.quote(termo_limpo)
    
    links_capturados = set()
    vagas_brutas_totais = set()

    # MOTOR INTELIGENTE: Decide se vai ler as Tabelas ou varrer o Google CSE
    usar_tabela_direta = False
    url_tabela = ""
    local_padrao = "Brasil"
    
    if termo_limpo in ["ba", "bahia", "salvador"]:
        usar_tabela_direta = True
        url_tabela = "https://concursosnobrasil.com/concursos/ba/"
        local_padrao = "Bahia"
    elif termo_limpo in ["br", "brasil", "nacional", "federal"]:
        usar_tabela_direta = True
        url_tabela = "https://concursosnobrasil.com/concursos/br/"
        local_padrao = "Nacional"

    with sync_playwright() as p:
        browser, page = iniciar_navegador_blindado(p, headless=headless)

        # ==========================================
        # ROTA 1: TABELAS DIRETAS (Com Fetch Invisível de Datas)
        # ==========================================
        if usar_tabela_direta:
            print(f"🤖 [Concursos Brasil] Modo Tabela Ativado. Acessando: {url_tabela}")
            try:
                page.goto(url_tabela, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(random.randint(2000, 3000))
                
                js_tabela = r"""
                (async function() {
                    var enc = [];
                    var linhas = document.querySelectorAll('table tbody tr');
                    
                    var promises = Array.from(linhas).map(async (linha) => {
                        try {
                            var aTag = linha.querySelector('a');
                            if(!aTag) return null;
                            
                            var titulo = aTag.innerText.trim();
                            var href = aTag.getAttribute('href') || '';
                            if (href.startsWith('/')) href = 'https://concursosnobrasil.com' + href;
                            
                            var empresa = titulo.split('-')[0].trim();
                            if(empresa.length > 35) empresa = "Órgão Público";
                            
                            var vagasTag = linha.querySelector('td.center');
                            var vagas = vagasTag ? vagasTag.innerText.trim() : "N/A";
                            var previsto = linha.querySelector('.label-previsto') ? " [PREVISTO]" : "";
                            
                            var tituloCompleto = titulo + previsto + " (" + vagas + " vagas)";
                            var dataStr = "Edital Ativo"; 
                            
                            // O GOLPE DE MESTRE: FETCH INVISÍVEL PARA PEGAR A TAG <time>
                            try {
                                var resp = await fetch(href, { signal: AbortSignal.timeout(4000) });
                                var html = await resp.text();
                                
                                // Caça o "27/07/2026" dentro da tag <time> mapeada pelo usuário
                                var matchTime = html.match(/<time[^>]*>.*?(\d{2}\/\d{2}\/\d{4})/i);
                                if (matchTime) {
                                    dataStr = matchTime[1];
                                } else {
                                    // Fallback: Caça qualquer data DD/MM/YYYY no artigo
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
                
                js_final = js_tabela.replace('LOCAL_AQUI', local_padrao)
                vagas_extraidas = page.evaluate(js_final)
                
                for vaga in vagas_extraidas:
                    vagas_brutas_totais.add(vaga)
                    
                print(f"✅ [Concursos Brasil] {len(vagas_brutas_totais)} editais extraídos da tabela.")
            except Exception as e:
                print(f"❌ Erro na tabela C_Brasil: {e}")

        # ==========================================
        # ROTA 2: MOTOR DE BUSCA (Google CSE com Fetch Invisível)
        # ==========================================
        else:
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
                        
                        var promises = Array.from(resultados).map(async (el) => {
                            try {
                                var aTag = el.querySelector('a.gs-title');
                                if (!aTag) return null;
                                
                                var tituloLimpo = aTag.innerText.trim();
                                var href = aTag.getAttribute('data-ctorig') || aTag.getAttribute('href') || '';
                                
                                if(!href) return null;

                                // FILTRO DE LIXO: Ignora blogs e foca só em concursos
                                if (href.includes('/artigo/') || href.includes('/cargos/')) return null;
                                if (!href.includes('/concursos/')) return null; 
                                
                                var empresa = tituloLimpo.split('-')[0].trim();
                                if(empresa.length > 35) empresa = "Órgão Público";
                                
                                var snippetTag = el.querySelector('.gs-snippet');
                                var detalhesStr = snippetTag ? snippetTag.innerText.trim() : '';
                                
                                var dataStr = 'Recente';
                                var matchData = detalhesStr.match(/^\d{2}\/\d{2}\/\d{4}/);
                                if (matchData) {
                                    dataStr = matchData[0];
                                }
                                
                                // FETCH INVISÍVEL NO CSE TAMBÉM
                                try {
                                    var resp = await fetch(href, { signal: AbortSignal.timeout(4000) });
                                    var html = await resp.text();
                                    var matchTime = html.match(/<time[^>]*>.*?(\d{2}\/\d{2}\/\d{4})/i);
                                    if (matchTime) {
                                        dataStr = matchTime[1];
                                    }
                                } catch(e) {}
                                
                                var localStr = "Brasil";
                                
                                return [tituloLimpo, href, empresa, localStr, dataStr].join('|||');
                            } catch(err) { return null; }
                        });
                        
                        var results = await Promise.all(promises);
                        return results.filter(r => r !== null);
                    })();
                    """
                    
                    vagas_desta_pagina = page.evaluate(js_cse)
                    
                    if not vagas_desta_pagina:
                        print(f"⚠️ [Concursos Brasil] Fim dos resultados relevantes na pág {pagina}.")
                        break
                        
                    novas_vagas = 0
                    for vaga_str in vagas_desta_pagina:
                        link = vaga_str.split('|||')[1]
                        if link not in links_capturados:
                            links_capturados.add(link)
                            vagas_brutas_totais.add(vaga_str)
                            novas_vagas += 1
                            
                    if novas_vagas == 0:
                        print(f"🛑 [Concursos Brasil] Repetição de links na pág {pagina}. Encerrando.")
                        break

                    print(f"✅ [Concursos Brasil] {novas_vagas} concursos mapeados na pág {pagina}.")

                except Exception as e:
                    print(f"❌ Erro na pág {pagina} do CSE: {e}")
                    break
        
        browser.close()
        
        print(f"📊 RELATÓRIO C_BRASIL: {len(vagas_brutas_totais)} resultados extraídos.")
        
        # Converte para a estrutura das 5 chaves do Dicionário de Ouro
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