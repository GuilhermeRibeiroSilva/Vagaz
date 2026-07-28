import psycopg2

HOST = "129.153.17.142"
PORTA = "5432"
USUARIO = "admin"
SENHA = "GuizinBot21"
BANCO = "job_db"

try:
    conexao = psycopg2.connect(host=HOST, port=PORTA, user=USUARIO, password=SENHA, database=BANCO)
    print("✅ SUCESSO! O PostgreSQL é uma máquina! Conectado com sucesso.")
    conexao.close()
except Exception as e:
    print(f"❌ Erro ao conectar: {e}")