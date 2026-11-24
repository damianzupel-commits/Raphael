"""Genera el ícono de la bandeja al vuelo con Pillow (sin assets binarios en el repo)."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

_COLORS = {
    "running": (52, 199, 89, 255),
    "starting": (255, 204, 0, 255),
    "stopped": (142, 142, 147, 255),
    "error": (255, 59, 48, 255),
}

_SIZE = 64
_MARGIN = 2
_BORDER_WIDTH = 5

# Windows reduce esto a 16x16 (o 20x20 con escalado) para la bandeja -- una
# fuente por defecto de Pillow ahí es ilegible. Probamos fuentes bold del
# sistema en orden de preferencia y caemos al default si ninguna existe.
_FONT_CANDIDATES = ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"]
_FONT_SIZE = 42


def _load_font() -> ImageFont.ImageFont:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for name in _FONT_CANDIDATES:
        path = windir / "Fonts" / name
        if path.exists():
            return ImageFont.truetype(str(path), _FONT_SIZE)
    return ImageFont.load_default()


_FONT = _load_font()


def build_image(state: str) -> Image.Image:
    # El semáforo por estado (círculo verde/amarillo/rojo con "J") se sacó a
    # pedido de Damian (2026-09-01): el ícono de bandeja ahora es la IMAGEN de
    # Raphael, fija. Se ignora `state` a propósito (la firma se mantiene para no
    # tocar a los que llaman con el estado). Si la imagen no está, cae al círculo
    # neutro de _fallback_image para no quedarse sin ícono.
    try:
        src = config.RAPHAEL_IMAGE if config.RAPHAEL_IMAGE.exists() else config.RAPHAEL_ICON
        img = Image.open(src).convert("RGBA")
        # Recorte central a cuadrado (la imagen es apaisada) + resize al ícono.
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        return img.crop((left, top, left + side, top + side)).resize((_SIZE, _SIZE), Image.LANCZOS)
    except Exception:
        return _fallback_image()


def _fallback_image() -> Image.Image:
    """Ícono de respaldo (círculo neutro con "R") si la imagen de Raphael no se
    puede cargar -- así la bandeja nunca se queda sin ícono."""
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        (_MARGIN, _MARGIN, _SIZE - _MARGIN, _SIZE - _MARGIN),
        fill=_COLORS["stopped"],
        outline=(255, 255, 255, 255),
        width=_BORDER_WIDTH,
    )
    text = "R"
    bbox = draw.textbbox((0, 0), text, font=_FONT)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (_SIZE - tw) / 2 - bbox[0]
    y = (_SIZE - th) / 2 - bbox[1]
    draw.text((x, y), text, font=_FONT, fill=(0, 0, 0, 255))
    return img
