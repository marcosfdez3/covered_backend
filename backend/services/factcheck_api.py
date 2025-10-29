# services/factcheck_api.py
import requests
import json
from datetime import datetime
from sqlalchemy.orm import Session

FAKE_CHECK_API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
API_KEY = "AIzaSyBuSalirZWdRh8CaIaDNfo3aEU61pIQCBo"

def verificar_api(texto: str, db: Session, url: str = None, usuario_id: str = None):
    from database import ConsultaNoticia
    
    # Guardar la consulta antes de hacer la verificación
    consulta = ConsultaNoticia(
        texto_consultado=texto,
        url_consulta=url,
        usuario_id=usuario_id,
        fecha_consulta=datetime.utcnow()
    )
    
    try:
        params = {"query": texto, "key": API_KEY}
        response = requests.get(FAKE_CHECK_API, params=params, timeout=30)
        data = response.json()
        
        if data.get("claims"):
            resultado = "verificado"
            detalle = data["claims"][0]
            # Simplificar respuesta para móvil
            detalle_movil = {
                "claim": detalle.get("text", ""),
                "fuente": detalle.get("claimant", "Fuente desconocida"),
                "calificacion": detalle.get("claimReview", [{}])[0].get("textualRating", "No disponible"),
                "url_revision": detalle.get("claimReview", [{}])[0].get("url", "")
            }
        else:
            resultado = "no_encontrado"
            detalle_movil = None
        
        consulta.resultado = resultado
        consulta.respuesta_api = str(detalle_movil) if detalle_movil else "Sin resultados"
        
        db.add(consulta)
        db.commit()
        db.refresh(consulta)
        
        return {
            "success": True,
            "resultado": resultado,
            "detalle": detalle_movil,
            "consulta_id": consulta.id,
            "fecha_procesamiento": consulta.fecha_consulta.isoformat()
        }
    
    except Exception as e:
        consulta.resultado = "error"
        consulta.respuesta_api = f"Error: {str(e)}"
        db.add(consulta)
        db.commit()
        return {
            "success": False,
            "error": str(e),
            "consulta_id": consulta.id
        }