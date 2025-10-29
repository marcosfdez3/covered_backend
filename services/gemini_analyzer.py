# services/gemini_analyzer.py
from google import genai
import json
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Cliente global
_client = None

def get_client():
    """Obtener cliente Gemini (singleton)"""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("❌ GEMINI_API_KEY no configurada")
        _client = genai.Client(api_key=api_key)
    return _client

def analizar_con_gemini(texto: str) -> Dict[str, Any]:
    """
    Analiza una afirmación usando Google Gemini (nueva librería)
    """
    try:
        client = get_client()
        
        prompt = f"""
        Eres un verificador de hechos profesional. Analiza esta afirmación y responde EXCLUSIVAMENTE en formato JSON válido:
        
        {{
            "veredicto": "probablemente_verdadero|probablemente_falso|mixto|no_verificable",
            "confianza": 1-10,
            "razonamiento": "explicación breve de tu análisis",
            "sesgos_detectados": ["lista de posibles sesgos"],
            "recomendacion": "recomendación al usuario",
            "elementos_clave": ["puntos importantes identificados"]
        }}
        
        INSTRUCCIONES IMPORTANTES:
        - Sé objetivo y basado en hechos conocidos
        - Si la afirmación contiene elementos tanto verdaderos como falsos, usa "mixto"
        - Si hace falta contexto específico, usa "no_verificable"
        - Identifica lenguaje emocional o sensacionalista
        
        Afirmación a verificar: "{texto}"
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",  # Modelo más rápido y económico
            contents=prompt
        )
        
        response_text = response.text.strip()
        logger.info(f"📨 Respuesta Gemini recibida: {response_text[:100]}...")
        
        # Limpiar respuesta
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        resultado = json.loads(response_text)
        
        return {
            "success": True,
            "fuente": "gemini",
            "resultado": resultado["veredicto"],
            "confianza": resultado["confianza"],
            "detalle": {
                "razonamiento": resultado["razonamiento"],
                "sesgos_detectados": resultado["sesgos_detectados"],
                "recomendacion": resultado["recomendacion"],
                "elementos_clave": resultado["elementos_clave"]
            }
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parseando JSON de Gemini: {e}")
        return {
            "success": False,
            "error": f"Error parseando respuesta: {str(e)}",
            "respuesta_cruda": response_text if 'response_text' in locals() else None
        }
    except Exception as e:
        logger.error(f"❌ Error con Gemini API: {e}")
        return {
            "success": False,
            "error": f"Error con Gemini: {str(e)}"
        }