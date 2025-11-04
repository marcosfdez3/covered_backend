# database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Obtener DATABASE_URL desde variables de entorno
DATABASE_URL = os.getenv("DATABASE_URL")

# Si la URL empieza con postgres://, cambiar a postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"🔗 Conectando a: {DATABASE_URL.split('@')[1] if DATABASE_URL else 'NO URL'}")

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
    usuario_id = Column(String(100), nullable=True)

def create_tables():
    try:
        print("🟡 Creando tablas...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas creadas exitosamente")
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        # No lances excepción, permite que la app continúe
        pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()