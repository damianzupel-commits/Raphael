"""Publicaciones de la brigada de Video en Instagram: PREPARAR (lo puede hacer un ayudante) y APROBAR (solo Damian).

Regla dura que cumple este módulo, no un prompt: ninguna tool publica. Un ayudante solo deja una publicación PENDIENTE
(video + texto + huella); publicarla exige `aprobar_y_publicar`, que se alcanza únicamente desde el endpoint que Damian
acciona (orquestador/server.py), nunca desde el registro de tools. Si el video o el texto cambian después de preparar,
la huella no coincide y no se publica. Una publicación se intenta UNA vez: si falla queda en `fallo` con el motivo.

La API de Instagram (Graph) se usa con carga resumible en 3 pasos: crear el contenedor, subir los bytes y publicarlo.
Credenciales SOLO del entorno: IG_USER_ID e IG_ACCESS_TOKEN (cuenta profesional). Versión de la API: IG_GRAPH_VERSION.
IMPORTANTE: los pasos contra Meta están probados con un cliente simulado; falta una prueba real con la cuenta de Damian.
Solo stdlib."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import video_edit

MAX_TEXTO = 2200
_ESTADOS = ("pendiente", "publicada", "fallo", "descartada")


class PublicacionError(Exception):
    """Error con mensaje para mostrarle a Damian tal cual."""


def carpeta() -> Path:
    d = video_edit.base_dir() / "publicaciones"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _huella(path: Path, texto: str) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    h.update(b"\x00" + texto.encode("utf-8"))
    return h.hexdigest()


def _ruta(pid: str) -> Path:
    if not isinstance(pid, str) or not pid.isalnum() or len(pid) > 40:
        raise PublicacionError("Identificador de publicación inválido.")
    return carpeta() / f"{pid}.json"


def _leer(pid: str) -> dict:
    p = _ruta(pid)
    if not p.is_file():
        raise PublicacionError(f"No existe la publicación {pid}.")
    return json.loads(p.read_text(encoding="utf-8"))


def _guardar(rec: dict) -> None:
    _ruta(rec["id"]).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def preparar(archivo: str, texto: str) -> dict:
    """Deja una publicación PENDIENTE de aprobación. No publica ni habla con Instagram."""
    if not isinstance(texto, str) or not texto.strip():
        raise PublicacionError("Falta el texto (la descripción) de la publicación.")
    if len(texto) > MAX_TEXTO:
        raise PublicacionError(f"El texto supera los {MAX_TEXTO} caracteres que admite Instagram.")
    path = video_edit.resolver(archivo, {".mp4", ".mov"})
    datos = video_edit.info(path)
    if not datos.get("duracion_s"):
        raise PublicacionError("No pude leer la duración del video.")
    pid = uuid.uuid4().hex[:12]
    rec = {"id": pid, "archivo": path.name, "path": str(path), "texto": texto.strip(), "duracion_s": datos["duracion_s"],
           "huella": _huella(path, texto.strip()), "estado": "pendiente", "creada": _ahora()}
    _guardar(rec)
    return {"id": pid, "estado": "pendiente", "archivo": path.name, "duracion_s": datos["duracion_s"],
            "aviso": "Quedó PENDIENTE: no se publicó nada. Damian la tiene que aprobar él (panel de publicaciones del orquestador)."}


def listar() -> list[dict]:
    out = []
    for p in sorted(carpeta().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({k: r.get(k) for k in ("id", "archivo", "texto", "duracion_s", "estado", "creada", "motivo", "permalink")})
    return out


def descartar(pid: str) -> dict:
    rec = _leer(pid)
    if rec["estado"] != "pendiente":
        raise PublicacionError(f"Solo se descarta una pendiente (esta está {rec['estado']}).")
    rec["estado"] = "descartada"
    _guardar(rec)
    return {"id": pid, "estado": "descartada"}


# --- Instagram (Graph API, carga resumible) -----------------------------------------------------------------------------
Http = Callable[..., dict]


def _http(method: str, url: str, *, data: dict | None = None, headers: dict | None = None, body: bytes | None = None, timeout: float = 120) -> dict:
    payload = body if body is not None else (urllib.parse.urlencode(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=payload, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - hosts fijos de Meta
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise PublicacionError(f"Instagram respondió {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from None
    except OSError as exc:
        raise PublicacionError(f"No pude hablar con Instagram: {exc}") from None
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {"raw": raw[:300]}


def aprobar_y_publicar(pid: str, *, http: Http = _http, esperar: float = 5.0, intentos: int = 60) -> dict:
    """Publica como Reel una publicación PENDIENTE. Es la ÚNICA puerta a Instagram y no está registrada como tool."""
    rec = _leer(pid)
    if rec["estado"] != "pendiente":
        raise PublicacionError(f"La publicación está {rec['estado']}: solo se aprueba una pendiente.")
    path = Path(rec["path"])
    if not path.is_file() or _huella(path, rec["texto"]) != rec["huella"]:
        raise PublicacionError("El video o el texto cambiaron después de prepararla: preparala de nuevo.")
    user, token = os.getenv("IG_USER_ID", "").strip(), os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not user or not token:
        raise PublicacionError("Faltan IG_USER_ID e IG_ACCESS_TOKEN en backend/.env (cuenta profesional de Instagram). La publicación sigue pendiente.")
    base = f"https://graph.facebook.com/{os.getenv('IG_GRAPH_VERSION', 'v21.0').strip() or 'v21.0'}"
    try:
        c = http("POST", f"{base}/{user}/media", data={"media_type": "REELS", "upload_type": "resumable", "caption": rec["texto"], "access_token": token})
        cid, uri = c.get("id"), c.get("uri")
        if not cid or not uri:
            raise PublicacionError(f"Instagram no devolvió el contenedor de carga: {str(c)[:200]}")
        tam = path.stat().st_size
        http("POST", uri, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(tam)}, body=path.read_bytes(), timeout=600)
        estado = ""
        for _ in range(max(1, intentos)):
            estado = str(http("GET", f"{base}/{cid}?fields=status_code&access_token={urllib.parse.quote(token)}").get("status_code", ""))
            if estado in ("FINISHED", "ERROR", "EXPIRED"):
                break
            time.sleep(esperar)
        if estado != "FINISHED":
            raise PublicacionError(f"Instagram no terminó de procesar el video (estado: {estado or 'sin respuesta'}).")
        pub = http("POST", f"{base}/{user}/media_publish", data={"creation_id": cid, "access_token": token})
        if not pub.get("id"):
            raise PublicacionError(f"Instagram no confirmó la publicación: {str(pub)[:200]}")
        rec.update(estado="publicada", publicada=_ahora(), media_id=pub["id"])
    except PublicacionError as exc:
        rec.update(estado="fallo", motivo=str(exc).replace(token, "***"))  # una sola vez: no se reintenta solo
        _guardar(rec)
        raise PublicacionError(rec["motivo"]) from None
    _guardar(rec)
    return {"id": pid, "estado": "publicada", "media_id": rec["media_id"]}
