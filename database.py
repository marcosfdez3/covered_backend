# database.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Configuración para PostgreSQL
# Formato: postgresql://usuario:password@host:puerto/nombre_bd
DATABASE_URL = "postgresql://postgres@localhost:5432/factcheck_db"

# Render usa postgres:// pero SQLAlchemy necesita postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ConsultaNoticia(Base):
    __tablename__ = "consultas_noticias"
    
    id = Column(Integer, primary_key=True, index=True)
    texto_consultado = Column(Text, nullable=False)
    resultado = Column(String(255), nullable=False)
    fecha_consulta = Column(DateTime, default=datetime.utcnow)
    url_consulta = Column(String(500), nullable=True)
    respuesta_api = Column(Text)
    usuario_id = Column(String(100), nullable=True)  # Para futura autenticación

# Crear las tablas
def create_tables():
    Base.metadata.create_all(bind=engine)

# Dependency para FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()