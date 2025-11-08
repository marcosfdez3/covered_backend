import requests
import os
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def extraer_con_scraperapi(url: str) -> str:
    """
    Extrae contenido usando ScraperAPI
    """
    try:
        api_key = os.getenv("SCRAPERAPI_KEY")
        
        if not api_key:
            logger.warning("SCRAPERAPI_KEY no configurada")
            return ""
        
        logger.info(f"🔗 ScraperAPI procesando: {url}")
        
        params = {
            "api_key": api_key,
            "url": url,
            "render": "false",    # Más rápido sin JavaScript
            "autoparse": "true",  # Que ScraperAPI limpie el HTML
            "country_code": "us"
        }
        
        response = requests.get(
            "http://api.scraperapi.com/",
            params=params,
            timeout=20
        )
        
        logger.info(f"📡 ScraperAPI status: {response.status_code}")
        
        if response.status_code == 200:
            # Procesar HTML devuelto por ScraperAPI
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Limpiar elementos no deseados
            for element in soup(["script", "style", "nav", "header", "footer", "aside", "meta"]):
                element.decompose()
            
            # Estrategia de extracción inteligente
            contenido = extraer_contenido_estrategico(soup)
            
            if contenido:
                contenido = limpiar_texto(contenido)
                logger.info(f"✅ ScraperAPI extrajo {len(contenido)} caracteres")
                return contenido
            else:
                logger.warning("ScraperAPI no pudo extraer contenido")
                return ""
                
        else:
            logger.error(f"ScraperAPI error: {response.status_code}")
            return ""
            
    except Exception as e:
        logger.error(f"Error ScraperAPI: {str(e)}")
        return ""

def extraer_contenido_estrategico(soup: BeautifulSoup) -> str:
    """
    Extrae contenido usando múltiples estrategias
    """
    # Estrategia 1: Elementos semánticos
    selectores_prioritarios = [
        'article',
        'main', 
        '[role="main"]',
        '.content',
        '.post-content',
        '.article-content',
        '.entry-content'
    ]
    
    for selector in selectores_prioritarios:
        elemento = soup.select_one(selector)
        if elemento:
            texto = elemento.get_text().strip()
            if len(texto) > 150:
                logger.info(f"✅ Contenido en: {selector}")
                return texto
    
    # Estrategia 2: Párrafos y encabezados del body
    body = soup.find('body')
    if body:
        textos = []
        for element in body.find_all(['p', 'h1', 'h2', 'h3']):
            text = element.get_text().strip()
            if text and 25 < len(text) < 800:
                textos.append(text)
        
        if textos:
            logger.info(f"✅ {len(textos)} fragmentos del body")
            return ' '.join(textos[:15])  # Máximo 15 fragmentos
    
    # Estrategia 3: Todo el texto estructurado
    texto_completo = soup.get_text()
    lineas = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
    lineas_filtradas = [linea for linea in lineas if 30 < len(linea) < 1000]
    
    if lineas_filtradas:
        logger.info(f"✅ {len(lineas_filtradas)} líneas estructuradas")
        return ' '.join(lineas_filtradas[:20])
    
    return ""

def limpiar_texto(texto: str) -> str:
    """
    Limpia y normaliza el texto extraído
    """
    # Unificar espacios
    texto = ' '.join(texto.split())
    
    # Limitar tamaño para no saturar la IA
    if len(texto) > 2800:
        texto = texto[:2800] + "..."
    
    return texto

def extraer_texto_desde_url(url: str) -> str:
    """
    Función principal - usa ScraperAPI como primario
    """
    try:
        # Normalizar URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed_url = urlparse(url)
        if not parsed_url.netloc:
            return "❌ URL inválida - dominio no válido"
        
        logger.info(f"🌐 Iniciando extracción para: {url}")
        
        # 1. PRIMERO: Intentar con ScraperAPI
        resultado = extraer_con_scraperapi(url)
        
        if resultado:
            return resultado
        
        # 2. Si ScraperAPI no devuelve contenido, mensaje claro
        logger.info("ScraperAPI no pudo extraer contenido")
        return "❌ No se pudo extraer contenido automáticamente de este enlace. Por favor, copia y pega el texto manualmente."
        
    except Exception as e:
        logger.error(f"Error en extracción: {str(e)}")
        return f"❌ Error procesando enlace: {str(e)}"