# main.py
import os
from dotenv import load_dotenv

# 🔥 CARGAR VARIABLES DE ENTORNO AL INICIO - ANTES DE CUALQUIER IMPORT
load_dotenv()

# Verificar variables críticas
if not os.getenv("GEMINI_API_KEY"):
    print("❌ ERROR: GEMINI_API_KEY no encontrada")
    print("💡 Verifica tu archivo .env")
    exit(1)

print(f"✅ API Key cargada: {os.getenv('GEMINI_API_KEY')[:20]}...")

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from typing import Optional

# Importar modelos y servicios DESPUÉS de cargar .env
from models.noticia import Noticia
from services.factcheck_api import verificar_api
from services.url_extractor import extraer_texto_desde_url
from services.hybrid_verifier import (
    verificar_hibrido, 
    obtener_estadisticas_hibridas,
    limpiar_consultas_antiguas
)
from database import get_db, create_tables

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - se ejecuta al iniciar la aplicación
    print("🟡 Iniciando aplicación FactCheck API...")
    create_tables()
    print("✅ Tablas de la base de datos creadas/verificadas")
    print("🚀 Sistema híbrido FactCheck + Gemini AI cargado")
    yield
    # Shutdown - se ejecuta al apagar la aplicación
    print("🔴 Apagando aplicación...")

app = FastAPI(
    title="FactCheck API",
    description="API de verificación de noticias con sistema híbrido (FactCheck + IA)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ENDPOINTS PRINCIPALES ====================

@app.post("/verificar", tags=["Verificación"])
def verificar_noticia(noticia: Noticia, db: Session = Depends(get_db)):
    """Endpoint original - Solo FactCheck tradicional"""
    texto = noticia.texto
    
    if noticia.url:
        try:
            texto_extraido = extraer_texto_desde_url(noticia.url)
            texto = f"{texto} {texto_extraido}" if texto else texto_extraido
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al extraer texto de la URL: {str(e)}")
    
    resultado = verificar_api(
        texto=texto, 
        db=db, 
        url=noticia.url,
        usuario_id=noticia.usuario_id
    )
    return resultado

@app.post("/verificar/v2", tags=["Verificación Híbrida"])
def verificar_hibrido_endpoint(
    noticia: Noticia, 
    db: Session = Depends(get_db),
    modo: str = Query("auto", description="Modo de verificación"),
    use_ia: bool = Query(True, description="Usar IA en el análisis")
):
    """NUEVO - Sistema Híbrido FactCheck + Gemini AI"""
    texto = noticia.texto
    
    if noticia.url:
        try:
            texto_extraido = extraer_texto_desde_url(noticia.url)
            texto = f"{texto} {texto_extraido}" if texto else texto_extraido
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al extraer texto de la URL: {str(e)}")
    
    resultado = verificar_hibrido(
        texto=texto,
        db=db,
        url=noticia.url,
        usuario_id=noticia.usuario_id,
        modo=modo,
        use_ia=use_ia
    )
    return resultado

@app.post("/verificar/movil", tags=["Móvil"])
def verificar_noticia_movil(noticia: Noticia, db: Session = Depends(get_db)):
    """Endpoint optimizado para aplicaciones móviles"""
    texto = noticia.texto
    
    if noticia.url:
        try:
            texto_extraido = extraer_texto_desde_url(noticia.url)
            texto = f"{texto} {texto_extraido}" if texto else texto_extraido
        except Exception as e:
            return {
                "success": False,
                "error": f"Error al procesar URL: {str(e)}"
            }
    
    resultado = verificar_hibrido(
        texto=texto,
        db=db,
        url=noticia.url,
        usuario_id=noticia.usuario_id,
        modo="auto",
        use_ia=True
    )
    return resultado

# ==================== GESTIÓN DE CONSULTAS ====================

@app.get("/historial", tags=["Historial"])
def obtener_historial(
    db: Session = Depends(get_db), 
    limit: int = Query(10, le=100),
    offset: int = Query(0),
    usuario_id: Optional[str] = Query(None)
):
    from database import ConsultaNoticia
    
    query = db.query(ConsultaNoticia)
    
    if usuario_id:
        query = query.filter(ConsultaNoticia.usuario_id == usuario_id)
    
    consultas = query.order_by(ConsultaNoticia.fecha_consulta.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()
    
    total = query.count()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "usuario_id": usuario_id,
        "consultas": [
            {
                "id": c.id,
                "texto": c.texto_consultado[:100] + "..." if len(c.texto_consultado) > 100 else c.texto_consultado,
                "resultado": c.resultado,
                "url": c.url_consulta,
                "fecha": c.fecha_consulta.isoformat(),
                "usuario_id": c.usuario_id
            }
            for c in consultas
        ]
    }

@app.get("/consulta/{consulta_id}", tags=["Historial"])
def obtener_consulta(consulta_id: int, db: Session = Depends(get_db)):
    from database import ConsultaNoticia
    
    consulta = db.query(ConsultaNoticia).filter(ConsultaNoticia.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    
    return {
        "id": consulta.id,
        "texto_consultado": consulta.texto_consultado,
        "resultado": consulta.resultado,
        "url_consulta": consulta.url_consulta,
        "fecha_consulta": consulta.fecha_consulta.isoformat(),
        "usuario_id": consulta.usuario_id,
        "respuesta_api": consulta.respuesta_api
    }

# ==================== ESTADÍSTICAS ====================

@app.get("/estadisticas", tags=["Estadísticas"])
def obtener_estadisticas(db: Session = Depends(get_db)):
    from database import ConsultaNoticia
    from sqlalchemy import func
    
    stats = db.query(
        func.count(ConsultaNoticia.id).label("total_consultas"),
        func.count(func.distinct(ConsultaNoticia.usuario_id)).label("usuarios_unicos"),
        func.avg(func.length(ConsultaNoticia.texto_consultado)).label("longitud_promedio")
    ).first()
    
    return {
        "total_consultas": stats.total_consultas,
        "usuarios_unicos": stats.usuarios_unicos,
        "longitud_promedio_texto": round(stats.longitud_promedio or 0, 2)
    }

@app.get("/estadisticas/v2", tags=["Estadísticas"])
def obtener_estadisticas_avanzadas(db: Session = Depends(get_db)):
    return obtener_estadisticas_hibridas(db)

# ==================== ADMINISTRACIÓN ====================

@app.delete("/admin/limpiar", tags=["Administración"])
def limpiar_consultas_antiguas_endpoint(
    db: Session = Depends(get_db),
    dias: int = Query(30, description="Eliminar consultas más antiguas que X días")
):
    if dias < 1:
        raise HTTPException(status_code=400, detail="El número de días debe ser al menos 1")
    
    resultado = limpiar_consultas_antiguas(db, dias)
    return resultado

@app.post("/admin/verificar-ia", tags=["Administración"])
def verificar_estado_ia():
    try:
        from services.gemini_analyzer import analizar_con_gemini
        
        resultado = analizar_con_gemini("Test de conexión")
        
        if resultado.get("success"):
            return {
                "status": "healthy",
                "servicio_ia": "gemini",
                "mensaje": "✅ Servicio de IA funcionando correctamente"
            }
        else:
            return {
                "status": "error",
                "servicio_ia": "gemini",
                "error": resultado.get("error", "Error desconocido"),
                "mensaje": "❌ Error en el servicio de IA"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "servicio_ia": "gemini",
            "error": str(e),
            "mensaje": "❌ No se pudo conectar con el servicio de IA"
        }

# ==================== HEALTH & INFO ====================

@app.get("/", tags=["Información"])
def read_root():
    return {
        "message": "🚀 FactCheck API v2.0 funcionando correctamente",
        "version": "2.0.0",
        "sistema": "Híbrido (FactCheck + Gemini AI)",
        "endpoints_principales": {
            "verificacion_tradicional": "/verificar",
            "verificacion_hibrida": "/verificar/v2",
            "verificacion_movil": "/verificar/movil",
            "historial": "/historial",
            "estadisticas": "/estadisticas/v2",
            "documentacion": "/docs"
        }
    }

@app.get("/health", tags=["Salud"])
def health_check():
    return {
        "status": "healthy",
        "service": "factcheck-api",
        "version": "2.0.0"
    }

@app.get("/info", tags=["Información"])
def info_completa():
    return {
        "nombre": "FactCheck API",
        "version": "2.0.0",
        "descripcion": "Sistema de verificación de noticias con IA",
        "tecnologias": {
            "backend": "FastAPI",
            "base_datos": "PostgreSQL",
            "ia": "Google Gemini",
            "factcheck": "Google FactCheck API"
        }
    }

@app.get("/status", tags=["Salud"])
def status_detallado(db: Session = Depends(get_db)):
    from database import ConsultaNoticia
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    try:
        stats = db.query(
            func.count(ConsultaNoticia.id).label("total_consultas"),
            func.count(func.distinct(ConsultaNoticia.usuario_id)).label("usuarios_unicos")
        ).first()
        
        hace_24_horas = datetime.utcnow() - timedelta(hours=24)
        consultas_24h = db.query(ConsultaNoticia)\
            .filter(ConsultaNoticia.fecha_consulta >= hace_24_horas)\
            .count()
        
        estado_ia = "unknown"
        try:
            from services.gemini_analyzer import analizar_con_gemini
            test_result = analizar_con_gemini("test de conexión")
            estado_ia = "healthy" if test_result.get("success") else "error"
        except Exception as e:
            estado_ia = f"error: {str(e)}"
        
        return {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "status": "connected",
                "total_consultas": stats.total_consultas or 0,
                "usuarios_unicos": stats.usuarios_unicos or 0,
                "consultas_24h": consultas_24h
            },
            "services": {
                "factcheck_api": "healthy",
                "gemini_ai": estado_ia,
                "url_extractor": "healthy"
            },
            "system": {
                "version": "2.0.0"
            }
        }
        
    except Exception as e:
        return {
            "status": "degraded",
            "error": f"Error obteniendo status: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

# ==================== EJECUCIÓN DIRECTA ====================

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando FactCheck API en modo desarrollo...")
    print("📚 Documentación disponible en: http://localhost:8000/docs")
    print("🔍 Health check en: http://localhost:8000/health")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True
    )