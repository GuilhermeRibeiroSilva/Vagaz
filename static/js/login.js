function toggleTheme() {
    const html = document.documentElement;
    const body = document.body;
    const icon = document.getElementById('theme-icon');

    if (html.classList.contains('dark')) {
        html.classList.remove('dark');
        body.classList.remove('dark');
        body.classList.add('light-theme');
        icon.classList.remove('fa-sun');
        icon.classList.add('fa-moon');
        localStorage.setItem('theme', 'light');
    } else {
        html.classList.add('dark');
        body.classList.add('dark');
        body.classList.remove('light-theme');
        icon.classList.remove('fa-moon');
        icon.classList.add('fa-sun');
        localStorage.setItem('theme', 'dark');
    }
}

if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    toggleTheme(); 
}

function switchTab(tab) {
    const slider = document.getElementById('form-slider');
    const sliderBg = document.getElementById('slider-bg');
    const btnLogin = document.getElementById('btn-login');
    const btnRegister = document.getElementById('btn-register');

    if (tab === 'register') {
        slider.style.transform = 'translateX(-50%)';
        sliderBg.style.left = 'calc(50% - 4px)';
        btnRegister.classList.remove('text-gray-500', 'dark:text-gray-400');
        btnRegister.classList.add('text-brand', 'dark:text-teal-400');
        btnLogin.classList.remove('text-brand', 'dark:text-teal-400');
        btnLogin.classList.add('text-gray-500', 'dark:text-gray-400');
    } else {
        slider.style.transform = 'translateX(0)';
        sliderBg.style.left = '4px';
        btnLogin.classList.remove('text-gray-500', 'dark:text-gray-400');
        btnLogin.classList.add('text-brand', 'dark:text-teal-400');
        btnRegister.classList.remove('text-brand', 'dark:text-teal-400');
        btnRegister.classList.add('text-gray-500', 'dark:text-gray-400');
    }
}

function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    document.getElementById('toast-message').innerText = message;

    if (isError) {
        toast.classList.replace('bg-brand', 'bg-red-500') || toast.classList.add('bg-red-500');
    } else {
        toast.classList.replace('bg-red-500', 'bg-brand') || toast.classList.add('bg-brand');
    }

    toast.classList.remove('opacity-0', '-translate-y-4');
    toast.classList.add('opacity-100', 'translate-y-0');

    setTimeout(() => {
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', '-translate-y-4');
    }, 4000);
}

document.getElementById('form-register')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-submit-reg');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

    const nome = document.getElementById('reg-nome').value;
    const email = document.getElementById('reg-email').value;
    const senha = document.getElementById('reg-senha').value;

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome, email, senha })
        });

        const data = await res.json();

        if (res.ok) {
            showToast("Conta criada com sucesso! Faça login.", false);
            switchTab('login');
            document.getElementById('login-email').value = email;
            document.getElementById('reg-senha').value = '';
        } else {
            showToast(data.detail, true);
        }
    } catch (err) {
        showToast("Erro no servidor.", true);
    }
    btn.innerHTML = 'Criar conta';
});

document.getElementById('form-login')?.addEventListener('submit', async function (e) {
    e.preventDefault();

    const inputEmail = this.querySelector('input[type="email"]');
    const inputSenha = this.querySelector('input[type="password"]');

    const dadosLogin = {
        email: inputEmail.value,
        senha: inputSenha.value,
        lembrar: true
    };

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dadosLogin)
        });

        const data = await response.json();

        if (response.ok) {
            if (data.is_admin === true) {
                window.location.href = "/admin";
            } else {
                window.location.href = "/dashboard";
            }
        } else {
            showToast(data.detail || "Erro ao fazer login", true);
        }
    } catch (error) {
        showToast("Erro de comunicação com o servidor.", true);
    }
});