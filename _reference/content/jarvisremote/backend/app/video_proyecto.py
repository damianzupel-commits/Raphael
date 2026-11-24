"""Proyecto de EDICIÓN de video: un documento único que editan, igual de bien, el usuario (panel) y la IA (tools).

Un proyecto es un JSON en `<carpeta de video>/proyectos/`. Tiene cinco pistas:
  V1 (video)  clips EN SECUENCIA, sin huecos: el orden de la lista es el orden en el tiempo (el `pos` se calcula). Cada clip puede
              entrar con una TRANSICIÓN (xfade) y llevar efectos (color, desenfoque, nitidez, viñeta, espejo, rotación).
  O1 (capas)  imágenes, GIFs animados o videos SUPERPUESTOS donde quieras: `x`/`y` (0–1, el centro de la capa), `escala`, `opacidad`,
              `rotacion`, `pos` y `dur`; pueden solaparse entre sí y con todo lo demás.
  T1 (texto)  títulos: cada uno con `pos` y `dur`.
  A1 (audio)  música o locución: cada clip con su `pos` absoluto y su volumen.
  A2 (audio)  efectos de sonido (el pack propio de Raphael en `efectos/`, o los tuyos): igual que A1, en su propia pista.
Toda modificación pasa por `aplicar(...)`, una lista de operaciones ATÓMICA (si una falla, no se aplica ninguna), con número de
revisión (si el proyecto cambió desde que lo leíste, se rechaza), historial para deshacer/rehacer y registro de quién lo cambió
(`usuario` o `ia`). Los originales nunca se tocan: `renderizar` deja un archivo NUEVO en `salida/`.
Todo el render es UN solo ffmpeg (filter_complex), de a uno, con la prioridad baja y los topes del núcleo de edición.
Solo stdlib."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import video_edit as ve

FORMATOS = {"vertical": (1080, 1920), "horizontal": (1920, 1080), "cuadrado": (1080, 1080)}
PISTAS = ("V1", "O1", "T1", "A1", "A2")
PISTAS_AUDIO = ("A1", "A2")
MAX_CLIPS = 200
MAX_HISTORIAL = 40
# Parámetros de un clip de video que se pueden ajustar, con su rango. Los de audio y texto, más abajo.
AJUSTES_V = {"velocidad": (0.25, 4.0), "volumen": (0.0, 4.0), "brillo": (-0.5, 0.5), "contraste": (0.5, 2.0), "saturacion": (0.0, 3.0),
             "zoom": (1.0, 3.0), "fundido_in": (0.0, 5.0), "fundido_out": (0.0, 5.0), "desenfoque": (0.0, 20.0), "nitidez": (0.0, 2.0),
             "vineta": (0.0, 1.0), "transicion_dur": (0.2, 3.0)}
AJUSTES_O = {"x": (0.0, 1.0), "y": (0.0, 1.0), "escala": (0.05, 1.0), "opacidad": (0.0, 1.0), "rotacion": (-180.0, 180.0),
             "fundido_in": (0.0, 5.0), "fundido_out": (0.0, 5.0)}
# Transiciones: nombre en español -> nombre de ffmpeg (xfade). "ninguna" = corte directo.
TRANSICIONES = {"ninguna": None, "fundido": "fade", "fundido_negro": "fadeblack", "fundido_blanco": "fadewhite", "disolver": "dissolve",
                "deslizar_izq": "slideleft", "deslizar_der": "slideright", "deslizar_arriba": "slideup", "deslizar_abajo": "slidedown",
                "limpiar": "wipeleft", "circulo": "circleopen", "zoom": "zoomin", "pixelar": "pixelize", "radial": "radial"}
ROTACIONES = (0, 90, 180, 270)
EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".webp"}
AJUSTES_A = {"volumen": (0.0, 4.0), "fundido_in": (0.0, 10.0), "fundido_out": (0.0, 10.0)}
AJUSTES_T = {"tamano": (12, 200)}
_LOCK = threading.RLock()


class ProyectoError(Exception):
    """Error con mensaje para mostrarle a Damian (o a la IA) tal cual."""


# --- almacenamiento ---------------------------------------------------------------------------------------------------------
def carpeta() -> Path:
    d = ve.base_dir() / "proyectos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ruta(pid: str, sufijo: str = "") -> Path:
    if not isinstance(pid, str) or not re.fullmatch(r"[\w\-]{1,60}", pid):
        raise ProyectoError("Identificador de proyecto inválido.")
    return carpeta() / f"{pid}{sufijo}.json"


def _cargar(pid: str) -> dict:
    p = _ruta(pid)
    if not p.is_file():
        raise ProyectoError(f"No existe el proyecto '{pid}'. Usá video_proyecto_crear o mirá la lista de proyectos.")
    return _normalizar(json.loads(p.read_text(encoding="utf-8")))


def _normalizar(p: dict) -> dict:
    """Un proyecto guardado con una versión anterior (sin las pistas nuevas) se abre igual."""
    for k in PISTAS:
        p["pistas"].setdefault(k, [])
    return p


def _guardar(p: dict, sufijo: str = "") -> None:
    ruta = _ruta(p["id"], sufijo)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


def _hist(pid: str) -> dict:
    ruta = _ruta(pid, ".hist")
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {"deshacer": [], "rehacer": []}


def _estado(p: dict) -> dict:
    return {"formato": p["formato"], "ancho": p["ancho"], "alto": p["alto"], "pistas": copy.deepcopy(p["pistas"])}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- lectura ----------------------------------------------------------------------------------------------------------------
def _dur_clip(c: dict) -> float:
    if "dur" in c and c.get("tipo") in ("imagen", "gif"):      # una capa de imagen o GIF dura lo que se le pida
        return round(c["dur"], 3)
    return round((c["fin"] - c["inicio"]) / c.get("velocidad", 1.0), 3)


def _tdur(anterior: float, c: dict) -> float:
    """Duración efectiva de la transición con la que ENTRA el clip `c` (se solapa con el final del anterior)."""
    if TRANSICIONES.get(c.get("transicion", "ninguna")) is None:
        return 0.0
    return round(min(float(c.get("transicion_dur", 0.6)), anterior / 2, _dur_clip(c) / 2), 3)


def _calcular(p: dict) -> dict:
    """El proyecto tal cual se muestra: con la posición y la duración de cada clip de V1 ya calculadas (con las transiciones solapadas)."""
    out = copy.deepcopy(p)
    t, anterior = 0.0, 0.0
    for k, c in enumerate(out["pistas"]["V1"]):
        c["dur"] = _dur_clip(c)
        c["tdur"] = _tdur(anterior, c) if k else 0.0
        c["pos"] = round(t - c["tdur"], 3)
        t, anterior = c["pos"] + c["dur"], c["dur"]
    for pista in ("O1", *PISTAS_AUDIO):
        for c in out["pistas"][pista]:
            c["dur"] = _dur_clip(c)
    out["duracion"] = round(t, 3)
    hist = _hist(p["id"])
    out["puede_deshacer"], out["puede_rehacer"] = bool(hist["deshacer"]), bool(hist["rehacer"])
    return out


def leer(pid: str) -> dict:
    with _LOCK:
        return _calcular(_cargar(pid))


def listar() -> list[dict]:
    out = []
    for f in sorted(carpeta().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.name.endswith(".hist.json"):
            continue
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": p["id"], "nombre": p["nombre"], "formato": p["formato"], "rev": p["rev"], "actualizado": p["actualizado"],
                        "duracion": _calcular(p)["duracion"]})
        except (OSError, ValueError, KeyError):
            continue
    return out


def crear(nombre: str, formato: str = "vertical") -> dict:
    if formato not in FORMATOS:
        raise ProyectoError(f"formato: {', '.join(FORMATOS)}.")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 80:
        raise ProyectoError("El nombre tiene que tener entre 1 y 80 caracteres.")
    limpio = re.sub(r"-{2,}", "-", re.sub(r"[^\w\-]+", "-", nombre.strip().lower(), flags=re.UNICODE)).strip("-")[:30] or "proyecto"
    pid = f"{limpio}-{uuid.uuid4().hex[:4]}"
    w, h = FORMATOS[formato]
    p = {"id": pid, "nombre": nombre.strip(), "rev": 1, "formato": formato, "ancho": w, "alto": h, "fps": 30,
         "pistas": {k: [] for k in PISTAS}, "creado": _ahora(), "actualizado": _ahora(), "ultimo_cambio": {"por": "sistema", "resumen": "proyecto creado"}}
    with _LOCK:
        _guardar(p)
    return _calcular(p)


# --- operaciones ------------------------------------------------------------------------------------------------------------
def _num(v: object, nombre: str, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ProyectoError(f"{nombre}: no es un número válido.")
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except ValueError:
        raise ProyectoError(f"{nombre}: '{v}' no es un número válido.") from None
    if not (lo <= x <= hi):
        raise ProyectoError(f"{nombre}: tiene que estar entre {lo} y {hi}.")
    return x


def _tiempo(v: object, nombre: str) -> float:
    try:
        return ve.segundos(v, nombre)
    except ve.VideoError as exc:
        raise ProyectoError(str(exc)) from None


def _nuevo_id(p: dict) -> str:
    usados = {c["id"] for pista in p["pistas"].values() for c in pista}
    for n in range(1, 10000):
        if f"c{n}" not in usados:
            return f"c{n}"
    raise ProyectoError("Demasiados clips.")


def _buscar(p: dict, cid: object) -> tuple[str, list, int]:
    for nombre, pista in p["pistas"].items():
        for i, c in enumerate(pista):
            if c["id"] == cid:
                return nombre, pista, i
    raise ProyectoError(f"No existe el clip '{cid}'. Los ids están en el proyecto (video_proyecto_ver).")


def _campos_v(extra: dict) -> dict:
    return {"velocidad": 1.0, "volumen": 1.0, "brillo": 0.0, "contraste": 1.0, "saturacion": 1.0, "zoom": 1.0, "fundido_in": 0.0, "fundido_out": 0.0,
            "desenfoque": 0.0, "nitidez": 0.0, "vineta": 0.0, "espejo": False, "rotacion": 0, "filtro": "ninguno",
            "transicion": "ninguna", "transicion_dur": 0.6, **extra}


def _op_agregar_clip(p: dict, o: dict) -> str:
    pista = o.get("pista", "V1")
    if pista not in ("V1", *PISTAS_AUDIO):
        raise ProyectoError("agregar_clip: pista V1 (video), A1 (música) o A2 (efectos de sonido). Imágenes y GIFs: agregar_overlay. Texto: agregar_texto.")
    if sum(len(x) for x in p["pistas"].values()) >= MAX_CLIPS:
        raise ProyectoError(f"El proyecto llegó al tope de {MAX_CLIPS} clips.")
    if pista == "A2" and not ve.efectos_dir().exists():
        ve.generar_efectos()               # primera vez que se pide un efecto de sonido: se arma el pack propio
    try:
        src = ve.resolver(o.get("archivo"), ve.VIDEO_EXT | (ve.AUDIO_EXT if pista != "V1" else set()))
        datos = ve.info(src)
    except ve.VideoError as exc:
        raise ProyectoError(str(exc)) from None
    if pista == "V1" and not datos["tiene_video"]:
        raise ProyectoError(f"'{src.name}' no tiene video: ponelo en la pista de audio (A1 o A2).")
    if pista != "V1" and not datos["tiene_audio"]:
        raise ProyectoError(f"'{src.name}' no tiene audio.")
    dur = datos["duracion_s"] or 0.0
    if dur <= 0:
        raise ProyectoError(f"No pude leer la duración de '{src.name}'.")
    ini = _tiempo(o["inicio"], "inicio") if o.get("inicio") is not None else 0.0
    fin = _tiempo(o["fin"], "fin") if o.get("fin") is not None else dur
    if not (0 <= ini < fin <= dur + 0.05):
        raise ProyectoError(f"inicio/fin: tienen que cumplir 0 ≤ inicio < fin ≤ {dur} s (duración de '{src.name}').")
    fin = min(fin, dur)
    c = {"id": _nuevo_id(p), "archivo": src.name, "inicio": ini, "fin": fin, "dur_src": dur, "tiene_audio": datos["tiene_audio"]}
    if pista == "V1":
        c.update(_campos_v({}))
        c.update(ancho_src=datos["ancho"], alto_src=datos["alto"])
        idx = o.get("indice")
        lista = p["pistas"]["V1"]
        i = len(lista) if idx is None else int(_num(idx, "indice", 0, len(lista)))
        lista.insert(i, c)
    else:
        c.update({"volumen": 1.0, "fundido_in": 0.0, "fundido_out": 0.0, "pos": _tiempo(o.get("pos", 0), "pos"), "velocidad": 1.0})
        p["pistas"][pista].append(c)
    return f"agregó {src.name} ({round(fin - ini, 1)} s) a {pista} como {c['id']}"


def _op_agregar_overlay(p: dict, o: dict) -> str:
    """Una imagen, un GIF animado o un video ENCIMA del video, en cualquier lugar y momento. `x`/`y` son el CENTRO de la capa (0–1 del cuadro)."""
    if sum(len(x) for x in p["pistas"].values()) >= MAX_CLIPS:
        raise ProyectoError(f"El proyecto llegó al tope de {MAX_CLIPS} clips.")
    try:
        src = ve.resolver(o.get("archivo"), ve.IMG_EXT | ve.VIDEO_EXT)
        datos = ve.info(src)
    except ve.VideoError as exc:
        raise ProyectoError(str(exc)) from None
    ext = src.suffix.lower()
    tipo = "imagen" if ext in EXT_IMAGEN else "gif" if ext == ".gif" else "video"
    c = {"id": _nuevo_id(p), "archivo": src.name, "tipo": tipo, "pos": _tiempo(o.get("pos", 0), "pos"), "x": 0.5, "y": 0.5, "escala": 0.3,
         "opacidad": 1.0, "rotacion": 0.0, "fundido_in": 0.0, "fundido_out": 0.0, "inicio": 0.0, "fin": 1.0, "dur_src": 1.0,
         "ancho_src": datos.get("ancho"), "alto_src": datos.get("alto")}
    for k, (lo, hi) in AJUSTES_O.items():
        if o.get(k) is not None:
            c[k] = _num(o[k], k, lo, hi)
    if tipo == "video":
        dur_src = datos["duracion_s"] or 0.0
        if dur_src <= 0:
            raise ProyectoError(f"No pude leer la duración de '{src.name}'.")
        ini = _tiempo(o["inicio"], "inicio") if o.get("inicio") is not None else 0.0
        fin = _tiempo(o["fin"], "fin") if o.get("fin") is not None else dur_src
        if o.get("dur") is not None:
            fin = min(fin, ini + _tiempo(o["dur"], "dur"))
        if not (0 <= ini < fin <= dur_src + 0.05):
            raise ProyectoError(f"inicio/fin: tienen que cumplir 0 ≤ inicio < fin ≤ {dur_src} s (duración de '{src.name}').")
        c.update(inicio=ini, fin=min(fin, dur_src), dur_src=dur_src)
    else:
        dur = _tiempo(o.get("dur", 3), "dur")
        if dur <= 0:
            raise ProyectoError("dur: tiene que ser mayor que 0.")
        c["dur"] = dur
        c["fin"] = dur
    p["pistas"]["O1"].append(c)
    return f"agregó {'el GIF' if tipo == 'gif' else 'la imagen' if tipo == 'imagen' else 'el video'} {src.name} como capa {c['id']} en ({c['x']}, {c['y']})"


def _op_agregar_texto(p: dict, o: dict) -> str:
    t = o.get("texto")
    if not isinstance(t, str) or not t.strip() or len(t) > 300:
        raise ProyectoError("agregar_texto: el texto tiene que tener entre 1 y 300 caracteres.")
    posicion = o.get("posicion", "abajo")
    if posicion not in ("arriba", "centro", "abajo"):
        raise ProyectoError("posicion: arriba, centro o abajo.")
    color = o.get("color", "blanco")
    if color not in ve.COLORES:
        raise ProyectoError(f"color: {', '.join(ve.COLORES)}.")
    dur = _tiempo(o.get("dur", 3), "dur")
    if dur <= 0:
        raise ProyectoError("dur: tiene que ser mayor que 0.")
    c = {"id": _nuevo_id(p), "texto": t.strip(), "pos": _tiempo(o.get("pos", 0), "pos"), "dur": dur, "posicion": posicion,
         "tamano": int(_num(o.get("tamano", 48), "tamano", *AJUSTES_T["tamano"])), "color": color}
    p["pistas"]["T1"].append(c)
    return f"agregó el texto «{c['texto'][:30]}» ({c['id']})"


def _op_recortar(p: dict, o: dict) -> str:
    pista, lista, i = _buscar(p, o.get("clip"))
    c = lista[i]
    if pista == "T1" or (pista == "O1" and c.get("tipo") != "video"):
        raise ProyectoError("recortar: un texto, una imagen o un GIF no se recortan; cambiá su `dur` con ajustar.")
    ini = _tiempo(o["inicio"], "inicio") if o.get("inicio") is not None else c["inicio"]
    fin = _tiempo(o["fin"], "fin") if o.get("fin") is not None else c["fin"]
    if not (0 <= ini < fin <= c["dur_src"] + 0.05):
        raise ProyectoError(f"recortar: 0 ≤ inicio < fin ≤ {c['dur_src']} s (duración del archivo original).")
    c["inicio"], c["fin"] = ini, min(fin, c["dur_src"])
    return f"recortó {c['id']} a {ini}–{c['fin']} s del original"


def _op_dividir(p: dict, o: dict) -> str:
    pista, lista, i = _buscar(p, o.get("clip"))
    if pista in ("T1", "O1"):
        raise ProyectoError("dividir: no se divide un texto ni una capa (cambiá su `pos` y su `dur`).")
    c = lista[i]
    en = _tiempo(o.get("en"), "en")                      # segundos de la LÍNEA DE TIEMPO
    inicio_clip = _calcular(p)["pistas"][pista][i]["pos"] if pista == "V1" else c["pos"]
    rel = en - inicio_clip
    if not (0.05 < rel < _dur_clip(c) - 0.05):
        raise ProyectoError(f"dividir: el momento {en} s tiene que caer adentro del clip {c['id']} (de {inicio_clip} a {round(inicio_clip + _dur_clip(c), 3)} s).")
    corte = round(c["inicio"] + rel * c.get("velocidad", 1.0), 3)
    segundo = copy.deepcopy(c)
    segundo["id"] = _nuevo_id(p)
    segundo["inicio"], c["fin"] = corte, corte
    segundo["fundido_in"], c["fundido_out"] = 0.0, 0.0
    if pista in PISTAS_AUDIO:
        segundo["pos"] = round(inicio_clip + rel, 3)
    lista.insert(i + 1, segundo)
    return f"dividió {c['id']} en {en} s: quedan {c['id']} y {segundo['id']}"


def _op_mover(p: dict, o: dict) -> str:
    pista, lista, i = _buscar(p, o.get("clip"))
    if pista == "V1":
        if o.get("indice") is None:
            raise ProyectoError("mover un clip de V1: indicá el `indice` (0 = primero). Los clips de video van uno tras otro.")
        j = int(_num(o["indice"], "indice", 0, len(lista) - 1))
        lista.insert(j, lista.pop(i))
        return f"movió {o['clip']} a la posición {j}"
    if o.get("pos") is None:
        raise ProyectoError("mover: indicá `pos` (segundos en la línea de tiempo).")
    lista[i]["pos"] = _tiempo(o["pos"], "pos")
    return f"movió {o['clip']} a los {lista[i]['pos']} s"


def _op_borrar(p: dict, o: dict) -> str:
    _pista, lista, i = _buscar(p, o.get("clip"))
    lista.pop(i)
    return f"borró {o['clip']}"


def _op_ajustar(p: dict, o: dict) -> str:
    pista, lista, i = _buscar(p, o.get("clip"))
    c = lista[i]
    rangos = {"V1": AJUSTES_V, "O1": AJUSTES_O, "T1": AJUSTES_T, "A1": AJUSTES_A, "A2": AJUSTES_A}[pista]
    de_tiempo = {"T1": ("pos", "dur"), "O1": ("pos", "dur") if c.get("tipo") != "video" else ("pos",), "A1": ("pos",), "A2": ("pos",), "V1": ()}[pista]
    extras = {"T1": ("texto", "posicion", "color"), "V1": ("transicion", "filtro", "espejo", "rotacion")}.get(pista, ())
    cambios = []
    for k, v in o.items():
        if k in ("op", "clip"):
            continue
        if k in extras:
            if k == "texto":
                if not isinstance(v, str) or not v.strip() or len(v) > 300:
                    raise ProyectoError("texto: entre 1 y 300 caracteres.")
                c[k] = v.strip()
            elif k == "posicion":
                if v not in ("arriba", "centro", "abajo"):
                    raise ProyectoError("posicion: arriba, centro o abajo.")
                c[k] = v
            elif k == "color":
                if v not in ve.COLORES:
                    raise ProyectoError(f"color: {', '.join(ve.COLORES)}.")
                c[k] = v
            elif k == "transicion":
                if v not in TRANSICIONES:
                    raise ProyectoError(f"transicion: {', '.join(TRANSICIONES)}.")
                c[k] = v
            elif k == "filtro":
                if v not in ve.FILTROS_COLOR:
                    raise ProyectoError(f"filtro: {', '.join(ve.FILTROS_COLOR)}.")
                c[k] = v
            elif k == "espejo":
                c[k] = v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "si", "sí", "yes")
            else:  # rotacion de un clip de video: múltiplos de 90
                try:
                    r = int(float(str(v).replace(",", ".")))
                except ValueError:
                    raise ProyectoError("rotacion: 0, 90, 180 o 270.") from None
                if r not in ROTACIONES:
                    raise ProyectoError("rotacion: 0, 90, 180 o 270 (en una capa, cualquier ángulo de -180 a 180).")
                c[k] = r
        elif k in de_tiempo:
            c[k] = _tiempo(v, k)
            if k == "dur" and c[k] <= 0:
                raise ProyectoError("dur: tiene que ser mayor que 0.")
            if k == "dur" and pista == "O1":
                c["fin"] = c[k]
        elif k in rangos:
            x = _num(v, k, *rangos[k])
            c[k] = int(x) if k == "tamano" else x
        else:
            posibles = sorted({*rangos, *de_tiempo, *extras})
            raise ProyectoError(f"ajustar: '{k}' no es un parámetro de un clip de {pista}. Posibles: {', '.join(posibles)}.")
        cambios.append(f"{k}={c[k]}")
    if not cambios:
        raise ProyectoError("ajustar: no indicaste ningún parámetro.")
    return f"ajustó {o['clip']}: {', '.join(cambios)}"


def _op_formato(p: dict, o: dict) -> str:
    f = o.get("formato")
    if f not in FORMATOS:
        raise ProyectoError(f"formato: {', '.join(FORMATOS)}.")
    p["formato"], (p["ancho"], p["alto"]) = f, FORMATOS[f]
    return f"cambió el formato a {f}"


def _op_renombrar(p: dict, o: dict) -> str:
    n = o.get("nombre")
    if not isinstance(n, str) or not n.strip() or len(n) > 80:
        raise ProyectoError("renombrar: el nombre tiene que tener entre 1 y 80 caracteres.")
    p["nombre"] = n.strip()
    return f"renombró el proyecto a «{p['nombre']}»"


OPERACIONES = {"agregar_clip": _op_agregar_clip, "agregar_overlay": _op_agregar_overlay, "agregar_texto": _op_agregar_texto, "recortar": _op_recortar, "dividir": _op_dividir,
               "mover": _op_mover, "borrar": _op_borrar, "ajustar": _op_ajustar, "formato": _op_formato, "renombrar": _op_renombrar}


def aplicar(pid: str, operaciones: list, por: str = "ia", rev_base: int | None = None) -> dict:
    """Aplica una lista de operaciones de forma ATÓMICA. Devuelve el proyecto nuevo y un resumen de lo que se hizo."""
    if por not in ("ia", "usuario"):
        raise ProyectoError("`por` tiene que ser 'ia' o 'usuario'.")
    if not isinstance(operaciones, list) or not operaciones or len(operaciones) > 50:
        raise ProyectoError("operaciones: una lista de 1 a 50 operaciones.")
    with _LOCK:
        p = _cargar(pid)
        if rev_base is not None and int(rev_base) != p["rev"]:
            raise ProyectoError(f"El proyecto cambió (revisión {p['rev']}, vos tenías la {rev_base}). Volvé a leerlo y repetí el cambio.")
        antes = _estado(p)
        trabajo = copy.deepcopy(p)
        resumen = []
        for n, o in enumerate(operaciones, 1):
            fn = OPERACIONES.get(o.get("op") if isinstance(o, dict) else None)
            if fn is None:
                raise ProyectoError(f"Operación {n}: '{o.get('op') if isinstance(o, dict) else o}' no existe. Opciones: {', '.join(OPERACIONES)}.")
            try:
                resumen.append(fn(trabajo, o))
            except ProyectoError as exc:
                raise ProyectoError(f"Operación {n} ({o.get('op')}): {exc} No se aplicó ningún cambio.") from None
        trabajo["rev"] += 1
        trabajo["actualizado"] = _ahora()
        trabajo["ultimo_cambio"] = {"por": por, "resumen": "; ".join(resumen)[:300]}
        h = _hist(pid)
        h["deshacer"] = (h["deshacer"] + [antes])[-MAX_HISTORIAL:]
        h["rehacer"] = []
        _guardar(trabajo)
        _guardar({"id": pid, **h}, ".hist")
        return {"proyecto": _calcular(trabajo), "resumen": resumen}


def _mover_historial(pid: str, por: str, hacia: str) -> dict:
    origen, destino = ("deshacer", "rehacer") if hacia == "deshacer" else ("rehacer", "deshacer")
    with _LOCK:
        p, h = _cargar(pid), _hist(pid)
        if not h[origen]:
            raise ProyectoError(f"No hay nada para {hacia}.")
        h[destino] = (h[destino] + [_estado(p)])[-MAX_HISTORIAL:]
        e = h[origen].pop()
        p.update(formato=e["formato"], ancho=e["ancho"], alto=e["alto"], pistas=e["pistas"])
        p["rev"] += 1
        p["actualizado"] = _ahora()
        p["ultimo_cambio"] = {"por": por, "resumen": f"{hacia} el último cambio"}
        _guardar(p)
        _guardar({"id": pid, **h}, ".hist")
        return {"proyecto": _calcular(p), "resumen": [p["ultimo_cambio"]["resumen"]]}


def deshacer(pid: str, por: str = "usuario") -> dict:
    return _mover_historial(pid, por, "deshacer")


def rehacer(pid: str, por: str = "usuario") -> dict:
    return _mover_historial(pid, por, "rehacer")


# --- render -----------------------------------------------------------------------------------------------------------------
def _atempo(f: float) -> str:
    partes = []
    while f < 0.5:
        partes.append("atempo=0.5")
        f /= 0.5
    while f > 2.0:
        partes.append("atempo=2.0")
        f /= 2.0
    partes.append(f"atempo={f:.4f}")
    return ",".join(partes)


def _par(x: int) -> int:
    return max(2, x - x % 2)


def _amix_normalize() -> bool:
    try:
        r = subprocess.run([ve.ffmpeg_exe(), "-hide_banner", "-h", "filter=amix"], capture_output=True, timeout=20)
        return b"normalize" in r.stdout
    except (OSError, subprocess.TimeoutExpired, ve.VideoError):
        return False


def _ass(p: dict, w: int, h: int) -> str | None:
    textos = p["pistas"]["T1"]
    if not textos:
        return None
    alin = {"arriba": 8, "centro": 5, "abajo": 2}
    ex = int(720 * w / h)
    estilos, lineas = [], []
    for k, c in enumerate(textos):
        estilos.append(f"Style: T{k},Arial,{c['tamano']},&H00{ve.COLORES[c['color']]},&H00000000,&H80000000,-1,1,3,1,{alin[c['posicion']]},60,60,50,1")
        limpio = re.sub(r"[{}\\]", "", c["texto"]).replace("\r", "").replace("\n", r"\N")
        lineas.append(f"Dialogue: 0,{ve._ass_tiempo(c['pos'])},{ve._ass_tiempo(c['pos'] + c['dur'])},T{k},{{\\fad(300,300)}}{limpio}")
    return (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {ex}\nPlayResY: 720\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            + "\n".join(estilos) + "\n\n[Events]\nFormat: Layer, Start, End, Style, Text\n" + "\n".join(lineas) + "\n")


def _cadena_video(c: dict, w: int, h: int, fps: int) -> list[str]:
    """Filtros de UN clip de V1: recorte, velocidad, zoom, giro, efectos, encuadre y color. Va entre [i:v] y la etiqueta."""
    dur, vel, z = c["dur"], c.get("velocidad", 1.0), c.get("zoom", 1.0)
    cad = [f"trim=start={c['inicio']}:end={c['fin']}", "setpts=PTS-STARTPTS"]
    if vel != 1.0:
        cad.append(f"setpts=PTS/{vel}")
    if z != 1.0:
        cad.append(f"crop=iw/{z}:ih/{z}")
    rot = int(c.get("rotacion", 0))
    cad += {0: [], 90: ["transpose=1"], 180: ["hflip", "vflip"], 270: ["transpose=2"]}[rot]
    if c.get("espejo"):
        cad.append("hflip")
    if c.get("desenfoque", 0) > 0:
        cad.append(f"gblur=sigma={c['desenfoque']}")
    if c.get("nitidez", 0) > 0:
        cad.append(f"unsharp=5:5:{c['nitidez']}")
    cad += [f"fps={fps}", f"scale={w}:{h}:force_original_aspect_ratio=decrease", f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2", "setsar=1"]
    if (c.get("brillo", 0.0), c.get("contraste", 1.0), c.get("saturacion", 1.0)) != (0.0, 1.0, 1.0):
        cad.append(f"eq=brightness={c['brillo']}:contrast={c['contraste']}:saturation={c['saturacion']}")
    if ve.FILTROS_COLOR.get(c.get("filtro", "ninguno")):
        cad.append(ve.FILTROS_COLOR[c["filtro"]])
    if c.get("vineta", 0) > 0:
        cad.append(f"vignette=angle={round(c['vineta'] * 3.14159 / 3, 3)}")
    if c.get("fundido_in", 0) > 0:
        cad.append(f"fade=t=in:st=0:d={min(c['fundido_in'], dur)}")
    if c.get("fundido_out", 0) > 0:
        cad.append(f"fade=t=out:st={max(0.0, dur - c['fundido_out'])}:d={min(c['fundido_out'], dur)}")
    return cad + ["format=yuv420p"]


def _cadena_capa(c: dict, w: int, h: int, fps: int) -> tuple[list[str], list[str]]:
    """(opciones de entrada, filtros) de UNA capa de O1. La capa se pone en `pos` con `setpts` y se dibuja con `overlay` en su centro (x, y)."""
    dur, tipo = c["dur"], c["tipo"]
    if tipo == "imagen":
        pre, cad = ["-loop", "1", "-framerate", str(fps), "-t", str(dur)], ["setpts=PTS-STARTPTS"]
    elif tipo == "gif":
        pre, cad = ["-ignore_loop", "0"], ["setpts=PTS-STARTPTS", f"trim=duration={dur}", "setpts=PTS-STARTPTS"]
    else:
        pre, cad = [], [f"trim=start={c['inicio']}:end={c['fin']}", "setpts=PTS-STARTPTS"]
    ancho = max(16, int(c["escala"] * w) // 2 * 2)
    cad += [f"fps={fps}", "format=rgba", f"scale={ancho}:-2"]
    if c.get("rotacion", 0):
        cad.append(f"rotate={round(c['rotacion'] * 3.14159265 / 180, 4)}:ow='hypot(iw,ih)':oh=ow:c=none")
    if c.get("opacidad", 1.0) < 1.0:
        cad.append(f"colorchannelmixer=aa={c['opacidad']}")
    if c.get("fundido_in", 0) > 0:
        cad.append(f"fade=t=in:st=0:d={min(c['fundido_in'], dur)}:alpha=1")
    if c.get("fundido_out", 0) > 0:
        cad.append(f"fade=t=out:st={max(0.0, dur - c['fundido_out'])}:d={min(c['fundido_out'], dur)}:alpha=1")
    cad.append(f"setpts=PTS+{c['pos']}/TB")
    return pre, cad


def construir(p: dict, calidad: str = "final") -> tuple[list[str], str, str | None]:
    """(entradas de ffmpeg, filter_complex, subtítulos ASS) del proyecto. Separado de `renderizar` para poder probarlo sin ffmpeg."""
    calc = _calcular(p)
    v1 = calc["pistas"]["V1"]
    if not v1:
        raise ProyectoError("El proyecto no tiene clips de video: agregá al menos uno a V1.")
    w, h = p["ancho"], p["alto"]
    if calidad == "preview":
        w, h = _par(w // 2), _par(h // 2)
    fps = int(p.get("fps", 30))
    entradas: list[str] = []
    n_in = [0]
    idx: dict[str, int] = {}

    def entrada(nombre: str, exts: set[str], pre: list[str] | None = None) -> int:
        """Un archivo como entrada de ffmpeg. Los de V1 y audio se comparten; las capas llevan opciones propias y no."""
        if pre is None and nombre in idx:
            return idx[nombre]
        try:
            ruta = str(ve.resolver(nombre, exts))
        except ve.VideoError as exc:
            raise ProyectoError(str(exc)) from None
        entradas.extend([*(pre or []), "-i", ruta])
        n_in[0] += 1
        if pre is None:
            idx[nombre] = n_in[0] - 1
        return n_in[0] - 1

    filtros, hay_trans = [], any(c["tdur"] > 0 for c in v1)
    for k, c in enumerate(v1):
        i = entrada(c["archivo"], ve.VIDEO_EXT)
        dur, vel = c["dur"], c.get("velocidad", 1.0)
        filtros.append(f"[{i}:v]{','.join(_cadena_video(c, w, h, fps))}[v{k}]")
        if c.get("tiene_audio"):
            au = [f"atrim=start={c['inicio']}:end={c['fin']}", "asetpts=PTS-STARTPTS"]
            if vel != 1.0:
                au.append(_atempo(vel))
            au.append(f"volume={c.get('volumen', 1.0)}")
            if c.get("fundido_in", 0) > 0:
                au.append(f"afade=t=in:st=0:d={min(c['fundido_in'], dur)}")
            if c.get("fundido_out", 0) > 0:
                au.append(f"afade=t=out:st={max(0.0, dur - c['fundido_out'])}:d={min(c['fundido_out'], dur)}")
            filtros.append(f"[{i}:a]{','.join(au + ['aresample=48000', 'aformat=channel_layouts=stereo'])}[a{k}]")
        else:
            filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={dur},asetpts=PTS-STARTPTS[a{k}]")
    if not hay_trans:
        filtros.append(f"{''.join(f'[v{k}][a{k}]' for k in range(len(v1)))}concat=n={len(v1)}:v=1:a=1[vc][ac]")
    else:
        # Los clips unidos por un corte se concatenan en un GRUPO; los grupos se unen con xfade / acrossfade (la transición va en el clip que ENTRA).
        grupos: list[list[int]] = []
        for k, c in enumerate(v1):
            if k and c["tdur"] > 0:
                grupos.append([k])
            elif grupos:
                grupos[-1].append(k)
            else:
                grupos.append([k])
        for g, miembros in enumerate(grupos):
            if len(miembros) == 1:
                filtros.append(f"[v{miembros[0]}]null[gv{g}];[a{miembros[0]}]anull[ga{g}]")
            else:
                filtros.append(f"{''.join(f'[v{k}][a{k}]' for k in miembros)}concat=n={len(miembros)}:v=1:a=1[gv{g}][ga{g}]")
        largo = sum(v1[k]["dur"] for k in grupos[0])
        av, aa = "gv0", "ga0"
        for g in range(1, len(grupos)):
            c, td = v1[grupos[g][0]], v1[grupos[g][0]]["tdur"]
            nombre = TRANSICIONES[c["transicion"]]
            filtros.append(f"[{av}][gv{g}]xfade=transition={nombre}:duration={td}:offset={round(largo - td, 3)}[xv{g}]")
            filtros.append(f"[{aa}][ga{g}]acrossfade=d={td}[xa{g}]")
            av, aa = f"xv{g}", f"xa{g}"
            largo = round(largo + sum(v1[k]["dur"] for k in grupos[g]) - td, 3)
        filtros.append(f"[{av}]null[vc];[{aa}]anull[ac]")
    # audio de A1 (música) y A2 (efectos), mezclado sobre el del video
    mezcla = ["[ac]"]
    for pista in PISTAS_AUDIO:
        for c in calc["pistas"][pista]:
            i = entrada(c["archivo"], ve.VIDEO_EXT | ve.AUDIO_EXT)
            ms = int(round(c["pos"] * 1000))
            au = [f"atrim=start={c['inicio']}:end={c['fin']}", "asetpts=PTS-STARTPTS", f"volume={c['volumen']}"]
            if c["fundido_in"] > 0:
                au.append(f"afade=t=in:st=0:d={min(c['fundido_in'], c['dur'])}")
            if c["fundido_out"] > 0:
                au.append(f"afade=t=out:st={max(0.0, c['dur'] - c['fundido_out'])}:d={min(c['fundido_out'], c['dur'])}")
            au += [f"adelay={ms}|{ms}", "aresample=48000", "aformat=channel_layouts=stereo"]
            etiqueta = f"m{len(mezcla) - 1}"
            filtros.append(f"[{i}:a]{','.join(au)}[{etiqueta}]")
            mezcla.append(f"[{etiqueta}]")
    if len(mezcla) > 1:
        n = len(mezcla)
        if _amix_normalize():
            filtros.append(f"{''.join(mezcla)}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[aout]")
        else:
            filtros.append(f"{''.join(mezcla)}amix=inputs={n}:duration=first:dropout_transition=0,volume={n}[aout]")
    else:
        filtros.append("[ac]anull[aout]")
    # capas (imágenes, GIFs, videos) encima del video, en el orden de la pista
    actual = "vc"
    for k, c in enumerate(calc["pistas"]["O1"]):
        pre, cad = _cadena_capa(c, w, h, fps)
        i = entrada(c["archivo"], ve.IMG_EXT | ve.VIDEO_EXT, pre)
        filtros.append(f"[{i}:v]{','.join(cad)}[o{k}]")
        filtros.append(f"[{actual}][o{k}]overlay=x=W*{c['x']}-w/2:y=H*{c['y']}-h/2:enable='between(t,{c['pos']},{round(c['pos'] + c['dur'], 3)})':eof_action=pass[vo{k}]")
        actual = f"vo{k}"
    ass = _ass(calc, w, h)
    filtros.append(f"[{actual}]subtitles=t.ass[vout]" if ass else f"[{actual}]null[vout]")
    return entradas, ";\n".join(filtros), ass


def renderizar(pid: str, calidad: str = "final") -> dict:
    """UN ffmpeg con todo el proyecto. `calidad='preview'` saca una versión liviana (mitad de resolución) para mirar rápido."""
    if calidad not in ("final", "preview"):
        raise ProyectoError("calidad: final o preview.")
    with _LOCK:
        p = _cargar(pid)
    entradas, grafo, ass = construir(p, calidad)
    out = ve.nueva_salida(p["id"], "preview" if calidad == "preview" else "editado", "mp4")
    rapido = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p"] if calidad == "preview" else ve._X264
    try:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "g.txt").write_text(grafo, encoding="utf-8")
            if ass:
                (Path(tmp) / "t.ass").write_text(ass, encoding="utf-8")
            ve._ffmpeg([*entradas, "-filter_complex_script", "g.txt", "-map", "[vout]", "-map", "[aout]", *rapido, *ve._AAC,
                        "-threads", str(ve._hilos()), "-movflags", "+faststart", str(out)], cwd=tmp)
    except ve.VideoError as exc:
        raise ProyectoError(str(exc)) from None
    return ve._hecho(out, proyecto=pid, rev=p["rev"], calidad=calidad)
