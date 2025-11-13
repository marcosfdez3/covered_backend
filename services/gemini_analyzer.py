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
    Analiza una afirmación/pregunta usando Google Gemini con búsqueda web opcional
    """
    try:
        client = get_client()
        
        prompt = f"""
Eres un asistente de verificación de hechos. Analiza el siguiente contenido:

CONTENIDO: "{texto}"

INSTRUCCIONES SEGÚN EL TIPO:

🔹 SI ES UNA PREGUNTA (contiene ¿?, 'es', 'son', 'fue', 'ha', 'han', 'cómo', 'cuándo', 'dónde', 'por qué', 'quién', 'cuál', etc.):
   - RESPONDE la pregunta basándote en hechos verificados y conocimiento actual
   - Proporciona contexto e información relevante
   - Si es sobre eventos actuales, indica la fecha de referencia
   - Si no tienes información suficiente, sé honesto sobre las limitaciones

🔹 SI ES UNA AFIRMACIÓN/NOTICIA:
   - VERIFICA su veracidad usando fuentes confiables
   - Identifica posibles sesgos o desinformación
   - Evalúa la coherencia lógica y consistencia

🔹 SI ES UNA URL:
   - Analiza el contenido del enlace

PARA TODOS LOS CASOS:
- Considera el contexto y la fecha actual
- Identifica lenguaje sensacionalista o emocional
- Sé objetivo y basado en hechos
- Proporciona recomendaciones útiles al usuario

FECHA ACTUAL: {datetime.now().strftime('%d de %B de %Y')}

Respuesta EXCLUSIVAMENTE en formato JSON válido:
{{
    "tipo_contenido": "pregunta|afirmacion|url",
    "veredicto": "probablemente_verdadero|probablemente_falso|mixto|no_verificable|respondido",
    "confianza": 1-10,
    "razonamiento": "explicación completa con contexto y hechos relevantes",
    "respuesta_directa": "respuesta clara y directa a la pregunta o verificación",
    "sesgos_detectados": ["lista de posibles sesgos identificados"],
    "elementos_clave": ["puntos importantes identificados"],
    "fecha_analisis": "{datetime.now().strftime('%Y-%m-%d')}",
    "recomendacion": "recomendación específica al usuario"
}}

EJEMPLOS:

Para pregunta "¿Ha dimitido el presidente X?":
{{
    "tipo_contenido": "pregunta",
    "veredicto": "respondido",
    "confianza": 8,
    "razonamiento": "Basado en información disponible hasta la fecha actual...",
    "respuesta_directa": "No, el presidente X no ha dimitido según las últimas informaciones...",
    "sesgos_detectados": [],
    "elementos_clave": ["estado actual del cargo", "fuentes de información"],
    "fecha_analisis": "2024-12-19",
    "recomendacion": "Consultar fuentes oficiales para confirmación"
}}

Para afirmación "El presidente X ha dimitido":
{{
    "tipo_contenido": "afirmacion", 
    "veredicto": "probablemente_falso",
    "confianza": 7,
    "razonamiento": "No hay evidencia de que el presidente X haya dimitido...",
    "respuesta_directa": "Esta afirmación parece ser falsa según la información disponible",
    "sesgos_detectados": ["posible desinformación"],
    "elementos_clave": ["falta de fuentes verificadas", "contradicción con información oficial"],
    "fecha_analisis": "2024-12-19",
    "recomendacion": "Verificar con medios oficiales antes de compartir"
}}
"""
        
        # Configurar generación
        generation_config = {
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 40,
        }
        
        # Intentar usar búsqueda web si está disponible
        if usar_busqueda:
            try:
                # Para Gemini 1.5 Pro con búsqueda web
                response = client.models.generate_content(
                    model="gemini-1.5-pro",
                    contents=prompt,
                    config=generation_config,
                    tools=[{"google_search_retrieval": {}}]
                )
            except Exception as e:
                logger.warning(f"Búsqueda web no disponible, usando modelo estándar: {e}")
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt,
                    config=generation_config
                )
        else:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
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
        response_text = response_text.strip()
        
        resultado = json.loads(response_text)
        
        # Preparar respuesta según el tipo de contenido
        if resultado.get("tipo_contenido") == "pregunta":
            resultado_final = "respondido"
        else:
            resultado_final = resultado["veredicto"]
        
        return {
            "success": True,
            "fuente": "gemini",
            "resultado": resultado_final,
            "confianza": resultado["confianza"],
            "detalle": {
                "tipo_contenido": resultado.get("tipo_contenido", "afirmacion"),
                "razonamiento": resultado["razonamiento"],
                "respuesta_directa": resultado.get("respuesta_directa", resultado["razonamiento"]),
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