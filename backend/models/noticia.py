from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class Noticia(BaseModel):
    texto: str
    url: Optional[str] = None
    usuario_id: Optional[str] = None
    dispositivo_id: Optional[str] = None  # Para identificar el dispositivo móvil

class NoticiaResponse(BaseModel):
    id: int
    resultado: str
    detalle: Optional[dict] = None
    consulta_id: Optional[int] = None
    fecha_procesamiento: datetime

    class Config:
        from_attributes = True