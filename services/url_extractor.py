import requests
import os
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def extraer_con_scraperapi(url: str) -> str:
    """
    Extrae contenido usando ScraperAPI
    1,000 requests gratis/mes - ideal para sitios complejos
    """
    try:
        api_key = os.getenv("SCRAPERAPI_KEY")
        
        if not api_key:
            logger.warning("❌ SCRAPERAPI_KEY no configurada")
            return "❌ Servicio de extracción no configurado"
        
        logger.info(f"🔗 ScraperAPI procesando: {url}")
        
        # Configurar parámetros para ScraperAPI
        params = {
            "api_key": api_key,
            "url": url,
            "render": "false",      # No JS (más rápido)
            "autoparse": "true",   # Que ScraperAPI limpie el HTML
            "country_code": "us"   # Servidores US
        }
        
        response = requests.get(
            "http://api.scraperapi.com/",
            params=params,
            timeout=25,  # ScraperAPI puede ser lento
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; Covered-Bot/1.0)'
            }
        )
        
        logger.info(f"📡 ScraperAPI response: {response.status_code}")
        
        if response.status_code == 200:
            # ScraperAPI devuelve HTML limpio
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remover elementos no deseados
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()
            
            # Estrategia de extracción inteligente
            contenido = extraer_contenido_inteligente(soup)
            
            if contenido:
                contenido = contenido.strip()[:2800]  # Limitar tamaño
                logger.info(f"✅ ScraperAPI extrajo {len(contenido)} caracteres")
                return contenido
            else:
                return "❌ No se pudo extraer contenido del sitio"
                
        elif response.status_code == 403:
            return "❌ Límite de ScraperAPI excedido o API key inválida"
        elif response.status_code == 404:
            return "❌ ScraperAPI no pudo acceder a este enlace"
        elif response.status_code == 429:
            return "❌ Demasiadas requests a ScraperAPI (límite excedido)"
        else:
            return f"❌ Error ScraperAPI: {response.status_code} - {response.text[:100]}"
            
    except requests.exceptions.Timeout:
        return "❌ Timeout - ScraperAPI no respondió a tiempo"
    except requests.exceptions.ConnectionError:
        return "❌ Error de conexión con ScraperAPI"
    except Exception as e:
        logger.error(f"❌ Error ScraperAPI: {str(e)}")
        return f"❌ Error con servicio de extracción: {str(e)}"

def extraer_contenido_inteligente(soup: BeautifulSoup) -> str:
    """
    Extrae contenido de forma inteligente buscando el texto principal
    """
    # Estrategia 1: Buscar elementos semánticos principales
    selectores_prioritarios = [
        'article', 
        'main',
        '[role="main"]',
        '.content',
        '#content',
        '.post-content',
        '.entry-content',
        '.article-content'
    ]
    
    for selector in selectores_prioritarios:
        elemento = soup.select_one(selector)
        if elemento:
            texto = elemento.get_text().strip()
            if len(texto) > 200:
                logger.info(f"✅ Encontrado contenido en: {selector}")
                return texto
    
    # Estrategia 2: Buscar en el body si no encontramos elementos semánticos
    body = soup.find('body')
    if body:
        # Extraer solo párrafos y encabezados del body
        textos = []
        for element in body.find_all(['p', 'h1', 'h2', 'h3']):
            text = element.get_text().strip()
            if text and len(text) > 30:  # Filtrar textos muy cortos
                textos.append(text)
        
        if textos:
            logger.info(f"✅ Extraídos {len(textos)} fragmentos del body")
            return ' '.join(textos)
    
    # Estrategia 3: Último recurso - todo el texto
    texto_completo = soup.get_text()
    lineas = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
    lineas_filtradas = [linea for linea in lineas if len(linea) > 40]
    
    if lineas_filtradas:
        logger.info(f"✅ Usando extracción completa: {len(lineas_filtradas)} líneas")
        return ' '.join(lineas_filtradas[:20])  # Máximo 20 líneas
    
    return ""

def extraccion_directa_fallback(url: str) -> str:
    """
    Fallback muy simple para cuando ScraperAPI no funciona
    """
    try:
        logger.info("🔄 Intentando extracción directa como fallback...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extracción mínima
        textos = []
        for element in soup.find_all(['p', 'h1']):
            text = element.get_text().strip()
            if text and 30 < len(text) < 1000:
                textos.append(text)
        
        if textos:
            resultado = ' '.join(textos[:8])[:2000]  # 8 párrafos máximo
            logger.info(f"✅ Extracción directa: {len(resultado)} caracteres")
            return resultado
        
        return "❌ No se pudo extraer contenido automáticamente"
        
    except Exception as e:
        logger.error(f"❌ Error en extracción directa: {e}")
        return f"❌ Error accediendo al sitio: {str(e)}"

def extraer_texto_desde_url(url: str) -> str:
    """
    Función principal - usa ScraperAPI como primario
    """
    try:
        # Validar y normalizar URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = 'https://' + url
            parsed_url = urlparse(url)
        
        if not parsed_url.netloc:
            return "❌ URL inválida - falta dominio"
        
        logger.info(f"🌐 Iniciando extracción para: {url}")
        
        # 1. PRIMERO: Intentar con ScraperAPI
        resultado_scraper = extraer_con_scraperapi(url)
        
        if not resultado_scraper.startswith("❌"):
            return resultado_scraper
        
        # 2. Si ScraperAPI falla, intentar extracción directa
        logger.info("🔄 ScraperAPI falló, intentando extracción directa...")
        resultado_directo = extraccion_directa_fallback(url)
        
        return resultado_directo
        
    except Exception as e:
        logger.error(f"💥 Error crítico en extracción: {e}")
        return f"❌ Error procesando enlace: {str(e)}"