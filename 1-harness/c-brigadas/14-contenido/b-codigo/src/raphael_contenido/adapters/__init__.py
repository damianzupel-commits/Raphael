"""Los adaptadores de la brigada Contenido: todo lo que habla con algo que es de la persona (cuentas, GPU, ffmpeg).

Cada servicio tiene tres: el REAL (lee su clave del entorno), el SIMULADO (`mode: mock` en la config o `CONTENIDO_MODO=mock`;
sus resultados llevan `simulado: true`) y el "SIN CLAVE" (el real al que le falta una variable: avisa cuál y no inventa nada).
"""

from .anuncios import AnunciosMeta, AnunciosMock, AnunciosSinClave
from .comfyui import ComfyMock, ComfySinServidor, ComfyUI
from .http import ServicioError
from .instagram import InstagramGraph, InstagramMock, InstagramSinClave
from .metricas import MetricasGraph, MetricasMock, MetricasSinClave

__all__ = ["AnunciosMeta", "AnunciosMock", "AnunciosSinClave", "ComfyMock", "ComfySinServidor", "ComfyUI", "InstagramGraph",
           "InstagramMock", "InstagramSinClave", "MetricasGraph", "MetricasMock", "MetricasSinClave", "ServicioError"]
