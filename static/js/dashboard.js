const scrapersVagas = ["Empregos", "InfoJobs", "Gupy", "LinkedIn", "Remotar"];
const scrapersConcursos = ["PCI Concursos", "Concursos Brasil"];
let filtrosAtuais = [];
let resultadosGlobais = [];
let subAbaAtual = 'radar';
let radarAtivoId = null;
let toastTimeout;

let vagasSelecionadas = new Set();
let paginaAtual = 1;
const ITENS_POR_PAGINA = 30;

let tagsTermos = [];
let tagsProibidas = [];
let tagsLocal = [];

if (localStorage.getItem('theme') === 'dark') document.documentElement.classList.add('dark');

function toggleTheme() {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
}

function showToast(msg, tipo = 'info') {
    const t = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');

    t.className = "fixed top-6 left-1/2 -translate-x-1/2 px-6 py-4 rounded-2xl shadow-2xl text-white font-bold opacity-0 pointer-events-none transform -translate-y-4 z-[100] transition-all flex items-center gap-3 border border-white/20 min-w-[300px] justify-center";

    if (tipo === 'success') {
        t.classList.add('bg-emerald-500');
        icon.className = "fa-solid fa-circle-check text-xl";
    } else if (tipo === 'error') {
        t.classList.add('bg-red-500');
        icon.className = "fa-solid fa-circle-exclamation text-xl";
    } else if (tipo === 'warning') {
        t.classList.add('bg-amber-500');
        icon.className = "fa-solid fa-triangle-exclamation text-xl";
    } else {
        t.classList.add('bg-slate-800', 'dark:bg-brand');
        icon.className = "fa-solid fa-circle-info text-xl";
    }

    document.getElementById('toast-message').innerText = msg;
    t.classList.remove('opacity-0', '-translate-y-4');
    t.classList.add('opacity-100', 'translate-y-0');

    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        t.classList.remove('opacity-100', 'translate-y-0');
        t.classList.add('opacity-0', '-translate-y-4');
    }, 3000);
}

function confirmarAcao(titulo, texto, tipo = 'danger', textConfirm = 'Confirmar') {
    return new Promise((resolve) => {
        const modal = document.getElementById('modal-confirm');
        const content = document.getElementById('modal-confirm-content');
        const iconBg = document.getElementById('confirm-icon-bg');
        const icon = document.getElementById('confirm-icon');
        let btnCancel = document.getElementById('btn-confirm-cancel');
        let btnOk = document.getElementById('btn-confirm-ok');

        document.getElementById('confirm-title').innerText = titulo;
        document.getElementById('confirm-text').innerHTML = texto;
        btnOk.innerText = textConfirm;

        iconBg.className = "w-20 h-20 rounded-full mx-auto flex items-center justify-center mb-6 shadow-lg";
        btnOk.className = "flex-1 text-white font-bold py-3.5 rounded-xl transition-all shadow-lg active:scale-95";

        if (tipo === 'danger') {
            iconBg.classList.add('bg-red-100', 'dark:bg-red-500/20');
            icon.className = "fa-solid fa-trash-can text-4xl text-red-500 dark:text-red-400";
            btnOk.classList.add('bg-red-500', 'hover:bg-red-600', 'shadow-red-500/30');
        } else if (tipo === 'warning') {
            iconBg.classList.add('bg-amber-100', 'dark:bg-amber-500/20');
            icon.className = "fa-solid fa-triangle-exclamation text-4xl text-amber-500 dark:text-amber-400";
            btnOk.classList.add('bg-amber-500', 'hover:bg-amber-600', 'shadow-amber-500/30');
        } else {
            iconBg.classList.add('bg-brand/10');
            icon.className = "fa-solid fa-circle-question text-4xl text-brand";
            btnOk.classList.add('bg-brand', 'hover:bg-brandHover', 'shadow-brand/30');
        }

        modal.classList.remove('opacity-0', 'pointer-events-none');
        content.classList.remove('scale-95');

        const newBtnOk = btnOk.cloneNode(true);
        const newBtnCancel = btnCancel.cloneNode(true);
        btnOk.replaceWith(newBtnOk);
        btnCancel.replaceWith(newBtnCancel);

        const closeAndResolve = (result) => {
            modal.classList.add('opacity-0', 'pointer-events-none');
            content.classList.add('scale-95');
            resolve(result);
        };

        newBtnOk.addEventListener('click', () => closeAndResolve(true));
        newBtnCancel.addEventListener('click', () => closeAndResolve(false));
    });
}

function renderTags(tipo) {
    const container = document.getElementById(tipo === 'termos' ? 'tags-termos' : (tipo === 'proibidas' ? 'tags-proibidas' : 'tags-local'));
    const arr = tipo === 'termos' ? tagsTermos : (tipo === 'proibidas' ? tagsProibidas : tagsLocal);
    
    let bgClass = 'bg-brand/20 text-brandHover dark:text-brand';
    if (tipo === 'proibidas') bgClass = 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400';
    if (tipo === 'local') bgClass = 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300';
    
    container.innerHTML = arr.map((tag, index) => `
        <span class="tag-badge ${bgClass}">${tag} <button type="button" onclick="removeTag('${tipo}',${index})" class="hover:text-slate-900 dark:hover:text-white ml-1 focus:outline-none"><i class="fa-solid fa-xmark"></i></button></span>
    `).join('');
}

function removeTag(tipo, index) {
    if (tipo === 'termos') tagsTermos.splice(index, 1);
    else if (tipo === 'proibidas') tagsProibidas.splice(index, 1);
    else tagsLocal.splice(index, 1);
    renderTags(tipo);
}

function adicionarTagLocal(val) {
    if (val && !tagsLocal.includes(val)) {
        tagsLocal.push(val);
        renderTags('local');
    }
}

function setupTagInput(inputId, tipo) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            const val = input.value.trim().replace(/,/g, '');
            if (val) {
                if (tipo === 'termos' && !tagsTermos.includes(val)) tagsTermos.push(val);
                else if (tipo === 'proibidas' && !tagsProibidas.includes(val)) tagsProibidas.push(val);
                renderTags(tipo);
                input.value = '';
            }
        }
        if (e.key === 'Backspace' && input.value === '') {
            const arr = tipo === 'termos' ? tagsTermos : tagsProibidas;
            if (arr.length > 0) { arr.pop(); renderTags(tipo); }
        }
    });
}
setupTagInput('f-termos-input', 'termos');
setupTagInput('f-proibidas-input', 'proibidas');

async function abrirConfiguracoes() {
    try {
        const res = await fetch('/api/usuario/dados');
        const data = await res.json();
        
        document.getElementById('cfg-nome').value = data.perfil.nome;
        document.getElementById('cfg-email').value = data.perfil.email;
        document.getElementById('cfg-senha').value = '';
        
        document.getElementById('cfg-emails').checked = data.config.receber_emails;
        document.getElementById('cfg-limpeza').value = data.config.ativa ? data.config.dias.toString() : "0";

        document.getElementById('modal-config').classList.remove('opacity-0', 'pointer-events-none');
        document.getElementById('modal-config-content').classList.remove('scale-95');
    } catch (e) { showToast("Erro ao ler dados."); }
}

function fecharConfiguracoes() {
    document.getElementById('modal-config').classList.add('opacity-0', 'pointer-events-none');
    document.getElementById('modal-config-content').classList.add('scale-95');
}

document.getElementById('form-perfil')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        nome: document.getElementById('cfg-nome').value,
        email: document.getElementById('cfg-email').value,
        senha: document.getElementById('cfg-senha').value
    };
    try {
        const res = await fetch('/api/usuario/perfil', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json();
        if(res.ok) { showToast("Perfil atualizado!"); } else { showToast(data.detail); }
    } catch (e) { showToast("Erro ao atualizar perfil."); }
});

document.getElementById('form-config')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const val = parseInt(document.getElementById('cfg-limpeza').value);
    const emails = document.getElementById('cfg-emails').checked;
    try {
        const res = await fetch('/api/usuario/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ativa: val > 0, dias: val > 0 ? val : 30, receber_emails: emails }) });
        showToast((await res.json()).mensagem || "Salvo com sucesso!");
        fecharConfiguracoes();
    } catch (e) { showToast("Erro ao salvar preferências."); }
});

async function modoFerias() {
    const confirmou = await confirmarAcao("Modo Férias", "Isso irá pausar a automação de <b>TODOS</b> os seus rastreadores. Deseja continuar?", "warning", "Pausar Tudo");
    if(confirmou) {
        await fetch('/api/filtros/pausar_todos', { method: 'POST' });
        showToast("Modo Férias Ativado!", "success");
        fecharConfiguracoes();
        carregarFiltros();
    }
}

async function excluirMinhaConta() {
    const confirmou = await confirmarAcao("Aviso Irreversível", "Isso excluirá <b>permanentemente</b> seu perfil, rastreadores e vagas salvas.<br>Tem certeza absoluta?", "danger", "Excluir Conta");
    if(confirmou) {
        const res = await fetch('/api/usuario/conta', { method: 'DELETE' });
        if(res.ok) {
            window.location.href = "/";
        }
    }
}

async function toggleTimerRapido(id) {
    try {
        const res = await fetch(`/api/filtros/${id}/toggle`, { method: 'PATCH' });
        showToast((await res.json()).mensagem); carregarFiltros();
    } catch (error) { showToast("Erro ao alterar automação."); }
}

function changeTab(tab) {
    document.querySelectorAll('.tab-content').forEach(e => e.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.querySelectorAll('nav button').forEach(e => { e.classList.remove('bg-brand/10', 'text-brand', 'font-medium'); e.classList.add('text-slate-500', 'dark:text-slate-400'); });
    const btn = document.getElementById(`nav-${tab}`);
    if(btn) {
        btn.classList.add('bg-brand/10', 'text-brand', 'font-medium'); btn.classList.remove('text-slate-500', 'dark:text-slate-400');
    }
}

function openModal() {
    document.getElementById('f-id').value = '';
    document.getElementById('form-filtro').reset();
    tagsTermos = []; tagsProibidas = []; tagsLocal = [];
    renderTags('termos'); renderTags('proibidas'); renderTags('local');
    document.getElementById('modal-title').innerText = "Criar Novo Rastreador";
    document.getElementById('f-intervalo').value = "1440";
    document.getElementById('f-data-max').value = "30";
    atualizarScrapers();
    document.getElementById('modal-filtro').classList.remove('opacity-0', 'pointer-events-none');
    document.getElementById('modal-content').classList.remove('scale-95');
}

function closeModal() { document.getElementById('modal-filtro').classList.add('opacity-0', 'pointer-events-none'); document.getElementById('modal-content').classList.add('scale-95'); }

function atualizarScrapers(scrapersMarcados = []) {
    const tipo = document.getElementById('f-tipo').value;
    const lista = tipo === 'Vagas' ? scrapersVagas : scrapersConcursos;
    document.getElementById('lista-scrapers').innerHTML = lista.map(s => {
        const isChecked = scrapersMarcados.length > 0 ? scrapersMarcados.includes(s) : true;
        return `
        <label class="flex items-center gap-3 bg-white dark:bg-slate-900 border ${isChecked ? 'border-brand' : 'border-slate-200 dark:border-slate-700'} p-3 rounded-xl cursor-pointer hover:border-brand/50 transition-colors shadow-sm">
            <input type="checkbox" value="${s}" class="form-scrapers w-4 h-4 accent-brand" ${isChecked ? 'checked' : ''} onchange="this.parentElement.classList.toggle('border-brand')">
            <span class="text-sm font-medium dark:text-slate-200 truncate">${s}</span>
        </label>`;
    }).join('');
}

async function carregarFiltros() {
    try {
        const res = await fetch('/api/filtros'); filtrosAtuais = await res.json();
        const grid = document.getElementById('grid-filtros'); grid.innerHTML = '';

        if (!filtrosAtuais || filtrosAtuais.length === 0) {
            grid.innerHTML = `<div class="col-span-full text-center py-20 bg-white dark:bg-darkCard rounded-3xl border border-dashed border-slate-300 dark:border-slate-700 text-slate-500 font-medium">Você não tem nenhum Rastreador configurado.<br>Clique em 'Novo Rastreador' para começar.</div>`;
            return;
        }

        filtrosAtuais.forEach(f => {
            const tagColor = f.tipo_busca === 'Vagas' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' : 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300';
            const listArr = (f.scrapers || "Nenhum").split(',');
            const scrapersLimitados = listArr.slice(0, 3).join(', ') + (listArr.length > 3 ? '...' : '');

            let healthColor = "bg-slate-300 dark:bg-slate-600";
            let ultimaVarreduraTexto = "Nunca rodou";
            if (f.ultima_varredura) {
                healthColor = "bg-brand animate-pulse";
                const dataObj = new Date(f.ultima_varredura);
                ultimaVarreduraTexto = dataObj.toLocaleDateString('pt-BR') + ' ' + dataObj.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            }

            const nomeTratado = f.nome_filtro ? f.nome_filtro : 'Rastreador';
                const locaisLimitados = f.localizacao ? f.localizacao.split(',').slice(0, 2).join(', ') + (f.localizacao.split(',').length > 2 ? '...' : '') : 'Geral';

                grid.innerHTML += `
                <div class="bg-white dark:bg-darkCard rounded-3xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm relative hover:shadow-lg transition-all group flex flex-col h-full">
                    <div class="flex justify-between items-start mb-4">
                        <span class="text-[10px] font-extrabold ${tagColor} px-2.5 py-1 rounded-md uppercase tracking-wide">${f.tipo_busca}</span>
                        <div class="flex items-center gap-2" title="Ligar/Desligar Automação">
                            <span class="text-[10px] font-bold ${f.timer_ativo ? 'text-brand' : 'text-slate-400'} uppercase">${f.timer_ativo ? 'Auto' : 'Parado'}</span>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" class="sr-only peer" ${f.timer_ativo ? 'checked' : ''} onchange="toggleTimerRapido(${f.id})">
                                <div class="w-9 h-5 bg-slate-300 dark:bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-brand"></div>
                            </label>
                        </div>
                    </div>
                    <h3 class="text-xl font-black dark:text-white leading-tight mb-4 pr-10 line-clamp-2" title="${nomeTratado}">${nomeTratado}</h3>
                    <div class="mb-6 text-xs space-y-2 text-slate-500 dark:text-slate-400 font-medium bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
                        <p class="flex items-start gap-2"><i class="fa-solid fa-magnifying-glass text-slate-400 mt-0.5"></i> <span class="line-clamp-1 flex-1">${f.termos || '-'}</span></p>
                        <p class="flex items-start gap-2"><i class="fa-solid fa-location-dot text-slate-400 mt-0.5"></i> <span class="line-clamp-1 flex-1">${locaisLimitados}</span></p>
                        <p class="flex items-start gap-2"><i class="fa-solid fa-robot text-slate-400 mt-0.5"></i> <span class="line-clamp-1 flex-1">${scrapersLimitados}</span></p>
                    </div>
                    <div class="mt-auto pt-4 border-t border-slate-100 dark:border-slate-700/50 flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <div class="w-2 h-2 rounded-full ${healthColor}"></div>
                            <span class="text-[10px] font-semibold text-slate-500">Última execução:<br><strong class="text-slate-700 dark:text-slate-300">${ultimaVarreduraTexto}</strong></span>
                        </div>
                        <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onclick="clonarFiltro(${f.id})" class="text-slate-400 hover:text-indigo-500 bg-slate-50 dark:bg-slate-800 p-2 rounded-lg transition-colors border border-slate-200 dark:border-slate-700" title="Duplicar"><i class="fa-solid fa-copy"></i></button>
                            <button onclick="editarFiltro(${f.id})" class="text-slate-400 hover:text-brand bg-slate-50 dark:bg-slate-800 p-2 rounded-lg transition-colors border border-slate-200 dark:border-slate-700" title="Editar"><i class="fa-solid fa-pen"></i></button>
                            <button onclick="deletarFiltro(${f.id})" class="text-slate-400 hover:text-red-500 bg-slate-50 dark:bg-slate-800 p-2 rounded-lg transition-colors border border-slate-200 dark:border-slate-700" title="Excluir"><i class="fa-solid fa-trash"></i></button>
                        </div>
                    </div>
                    <button onclick="rodarFiltro(${f.id})" class="w-full mt-4 bg-brand text-white font-bold py-3 rounded-xl hover:bg-brandHover transition-colors shadow-md shadow-brand/20 active:scale-[0.98] flex justify-center items-center gap-2">
                        <i class="fa-solid fa-play"></i> Iniciar Varredura
                    </button>
                </div>`;
        });
    } catch (e) { }
}

function editarFiltro(id) {
    const f = filtrosAtuais.find(x => x.id === id); if (!f) return;
    document.getElementById('modal-title').innerText = "Editar Rastreador";
    document.getElementById('f-id').value = f.id;
    document.getElementById('f-tipo').value = f.tipo_busca;
    document.getElementById('f-nome').value = f.nome_filtro;
    document.getElementById('f-data-max').value = f.max_dias || 30;
    document.getElementById('f-intervalo').value = f.intervalo_timer;
    
    tagsTermos = f.termos ? f.termos.split(',').map(s=>s.trim()) : [];
    tagsProibidas = f.palavras_proibidas ? f.palavras_proibidas.split(',').map(s=>s.trim()) : [];
    tagsLocal = f.localizacao ? f.localizacao.split(',').map(s=>s.trim()) : [];
    
    renderTags('termos'); renderTags('proibidas'); renderTags('local');
    atualizarScrapers((f.scrapers || '').split(','));
    document.getElementById('modal-filtro').classList.remove('opacity-0', 'pointer-events-none');
    document.getElementById('modal-content').classList.remove('scale-95');
}

function clonarFiltro(id) {
    const f = filtrosAtuais.find(x => x.id === id); if (!f) return;
    document.getElementById('modal-title').innerText = "Clonar Rastreador";
    document.getElementById('f-id').value = '';
    document.getElementById('f-tipo').value = f.tipo_busca;
    document.getElementById('f-nome').value = f.nome_filtro + " (Cópia)";
    document.getElementById('f-data-max').value = f.max_dias || 30;
    document.getElementById('f-intervalo').value = f.intervalo_timer;
    
    tagsTermos = f.termos ? f.termos.split(',').map(s=>s.trim()) : [];
    tagsProibidas = f.palavras_proibidas ? f.palavras_proibidas.split(',').map(s=>s.trim()) : [];
    tagsLocal = f.localizacao ? f.localizacao.split(',').map(s=>s.trim()) : [];
    
    renderTags('termos'); renderTags('proibidas'); renderTags('local');
    atualizarScrapers((f.scrapers || '').split(','));
    document.getElementById('modal-filtro').classList.remove('opacity-0', 'pointer-events-none');
    document.getElementById('modal-content').classList.remove('scale-95');
}

async function salvarFiltro() {
    let scrapers = [];
    document.querySelectorAll('.form-scrapers:checked').forEach(el => scrapers.push(el.value));
    if (scrapers.length === 0) { alert("Selecione pelo menos um motor de busca!"); return; }
    if (tagsTermos.length === 0) { alert("Você precisa adicionar pelo menos um Termo Alvo!"); return; }
    if (tagsLocal.length === 0) { tagsLocal = ["Brasil"]; }

    const payload = {
        tipo_busca: document.getElementById('f-tipo').value,
        nome_filtro: document.getElementById('f-nome').value,
        termos: tagsTermos.join(','),
        palavras_proibidas: tagsProibidas.join(','),
        localizacao: tagsLocal.join(','),
        formato: "Padrão",
        scrapers: scrapers.join(','),
        max_dias: parseInt(document.getElementById('f-data-max').value),
        timer_ativo: false,
        intervalo_timer: parseInt(document.getElementById('f-intervalo').value)
    };

    const id = document.getElementById('f-id').value;
    const url = id ? `/api/filtros?id=${id}` : '/api/filtros';

    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (res.ok) { closeModal(); showToast("Rastreador salvo!"); carregarFiltros(); }
}

async function deletarFiltro(id) {
    const confirmou = await confirmarAcao("Apagar Rastreador", "Esta ação apagará este rastreador. As vagas já salvas no cofre não serão perdidas.<br>Confirmar?", "danger", "Apagar");
    if (confirmou) {
        await fetch(`/api/filtros/${id}`, { method: 'DELETE' }); 
        showToast("Rastreador apagado.", "success"); 
        carregarFiltros();
    }
}

let controllerVarredura = null; let varreduraEmSegundoPlano = false; let radarAtivoLoop = null; let statusInterval = null;

async function rodarFiltro(id) {
    radarAtivoLoop = id; varreduraEmSegundoPlano = false; controllerVarredura = new AbortController();
    const overlay = document.getElementById('loader-overlay'); const icon = document.getElementById('loader-icon');
    const title = document.getElementById('loader-title'); const text = document.getElementById('loader-text');
    const actions = document.getElementById('loader-actions'); const widget = document.getElementById('widget-segundo-plano');
    const barraProgress = document.getElementById('loader-progress');

    widget.classList.add('hidden'); icon.className = "fa-solid fa-satellite-dish fa-beat-fade text-5xl text-brand mb-4";
    title.innerText = "Iniciando Motor..."; title.className = "text-xl font-black dark:text-white"; 
    text.innerText = "Entrando na fila..."; barraProgress.style.width = "0%";
    actions.classList.remove('hidden'); overlay.classList.remove('hidden'); overlay.classList.add('flex');

    try {
        const res = await fetch(`/api/filtros/${id}/rodar`, { method: 'POST', signal: controllerVarredura.signal });
        if (!res.ok) throw new Error("Erro_Servidor");
    } catch (e) { 
        if (e.name !== 'AbortError') showToast("❌ Erro ao enviar comando.");
        return;
    }

    statusInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/varredura/${id}/status`); 
            const data = await res.json();
            
            if(data.etapa) { 
                text.innerText = data.etapa; 
                document.getElementById('widget-status').innerText = data.etapa; 
            }
            if(data.progresso !== undefined) {
                barraProgress.style.width = data.progresso + "%";
            }

            if (data.etapa && data.etapa.includes('Aguardando')) {
                document.getElementById('widget-segundo-plano').classList.replace('border-brand/50', 'border-yellow-500/50');
                document.querySelector('#widget-segundo-plano i').classList.replace('text-brand', 'text-yellow-500');
            } else {
                document.getElementById('widget-segundo-plano').classList.replace('border-yellow-500/50', 'border-brand/50');
                document.querySelector('#widget-segundo-plano i').classList.replace('text-yellow-500', 'text-brand');
            }

            if (data.progresso === 100 || (data.etapa && data.etapa.includes('Concluído'))) {
                clearInterval(statusInterval);
                barraProgress.style.width = "100%";
                
                if (varreduraEmSegundoPlano) { 
                    widget.classList.add('hidden'); 
                    showToast(`✅ Busca Finalizada!`, `success`); 
                    carregarResultados(); 
                    return; 
                }

                actions.classList.add('hidden'); 
                icon.className = "fa-solid fa-circle-check text-5xl text-brand mb-4";
                title.innerText = "Concluído!"; 
                title.className = "text-xl font-black text-brand"; 
                text.innerText = "Novas vagas adicionadas ao cofre.";
                
                await carregarResultados(); 
                carregarFiltros(); 
                
                setTimeout(() => { 
                    overlay.classList.add('hidden'); 
                    overlay.classList.remove('flex'); 
                    changeTab('resultados'); 
                }, 2500);
            }

        } catch(e) {}
    }, 3500);
}

function ocultarLoaderSegundoPlano() { varreduraEmSegundoPlano = true; document.getElementById('loader-overlay').classList.add('hidden'); document.getElementById('loader-overlay').classList.remove('flex'); document.getElementById('widget-segundo-plano').classList.remove('hidden'); showToast("Rodando em segundo plano."); }
function maximizarLoader() { varreduraEmSegundoPlano = false; document.getElementById('widget-segundo-plano').classList.add('hidden'); document.getElementById('loader-overlay').classList.remove('hidden'); document.getElementById('loader-overlay').classList.add('flex'); }

async function cancelarVarreduraFrontend() { 
    if(radarAtivoLoop) fetch(`/api/varredura/${radarAtivoLoop}/cancelar`, { method: 'POST' }).catch(()=>{}); 
    if (controllerVarredura) controllerVarredura.abort(); 
    if (typeof statusInterval !== 'undefined') clearInterval(statusInterval);
    document.getElementById('widget-segundo-plano').classList.add('hidden'); 
    
    const overlay = document.getElementById('loader-overlay'); 
    const icon = document.getElementById('loader-icon');
    const title = document.getElementById('loader-title'); 
    const text = document.getElementById('loader-text');
    const actions = document.getElementById('loader-actions'); 
    const barraProgress = document.getElementById('loader-progress');
    
    actions.classList.add('hidden'); 
    icon.className = "fa-solid fa-ban text-5xl text-amber-500 mb-4"; 
    title.innerText = "Operação Abortada"; 
    title.className = "text-xl font-black text-amber-500"; 
    text.innerText = "A busca foi cancelada a seu pedido."; 
    if(barraProgress) barraProgress.style.width = "0%";
    
    setTimeout(() => { 
        overlay.classList.add('hidden'); 
        overlay.classList.remove('flex'); 
    }, 2000); 
}

function parseDataReal(dataStr) {
    if (!dataStr) return new Date(2000, 0, 1);
    let s = dataStr.toLowerCase(); let hoje = new Date();
    if (s.includes('hoje') || s.includes('recente') || s.includes('agora') || s.includes('hora') || s.includes('minuto')) return hoje;
    if (s.includes('ontem')) { hoje.setDate(hoje.getDate() - 1); return hoje; }
    let pt1 = s.match(/(\d{2})\/(\d{2})\/(\d{4})/); if (pt1) return new Date(`${pt1[3]}-${pt1[2]}-${pt1[1]}T12:00:00`);
    return new Date(2000, 0, 1);
}

function toggleSelecaoCard(event, id) {
    if (event.target.closest('a') || event.target.closest('button')) {
        return;
    }
    
    if (vagasSelecionadas.has(id)) {
        vagasSelecionadas.delete(id);
    } else {
        vagasSelecionadas.add(id);
    }
    
    atualizarBarraBulk();
    renderizarResultados(); 
}

function limparSelecao() {
    vagasSelecionadas.clear();
    atualizarBarraBulk();
    renderizarResultados();
}

function selecionarTodasNaTela(idsNaTela) {
    if (idsNaTela && idsNaTela.length > 0) {
        idsNaTela.forEach(id => vagasSelecionadas.add(id));
        atualizarBarraBulk();
        renderizarResultados();
    }
}

function atualizarBarraBulk() {
    const barra = document.getElementById('barra-bulk');
    const count = document.getElementById('bulk-count');
    if (vagasSelecionadas.size > 0) {
        count.innerText = vagasSelecionadas.size;
        barra.classList.remove('translate-y-24', 'opacity-0', 'pointer-events-none');
    } else {
        barra.classList.add('translate-y-24', 'opacity-0', 'pointer-events-none');
    }
}

async function excluirSelecionadas() {
    const confirmou = await confirmarAcao("Excluir Vagas", `Tem certeza que deseja excluir <b>${vagasSelecionadas.size} vagas</b> do seu cofre?`, "danger", "Sim, excluir");
    if (confirmou) {
        const ids = Array.from(vagasSelecionadas);
        showToast(`Excluindo ${ids.length} vagas... Aguarde.`, "warning");
        
        let apagadas = 0;
        for (let id of ids) {
            try {
                await fetch(`/api/resultados/${id}`, { method: 'DELETE' });
                apagadas++;
            } catch(e) {}
        }
        
        resultadosGlobais = resultadosGlobais.filter(v => !vagasSelecionadas.has(v.id));
        limparSelecao();
        renderizarResultados();
        showToast(`Sucesso! ${apagadas} vagas foram excluídas.`, "success");
    }
}

function mudarSubAba(aba) {
    subAbaAtual = aba; radarAtivoId = null; paginaAtual = 1; limparSelecao();
    ['radar', 'vagas', 'concursos'].forEach(id => { 
        const btn = document.getElementById(`btn-sub-${id}`);
        if(btn) btn.className = `px-5 py-2 rounded-lg text-sm font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-all`; 
    });
    const activeBtn = document.getElementById(`btn-sub-${aba}`);
    if(activeBtn) activeBtn.className = `px-5 py-2 rounded-lg text-sm font-bold bg-brand text-white shadow transition-all`;
    
    document.getElementById('barra-filtros-locais').style.display = (aba === 'radar') ? 'none' : 'flex';
    document.getElementById('filtro-texto').value = ''; 
    document.getElementById('filtro-local').value = ''; 
    document.getElementById('filtro-ordem').value = 'data-recente';
    
    const selectScraper = document.getElementById('filtro-scraper');
    let opcoesHtml = '<option value="todos">Qualquer Plataforma</option>';
    if (aba === 'vagas') { scrapersVagas.forEach(s => { opcoesHtml += `<option value="${s}">${s}</option>`; }); }
    else if (aba === 'concursos') { scrapersConcursos.forEach(s => { opcoesHtml += `<option value="${s}">${s}</option>`; }); }
    selectScraper.innerHTML = opcoesHtml; 
    renderizarResultados();
}

async function carregarResultados() { try { const res = await fetch('/api/resultados'); resultadosGlobais = await res.json(); renderizarResultados(); } catch (e) { } }
function filtrarResultadosLocais() { paginaAtual = 1; renderizarResultados(); }
function carregarMaisVagas() { paginaAtual++; renderizarResultados(); }

async function limparVagasRadar(id) {
    const confirmou = await confirmarAcao("Esvaziar Rastreador", "Você está prestes a apagar <b>TODAS</b> as vagas encontradas por este rastreador.<br>Continuar?", "danger", "Esvaziar");
    if (confirmou) {
        try { 
            const res = await fetch(`/api/filtros/${id}/vagas`, { method: 'DELETE' }); 
            if(res.ok) { 
                showToast("Rastreador esvaziado!", "success"); 
                radarAtivoId = null; 
                document.getElementById('barra-filtros-locais').style.display = 'none'; 
                await carregarResultados(); 
            } 
        } catch(e) {}
    }
}

async function deletarVagaIndividual(id) {
    const confirmou = await confirmarAcao("Descartar Vaga", "Deseja excluir esta oportunidade permanentemente do seu cofre?", "danger", "Descartar");
    if (confirmou) { 
        try { 
            const res = await fetch(`/api/resultados/${id}`, { method: 'DELETE' }); 
            if (res.ok) { 
                showToast("Oportunidade excluída!", "success"); 
                resultadosGlobais = resultadosGlobais.filter(v => v.id !== id); 
                vagasSelecionadas.delete(id); 
                atualizarBarraBulk(); 
                renderizarResultados(); 
            } 
        } catch (e) { } 
    }
}

function abrirRadarResultados(id) {
    radarAtivoId = id; 
    paginaAtual = 1; 
    limparSelecao(); 
    document.getElementById('barra-filtros-locais').style.display = 'flex';
    
    const r = filtrosAtuais.find(f => f.id === id); 
    const sel = document.getElementById('filtro-scraper'); 
    let op = '<option value="todos">Qualquer Plataforma</option>';
    if (r && r.scrapers) {
        r.scrapers.split(',').forEach(site => { 
            op += `<option value="${site.trim()}">${site.trim()}</option>`; 
        });
    }
    sel.innerHTML = op; 
    renderizarResultados();
}

function fecharRadar() { 
    radarAtivoId = null; 
    paginaAtual = 1; 
    limparSelecao(); 
    document.getElementById('barra-filtros-locais').style.display = 'none'; 
    renderizarResultados(); 
}

function renderizarResultados() {
    const area = document.getElementById('area-resultados');
    
    if (subAbaAtual === 'radar' && radarAtivoId === null) {
        if (!filtrosAtuais || filtrosAtuais.length === 0) { area.innerHTML = `<div class="text-center py-20 bg-white dark:bg-darkCard rounded-3xl border border-dashed border-slate-300 dark:border-slate-700 mt-8"><i class="fa-solid fa-satellite-dish text-5xl mb-4 text-slate-300 dark:text-slate-600"></i><h3 class="text-xl font-bold dark:text-white mb-2">Nenhum Rastreador</h3></div>`; return; }
        let grupos = {};
        filtrosAtuais.forEach(f => { grupos[f.id] = { nome: f.nome_filtro || 'Sem Nome', tipo: f.tipo_busca, qtd: 0 }; });
        if (resultadosGlobais) { resultadosGlobais.forEach(v => { if (v.filtro_id && grupos[v.filtro_id]) grupos[v.filtro_id].qtd++; }); }
        
        let htmlGrid = '<div class="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-6 mt-4">';
        for (const id in grupos) {
            const g = grupos[id]; 
            const isVaga = g.tipo === 'Vagas';
            const icon = isVaga ? 'fa-briefcase' : 'fa-building-columns'; 
            const gradient = isVaga ? 'from-brand to-teal-600' : 'from-indigo-500 to-purple-600';
            const shadow = isVaga ? 'shadow-brand/30' : 'shadow-indigo-500/30';
            
            const nomeFormatado = g.nome ? g.nome : 'Rastreador';

            htmlGrid += `
            <div onclick="abrirRadarResultados(${id})" class="bg-white dark:bg-darkCard p-6 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-xl hover:-translate-y-1 cursor-pointer transition-all flex flex-col items-start group relative overflow-hidden">
                <div class="absolute -right-6 -top-6 w-24 h-24 bg-gradient-to-br ${gradient} opacity-10 rounded-full blur-2xl group-hover:opacity-20 transition-opacity"></div>
                <div class="w-14 h-14 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center mb-5 shadow-lg${shadow} text-white transform group-hover:scale-110 transition-transform">
                    <i class="fa-solid ${icon} text-2xl"></i>
                </div>
                <span class="text-[10px] font-black uppercase tracking-wider text-slate-400 mb-1">${g.tipo}</span>
                <h4 class="text-lg font-black dark:text-white mb-4 line-clamp-2 w-full pr-4 leading-tight">${nomeFormatado}</h4>
                <div class="mt-auto w-full flex justify-between items-center border-t border-slate-100 dark:border-slate-800 pt-4">
                    <span class="text-sm font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-3 py-1.5 rounded-lg">${g.qtd} vagas</span>
                    <i class="fa-solid fa-arrow-right text-slate-300 group-hover:text-brand transition-colors"></i>
                </div>
            </div>`;
        }
        area.innerHTML = htmlGrid + '</div>'; return;
    }

    if (!resultadosGlobais || resultadosGlobais.length === 0) { area.innerHTML = `<div class="text-center py-20 bg-white dark:bg-darkCard rounded-3xl border border-dashed border-slate-300 dark:border-slate-700 mt-8"><i class="fa-solid fa-box-open text-5xl mb-4 text-slate-300 dark:text-slate-600"></i><h3 class="text-xl font-bold dark:text-white mb-2">Cofre Vazio</h3><p class="text-slate-500">Rode um rastreador para preencher.</p></div>`; return; }

    let lista = []; let titulo = ""; let dataLimite = null;
    if (subAbaAtual === 'radar' && radarAtivoId !== null) {
        lista = resultadosGlobais.filter(v => v.filtro_id === radarAtivoId);
        const rObj = filtrosAtuais.find(f => f.id === radarAtivoId);
        if(rObj) { dataLimite = new Date(); dataLimite.setDate(dataLimite.getDate() - (rObj.max_dias || 30)); dataLimite.setHours(0,0,0,0); }
        const nomeRadarTitle = rObj && rObj.nome_filtro ? rObj.nome_filtro : 'Rastreador';
        
        titulo = `<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6"><div class="flex items-center gap-4"><button onclick="fecharRadar()" class="w-10 h-10 bg-white dark:bg-darkCard border border-slate-200 dark:border-slate-700 rounded-full hover:bg-slate-50 hover:scale-105 shadow-sm transition-all"><i class="fa-solid fa-arrow-left dark:text-white"></i></button><h3 class="text-xl font-bold dark:text-white truncate">Rastreador: <span class="text-brand">${nomeRadarTitle}</span></h3></div><button onclick="limparVagasRadar(${radarAtivoId})" class="bg-red-50 text-red-500 hover:bg-red-500 hover:text-white border border-red-200 px-4 py-2 rounded-xl text-sm font-bold transition-all"><i class="fa-solid fa-broom"></i> Esvaziar Vagas</button></div>`;
    } else if (subAbaAtual === 'vagas') { lista = resultadosGlobais.filter(v => v.tipo_busca === 'Vagas'); } 
    else if (subAbaAtual === 'concursos') { lista = resultadosGlobais.filter(v => v.tipo_busca === 'Concursos'); }

    if(dataLimite) lista = lista.filter(v => parseDataReal(v.data_publicacao) >= dataLimite);

    const txt = document.getElementById('filtro-texto').value.toLowerCase(); const loc = document.getElementById('filtro-local').value.toLowerCase(); const sc = document.getElementById('filtro-scraper').value; const ord = document.getElementById('filtro-ordem').value;
    if (txt) lista = lista.filter(v => (v.titulo||'').toLowerCase().includes(txt) || (v.empresa||'').toLowerCase().includes(txt));
    if (loc) lista = lista.filter(v => (v.local||'').toLowerCase().includes(loc));
    if (sc !== 'todos') lista = lista.filter(v => v.scraper === sc);

    if (ord === 'data-recente') lista.sort((a, b) => parseDataReal(b.data_publicacao) - parseDataReal(a.data_publicacao)); 
    else if (ord === 'data-antiga') lista.sort((a, b) => parseDataReal(a.data_publicacao) - parseDataReal(b.data_publicacao)); 

    const totalItens = lista.length;
    const listaPaginada = lista.slice(0, paginaAtual * ITENS_POR_PAGINA);

    if (totalItens === 0) { 
        area.innerHTML = titulo + `<div class="text-center py-10 text-slate-500 font-medium">Nenhuma oportunidade atende aos filtros.</div>`;
    } else { 
        let infoHeader = `<div class="flex justify-between items-center mb-6"><p class="text-sm font-bold text-slate-400">${totalItens} oportunidades filtradas</p>`;
        
        if (listaPaginada.length > 0 && vagasSelecionadas.size > 0) {
            const arrayIds = `[${listaPaginada.map(v => v.id).join(',')}]`;
            infoHeader += `<button onclick="selecionarTodasNaTela(${arrayIds})" class="text-xs font-bold text-brand hover:text-brandHover bg-brand/10 px-3 py-1.5 rounded-lg transition-colors"><i class="fa-solid fa-check-double mr-1"></i> Selecionar todas na tela</button>`;
        }
        infoHeader += `</div>`;

        let htmlCards = gerarGrid(listaPaginada);
        
        let btnCarregarMais = '';
        if (totalItens > listaPaginada.length) {
            btnCarregarMais = `
            <div class="flex justify-center mt-10 mb-8">
                <button onclick="carregarMaisVagas()" class="bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-bold py-3 px-8 rounded-xl transition-colors shadow-sm flex items-center gap-2">
                    <i class="fa-solid fa-arrow-rotate-right"></i> Carregar Mais Vagas (${totalItens - listaPaginada.length} restantes)
                </button>
            </div>`;
        }

        area.innerHTML = titulo + infoHeader + htmlCards + btnCarregarMais;
    }
}

function gerarGrid(lista) {
    return `<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">` + lista.map(v => {
        const btnTxt = scrapersConcursos.includes(v.scraper) ? 'Ver Concurso' : 'Ver Vaga';
        const isRemoto = (v.local || '').toLowerCase().includes('remoto');
        const estaSelecionada = vagasSelecionadas.has(v.id);
        
        const bordaClass = estaSelecionada 
            ? 'ring-2 ring-brand border-brand bg-brand/5 dark:bg-brand/10' 
            : 'border-slate-200 dark:border-slate-700 hover:border-brand/40 bg-white dark:bg-darkCard';
        
        const bolinhaMarcada = estaSelecionada
            ? `<div class="absolute top-4 right-4 w-6 h-6 rounded-full bg-brand flex items-center justify-center shadow-sm z-10"><i class="fa-solid fa-check text-white text-[10px]"></i></div>`
            : ``;
        
        const localBadge = isRemoto 
            ? `<span class="flex items-center gap-1.5 text-[11px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400 px-3 py-1.5 rounded-md w-max"><i class="fa-solid fa-house-laptop"></i> ${v.local || 'Remoto'}</span>`
            : `<span class="flex items-center gap-1.5 text-[11px] font-bold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 px-3 py-1.5 rounded-md w-max truncate max-w-full"><i class="fa-solid fa-location-dot text-slate-400"></i> ${v.local || 'N/A'}</span>`;

        return `
        <div onclick="toggleSelecaoCard(event, ${v.id})" class="rounded-2xl p-5 border shadow-sm relative flex flex-col transition-all duration-300 cursor-pointer ${bordaClass}">
            
            ${bolinhaMarcada}

            <div class="flex items-center gap-3 mb-4 pr-10">
                <div class="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center shrink-0">
                    <i class="fa-regular fa-building text-slate-400 text-sm"></i>
                </div>
                <div class="flex flex-col min-w-0">
                    <span class="text-xs font-black text-slate-800 dark:text-slate-200 truncate" title="${v.empresa || 'Confidencial'}">${v.empresa || 'Confidencial'}</span>
                    <span class="text-[10px] font-bold text-slate-400">${v.scraper || 'Site'}</span>
                </div>
            </div>

            <h4 class="text-base font-black dark:text-white mb-4 leading-snug" title="${v.titulo || 'Oportunidade'}">
                ${v.titulo || 'Oportunidade'}
            </h4>

            <div class="flex flex-col gap-2 mb-6 mt-auto">
                ${localBadge}
                <span class="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 dark:text-slate-400 px-1 mt-1">
                    <i class="fa-regular fa-clock"></i> Capturado: ${v.data_publicacao || 'Recente'}
                </span>
            </div>

            <div class="flex items-center gap-3 mt-auto">
                <a href="${v.link || '#'}" target="_blank" class="flex-1 flex justify-center items-center gap-2 text-sm font-bold text-white bg-slate-800 hover:bg-slate-900 dark:bg-brand dark:hover:bg-brandHover py-3 rounded-xl active:scale-95 transition-all">
                    ${btnTxt} <i class="fa-solid fa-arrow-up-right-from-square text-xs ml-1 opacity-70"></i>
                </a>
                <button onclick="deletarVagaIndividual(${v.id})" class="w-11 h-11 shrink-0 flex justify-center items-center rounded-xl bg-slate-100 hover:bg-red-50 dark:bg-slate-800 dark:hover:bg-red-500/10 text-slate-400 hover:text-red-500 transition-colors" title="Descartar oportunidade">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        </div>
        `}).join('') + `</div>`;
}

carregarFiltros();