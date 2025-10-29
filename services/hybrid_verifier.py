# services/hybrid_verifier.py
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verificar_hibrido(
    texto: str, 
    db: Session, 
    url: str = None, 
    usuario_id: str = None, 
    modo: str = "auto",
    use_ia: bool = True
) -> Dict[str, Any]:
    """
    Sistema híbrido de verificación que combina FactCheck tradicional + Gemini AI
    """
    
    # Guardar en base de datos
    from database import ConsultaNoticia
    
    consulta = ConsultaNoticia(
        texto_consultado=texto,
        url_consulta=url,
        usuario_id=usuario_id,
        fecha_consulta=datetime.utcnow(),
        resultado="procesando"
    )
    
    try:
        db.add(consulta)
        db.commit()
        db.refresh(consulta)
        
        logger.info(f"🔍 Iniciando verificación híbrida - Modo: {modo}, Texto: {texto[:100]}...")
        
        # Si IA está desactivada, usar solo factcheck
        if not use_ia:
            modo = "solo_factcheck"
        
        # ESTRATEGIA AUTO: Decidir basado en el tipo de consulta
        if modo == "auto":
            modo = _elegir_modo_inteligente(texto)
            logger.info(f"🤖 Modo auto seleccionado: {modo}")
        
        # EJECUCIÓN SEGÚN MODO
        if modo == "factcheck_first":
            resultado = _estrategia_factcheck_primero(texto, db)
        elif modo == "ia_first":
            resultado = _estrategia_ia_primero(texto)
        elif modo == "solo_ia":
            resultado = _estrategia_solo_ia(texto)
        elif modo == "solo_factcheck":
            resultado = _estrategia_solo_factcheck(texto, db)
        else:  # auto
            resultado = _estrategia_auto(texto, db)
        
        # Guardar resultados en BD
        consulta.resultado = resultado.get("resultado_final", "procesado")
        consulta.respuesta_api = _preparar_respuesta_para_bd(resultado)
        
        db.add(consulta)
        db.commit()
        db.refresh(consulta)
        
        # ✅ RESPUESTA MEJORADA CON RAZONAMIENTO
        respuesta = {
            "success": True,
            "consulta_id": consulta.id,
            "fecha_procesamiento": consulta.fecha_consulta.isoformat(),
            "modo_utilizado": modo,
            "texto_consultado": texto[:500] + "..." if len(texto) > 500 else texto,
            "resultado": resultado.get("resultado_final", "error"),
            "confianza": resultado.get("confianza", 0),
            "fuente_primaria": resultado.get("fuente_primaria", "desconocida"),
            "tiene_verificacion_oficial": resultado.get("tiene_verificacion_oficial", False),
            "recomendacion": resultado.get("recomendacion", ""),
            # ✅ NUEVO: Razonamiento siempre disponible
            "razonamiento": _obtener_razonamiento(resultado)
        }
        
        # ✅ Mantener detalles completos para compatibilidad
        if resultado.get("detalle_ia"):
            respuesta["analisis_ia"] = resultado["detalle_ia"]
        
        if resultado.get("detalle_factcheck"):
            respuesta["verificacion_factcheck"] = resultado["detalle_factcheck"]
        
        logger.info(f"✅ Verificación completada - Resultado: {resultado.get('resultado_final')}")
        return respuesta
        
    except Exception as e:
        logger.error(f"❌ Error en verificación híbrida: {str(e)}")
        
        consulta.resultado = "error"
        consulta.respuesta_api = f"Error en verificación híbrida: {str(e)}"
        db.add(consulta)
        db.commit()
        
        return {
            "success": False,
            "error": str(e),
            "consulta_id": consulta.id if 'consulta' in locals() else None,
            "modo_utilizado": modo,
            "resultado": "error",
            "confianza": 0,
            "razonamiento": f"Error en el análisis: {str(e)}"  # ✅ Razonamiento incluso en error
        }

def _obtener_razonamiento(resultado: Dict[str, Any]) -> str:
    """
    Extrae el razonamiento de la respuesta, priorizando diferentes fuentes
    """
    # 1. Razonamiento directo de IA
    if resultado.get("detalle_ia") and resultado["detalle_ia"].get("razonamiento"):
        return resultado["detalle_ia"]["razonamiento"]
    
    # 2. Razonamiento de FactCheck
    if resultado.get("detalle_factcheck") and isinstance(resultado["detalle_factcheck"], dict):
        if resultado["detalle_factcheck"].get("razonamiento"):
            return resultado["detalle_factcheck"]["razonamiento"]
    
    # 3. Razonamiento de análisis complementario
    if resultado.get("analisis_ia_complementario") and resultado["analisis_ia_complementario"].get("razonamiento"):
        return resultado["analisis_ia_complementario"]["razonamiento"]
    
    # 4. Razonamiento por defecto basado en el resultado
    resultado_final = resultado.get("resultado_final", "desconocido")
    razonamientos_por_defecto = {
        "verificado": "Esta información ha sido verificada por fuentes oficiales de fact-checking.",
        "probablemente_verdadero": "El análisis sugiere que esta afirmación es probablemente verdadera basándose en información disponible.",
        "probablemente_falso": "El análisis indica que esta afirmación contiene elementos cuestionables o inexactos.",
        "mixto": "La afirmación contiene elementos tanto verdaderos como falsos. Se requiere verificación adicional.",
        "no_encontrado": "No se encontraron verificaciones específicas para esta afirmación.",
        "no_se_puede_verificar": "No hay suficiente información disponible para verificar esta afirmación.",
        "error": "No se pudo completar el análisis debido a un error técnico."
    }
    
    return razonamientos_por_defecto.get(resultado_final, "Análisis completado.")

def _elegir_modo_inteligente(texto: str) -> str:
    """
    Decide automáticamente la mejor estrategia basada en el texto
    """
    texto_lower = texto.lower().strip()
    
    # Casos para FactCheck primero (afirmaciones específicas, noticias virales)
    factcheck_keywords = [
        "viral", "fake news", "noticia falsa", "desinformación", "bulo",
        "política", "elecciones", "covid", "vacuna", "salud pública", "gobierno",
        "presidente", "ministro", "ley", "decreto", "twitter", "facebook", "whatsapp",
        "compartido", "cadena", "forwarded"
    ]
    
    # Casos para IA primero (preguntas, análisis, consejos)
    ia_keywords = [
        "¿cómo", "por qué", "cuál es", "qué significa", "es bueno", "es malo",
        "consejo", "recomendación", "opinión", "análisis", "beneficios", "riesgos",
        "funciona", "efectivo", "seguro", "peligroso", "mito", "realidad"
    ]
    
    # Preguntas directas
    if texto_lower.startswith(('¿', '?')) or any(texto_lower.startswith(p) for p in ['es ', 'son ', 'fue ', 'fueron ']):
        return "ia_first"
    
    # Textos muy largos (probablemente artículos completos)
    if len(texto.split()) > 100:
        return "factcheck_first"
    
    # Textos muy cortos (búsquedas simples)
    if len(texto.split()) < 5:
        return "ia_first"
    
    # Verificar keywords
    if any(keyword in texto_lower for keyword in factcheck_keywords):
        return "factcheck_first"
    elif any(keyword in texto_lower for keyword in ia_keywords):
        return "ia_first"
    
    # Por defecto: factcheck primero (más confiable cuando hay resultados)
    return "factcheck_first"

def _estrategia_factcheck_primero(texto: str, db: Session) -> Dict[str, Any]:
    """Primero intenta FactCheck, luego IA si no encuentra"""
    logger.info("🔄 Ejecutando estrategia: FactCheck primero")
    
    # 1. FactCheck tradicional
    from services.factcheck_api import verificar_api
    resultado_fc = verificar_api(texto, db)
    
    if resultado_fc.get("success") and resultado_fc.get("resultado") == "verificado":
        logger.info("✅ FactCheck encontró verificación existente")
        return {
            "fuente_primaria": "factcheck",
            "veredicto_final": resultado_fc["resultado"],
            "confianza": 9,
            "detalle_factcheck": resultado_fc.get("detalle"),
            "resultado_final": "verificado",
            "tiene_verificacion_oficial": True,
            "recomendacion": "Esta afirmación ha sido verificada por fuentes oficiales de fact-checking."
        }
    
    # 2. Fallback a Gemini AI
    logger.info("🔍 FactCheck no encontró resultados, usando Gemini AI...")
    resultado_ia = _analizar_con_gemini(texto)
    
    if resultado_ia["success"]:
        logger.info(f"🤖 Gemini AI completó análisis: {resultado_ia['resultado']}")
        return {
            "fuente_primaria": "gemini_fallback",
            "veredicto_final": resultado_ia["resultado"],
            "confianza": resultado_ia.get("confianza", 5),
            "detalle_ia": resultado_ia.get("detalle", {}),
            "factcheck_previo": "no_encontrado",
            "resultado_final": resultado_ia["resultado"],
            "tiene_verificacion_oficial": False,
            "recomendacion": "Análisis basado en IA - verificar con fuentes adicionales."
        }
    
    # 3. Si todo falla
    logger.warning("⚠️ Ambos métodos fallaron")
    return {
        "fuente_primaria": "error",
        "veredicto_final": "no_se_puede_verificar",
        "confianza": 0,
        "resultado_final": "error",
        "tiene_verificacion_oficial": False,
        "recomendacion": "No se pudo verificar la afirmación. Intente con otras fuentes."
    }

def _estrategia_ia_primero(texto: str) -> Dict[str, Any]:
    """Usa IA primero para análisis contextual"""
    logger.info("🔄 Ejecutando estrategia: IA primero")
    
    resultado_ia = _analizar_con_gemini(texto)
    
    if resultado_ia["success"]:
        logger.info(f"🤖 Gemini AI completó análisis: {resultado_ia['resultado']}")
        return {
            "fuente_primaria": "gemini",
            "veredicto_final": resultado_ia["resultado"],
            "confianza": resultado_ia.get("confianza", 5),
            "detalle_ia": resultado_ia.get("detalle", {}),
            "resultado_final": resultado_ia["resultado"],
            "tiene_verificacion_oficial": False,
            "recomendacion": "Análisis basado en IA - considerar verificar con fuentes oficiales."
        }
    
    logger.warning("⚠️ Gemini AI falló")
    return {
        "fuente_primaria": "error",
        "veredicto_final": "no_se_puede_verificar",
        "confianza": 0,
        "resultado_final": "error",
        "tiene_verificacion_oficial": False
    }

def _estrategia_solo_ia(texto: str) -> Dict[str, Any]:
    """Solo usa IA (para comparación o casos específicos)"""
    logger.info("🔄 Ejecutando estrategia: Solo IA")
    return _estrategia_ia_primero(texto)

def _estrategia_solo_factcheck(texto: str, db: Session) -> Dict[str, Any]:
    """Solo usa FactCheck tradicional"""
    logger.info("🔄 Ejecutando estrategia: Solo FactCheck")
    
    from services.factcheck_api import verificar_api
    resultado_fc = verificar_api(texto, db)
    
    if resultado_fc.get("success"):
        return {
            "fuente_primaria": "factcheck",
            "veredicto_final": resultado_fc["resultado"],
            "confianza": 8 if resultado_fc["resultado"] == "verificado" else 5,
            "detalle_factcheck": resultado_fc.get("detalle"),
            "resultado_final": resultado_fc["resultado"],
            "tiene_verificacion_oficial": resultado_fc["resultado"] == "verificado",
            "recomendacion": "Resultado basado en verificaciones existentes."
        }
    
    return {
        "fuente_primaria": "factcheck",
        "veredicto_final": "no_encontrado",
        "confianza": 0,
        "resultado_final": "no_encontrado",
        "tiene_verificacion_oficial": False,
        "recomendacion": "No se encontraron verificaciones existentes para esta afirmación."
    }

def _estrategia_auto(texto: str, db: Session) -> Dict[str, Any]:
    """Estrategia balanceada que usa ambos sistemas de forma inteligente"""
    logger.info("🔄 Ejecutando estrategia: Auto (balanceada)")
    
    from services.factcheck_api import verificar_api
    resultado_fc = verificar_api(texto, db)
    resultado_ia = _analizar_con_gemini(texto)
    
    # Combinar resultados inteligentemente
    return _combinar_resultados(resultado_fc, resultado_ia)

def _combinar_resultados(factcheck: Dict, ia: Dict) -> Dict[str, Any]:
    """Combina resultados de FactCheck e IA inteligentemente"""
    
    fc_exitoso = factcheck.get("success", False)
    ia_exitosa = ia.get("success", False)
    
    # Si FactCheck encontró verificación, priorizar (alta confianza)
    if fc_exitoso and factcheck.get("resultado") == "verificado":
        logger.info("✅ Combinación: Priorizando FactCheck verificado")
        return {
            "fuente_primaria": "factcheck",
            "veredicto_final": "verificado",
            "confianza": 9,
            "detalle_factcheck": factcheck.get("detalle"),
            "analisis_ia_complementario": ia.get("detalle") if ia_exitosa else None,
            "resultado_final": "verificado",
            "tiene_verificacion_oficial": True,
            "recomendacion": "Verificación confirmada por fuentes oficiales de fact-checking."
        }
    
    # Si IA tiene alta confianza y FactCheck no encontró nada
    if ia_exitosa and ia.get("confianza", 0) >= 7:
        logger.info("✅ Combinación: Usando IA con alta confianza")
        veredicto_ia = ia["resultado"]
        return {
            "fuente_primaria": "gemini",
            "veredicto_final": veredicto_ia,
            "confianza": ia["confianza"],
            "detalle_ia": ia["detalle"],
            "factcheck_previo": factcheck.get("resultado") if fc_exitoso else "no_encontrado",
            "resultado_final": veredicto_ia,
            "tiene_verificacion_oficial": False,
            "recomendacion": "Análisis basado en IA con alta confianza - considerar verificación adicional."
        }
    
    # Si ambos métodos coinciden en el veredicto
    if (fc_exitoso and ia_exitosa and 
        _veredictos_coinciden(factcheck.get("resultado"), ia.get("resultado"))):
        logger.info("✅ Combinación: Ambos métodos coinciden")
        veredicto_combinado = _traducir_veredicto_combinado(factcheck.get("resultado"), ia.get("resultado"))
        return {
            "fuente_primaria": "combinado",
            "veredicto_final": veredicto_combinado,
            "confianza": max(factcheck.get("confianza", 0), ia.get("confianza", 0)) + 1,
            "detalle_factcheck": factcheck.get("detalle") if fc_exitoso else None,
            "detalle_ia": ia.get("detalle") if ia_exitosa else None,
            "resultado_final": veredicto_combinado,
            "tiene_verificacion_oficial": False,
            "recomendacion": "Múltiples métodos de análisis coinciden en este veredicto."
        }
    
    # Caso por defecto - usar el mejor disponible
    logger.info("🔍 Combinación: Usando mejor resultado disponible")
    if ia_exitosa:
        return {
            "fuente_primaria": "gemini",
            "veredicto_final": ia["resultado"],
            "confianza": ia.get("confianza", 5),
            "detalle_ia": ia.get("detalle", {}),
            "factcheck_previo": factcheck.get("resultado") if fc_exitoso else "no_encontrado",
            "resultado_final": ia["resultado"],
            "tiene_verificacion_oficial": False,
            "recomendacion": "Análisis basado en IA - verificar con fuentes adicionales para confirmación."
        }
    elif fc_exitoso:
        return {
            "fuente_primaria": "factcheck",
            "veredicto_final": factcheck["resultado"],
            "confianza": 6 if factcheck["resultado"] == "no_encontrado" else 8,
            "detalle_factcheck": factcheck.get("detalle"),
            "resultado_final": factcheck["resultado"],
            "tiene_verificacion_oficial": factcheck["resultado"] == "verificado",
            "recomendacion": "Basado en búsqueda en base de datos de fact-checking."
        }
    else:
        return {
            "fuente_primaria": "error",
            "veredicto_final": "no_se_puede_verificar",
            "confianza": 0,
            "resultado_final": "error",
            "tiene_verificacion_oficial": False,
            "recomendacion": "No se pudo analizar la afirmación. Intente reformular o usar otras fuentes."
        }

def _veredictos_coinciden(veredicto_fc: str, veredicto_ia: str) -> bool:
    """Determina si los veredictos de FactCheck e IA son consistentes"""
    if not veredicto_fc or not veredicto_ia:
        return False
    
    # Mapeo de equivalencias
    equivalencias = {
        "verificado": ["probablemente_verdadero"],
        "no_encontrado": ["no_verificable", "no_se_puede_verificar"],
        "probablemente_falso": ["probablemente_falso", "falso"]
    }
    
    veredicto_fc = veredicto_fc.lower()
    veredicto_ia = veredicto_ia.lower()
    
    # Coincidencia directa
    if veredicto_fc == veredicto_ia:
        return True
    
    # Coincidencia por equivalencias
    for fc_key, ia_values in equivalencias.items():
        if veredicto_fc == fc_key and veredicto_ia in ia_values:
            return True
        if veredicto_ia == fc_key and veredicto_fc in ia_values:
            return True
    
    return False

def _traducir_veredicto_combinado(veredicto_fc: str, veredicto_ia: str) -> str:
    """Traduce veredictos combinados a un formato estándar"""
    # Priorizar veredictos más específicos de IA
    if veredicto_ia in ["probablemente_verdadero", "probablemente_falso", "mixto"]:
        return veredicto_ia
    elif veredicto_fc == "verificado":
        return "probablemente_verdadero"
    else:
        return veredicto_ia or veredicto_fc or "no_se_puede_verificar"

def _analizar_con_gemini(texto: str) -> Dict[str, Any]:
    """Función interna para analizar con Gemini"""
    try:
        from services.gemini_analyzer import analizar_con_gemini as gemini_analyzer
        return gemini_analyzer(texto)
    except Exception as e:
        logger.error(f"Error llamando a Gemini analyzer: {e}")
        return {
            "success": False,
            "error": f"Error con servicio de IA: {str(e)}"
        }

def _preparar_respuesta_para_bd(resultado: Dict[str, Any]) -> str:
    """Prepara la respuesta para almacenar en la base de datos"""
    try:
        # Extraer información clave para BD
        respuesta_bd = {
            "fuente_primaria": resultado.get("fuente_primaria"),
            "veredicto_final": resultado.get("veredicto_final"),
            "confianza": resultado.get("confianza"),
            "tiene_verificacion_oficial": resultado.get("tiene_verificacion_oficial", False),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Añadir detalles específicos si existen
        if "detalle_factcheck" in resultado and resultado["detalle_factcheck"]:
            respuesta_bd["detalle_factcheck"] = resultado["detalle_factcheck"]
        
        if "detalle_ia" in resultado and resultado["detalle_ia"]:
            # Limitar tamaño de detalle_ia para BD
            detalle_ia = resultado["detalle_ia"].copy()
            if "razonamiento" in detalle_ia and len(detalle_ia["razonamiento"]) > 500:
                detalle_ia["razonamiento"] = detalle_ia["razonamiento"][:500] + "..."
            respuesta_bd["detalle_ia"] = detalle_ia
        
        return str(respuesta_bd)
    
    except Exception as e:
        logger.error(f"Error preparando respuesta para BD: {e}")
        return f"Resultado: {resultado.get('resultado_final', 'error')}"

def obtener_estadisticas_hibridas(db: Session) -> Dict[str, Any]:
    """Obtiene estadísticas del uso del sistema híbrido"""
    from database import ConsultaNoticia
    from sqlalchemy import func
    
    try:
        stats = db.query(
            func.count(ConsultaNoticia.id).label("total_consultas"),
            func.count(func.distinct(ConsultaNoticia.usuario_id)).label("usuarios_unicos"),
            func.avg(func.length(ConsultaNoticia.texto_consultado)).label("longitud_promedio")
        ).first()
        
        # Consulta para distribución de fuentes
        distribucion_fuentes = db.query(
            ConsultaNoticia.resultado,
            func.count(ConsultaNoticia.id).label("cantidad")
        ).group_by(ConsultaNoticia.resultado).all()
        
        return {
            "total_consultas": stats.total_consultas or 0,
            "usuarios_unicos": stats.usuarios_unicos or 0,
            "longitud_promedio_texto": round(stats.longitud_promedio or 0, 2),
            "distribucion_resultados": {
                resultado: cantidad for resultado, cantidad in distribucion_fuentes
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas híbridas: {e}")
        return {
            "total_consultas": 0,
            "usuarios_unicos": 0,
            "longitud_promedio_texto": 0,
            "distribucion_resultados": {},
            "error": str(e)
        }

def limpiar_consultas_antiguas(db: Session, dias: int = 30) -> Dict[str, Any]:
    """Limpia consultas más antiguas que X días"""
    from database import ConsultaNoticia
    from datetime import datetime, timedelta
    
    try:
        fecha_limite = datetime.utcnow() - timedelta(days=dias)
        
        consultas_eliminadas = db.query(ConsultaNoticia)\
            .filter(ConsultaNoticia.fecha_consulta < fecha_limite)\
            .delete()
        
        db.commit()
        
        return {
            "success": True,
            "consultas_eliminadas": consultas_eliminadas,
            "fecha_limite": fecha_limite.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error limpiando consultas antiguas: {e}")
        return {
            "success": False,
            "error": str(e)
        }