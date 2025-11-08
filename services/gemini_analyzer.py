# services/gemini_analyzer.py
from google import genai
import json
import os
from typing import Dict, Any
import logging
from datetime import datetime

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

def analizar_con_gemini(texto: str, usar_busqueda: bool = True) -> Dict[str, Any]:
    """
    Analiza una afirmación usando Google Gemini con búsqueda web opcional
    """
    try:
        client = get_client()
        
        prompt = f"""
        Eres un verificador de hechos profesional. Analiza esta afirmación y responde EXCLUSIVAMENTE en formato JSON válido:
        
        {{
            "veredicto": "probablemente_verdadero|probablemente_falso|mixto|no_verificable",
            "confianza": 1-10,
            "razonamiento": "explicación breve de tu análisis basado en información disponible",
            "sesgos_detectados": ["lista de posibles sesgos"],
            "recomendacion": "recomendación al usuario",
            "elementos_clave": ["puntos importantes identificados"],
            "fecha_analisis": "{datetime.now().strftime('%Y-%m-%d')}"
        }}
        
        INSTRUCCIONES CRÍTICAS:
        1. Para noticias recientes o eventos actuales, usa la información más actualizada disponible
        2. Si la afirmación menciona fechas futuras, analiza su plausibilidad basándote en patrones históricos
        3. Considera el contexto y la coherencia lógica
        4. Identifica lenguaje sensacionalista o emocional
        5. Si es una noticia, analiza fuentes y posibles sesgos
        
        FECHA ACTUAL: {datetime.now().strftime('%d de %B de %Y')}
        
        Afirmación a verificar: "{texto}"
        """
        
        # Configurar búsqueda web si está disponible y se solicita
        generation_config = {
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 40,
        }
        
        # Intentar usar búsqueda web si está disponible
        if usar_busqueda:
            try:
                # Para Gemini 1.5 o superior con búsqueda web
                response = client.models.generate_content(
                    model="gemini-1.5-flash",  # Modelo que soporta búsqueda web
                    contents=prompt,
                    config=generation_config,
                    tools=[{"google_search_retrieval": {}}]
                )
            except Exception as e:
                logger.warning(f"Búsqueda web no disponible, usando modelo estándar: {e}")
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=generation_config
                )
        else:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=generation_config
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
                "elementos_clave": resultado["elementos_clave"],
                "fecha_analisis": resultado.get("fecha_analisis", datetime.now().strftime('%Y-%m-%d'))
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