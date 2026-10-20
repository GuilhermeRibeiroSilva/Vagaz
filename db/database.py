from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    
    is_admin = Column(Boolean, default=False)
    
    vagas_salvas = relationship("SavedJob", back_populates="dono", cascade="all, delete-orphan")
    filtros = relationship("SearchFilter", back_populates="dono", cascade="all, delete-orphan")
    configuracao = relationship("UserConfig", back_populates="dono", uselist=False, cascade="all, delete-orphan")

class SavedJob(Base):
    __tablename__ = "saved_jobs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filtro_id = Column(Integer, ForeignKey("search_filters.id", ondelete="CASCADE"), index=True, nullable=True) 
    tipo_busca = Column(String, default="Vagas") 
    scraper = Column(String, default="Desconhecido", index=True)
    empresa = Column(String, default="Confidencial") 
    titulo = Column(String, nullable=False)
    link = Column(String, nullable=False)
    data_publicacao = Column(String)
    local = Column(String)
    formato = Column(String)
    data_salva = Column(DateTime, default=datetime.utcnow, index=True)
    
    dono = relationship("User", back_populates="vagas_salvas")
    radar = relationship("SearchFilter")

class SearchFilter(Base):
    __tablename__ = "search_filters"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tipo_busca = Column(String, default="Vagas") 
    nome_filtro = Column(String, nullable=False)
    termos = Column(String, nullable=False)
    palavras_proibidas = Column(String, default="") 
    localizacao = Column(String)
    formato = Column(String)
    scrapers = Column(String)
    max_dias = Column(Integer, default=30)
    timer_ativo = Column(Boolean, default=False, index=True)
    intervalo_timer = Column(Integer, default=60) 
    ativo = Column(Boolean, default=True)
    ultima_varredura = Column(DateTime, nullable=True)
    
    dono = relationship("User", back_populates="filtros")

class AppConfig(Base):
    __tablename__ = "app_configs"
    chave = Column(String, primary_key=True, index=True)
    valor = Column(String, nullable=False)

class UserConfig(Base):
    __tablename__ = "user_configs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    auto_limpeza_ativa = Column(Boolean, default=False)
    auto_limpeza_dias = Column(Integer, default=30) 
    receber_emails = Column(Boolean, default=True) 
    
    dono = relationship("User", back_populates="configuracao")

if __name__ == "__main__":
    print("⏳ Atualizando tabelas no PostgreSQL (Otimizado com Índices)...")
    Base.metadata.drop_all(bind=engine) 
    Base.metadata.create_all(bind=engine) 
    
    print("⏳ Injetando usuário Admin e Configurações Individuais dos Scrapers...")
    db = SessionLocal()
    try:
        scrapers_lista = ["Empregos", "InfoJobs", "Gupy", "LinkedIn", "Remotar", "PCI", "C_Brasil"]
        for s in scrapers_lista:
            db.add(AppConfig(chave=f"headless_{s}", valor="true"))
        
        senha_pura = os.getenv("ADMIN_PASSWORD", "mudar_senha_imediatamente")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@vagaz.com")
        
        senha_blindada = bcrypt.hashpw(senha_pura.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        admin_user = User(
            nome="Administrador",
            email=admin_email,
            senha_hash=senha_blindada, 
            is_admin=True
        )
        db.add(admin_user)
        
        db.commit()
        print("✅ Dados do Admin e Configs injetados com sucesso!")
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao injetar dados: {e}")
    finally:
        db.close()
        
    print("✅ SUCESSO! Banco de Dados atualizado, indexado e pronto!")