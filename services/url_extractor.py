# services/url_extractor.py
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def extraer_texto_desde_url(url: str) -> str:
    try:
        # Validar URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("URL inválida")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Eliminar scripts y styles
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extraer texto de los párrafos y títulos
        textos = []
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text = element.get_text().strip()
            if text:
                textos.append(text)
        
        return ' '.join(textos)
        
    except requests.RequestException as e:
        raise Exception(f"Error al acceder a la URL: {str(e)}")
    except Exception as e:
        raise Exception(f"Error al procesar el contenido: {str(e)}") 
