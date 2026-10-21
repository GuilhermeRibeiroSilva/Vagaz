# 📡 Vagaz - O Seu Radar de Oportunidades

![Vagaz Banner](https://img.shields.io/badge/Status-Online-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Uma plataforma web automatizada projetada para rastrear, consolidar e notificar oportunidades de emprego (CLT/PJ) e concursos públicos no Brasil, centralizando tudo em um painel único e moderno.

🌐 **Acesse a plataforma:** [[Acesse aqui!](https://vagaz.duckdns.org/)]

---

## ⚠️ Aviso Legal (Disclaimer Educacional)

**Este projeto foi desenvolvido com fins estritamente educacionais, de pesquisa e aprendizado de engenharia de software.** 

O Vagaz **não tem** a intenção de burlar sistemas de segurança, sobrecarregar servidores de terceiros, violar termos de serviço ou competir comercialmente com as plataformas mapeadas. As requisições são feitas com espaçamentos temporais humanos, simulação de navegador legítimo e rotinas diárias controladas para não causar impacto aos sites alvo. Os dados coletados são públicos e não são comercializados. 

---

## ✨ Funcionalidades Principais

* 🤖 **Rastreadores Inteligentes:** Robôs especializados na extração limpa de dados das 7 principais plataformas do Brasil (Empregos.com, InfoJobs, Gupy, LinkedIn, Remotar, PCI Concursos e Concursos Brasil).
* ⚙️ **Processamento em 2º Plano:** Varreduras assíncronas que não travam a interface do usuário.
* 📧 **Alertas via E-mail:** Notificações automáticas com o top 4 de vagas encontradas nos rastreamentos diários.
* 🛡️ **Painel Administrativo:** Controle total do sistema, monitoramento de robôs (QA) e gestão de usuários.
* 🧹 **Auto-Limpeza Inteligente:** Descarte automático de vagas antigas (60 dias) para manter a performance do servidor.
* 🎨 **UI/UX Moderna:** Interface responsiva construída com Tailwind CSS, com suporte a Dark/Light mode.

## 🛠️ Stack Tecnológica

**Backend:**
* [Python 3](https://www.python.org/)
* [FastAPI](https://fastapi.tiangolo.com/) (Motor assíncrono e API)
* [Playwright](https://playwright.dev/python/) (Web Scraping Avançado / Headless Browser)
* [SQLAlchemy](https://www.sqlalchemy.org/) (ORM)

**Frontend:**
* HTML5 / CSS3 / Vanilla JS
* [Tailwind CSS](https://tailwindcss.com/)
* Jinja2 (Templates)

**Infraestrutura:**
* [Docker](https://www.docker.com/) & Docker Compose
* GitHub Actions (CI/CD Deploy Automático)
* PostgreSQL / SQLite

## 🚀 Como Rodar Localmente

1. Clone o repositório:
```bash
git clone [https://github.com/SeuUsuario/Vagaz.git](https://github.com/SeuUsuario/Vagaz.git)
cd Vagaz
