# Usa a imagem oficial do Playwright com Python já embutido (evita erros de Chromium)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# Copia os arquivos de requisitos primeiro (para aproveitar o cache do Docker)
COPY requirements.txt .

# Instala as bibliotecas do Python
RUN pip install --no-cache-dir -r requirements.txt

# Garante que os navegadores do Playwright sejam instalados e atualizados
RUN playwright install chromium
RUN playwright install-deps

# Copia todo o resto do seu projeto para dentro do contêiner
COPY . .

# Expõe a porta 8000 para o mundo externo
EXPOSE 8000

# O comando que vai ligar a sua API quando o contêiner iniciar
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]