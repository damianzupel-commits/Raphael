"""Reglas para entender un pedido corto de Damián cuando NO hay modelo (o cuando el modelo local está apagado).

Solo entiende órdenes explícitas y se queda corto a propósito: ante la duda devuelve None y no hace nada. Nunca inventa.
Solo se usa con mensajes de confianza (los que escribió Damián), jamás con contenido de terceros.
"""

from __future__ import annotations

import re

from raphael_core.text_es import normalize

URL = re.compile(r"https?://[^\s<>\"']+")

#: nombre que dice Damián -> lo que entiende el lanzador de Windows
PC_APPS = {"calculadora": "calc", "bloc de notas": "notepad", "notepad": "notepad", "paint": "mspaint",
           "explorador": "explorer", "explorador de archivos": "explorer", "administrador de tareas": "taskmgr"}
#: nombre -> package name de Android
PHONE_APPS = {"whatsapp": "com.whatsapp", "chrome": "com.android.chrome", "camara": "com.android.camera",
              "calculadora": "com.google.android.calculator", "ajustes": "com.android.settings",
              "configuracion": "com.android.settings", "instagram": "com.instagram.android",
              "telegram": "org.telegram.messenger", "youtube": "com.google.android.youtube"}

_OPEN = re.compile(r"^(?:por favor\s+)?(?:abri|abre|abrime|lanza|lanzame|inicia)\s+(?:la |el |una |un )?(?P<what>.+?)\s*[.!]*$")
_RUN = re.compile(r"^(?:ejecuta|corre|correme|ejecutame)\s*(?:el\s+)?(?:comando\s*)?[:`]\s*`?(?P<cmd>[^`]+?)`?\s*$")
_SHOT = re.compile(r"\b(captura|screenshot|pantallazo)\b.*\b(pantalla|escritorio)\b|\b(captura|pantallazo|screenshot)\b")
_PHONE = re.compile(r"\b(celular|telefono|movil)\b")
_PHOTO = re.compile(r"\b(foto|fotografia)\b")
_READ_SCREEN = re.compile(r"\b(lee|leeme|mostrame|que hay en)\b.*\bpantalla\b")


def _clean_name(text: str) -> str:
    text = re.sub(r"\s+en (?:el |mi )?(?:celular|telefono|movil)\s*$", "", text).strip()
    return re.sub(r"\s+", " ", text)


def parse(original: str) -> tuple[str, str, dict] | None:
    """(cocinero, acción, datos) o None. Entiende el texto tal cual lo escribió Damián (con mayúsculas y tildes)."""
    t = normalize(original).strip()
    if not t:
        return None
    if _RUN.match(t):
        # el comando se toma del texto original: las mayúsculas y las tildes importan en una ruta o un argumento
        cmd = _extract_original_command(original)
        return ("pc", "ejecutar_comando", {"command": cmd.strip()}) if cmd and cmd.strip() else None
    if url := URL.search(original):
        if re.match(r"^(?:abri|abre|abrime|entra|anda|ve|navega)\b", t) or t.startswith(("http", "www")):
            return ("browser-web", "abrir_url", {"url": url.group(0).rstrip(".,;)")})
        return None
    phone = bool(_PHONE.search(t))
    if phone and _READ_SCREEN.search(t):
        return ("phone", "leer_pantalla_celular", {})
    if phone and _PHOTO.search(t):
        return ("phone", "sacar_foto", {"camera": "front" if re.search(r"\b(frontal|selfie)\b", t) else "back"})
    if m := _OPEN.match(t):
        name = _clean_name(m.group("what"))
        if phone:
            pkg = PHONE_APPS.get(name)
            return ("phone", "celular_abrir_app", {"package_name": pkg}) if pkg else None
        return ("pc", "abrir_app", {"app": PC_APPS.get(name, name)}) if name else None
    if not phone and _SHOT.search(t):
        return ("pc", "capturar_pantalla", {})
    return None


def _extract_original_command(original: str) -> str | None:
    """El comando tal cual lo escribió Damián (después de los dos puntos o entre comillas invertidas)."""
    if "`" in original:
        parts = original.split("`")
        return parts[1] if len(parts) >= 3 else None
    if ":" in original:
        return original.split(":", 1)[1]
    return None
