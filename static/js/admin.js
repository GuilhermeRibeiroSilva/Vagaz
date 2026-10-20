const API_BASE = '/api/admin';
let dashboardInterval = null;
let filaInterval = null;

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast-enter flex items-center p-4 rounded-xl shadow-lg border pointer-events-auto ${type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/20 dark:text-emerald-400' : 'bg-red-50 border-red-200 text-red-700 dark:bg-red-500/10 dark:border-red-500/20 dark:text-red-400'}`;
    toast.innerHTML = `<i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-triangle-exclamation'} text-xl mr-3"></i><span class="font-bold text-sm">${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.classList.replace('toast-enter', 'toast-exit'); setTimeout(() => toast.remove(), 300); }, 4000);
}

let confirmCallback = null;
function showConfirm(title, message, isDanger, onConfirm) {
    document.getElementById('confirm-title').innerText = title;
    document.getElementById('confirm-message').innerText = message;
    const icon = document.getElementById('confirm-icon');
    const btnYes = document.getElementById('confirm-btn-yes');
    
    if (isDanger) {
        icon.className = "w-16 h-16 rounded-full bg-red-100 dark:bg-red-500/20 text-red-500 flex items-center justify-center text-3xl mx-auto mb-4";
        icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
        btnYes.className = "flex-1 bg-red-500 hover:bg-red-600 text-white font-bold py-2.5 rounded-lg shadow-lg shadow-red-500/30";
    } else {
        icon.className = "w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-500 flex items-center justify-center text-3xl mx-auto mb-4";
        icon.innerHTML = '<i class="fa-solid fa-circle-question"></i>';
        btnYes.className = "flex-1 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2.5 rounded-lg shadow-lg shadow-blue-500/30";
    }
    confirmCallback = onConfirm; document.getElementById('modal-confirm').classList.remove('hidden');
}

function fecharConfirm() { document.getElementById('modal-confirm').classList.add('hidden'); confirmCallback = null; }
document.getElementById('confirm-btn-yes').addEventListener('click', () => { if(confirmCallback) confirmCallback(); fecharConfirm(); });

if(localStorage.getItem('theme') === 'light') { document.documentElement.classList.remove('dark'); document.getElementById('theme-icon').classList.replace('fa-sun', 'fa-moon'); }
function toggleTheme() { document.documentElement.classList.toggle('dark'); const isDark = document.documentElement.classList.contains('dark'); localStorage.setItem('theme', isDark ? 'dark' : 'light'); document.getElementById('theme-icon').className = isDark ? 'fa-solid fa-sun' : 'fa-solid fa-moon'; }

function mudarAba(abaId) {
    document.querySelectorAll('main > section').forEach(s => s.classList.add('hidden'));
    document.getElementById('aba-' + abaId).classList.remove('hidden');
    document.querySelectorAll('.aba-btn').forEach(b => b.className = "w-full flex items-center gap-3 px-4 py-3 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-xl font-bold transition-all aba-btn");
    document.getElementById('btn-' + abaId).className = "w-full flex items-center gap-3 px-4 py-3 bg-brand/20 text-brandHover dark:text-brand rounded-xl font-bold transition-all aba-btn";

    clearInterval(dashboardInterval); clearInterval(filaInterval);
    if(abaId === 'dashboard') { carregarStats(); dashboardInterval = setInterval(carregarStats, 5000); }
    if(abaId === 'usuarios') carregarUsuarios();
    if(abaId === 'database') carregarTabelas();
    if(abaId === 'scrapers') { carregarScrapers(); carregarFila(); filaInterval = setInterval(carregarFila, 5000); }
}

let lastTopScrapers = "";

async function carregarStats() {
    try {
        const res = await fetch(`${API_BASE}/stats`, { cache: 'no-store' });
        const stats = await res.json();

        function updateNumber(id, newValue) {
            const el = document.getElementById(id);
            if (el && el.innerText != newValue) {
                el.innerText = newValue;
                el.style.transition = 'color 0.3s ease';
                el.style.color = '#10b981';
                setTimeout(() => { el.style.color = ''; }, 1000);
            }
        }

        updateNumber('stat-vagas-hoje', stats.vagas_hoje || 0);
        updateNumber('stat-vagas', stats.total_vagas || 0);
        updateNumber('stat-usuarios', stats.total_usuarios || 0);
        updateNumber('stat-filtros-totais', stats.total_filtros || 0);
        
        const currentTop = JSON.stringify(stats.top_scrapers);
        if (currentTop !== lastTopScrapers) {
            lastTopScrapers = currentTop;
            const cont = document.getElementById('stat-top-scrapers');
            
            if(stats.top_scrapers?.length > 0) {
                cont.innerHTML = stats.top_scrapers.map((s, i) => {
                    let cor = i === 0 ? 'text-yellow-500' : i === 1 ? 'text-slate-400' : 'text-amber-600';
                    return `
                        <div class="flex justify-between items-center bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-700 animate-fade-in">
                            <span class="font-bold text-slate-700 dark:text-slate-200 flex items-center">
                                <i class="fa-solid fa-medal ${cor} mr-3 text-lg"></i> ${s.nome}
                            </span>
                            <span class="bg-brand/20 text-brand px-3 py-1 rounded-lg text-xs font-black transition-colors duration-500 highlight-badge">
                                ${s.total} Vagas
                            </span>
                        </div>
                    `;
                }).join('');
                
                setTimeout(() => {
                    cont.querySelectorAll('.highlight-badge').forEach(el => {
                        el.style.backgroundColor = 'transparent';
                    });
                }, 800);
            }
        }
    } catch(e) {}
}

async function carregarScrapers() {
    try {
        const res = await fetch(`${API_BASE}/scrapers`, { cache: 'no-store' });
        let db = await res.json();
        
        const scrapersEsperados = ["Empregos", "InfoJobs", "Gupy", "LinkedIn", "Remotar", "PCI", "C_Brasil"];
        
        let html = '';
        scrapersEsperados.forEach(nome => {
            let config = db.find(s => s.nome === nome);
            let isHeadless = config ? config.headless : true;
            
            let nomeExibicao = nome.replace('_', ' ');
            if (nome === 'PCI') nomeExibicao = 'PCI Concursos';
            if (nome === 'C_Brasil') nomeExibicao = 'Concursos Brasil';
            if (nome === 'Gran') nomeExibicao = 'Gran Cursos';
            
            html += `
            <div class="flex flex-col items-center justify-center p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700">
                <span class="font-bold text-sm mb-3 dark:text-slate-300 truncate w-full text-center" title="${nomeExibicao}">${nomeExibicao}</span>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" class="sr-only peer" ${isHeadless ? 'checked' : ''} onchange="toggleScraper('${nome}')">
                    <div class="w-11 h-6 bg-slate-300 dark:bg-slate-600 rounded-full peer peer-checked:bg-brand after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
                </label>
            </div>`;
        });
        document.getElementById('grid-scrapers').innerHTML = html;
    } catch(e) {}
}

async function toggleScraper(nome) {
    const res = await fetch(`${API_BASE}/scrapers/${nome}/toggle`, { method: 'POST' });
    if (!res.ok) { showToast(`O scraper ${nome} continuará invisível.`, 'warning'); carregarScrapers(); }
}

async function carregarFila() {
    try {
        const res = await fetch(`${API_BASE}/fila`, { cache: 'no-store' }); 
        const data = await res.json();
        document.getElementById('status-fila').innerText = data.tamanho_fila;
        const ativos = document.getElementById('status-ativos');
        ativos.innerHTML = data.varreduras_ativas.length > 0 
            ? data.varreduras_ativas.map(v => `<div class="text-sm bg-brand/10 border border-brand/20 p-3 rounded-lg text-brand font-medium animate-pulse"><i class="fa-solid fa-gear fa-spin mr-2"></i> [Radar ${v.id}] ${v.etapa}</div>`).join('') 
            : '<p class="text-sm text-slate-500 italic"><i class="fa-solid fa-mug-hot mr-2"></i>Nenhuma varredura acontecendo no momento.</p>';
    } catch(e) {}
}

async function testarSite(btnId, url) {
    const btn = document.getElementById(btnId);
    const badge = document.getElementById(`badge-${btnId}`);
    btn.disabled = true; badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-slate-400"></i>';
    try {
        const res = await fetch(`${API_BASE}/qa/ping`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url: url}) });
        const result = await res.json();
        if (result.status === 'ok') badge.innerHTML = `<span class="text-green-500 font-bold text-xs"><i class="fa-solid fa-circle-check"></i> OK (200)</span>`;
        else if (result.status === 'warning') badge.innerHTML = `<span class="text-yellow-500 font-bold text-xs" title="${result.message}"><i class="fa-solid fa-shield-halved"></i> Bloq (${result.code})</span>`;
        else badge.innerHTML = `<span class="text-red-500 font-bold text-xs"><i class="fa-solid fa-circle-xmark"></i> Erro (${result.code})</span>`;
    } catch(e) { badge.innerHTML = `<span class="text-red-500 font-bold text-xs"><i class="fa-solid fa-triangle-exclamation"></i> Falhou</span>`; }
    btn.disabled = false;
}

async function carregarUsuarios() {
    const tbody = document.getElementById('lista-usuarios');
    tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center dark:text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Carregando...</td></tr>';
    try {
        const res = await fetch(`${API_BASE}/usuarios`, { cache: 'no-store' });
        const usuarios = await res.json();
        
        tbody.innerHTML = usuarios.map(u => {
            let maxTags = 3;
            let tagsHtml = '';
            if (u.filtros.length > 0) {
                tagsHtml = u.filtros.slice(0, maxTags).map(f => `<span class="bg-brand/10 text-brandHover dark:text-brand border border-brand/20 px-2 py-1 rounded text-[10px] font-bold mr-1 inline-block mb-1">${f.termo}</span>`).join('');
                if (u.filtros.length > maxTags) tagsHtml += `<span class="bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400 px-2 py-1 rounded text-[10px] font-bold inline-block mb-1">+${u.filtros.length - maxTags} radares</span>`;
            } else {
                tagsHtml = '<span class="text-slate-400 italic text-xs">Sem radares</span>';
            }

            return `
            <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors border-b border-slate-50 dark:border-slate-800">
                <td class="p-4 font-bold text-slate-400">#${u.id}</td>
                <td class="p-4"><p class="font-bold text-slate-800 dark:text-white">${u.nome} ${u.is_admin ? '<span class="bg-amber-100 text-amber-700 text-[10px] px-2 py-0.5 rounded font-bold uppercase ml-2">Admin</span>' : ''}</p><p class="text-xs text-slate-500">${u.email}</p></td>
                <td class="p-4 max-w-xs flex-wrap">${tagsHtml}</td>
                <td class="p-4"><span class="font-black text-brand text-lg">${u.total_vagas}</span><span class="text-slate-400 text-xs ml-1">vagas</span></td>
                <td class="p-4 text-center space-x-2">
                   <button onclick="inspecionarUsuario(${u.id}, '${u.nome}')" class="bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-brand hover:text-slate-900 w-8 h-8 rounded transition-colors font-bold"><i class="fa-solid fa-eye text-xs"></i></button>
                   <button onclick="abrirModalEditarUsuario(${u.id}, '${u.nome}', '${u.email}')" class="bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-blue-500 hover:text-white w-8 h-8 rounded transition-colors font-bold"><i class="fa-solid fa-pen text-xs"></i></button>
                   ${!u.is_admin ? `<button onclick="deletarUsuario(${u.id})" class="bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-red-500 hover:text-white w-8 h-8 rounded transition-colors font-bold"><i class="fa-solid fa-trash text-xs"></i></button>` : ''}
                </td>
            </tr>`;
        }).join('');
    } catch(e) {}
}

function abrirModalCriarUsuario() { document.getElementById('form-criar-usuario').reset(); document.getElementById('modal-criar-usuario').classList.remove('hidden'); }
function fecharModalCriarUsuario() { document.getElementById('modal-criar-usuario').classList.add('hidden'); }

document.getElementById('form-criar-usuario').addEventListener('submit', async (e) => {
    e.preventDefault();
    const dados = { nome: document.getElementById('novo-nome').value, email: document.getElementById('novo-email').value, senha: document.getElementById('novo-senha').value };
    const res = await fetch(`${API_BASE}/usuarios`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(dados) });
    if(res.ok) { showToast("Usuário criado com sucesso!"); fecharModalCriarUsuario(); carregarUsuarios(); } 
    else { const err = await res.json(); showToast(err.detail || "Erro.", "error"); }
});

function abrirModalEditarUsuario(id, nome, email) {
    document.getElementById('edit-id').value = id; document.getElementById('edit-nome').value = nome; document.getElementById('edit-email').value = email; document.getElementById('edit-senha').value = '';
    document.getElementById('modal-editar-usuario').classList.remove('hidden');
}
function fecharModalEditarUsuario() { document.getElementById('modal-editar-usuario').classList.add('hidden'); }

document.getElementById('form-editar-usuario').addEventListener('submit', async (e) => {
    e.preventDefault();
    const dados = { nome: document.getElementById('edit-nome').value, email: document.getElementById('edit-email').value, senha: document.getElementById('edit-senha').value };
    const res = await fetch(`${API_BASE}/usuarios/${document.getElementById('edit-id').value}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(dados) });
    if(res.ok) { showToast("Usuário atualizado!"); fecharModalEditarUsuario(); carregarUsuarios(); } else { showToast("Erro ao editar.", "error"); }
});

function deletarUsuario(id) {
    showConfirm("Excluir Usuário", "Isso apagará todas as vagas e radares dele permanentemente.", true, async () => {
        await fetch(`${API_BASE}/usuarios/${id}`, { method: 'DELETE' });
        showToast("Usuário excluído."); carregarUsuarios();
    });
}

function getScraperColor(nome) {
    if(!nome) return 'bg-slate-200 text-slate-700';
    if(nome.includes('LinkedIn')) return 'bg-blue-100 text-blue-700 border-blue-200';
    if(nome.includes('Gupy')) return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    if(nome.includes('Remotar')) return 'bg-purple-100 text-purple-700 border-purple-200';
    if(nome.includes('Empregos')) return 'bg-orange-100 text-orange-700 border-orange-200';
    if(nome.includes('Concursos')) return 'bg-amber-100 text-amber-700 border-amber-200';
    return 'bg-slate-200 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700';
}

async function inspecionarUsuario(id, nomeUser) {
    const container = document.getElementById('conteudo-inspecao');
    document.getElementById('inspecao-titulo').innerHTML = `<i class="fa-solid fa-radar text-brand mr-2"></i> Radares: ${nomeUser}`;
    container.innerHTML = '<p class="text-center dark:text-slate-400 py-8"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Puxando banco de dados...</p>';
    document.getElementById('modal-inspecao').classList.remove('hidden');

    try {
        const res = await fetch(`${API_BASE}/usuarios/${id}/detalhes`, { cache: 'no-store' });
        const data = await res.json();
        if(data.filtros.length === 0) { container.innerHTML = '<p class="text-center text-slate-500 py-8">Nenhum radar configurado.</p>'; return; }

        let totalVagas = 0; data.filtros.forEach(f => totalVagas += f.vagas.length);
        document.getElementById('inspecao-stats').innerHTML = `<span class="bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs px-3 py-1 rounded-full font-bold">Radares: ${data.filtros.length}</span><span class="bg-brand/20 text-brand text-xs px-3 py-1 rounded-full font-bold">Vagas: ${totalVagas}</span>`;

        container.innerHTML = data.filtros.map(f => `
            <div class="bg-white dark:bg-darkCard rounded-xl border border-slate-200 dark:border-slate-700 mb-8 overflow-hidden shadow-sm">
                <div class="bg-slate-100 dark:bg-slate-800/80 p-4 border-b border-slate-200 dark:border-slate-700">
                    <div class="flex justify-between items-start mb-3">
                        <h4 class="font-black text-slate-800 dark:text-white text-lg flex items-center gap-2">
                            ${f.nome} <span class="text-[10px] bg-slate-200 dark:bg-slate-700 px-2 py-0.5 rounded-full text-slate-500">ID: ${f.id}</span>
                            ${f.timer_ativo ? '<span class="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full uppercase shadow-sm"><i class="fa-solid fa-robot mr-1"></i> Auto</span>' : ''}
                        </h4>
                        <button onclick="limparVagasRadarAdmin(${f.id}, ${id}, '${nomeUser}')" class="bg-red-50 text-red-500 hover:bg-red-500 hover:text-white border border-red-200 px-3 py-1.5 rounded-lg font-bold text-xs transition-colors"><i class="fa-solid fa-broom mr-1"></i> Limpar ${f.vagas.length} Vagas</button>
                    </div>
                    
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs bg-white dark:bg-slate-900/50 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
                        <div><span class="block text-slate-400 font-bold mb-0.5 uppercase tracking-wider text-[10px]">Termos Buscados</span><span class="dark:text-slate-300 font-medium">${f.termos}</span></div>
                        <div><span class="block text-slate-400 font-bold mb-0.5 uppercase tracking-wider text-[10px]">Palavras Ignoradas</span><span class="dark:text-slate-300 font-medium">${f.palavras_proibidas || '-'}</span></div>
                        <div><span class="block text-slate-400 font-bold mb-0.5 uppercase tracking-wider text-[10px]">Localização</span><span class="dark:text-slate-300 font-medium">${f.localizacao || 'Brasil'}</span></div>
                        <div><span class="block text-slate-400 font-bold mb-0.5 uppercase tracking-wider text-[10px]">Plataformas</span><span class="dark:text-slate-300 font-medium truncate block w-full" title="${f.scrapers}">${f.scrapers}</span></div>
                    </div>
                </div>

                <div class="max-h-80 overflow-y-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 dark:bg-slate-900/50 sticky top-0 border-b border-slate-100 dark:border-slate-800 text-xs uppercase text-slate-500 font-bold">
                            <tr><th class="p-3">Título da Vaga / Empresa</th><th class="p-3 w-48">Plataforma / Data</th><th class="p-3 w-16 text-center">Ação</th></tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100 dark:divide-slate-800/50">
                            ${f.vagas.length > 0 ? f.vagas.map(v => `
                                <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                                    <td class="p-3">
                                        <p class="font-bold text-slate-700 dark:text-slate-300 truncate max-w-md">${v.titulo}</p>
                                        <p class="text-xs text-slate-500 truncate max-w-md mt-0.5"><i class="fa-solid fa-building mr-1"></i>${v.empresa} <span class="mx-1">•</span> <i class="fa-solid fa-location-dot mr-1"></i>${v.local}</p>
                                    </td>
                                    <td class="p-3">
                                        <span class="${getScraperColor(v.scraper)} border px-2 py-0.5 rounded text-[10px] font-bold uppercase block w-max mb-1">${v.scraper}</span>
                                        <p class="text-xs text-slate-500"><i class="fa-solid fa-clock mr-1"></i>${v.data}</p>
                                    </td>
                                    <td class="p-3 text-center"><a href="${v.link}" target="_blank" class="text-slate-400 hover:text-brand text-lg transition-colors"><i class="fa-solid fa-arrow-up-right-from-square"></i></a></td>
                                </tr>
                            `).join('') : '<tr><td colspan="3" class="p-4 text-xs text-slate-400 italic text-center">Nenhum resultado capturado.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        `).join('');
    } catch(e) { container.innerHTML = '<p class="text-red-500 text-center py-8">Erro ao puxar dados.</p>'; }
}

function limparVagasRadarAdmin(filtroId, userId, nomeUser) {
    showConfirm("Esvaziar Radar", "Confirma a exclusão de todas as vagas deste radar? (O radar em si não será apagado)", true, async () => {
        await fetch(`${API_BASE}/filtros/${filtroId}/vagas`, { method: 'DELETE' });
        showToast("Vagas excluídas com sucesso.");
        inspecionarUsuario(userId, nomeUser); carregarUsuarios(); 
    });
}
function fecharModalInspecao() { document.getElementById('modal-inspecao').classList.add('hidden'); }

async function carregarTabelas() {
    try {
        const res = await fetch(`${API_BASE}/db/tables`, { cache: 'no-store' });
        const tabelas = await res.json();
        document.getElementById('grid-tabelas-negocio').innerHTML = ''; document.getElementById('grid-tabelas-sistema').innerHTML = '';
        tabelas.forEach(t => {
            const html = `
                <div class="bg-white dark:bg-darkCard rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 flex justify-between items-center hover:border-brand dark:hover:border-brand transition-colors group">
                    <div class="cursor-pointer flex-1" onclick="verTabela('${t.nome}')">
                        <h4 class="text-lg font-black text-slate-800 dark:text-white uppercase tracking-tight group-hover:text-brand transition-colors">${t.nome}</h4>
                        <p class="text-xs font-bold text-slate-400 mt-1">${t.linhas} registros</p>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="limparTabelaUnica('${t.nome}')" class="bg-red-50 text-red-500 hover:bg-red-500 hover:text-white w-9 h-9 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"><i class="fa-solid fa-broom text-sm"></i></button>
                        <div class="bg-slate-50 dark:bg-slate-800 w-9 h-9 rounded-full flex items-center justify-center group-hover:bg-brand/20 transition-colors cursor-pointer" onclick="verTabela('${t.nome}')"><i class="fa-solid fa-chevron-right text-slate-400 group-hover:text-brand text-sm"></i></div>
                    </div>
                </div>`;
            if (['users', 'saved_jobs', 'search_filters'].includes(t.nome)) document.getElementById('grid-tabelas-negocio').innerHTML += html;
            else document.getElementById('grid-tabelas-sistema').innerHTML += html;
        });
    } catch(e) {}
}

function limparTabelaUnica(tabela) {
    let aviso = "Você vai DELETAR TODOS OS REGISTROS desta tabela. Essa ação é agressiva.";
    if (tabela === 'users') aviso += "\n\nALERTA: Isso quebrará chaves estrangeiras. Limpe vagas e filtros primeiro!";
    showConfirm("Truncar Tabela", aviso, true, async () => {
        await fetch(`${API_BASE}/db/clear/${tabela}`, { method: 'DELETE' });
        showToast(`Tabela ${tabela} esvaziada.`); carregarTabelas(); 
    });
}

function abrirNukeConfirm() {
    showConfirm("PROTOCOLO DE EXTERMÍNIO", "Isso apagará TODAS as vagas, radares, configurações e usuários comuns. Somente a sua conta Admin sobreviverá. Tem certeza absoluta?", true, async () => {
        await fetch(`${API_BASE}/db/nuke`, { method: 'DELETE' });
        showToast("Limpeza Total Concluída."); carregarTabelas(); carregarStats();
    });
}

function formatarDado(coluna, valor) {
    if (valor === null || valor === undefined) return '<span class="text-slate-400 italic">null</span>';
    if (typeof valor === 'boolean' || valor === true || valor === false) return valor ? '<span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase">TRUE</span>' : '<span class="bg-slate-200 text-slate-500 px-2 py-0.5 rounded text-[10px] font-bold uppercase">FALSE</span>';
    if (typeof valor === 'string' && valor.startsWith('http')) return `<a href="${valor}" target="_blank" class="text-blue-500 hover:text-blue-600 hover:underline flex items-center gap-1"><i class="fa-solid fa-link text-xs"></i> Abrir URL</a>`;
    
    if (typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(valor)) { 
        try { 
            const d = new Date(valor); 
            if (!isNaN(d.getTime())) {
                return `<span class="text-slate-500"><i class="fa-regular fa-clock mr-1"></i>${d.toLocaleDateString('pt-BR')} ${d.toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'})}</span>`; 
            }
        } catch(e) {} 
    }
    return valor;
}

async function verTabela(nome) {
    document.getElementById('titulo-modal-tabela').innerHTML = `<i class="fa-solid fa-table text-brand mr-2"></i> ${nome.toUpperCase()}`;
    const thead = document.getElementById('thead-tabela'); const tbody = document.getElementById('tbody-tabela');
    thead.innerHTML = ''; tbody.innerHTML = '<tr><td class="p-8 text-center text-slate-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Puxando registros...</td></tr>';
    document.getElementById('modal-tabela').classList.remove('hidden');

    try {
        const res = await fetch(`${API_BASE}/db/tables/${nome}/dados`, { cache: 'no-store' });
        const dados = await res.json();
        if(dados.length === 0) { tbody.innerHTML = '<tr><td class="p-8 text-center text-slate-500 italic">Tabela vazia.</td></tr>'; return; }
        const colunas = Object.keys(dados[0]);
        thead.innerHTML = `<tr>${colunas.map(c => `<th class="p-4 uppercase tracking-wider text-[10px] text-slate-500 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900">${c}</th>`).join('')}</tr>`;
        tbody.innerHTML = dados.map(l => `<tr class="hover:bg-slate-50 dark:hover:bg-slate-800/30">${colunas.map(c => `<td class="p-4 truncate max-w-[200px] border-b border-slate-50 dark:border-slate-800/50" title="${l[c]}">${formatarDado(c, l[c])}</td>`).join('')}</tr>`).join('');
    } catch(e) { tbody.innerHTML = '<tr><td class="p-4 text-red-500">Erro ao ler tabela.</td></tr>'; }
}
function fecharModalTabela() { document.getElementById('modal-tabela').classList.add('hidden'); }

window.onload = () => mudarAba('dashboard');