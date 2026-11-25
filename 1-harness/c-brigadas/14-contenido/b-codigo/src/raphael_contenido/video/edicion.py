"""Edición de video para el cocinero Video (brigada Contenido, portado de JarvisRemote `app/video_edit.py`): un envoltorio fino y ACOTADO sobre ffmpeg (y faster-whisper para transcribir).

Reglas duras (las hace cumplir este módulo, no un prompt):
  - CARPETA FIJA: solo se lee dentro de `VIDEO_EDIT_DIR` (default `Documentos/Videos-Raphael`), con `entrada/` y `salida/`.
    Una ruta que salga de ahí (absoluta, `..`, enlace simbólico) se rechaza.
  - EL ORIGINAL NO SE TOCA: toda operación escribe un archivo NUEVO en `salida/`, con nombre único. Nunca se pisa ni se
    borra nada (ffmpeg corre con `-n`: si el destino existiera, falla en vez de sobrescribir).
  - ffmpeg se invoca con lista de argumentos (sin shell), con tope de tiempo, de a UN trabajo por vez, con pocos hilos y
    prioridad baja. Motivo real: esta PC tiene antecedentes de apagarse bajo carga sostenida; por eso también se prefiere
    copiar los streams (sin recodificar) cuando la operación lo permite.

Solo stdlib (faster-whisper corre en un subproceso). Todo lo que toca el mundo (ffmpeg, Whisper, la carpeta de trabajo) se
inyecta con `configure(...)`: en producción es el real; en los tests, el simulado de `runner.py` y sin ffmpeg ni Whisper.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
SUB_EXT = {".srt"}
FORMATOS_SALIDA = {"mp4", "mov", "mkv", "mp3", "wav", "m4a"}
MAX_UNIR = 20
MAX_TRAMOS = 200          # tope de tramos al quitar silencios (un filtro más largo no entra en la línea de comandos)
_LOCK = threading.Lock()  # un ffmpeg / una transcripción a la vez


class VideoError(Exception):
    """Error de una operación de video, con un mensaje que se le puede mostrar al dueño tal cual."""


# --- inyección: carpeta, ffmpeg y Whisper --------------------------------------------------------------------------------
_BASE: Path | None = None
_RUNNER = None       # objeto con .exe() y .run(cmd, timeout, cwd) -> (returncode, stderr); ver runner.py
_WHISPER_FN = None   # (wav, idioma) -> [{'inicio','fin','texto'}]; None = faster-whisper real


def configure(*, base: str | Path | None = None, runner=None, whisper=None) -> None:
    """Fija la carpeta de trabajo y los adaptadores. Lo llama el cocinero Video al arrancar (y los tests)."""
    global _BASE, _RUNNER, _WHISPER_FN
    _BASE = Path(base).expanduser() if base else None
    _RUNNER = runner
    _WHISPER_FN = whisper


def runner():
    global _RUNNER
    if _RUNNER is None:
        from .runner import RealRunner
        _RUNNER = RealRunner()
    return _RUNNER


# --- carpeta fija ---------------------------------------------------------------------------------------------------
def base_dir() -> Path:
    if _BASE is not None:
        return _BASE
    override = os.getenv("VIDEO_EDIT_DIR", "").strip()
    return Path(override).expanduser() if override else Path.home() / "Documents" / "Videos-Raphael"


def entrada_dir() -> Path:
    return base_dir() / "entrada"


def salida_dir() -> Path:
    return base_dir() / "salida"


def efectos_dir() -> Path:
    """Efectos de sonido y recursos sueltos (también se buscan ahí): el pack propio de Raphael y lo que el usuario ponga."""
    return base_dir() / "efectos"


# Pack propio de efectos de sonido: SINTÉTICOS (generados con ffmpeg, sin copyright ni descargas). Son sonidos simples;
# para efectos de estudio, el usuario deja los suyos en `efectos/`.
_SFX = {
    "ding": "sine=f=1318:d=0.7,afade=t=out:st=0.05:d=0.65",
    "campana": "sine=f=880:d=1.4,tremolo=f=6:d=0.3,afade=t=out:st=0.1:d=1.3",
    "pop": "sine=f=520:d=0.12,afade=t=out:st=0.02:d=0.1",
    "tic": "sine=f=1800:d=0.05,afade=t=out:st=0:d=0.05",
    "whoosh": "anoisesrc=d=0.9:c=pink:a=0.5,highpass=f=300,lowpass=f=4000,afade=t=in:st=0:d=0.4,afade=t=out:st=0.4:d=0.5",
    "subida": "aevalsrc=0.4*sin(2*PI*(300+900*t)*t):d=1.0,afade=t=out:st=0.8:d=0.2",
    "caida": "aevalsrc=0.4*sin(2*PI*(1200-900*t)*t):d=1.0,afade=t=out:st=0.8:d=0.2",
    "alerta": "sine=f=990:d=0.35,tremolo=f=12:d=0.8,afade=t=out:st=0.25:d=0.1",
}


def generar_efectos() -> list[str]:
    """Crea en `efectos/` los que falten del pack sintético. Devuelve los nombres creados. Nunca pisa un archivo existente."""
    d = efectos_dir()
    d.mkdir(parents=True, exist_ok=True)
    hechos = []
    for nombre, expr in _SFX.items():
        destino = d / f"{nombre}.wav"
        if destino.exists():
            continue
        try:
            _ffmpeg(["-f", "lavfi", "-i", expr, "-ar", "48000", "-ac", "2", str(destino)])
            hechos.append(destino.name)
        except Exception:
            destino.unlink(missing_ok=True)       # un efecto que no se pudo generar no frena a los demás
    return hechos


def asegurar_carpetas() -> None:
    for d in (entrada_dir(), salida_dir()):
        d.mkdir(parents=True, exist_ok=True)


def resolver(nombre: str, extensiones: set[str] | None = None) -> Path:
    """Un archivo EXISTENTE dentro de la carpeta fija. Se busca tal cual (relativo a la carpeta), en `entrada/` y en `salida/`."""
    if not isinstance(nombre, str) or not nombre.strip():
        raise VideoError("Falta el nombre del archivo.")
    asegurar_carpetas()
    base = base_dir().resolve()
    dado = Path(nombre.strip())
    candidatos = [dado] if dado.is_absolute() else [base / dado, entrada_dir() / dado, salida_dir() / dado, efectos_dir() / dado]
    for c in candidatos:
        try:
            real = c.resolve()
        except OSError:
            continue
        if not real.is_relative_to(base):  # absoluta afuera, `..`, o un enlace que apunta afuera
            raise VideoError(f"'{nombre}' está fuera de la carpeta de video ({base}). La brigada solo trabaja ahí adentro.")
        if real.is_file():
            ext = real.suffix.lower()
            if ext not in (extensiones or (VIDEO_EXT | AUDIO_EXT | SUB_EXT | IMG_EXT)):
                raise VideoError(f"'{real.name}' no es un tipo de archivo que esta operación acepte ({ext or 'sin extensión'}).")
            return real
    raise VideoError(f"No encontré '{nombre}' en la carpeta de video. Poné el archivo en {entrada_dir()} (usá video_listar para ver qué hay).")


def nueva_salida(origen: str, sufijo: str, ext: str) -> Path:
    """Ruta NUEVA en `salida/` (nunca existente): `<origen>-<sufijo>[-N].<ext>`, con el nombre saneado."""
    asegurar_carpetas()
    limpio = re.sub(r"-{2,}", "-", re.sub(r"[^\w\-]+", "-", Path(origen).stem, flags=re.UNICODE)).strip("-")[:60] or "video"
    suf = re.sub(r"-{2,}", "-", re.sub(r"[^\w\-]+", "-", sufijo, flags=re.UNICODE)).strip("-")[:30] or "editado"
    ext = ext.lower().lstrip(".")
    for n in range(1, 1000):
        p = salida_dir() / f"{limpio}-{suf}{'' if n == 1 else f'-{n}'}.{ext}"
        if not p.exists():
            return p
    raise VideoError("Demasiados archivos con el mismo nombre en la carpeta de salida.")


# --- ffmpeg -----------------------------------------------------------------------------------------------------------
def ffmpeg_exe() -> str:
    return runner().exe()


def _hilos() -> int:
    try:
        n = int(os.getenv("VIDEO_FFMPEG_THREADS", "0"))
    except ValueError:
        n = 0
    return max(1, n) if n > 0 else max(1, min(4, (os.cpu_count() or 2) // 2))


def _timeout() -> float:
    try:
        return max(30.0, float(os.getenv("VIDEO_FFMPEG_TIMEOUT_SECONDS", "1800")))
    except ValueError:
        return 1800.0


def _ffmpeg(args: list[str], *, cwd: str | None = None, permitir_fallo: bool = False) -> str:
    """Corre ffmpeg (sin shell, sin sobrescribir, sin stdin) y devuelve su stderr. VideoError si falla."""
    r = runner()
    cmd = [r.exe(), "-hide_banner", "-nostdin", "-n", *args]
    with _LOCK:
        code, err = r.run(cmd, _timeout(), cwd)
    if code != 0 and not permitir_fallo:
        ultimas = " | ".join(line.strip() for line in err.strip().splitlines()[-3:])
        raise VideoError(f"ffmpeg falló: {ultimas[:400]}")
    return err


_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]
_AAC = ["-c:a", "aac", "-b:a", "160k"]


def _codificar() -> list[str]:
    return [*_X264, *_AAC, "-threads", str(_hilos()), "-movflags", "+faststart"]


def segundos(valor: object, nombre: str = "tiempo") -> float:
    """'90', 90, '1:30', '01:02:03.5' -> segundos."""
    if isinstance(valor, bool):
        raise VideoError(f"{nombre}: no es un tiempo válido.")
    if isinstance(valor, (int, float)):
        s = float(valor)
    else:
        m = re.fullmatch(r"\s*(?:(\d+):)?(?:(\d+):)?(\d+(?:[.,]\d+)?)\s*", str(valor))
        if not m:
            raise VideoError(f"{nombre}: '{valor}' no es un tiempo válido (usá segundos o mm:ss o hh:mm:ss).")
        a, b, c = m.group(1), m.group(2), float(m.group(3).replace(",", "."))
        s = (int(a) * 3600 + int(b) * 60 + c) if b is not None else ((int(a) * 60 + c) if a is not None else c)
    if s < 0 or s > 48 * 3600:
        raise VideoError(f"{nombre}: fuera de rango.")
    return round(s, 3)


def info(path: Path) -> dict:
    """Duración, resolución y pistas, leídos de lo que ffmpeg informa del archivo (no hace falta ffprobe)."""
    err = _ffmpeg(["-i", str(path)], permitir_fallo=True)
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    v = re.search(r"Stream #\S+.*Video:.*?(\d{2,5})x(\d{2,5})", err)
    fps = re.search(r"(\d+(?:\.\d+)?)\s*fps", err)
    if not d and not v and "Audio:" not in err:
        raise VideoError(f"'{path.name}' no se pudo leer como video o audio.")
    return {"archivo": path.name, "duracion_s": round(int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)), 2) if d else None,
            "ancho": int(v.group(1)) if v else None, "alto": int(v.group(2)) if v else None,
            "fps": float(fps.group(1)) if fps else None, "tiene_video": bool(v), "tiene_audio": "Audio:" in err,
            "tamano_mb": round(path.stat().st_size / 1_048_576, 2)}


def _hecho(salida: Path, **extra) -> dict:
    if not salida.is_file() or salida.stat().st_size == 0:
        raise VideoError("La operación terminó pero no dejó un archivo de salida.")
    datos = info(salida) if salida.suffix.lower() in (VIDEO_EXT | AUDIO_EXT) else {"archivo": salida.name}
    return {"path": str(salida), **datos, **extra, "original_intacto": True}


# --- operaciones ------------------------------------------------------------------------------------------------------
def listar() -> dict:
    asegurar_carpetas()

    def de(d: Path) -> list[dict]:
        out = []
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in (VIDEO_EXT | AUDIO_EXT | SUB_EXT | IMG_EXT):
                out.append({"archivo": p.name, "tamano_mb": round(p.stat().st_size / 1_048_576, 2)})
        return out[:200]

    return {"carpeta": str(base_dir()), "entrada": de(entrada_dir()), "salida": de(salida_dir()),
            "efectos": de(efectos_dir()) if efectos_dir().is_dir() else []}


def recortar(archivo: str, inicio: object, fin: object, preciso: bool = False) -> dict:
    src = resolver(archivo, VIDEO_EXT | AUDIO_EXT)
    a, b = segundos(inicio, "inicio"), segundos(fin, "fin")
    if b <= a:
        raise VideoError("El fin tiene que ser posterior al inicio.")
    dur = info(src)["duracion_s"]
    if dur and a >= dur:
        raise VideoError(f"El inicio ({a} s) está después del final del video ({dur} s).")
    out = nueva_salida(src.name, f"recorte-{int(a)}-{int(b)}", src.suffix)
    if preciso:  # recodifica: corte exacto al cuadro, más lento y más carga
        _ffmpeg(["-ss", str(a), "-to", str(b), "-i", str(src), *_codificar(), str(out)])
    else:        # copia los streams: rápido y liviano; el corte cae en el cuadro clave más cercano
        _ffmpeg(["-ss", str(a), "-to", str(b), "-i", str(src), "-c", "copy", "-avoid_negative_ts", "make_zero", str(out)])
    return _hecho(out, modo="preciso (recodificado)" if preciso else "rápido (sin recodificar; el corte puede correrse hasta el cuadro clave)")


def unir(archivos: list) -> dict:
    if not isinstance(archivos, list) or not 2 <= len(archivos) <= MAX_UNIR:
        raise VideoError(f"Para unir hacen falta entre 2 y {MAX_UNIR} archivos, en el orden en que van.")
    srcs = [resolver(a, VIDEO_EXT) for a in archivos]
    out = nueva_salida(srcs[0].name, f"unido-{len(srcs)}", "mp4")
    with tempfile.TemporaryDirectory() as tmp:
        lista = Path(tmp) / "lista.txt"
        lista.write_text("".join("file '" + str(s).replace("'", "'\\''") + "'\n" for s in srcs), encoding="utf-8")
        try:  # 1º sin recodificar (sirve cuando los clips tienen el mismo formato)
            _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(out)])
            return _hecho(out, modo="sin recodificar", partes=len(srcs))
        except VideoError:
            if out.exists():
                out = nueva_salida(srcs[0].name, f"unido-{len(srcs)}", "mp4")  # no se borra nada: nombre nuevo
    infos = [info(s) for s in srcs]
    if not all(i["tiene_video"] and i["tiene_audio"] for i in infos):
        raise VideoError("Los clips tienen formatos distintos y alguno no tiene audio o video: no se pueden unir automáticamente.")
    w, h = infos[0]["ancho"], infos[0]["alto"]
    filtros = "".join(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];"
                      f"[{i}:a]aresample=48000[a{i}];" for i in range(len(srcs)))
    filtros += "".join(f"[v{i}][a{i}]" for i in range(len(srcs))) + f"concat=n={len(srcs)}:v=1:a=1[v][a]"
    entradas = [x for s in srcs for x in ("-i", str(s))]
    _ffmpeg([*entradas, "-filter_complex", filtros, "-map", "[v]", "-map", "[a]", *_codificar(), str(out)])
    return _hecho(out, modo="recodificado (los clips tenían formatos distintos)", partes=len(srcs))


def convertir(archivo: str, formato: str = "mp4", alto: int | None = None) -> dict:
    src = resolver(archivo, VIDEO_EXT | AUDIO_EXT)
    formato = str(formato or "mp4").lower().lstrip(".")
    if formato not in FORMATOS_SALIDA:
        raise VideoError(f"Formato no soportado: {formato}. Opciones: {', '.join(sorted(FORMATOS_SALIDA))}.")
    if alto is not None and (isinstance(alto, bool) or not isinstance(alto, int) or not 144 <= alto <= 2160):
        raise VideoError("El alto tiene que ser un número entre 144 y 2160 (por ejemplo 720 o 1080).")
    if formato in ("mp3", "wav", "m4a"):  # solo el audio
        codec = {"mp3": ["-c:a", "libmp3lame", "-b:a", "192k"], "wav": ["-c:a", "pcm_s16le"], "m4a": _AAC}[formato]
        out = nueva_salida(src.name, "audio", formato)
        _ffmpeg(["-i", str(src), "-vn", *codec, str(out)])
        return _hecho(out)
    out = nueva_salida(src.name, f"{alto}p" if alto else "convertido", formato)
    escala = ["-vf", f"scale=-2:{alto}"] if alto else []
    _ffmpeg(["-i", str(src), *escala, *_codificar(), str(out)])
    return _hecho(out)


def detectar_silencios(src: Path, umbral_db: float, min_silencio: float) -> list[tuple[float, float]]:
    err = _ffmpeg(["-i", str(src), "-vn", "-af", f"silencedetect=noise={umbral_db}dB:d={min_silencio}", "-f", "null", "-"])
    ini = [float(x) for x in re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", err)]
    fin = [float(x) for x in re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", err)]
    return [(max(0.0, a), b) for a, b in zip(ini, fin + [float("inf")] * (len(ini) - len(fin)))]


def quitar_silencios(archivo: str, umbral_db: float = -35.0, min_silencio: float = 0.6, margen: float = 0.15) -> dict:
    src = resolver(archivo, VIDEO_EXT)
    try:
        umbral_db, min_silencio, margen = float(umbral_db), float(min_silencio), float(margen)
    except (TypeError, ValueError):
        raise VideoError("umbral_db, min_silencio y margen tienen que ser números.") from None
    if not (-80 <= umbral_db <= -10 and 0.2 <= min_silencio <= 10 and 0 <= margen <= 1):
        raise VideoError("Valores fuera de rango: umbral_db entre -80 y -10, min_silencio entre 0.2 y 10 s, margen entre 0 y 1 s.")
    datos = info(src)
    dur = datos["duracion_s"] or 0.0
    if not datos["tiene_audio"]:
        raise VideoError("El video no tiene audio: no hay silencios que detectar.")
    silencios = detectar_silencios(src, umbral_db, min_silencio)
    tramos, cursor = [], 0.0
    for a, b in silencios:  # se conserva lo que queda ENTRE silencios, con un margen para no cortar palabras
        if a + margen > cursor + 0.05:
            tramos.append((cursor, min(dur, a + margen)))
        cursor = max(cursor, min(dur, b) - margen)
    if dur - cursor > 0.05:
        tramos.append((cursor, dur))
    if not silencios:
        return {"sin_cambios": True, "motivo": "no se detectaron silencios con esos valores", **datos, "original_intacto": True}
    if not tramos or len(tramos) > MAX_TRAMOS:
        raise VideoError("No se pudo armar el corte: " + ("el video es casi todo silencio." if not tramos else
                                                         f"hay demasiados tramos ({len(tramos)}); subí min_silencio."))
    cond = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in tramos)
    out = nueva_salida(src.name, "sin-silencios", "mp4")
    _ffmpeg(["-i", str(src), "-vf", f"select='{cond}',setpts=N/FRAME_RATE/TB", "-af", f"aselect='{cond}',asetpts=N/SR/TB",
             *_codificar(), str(out)])
    r = _hecho(out, tramos=len(tramos))
    r["segundos_quitados"] = round(dur - (r.get("duracion_s") or dur), 2)
    return r


def audio(archivo: str, normalizar: bool = True, reducir_ruido: bool = False, musica: str | None = None, volumen_musica: float = 0.15) -> dict:
    src = resolver(archivo, VIDEO_EXT)
    if not info(src)["tiene_audio"]:
        raise VideoError("El video no tiene audio.")
    if not (normalizar or reducir_ruido or musica):
        raise VideoError("No pediste ningún cambio de audio (normalizar, reducir ruido o música).")
    try:
        volumen_musica = float(volumen_musica)
    except (TypeError, ValueError):
        raise VideoError("volumen_musica tiene que ser un número.") from None
    if not 0.01 <= volumen_musica <= 1.0:
        raise VideoError("volumen_musica va entre 0.01 y 1.0 (0.15 es un fondo suave).")
    cadena = ([] if not reducir_ruido else ["afftdn=nf=-25"]) + ([] if not normalizar else ["loudnorm=I=-16:TP=-1.5:LRA=11"])
    hecho = "+".join(x for x, s in (("ruido", reducir_ruido), ("normalizado", normalizar), ("musica", bool(musica))) if s)
    out = nueva_salida(src.name, f"audio-{hecho}", "mp4")
    comun = ["-c:v", "copy", *_AAC, "-movflags", "+faststart"]  # el video se copia tal cual: solo se rehace el audio
    if musica:
        mus = resolver(musica, AUDIO_EXT)
        voz = ",".join(cadena) or "anull"
        fc = f"[0:a]{voz}[voz];[1:a]volume={volumen_musica}[mus];[voz][mus]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
        _ffmpeg(["-i", str(src), "-stream_loop", "-1", "-i", str(mus), "-filter_complex", fc, "-map", "0:v", "-map", "[a]", *comun, "-shortest", str(out)])
    else:
        _ffmpeg(["-i", str(src), "-af", ",".join(cadena), "-map", "0:v", "-map", "0:a", *comun, str(out)])
    return _hecho(out, cambios=hecho)


def vertical(archivo: str, inicio: object = None, fin: object = None) -> dict:
    """Clip vertical 9:16 (1080x1920) recortando el centro del cuadro. Con inicio/fin, además recorta ese tramo."""
    src = resolver(archivo, VIDEO_EXT)
    datos = info(src)
    if not datos["tiene_video"]:
        raise VideoError("El archivo no tiene video.")
    tramo: list[str] = []
    suf = "vertical"
    if inicio is not None or fin is not None:
        a = segundos(inicio if inicio is not None else 0, "inicio")
        b = segundos(fin, "fin") if fin is not None else (datos["duracion_s"] or 0)
        if b <= a:
            raise VideoError("El fin tiene que ser posterior al inicio.")
        if b - a > 180:
            raise VideoError("Un clip vertical no puede durar más de 180 segundos.")
        tramo, suf = ["-ss", str(a), "-to", str(b)], f"vertical-{int(a)}-{int(b)}"
    vf = "crop='min(iw,ih*9/16)':ih,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
    out = nueva_salida(src.name, suf, "mp4")
    _ffmpeg([*tramo, "-i", str(src), "-vf", vf, *_codificar(), str(out)])
    return _hecho(out)


def _t_srt(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def a_srt(segmentos: list[dict]) -> str:
    return "".join(f"{i}\n{_t_srt(s['inicio'])} --> {_t_srt(s['fin'])}\n{s['texto'].strip()}\n\n" for i, s in enumerate(segmentos, 1))


_WHISPER_SCRIPT = (
    "import json,os,sys\n"
    "from faster_whisper import WhisperModel\n"
    "m=WhisperModel(os.environ.get('VIDEO_WHISPER_MODEL','small'),device='cpu',compute_type='int8',cpu_threads=int(sys.argv[3]))\n"
    "segs,_=m.transcribe(sys.argv[1],language=sys.argv[2] or None,vad_filter=True)\n"
    "print(json.dumps([{'inicio':round(s.start,2),'fin':round(s.end,2),'texto':s.text.strip()} for s in segs if s.text.strip()]))\n"
)


def _python_con_whisper() -> str | None:
    """Un intérprete que tenga faster-whisper: el actual, o el que indique `VIDEO_WHISPER_PYTHON`."""
    import importlib.util

    if importlib.util.find_spec("faster_whisper"):
        return sys.executable
    return os.getenv("VIDEO_WHISPER_PYTHON", "").strip() or None


def _popen_kwargs() -> dict:
    if sys.platform == "win32":
        return {"creationflags": 0x00004000 | 0x08000000}  # BELOW_NORMAL_PRIORITY_CLASS | CREATE_NO_WINDOW
    return {"preexec_fn": lambda: os.nice(10)}


def _whisper(wav: str, idioma: str) -> list[dict]:
    """Transcribe con faster-whisper en ESTA PC (CPU, pocos hilos, sin red), en un subproceso de prioridad baja. Con un
    transcriptor inyectado (`configure(whisper=...)`, el simulado de los tests) no corre nada real."""
    import json

    if _WHISPER_FN is not None:
        return _WHISPER_FN(wav, idioma)

    py = _python_con_whisper()
    if not py:
        raise VideoError("Para transcribir hace falta faster-whisper (pip install faster-whisper).")
    env = {**os.environ, "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        p = subprocess.run([py, "-c", _WHISPER_SCRIPT, wav, idioma or "", str(_hilos())], capture_output=True, timeout=_timeout(), env=env,
                           **_popen_kwargs())
    except subprocess.TimeoutExpired:
        raise VideoError(f"La transcripción superó el tiempo máximo ({int(_timeout())} s) y se cortó.") from None
    if p.returncode != 0:
        ultimas = " | ".join(x.strip() for x in p.stderr.decode("utf-8", "replace").strip().splitlines()[-2:])
        raise VideoError(f"Whisper falló: {ultimas[:300]} (si es el modelo: tiene que estar descargado)")
    try:
        return json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise VideoError("Whisper terminó sin devolver una transcripción.") from None


def transcribir(archivo: str, idioma: str = "es") -> dict:
    src = resolver(archivo, VIDEO_EXT | AUDIO_EXT)
    if not info(src)["tiene_audio"]:
        raise VideoError("El archivo no tiene audio para transcribir.")
    if not re.fullmatch(r"[a-z]{2}", str(idioma or "")):
        raise VideoError("El idioma va como código de dos letras (es, en, pt...).")
    with tempfile.TemporaryDirectory() as tmp:
        wav = str(Path(tmp) / "audio.wav")
        _ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
        with _LOCK:
            segmentos = _whisper(wav, idioma)
    if not segmentos:
        raise VideoError("No se detectó voz en el audio.")
    out = nueva_salida(src.name, "subtitulos", "srt")
    out.write_text(a_srt(segmentos), encoding="utf-8")
    texto = " ".join(s["texto"] for s in segmentos)
    return {"path": str(out), "archivo": out.name, "segmentos": len(segmentos), "duracion_s": segmentos[-1]["fin"],
            "texto": texto[:4000], "momentos": segmentos[:150], "original_intacto": True}


def subtitular(archivo: str, subtitulos: str, quemar: bool = True) -> dict:
    src = resolver(archivo, VIDEO_EXT)
    srt = resolver(subtitulos, SUB_EXT)
    if quemar:  # dibuja el texto sobre la imagen: recodifica. El .srt se copia a un temporal con nombre simple para no
        out = nueva_salida(src.name, "subtitulado", "mp4")  # pelear con el escapado de rutas del filtro en Windows.
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copyfile(srt, Path(tmp) / "s.srt")
            _ffmpeg(["-i", str(src), "-vf", "subtitles=s.srt", *_codificar(), str(out)], cwd=tmp)
        return _hecho(out, modo="subtítulos quemados en la imagen")
    out = nueva_salida(src.name, "con-subtitulos", "mp4")  # pista de subtítulos aparte: no recodifica
    _ffmpeg(["-i", str(src), "-i", str(srt), "-map", "0:v", "-map", "0:a?", "-map", "1:0", "-c:v", "copy", "-c:a", "copy",
             "-c:s", "mov_text", str(out)])
    return _hecho(out, modo="pista de subtítulos (se activa desde el reproductor)")


# ====================================================================================================================
# Segunda tanda: lo que un editor tipo Filmora ofrece como operaciones (transiciones, títulos, velocidad, color, capas...)
# ====================================================================================================================
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TRANSICIONES = ("fade", "dissolve", "fadeblack", "fadewhite", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright",
                "circleopen", "circleclose", "pixelize", "radial", "smoothleft", "smoothright")
MAX_TRANSICION = 8
FILTROS_COLOR = {
    "ninguno": "",
    "bn": "hue=s=0",
    "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "calido": "colorchannelmixer=rr=1.08:bb=0.92",
    "frio": "colorchannelmixer=rr=0.92:bb=1.08",
    "vintage": "curves=preset=vintage",
    "contraste_fuerte": "curves=preset=strong_contrast",
}
POSICIONES = {"arriba_izquierda": ("M", "M"), "arriba_derecha": ("W-w-M", "M"), "abajo_izquierda": ("M", "H-h-M"),
              "abajo_derecha": ("W-w-M", "H-h-M"), "centro": ("(W-w)/2", "(H-h)/2")}
COLORES = {"blanco": "FFFFFF", "negro": "000000", "amarillo": "00FFFF", "rojo": "0000FF", "verde": "00FF00", "azul": "FF0000", "cian": "FFFF00"}  # BGR (ASS)


def _num(valor: object, nombre: str, minimo: float, maximo: float) -> float:
    try:
        if isinstance(valor, bool):
            raise ValueError
        x = float(valor)
    except (TypeError, ValueError):
        raise VideoError(f"{nombre} tiene que ser un número.") from None
    if not minimo <= x <= maximo:
        raise VideoError(f"{nombre} va entre {minimo} y {maximo}.")
    return x


def _video(archivo: str) -> tuple[Path, dict]:
    src = resolver(archivo, VIDEO_EXT)
    datos = info(src)
    if not datos["tiene_video"]:
        raise VideoError(f"'{src.name}' no tiene video.")
    return src, datos


def _audio_opcional(datos: dict, filtro_audio: str | None = None) -> list[str]:
    """Argumentos de audio: con filtro si hay audio y hace falta; copia si hay y no se toca; nada si el video es mudo."""
    if not datos["tiene_audio"]:
        return ["-an"]
    return ["-af", filtro_audio, *_AAC] if filtro_audio else ["-c:a", "copy"]


def _solo_video(src: Path, datos: dict, vf: str, sufijo: str, extra_in: list[str] | None = None) -> dict:
    """Aplica un filtro de IMAGEN y conserva el audio tal cual."""
    out = nueva_salida(src.name, sufijo, "mp4")
    _ffmpeg([*(extra_in or []), "-i", str(src), "-vf", vf, *_X264, *_audio_opcional(datos), "-threads", str(_hilos()), "-movflags", "+faststart", str(out)])
    return _hecho(out)


def transicion(archivos: list, tipo: str = "fade", duracion: float = 1.0) -> dict:
    """Une clips con una TRANSICIÓN entre cada par (fundido, barrido, deslizamiento...). Recodifica."""
    if not isinstance(archivos, list) or not 2 <= len(archivos) <= MAX_TRANSICION:
        raise VideoError(f"Para unir con transición hacen falta entre 2 y {MAX_TRANSICION} clips, en orden.")
    if tipo not in TRANSICIONES:
        raise VideoError(f"Transición desconocida: {tipo}. Opciones: {', '.join(TRANSICIONES)}.")
    d = _num(duracion, "duracion", 0.2, 3.0)
    pares = [_video(a) for a in archivos]
    if any(not i["tiene_audio"] for _s, i in pares):
        raise VideoError("Todos los clips tienen que tener audio para unirlos con transición.")
    if any((i["duracion_s"] or 0) < d * 2 + 0.2 for _s, i in pares):
        raise VideoError(f"Algún clip es demasiado corto para una transición de {d} s.")
    w, h = pares[0][1]["ancho"], pares[0][1]["alto"]
    n = len(pares)
    fc = "".join(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p,settb=AVTB[v{i}];"
                 f"[{i}:a]aresample=48000,asettb=AVTB[a{i}];" for i in range(n))
    acumulado, v, a = 0.0, "v0", "a0"
    for i in range(1, n):
        acumulado += (pares[i - 1][1]["duracion_s"] or 0) - d
        fc += f"[{v}][v{i}]xfade=transition={tipo}:duration={d}:offset={acumulado:.3f}[x{i}];[{a}][a{i}]acrossfade=d={d}[y{i}];"
        v, a = f"x{i}", f"y{i}"
    out = nueva_salida(pares[0][0].name, f"transicion-{tipo}-{n}", "mp4")
    _ffmpeg([*[x for s, _i in pares for x in ("-i", str(s))], "-filter_complex", fc.rstrip(";"), "-map", f"[{v}]", "-map", f"[{a}]", *_codificar(), str(out)])
    return _hecho(out, transicion=tipo, partes=n)


def velocidad(archivo: str, factor: float) -> dict:
    """Cámara lenta (factor < 1) o rápida (factor > 1). El audio acompaña sin cambiar de tono."""
    src, datos = _video(archivo)
    f = _num(factor, "factor", 0.25, 4.0)
    if abs(f - 1) < 0.01:
        raise VideoError("Con factor 1 el video queda igual.")
    tempos, resto = [], f
    while resto > 2.0:
        tempos.append("atempo=2.0")
        resto /= 2.0
    while resto < 0.5:
        tempos.append("atempo=0.5")
        resto /= 0.5
    tempos.append(f"atempo={resto:.4f}")
    out = nueva_salida(src.name, f"velocidad-{str(f).replace('.', '_')}x", "mp4")
    _ffmpeg(["-i", str(src), "-vf", f"setpts=PTS/{f}", *_X264, *_audio_opcional(datos, ",".join(tempos)), "-threads", str(_hilos()), "-movflags", "+faststart", str(out)])
    return _hecho(out, factor=f)


def color(archivo: str, brillo: float = 0.0, contraste: float = 1.0, saturacion: float = 1.0, filtro: str = "ninguno") -> dict:
    src, datos = _video(archivo)
    b, c, s = _num(brillo, "brillo", -0.5, 0.5), _num(contraste, "contraste", 0.5, 2.0), _num(saturacion, "saturacion", 0.0, 3.0)
    if filtro not in FILTROS_COLOR:
        raise VideoError(f"Filtro desconocido: {filtro}. Opciones: {', '.join(FILTROS_COLOR)}.")
    if b == 0 and c == 1 and s == 1 and filtro == "ninguno":
        raise VideoError("No pediste ningún cambio de color.")
    partes = [f"eq=brightness={b}:contrast={c}:saturation={s}"] if (b, c, s) != (0, 1, 1) else []
    if FILTROS_COLOR[filtro]:
        partes.append(FILTROS_COLOR[filtro])
    return _solo_video(src, datos, ",".join(partes), f"color-{filtro}" if filtro != "ninguno" else "color")


def _ass_tiempo(s: float) -> str:
    cs = int(round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def texto(archivo: str, texto: str, posicion: str = "abajo", inicio: object = None, fin: object = None, tamano: int = 48,
          color: str = "blanco") -> dict:
    """Título o texto sobre el video, con contorno y fundido suave. Se dibuja con el motor de subtítulos (no depende de rutas de fuentes)."""
    src, datos = _video(archivo)
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 300:
        raise VideoError("El texto tiene que tener entre 1 y 300 caracteres.")
    alin = {"arriba": 8, "centro": 5, "abajo": 2}.get(posicion)
    if alin is None:
        raise VideoError("posicion: arriba, centro o abajo.")
    if color not in COLORES:
        raise VideoError(f"color: {', '.join(COLORES)}.")
    tam = int(_num(tamano, "tamano", 12, 200))
    dur = datos["duracion_s"] or 0.0
    a = segundos(inicio, "inicio") if inicio is not None else 0.0
    b = segundos(fin, "fin") if fin is not None else dur
    if b <= a:
        raise VideoError("El fin tiene que ser posterior al inicio.")
    limpio = re.sub(r"[{}\\]", "", texto.strip()).replace("\r", "").replace("\n", r"\N")  # sin etiquetas de estilo coladas en el texto
    ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\nWrapStyle: 0\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           f"Style: T,Arial,{tam},&H00{COLORES[color]},&H00000000,&H80000000,-1,1,3,1,{alin},60,60,50,1\n\n[Events]\n"
           "Format: Layer, Start, End, Style, Text\n"
           f"Dialogue: 0,{_ass_tiempo(a)},{_ass_tiempo(b)},T,{{\\fad(300,300)}}{limpio}\n")
    out = nueva_salida(src.name, "texto", "mp4")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "t.ass").write_text(ass, encoding="utf-8")
        _ffmpeg(["-i", str(src), "-vf", "subtitles=t.ass", *_X264, *_audio_opcional(datos), "-threads", str(_hilos()), "-movflags", "+faststart", str(out)], cwd=tmp)
    return _hecho(out, texto=texto.strip()[:80])


def superponer(archivo: str, capa: str, posicion: str = "abajo_derecha", escala: float = 0.2, opacidad: float = 1.0,
               inicio: object = None, fin: object = None) -> dict:
    """Logo, marca de agua o video encima (imagen en imagen). `escala` = ancho de la capa respecto del ancho del video."""
    src, datos = _video(archivo)
    cap = resolver(capa, IMG_EXT | VIDEO_EXT)
    if posicion not in POSICIONES:
        raise VideoError(f"posicion: {', '.join(POSICIONES)}.")
    e, op = _num(escala, "escala", 0.03, 1.0), _num(opacidad, "opacidad", 0.05, 1.0)
    x, y = (p.replace("M", str(max(8, int((datos["ancho"] or 1280) * 0.02)))) for p in POSICIONES[posicion])
    cuando = ""
    if inicio is not None or fin is not None:
        a = segundos(inicio if inicio is not None else 0, "inicio")
        b = segundos(fin, "fin") if fin is not None else (datos["duracion_s"] or 0)
        if b <= a:
            raise VideoError("El fin tiene que ser posterior al inicio.")
        cuando = f":enable='between(t,{a},{b})'"
    ancho = max(16, int((datos["ancho"] or 1280) * e) // 2 * 2)
    es_imagen = cap.suffix.lower() in IMG_EXT
    fc = (f"[1:v]scale={ancho}:-2,format=rgba,colorchannelmixer=aa={op}[capa];[0:v][capa]overlay={x}:{y}{cuando}"
          f"{'' if es_imagen else ':eof_action=pass'}[v]")
    out = nueva_salida(src.name, "superpuesto", "mp4")
    _ffmpeg(["-i", str(src), *(["-loop", "1"] if es_imagen else []), "-i", str(cap), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             *_X264, *_audio_opcional(datos), "-threads", str(_hilos()), "-movflags", "+faststart", "-t", str(datos["duracion_s"] or 0), str(out)])
    return _hecho(out, capa=cap.name)


def fundidos(archivo: str, entrada: float = 1.0, salida: float = 1.0) -> dict:
    """Fundido desde negro al empezar y a negro al terminar (imagen y sonido)."""
    src, datos = _video(archivo)
    fi, fo = _num(entrada, "entrada", 0, 5), _num(salida, "salida", 0, 5)
    dur = datos["duracion_s"] or 0.0
    if fi == 0 and fo == 0:
        raise VideoError("Indicá al menos un fundido (entrada o salida).")
    if fi + fo >= dur:
        raise VideoError("Los fundidos duran más que el video.")
    v = [x for x in (f"fade=t=in:st=0:d={fi}" if fi else "", f"fade=t=out:st={dur - fo:.3f}:d={fo}" if fo else "") if x]
    a = [x for x in (f"afade=t=in:st=0:d={fi}" if fi else "", f"afade=t=out:st={dur - fo:.3f}:d={fo}" if fo else "") if x]
    out = nueva_salida(src.name, "fundidos", "mp4")
    _ffmpeg(["-i", str(src), "-vf", ",".join(v), *_X264, *_audio_opcional(datos, ",".join(a)), "-threads", str(_hilos()), "-movflags", "+faststart", str(out)])
    return _hecho(out)


def rotar(archivo: str, giro: str) -> dict:
    src, datos = _video(archivo)
    vf = {"90": "transpose=1", "270": "transpose=2", "180": "hflip,vflip", "espejo": "hflip", "voltear": "vflip"}.get(str(giro))
    if not vf:
        raise VideoError("giro: 90, 180, 270 (grados, sentido horario), espejo (horizontal) o voltear (vertical).")
    return _solo_video(src, datos, vf, f"giro-{giro}")


def encuadrar(archivo: str, x: float, y: float, ancho: float, alto: float) -> dict:
    """Recorta el CUADRO (zoom a una zona). Valores en porcentaje del cuadro original: x, y = esquina superior izquierda."""
    src, datos = _video(archivo)
    px, py, pw, ph = (_num(v, n, 0, 100) for v, n in ((x, "x"), (y, "y"), (ancho, "ancho"), (alto, "alto")))
    if pw < 10 or ph < 10 or px + pw > 100.01 or py + ph > 100.01:
        raise VideoError("La zona tiene que entrar en el cuadro y medir al menos 10 % de ancho y de alto.")
    vf = f"crop=trunc(iw*{pw / 100:.4f}/2)*2:trunc(ih*{ph / 100:.4f}/2)*2:iw*{px / 100:.4f}:ih*{py / 100:.4f}"
    return _solo_video(src, datos, vf, "encuadre")


def estabilizar(archivo: str) -> dict:
    """Reduce el temblor de cámara (filtro deshake). Es lento: analiza cuadro por cuadro."""
    src, datos = _video(archivo)
    return _solo_video(src, datos, "deshake=rx=32:ry=32:edge=mirror", "estabilizado")


def pantalla_verde(archivo: str, fondo: str, color: str = "verde", tolerancia: float = 0.15) -> dict:
    """Reemplaza el fondo verde (o azul) de un video por una imagen o video de fondo."""
    src, datos = _video(archivo)
    fon = resolver(fondo, IMG_EXT | VIDEO_EXT)
    clave = {"verde": "0x00FF00", "azul": "0x0000FF"}.get(color)
    if not clave:
        raise VideoError("color: verde o azul.")
    tol = _num(tolerancia, "tolerancia", 0.01, 0.5)
    w, h = datos["ancho"], datos["alto"]
    es_imagen = fon.suffix.lower() in IMG_EXT
    fc = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[fondo];"
          f"[0:v]chromakey={clave}:{tol}:0.08[frente];[fondo][frente]overlay=shortest=1[v]")
    out = nueva_salida(src.name, "pantalla-verde", "mp4")
    _ffmpeg(["-i", str(src), *(["-loop", "1"] if es_imagen else ["-stream_loop", "-1"]), "-i", str(fon), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             *_X264, *_audio_opcional(datos), "-threads", str(_hilos()), "-movflags", "+faststart", "-t", str(datos["duracion_s"] or 0), str(out)])
    return _hecho(out, fondo=fon.name)


def escenas(archivo: str, sensibilidad: float = 0.35) -> dict:
    """Detecta los cambios de escena (solo lee): devuelve en qué segundos cambia el plano, para saber dónde cortar."""
    src, datos = _video(archivo)
    s = _num(sensibilidad, "sensibilidad", 0.1, 0.9)
    err = _ffmpeg(["-i", str(src), "-an", "-vf", f"select='gt(scene,{s})',showinfo", "-f", "null", "-"])
    cortes = sorted({round(float(t), 2) for t in re.findall(r"pts_time:(\d+(?:\.\d+)?)", err)})[:300]
    bordes = [0.0, *cortes, datos["duracion_s"] or 0.0]
    return {"archivo": src.name, "duracion_s": datos["duracion_s"], "cambios_de_escena": cortes,
            "tramos": [{"inicio": a, "fin": b} for a, b in zip(bordes, bordes[1:]) if b - a > 0.3][:300]}


def gif(archivo: str, inicio: object, fin: object, ancho: int = 480) -> dict:
    src, _datos = _video(archivo)
    a, b = segundos(inicio, "inicio"), segundos(fin, "fin")
    if not 0 < b - a <= 15:
        raise VideoError("Un GIF va de 0 a 15 segundos.")
    w = int(_num(ancho, "ancho", 120, 800))
    out = nueva_salida(src.name, f"gif-{int(a)}-{int(b)}", "gif")
    fc = f"fps=12,scale={w}:-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
    _ffmpeg(["-ss", str(a), "-to", str(b), "-i", str(src), "-filter_complex", fc, str(out)])
    if not out.is_file() or out.stat().st_size == 0:
        raise VideoError("No se pudo generar el GIF.")
    return {"path": str(out), "archivo": out.name, "tamano_mb": round(out.stat().st_size / 1_048_576, 2), "original_intacto": True}


def captura(archivo: str, momento: object) -> dict:
    """Una imagen fija (JPG) del video en ese momento."""
    src, datos = _video(archivo)
    t = segundos(momento, "momento")
    if datos["duracion_s"] and t >= datos["duracion_s"]:
        raise VideoError("Ese momento está después del final del video.")
    out = nueva_salida(src.name, f"captura-{int(t)}", "jpg")
    _ffmpeg(["-ss", str(t), "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)])
    if not out.is_file():
        raise VideoError("No se pudo sacar la captura.")
    return {"path": str(out), "archivo": out.name, "original_intacto": True}


def reversa(archivo: str) -> dict:
    """El video al revés. Solo clips cortos: ffmpeg lo carga entero en memoria."""
    src, datos = _video(archivo)
    if (datos["duracion_s"] or 0) > 30:
        raise VideoError("La reversa admite clips de hasta 30 segundos (recortá antes el tramo).")
    out = nueva_salida(src.name, "reversa", "mp4")
    _ffmpeg(["-i", str(src), "-vf", "reverse", *_X264, *_audio_opcional(datos, "areverse"), "-threads", str(_hilos()), "-movflags", "+faststart", str(out)])
    return _hecho(out)


# --- grabación de pantalla --------------------------------------------------------------------------------------------
def _max_grabacion() -> float:
    try:
        return max(5.0, float(os.getenv("VIDEO_GRABACION_MAX_SECONDS", "300")))
    except ValueError:
        return 300.0


def grabar_pantalla(duracion: object, nombre: str = "grabacion", ventana: str | None = None, escritorio_completo: bool = False) -> dict:
    """Graba la pantalla (sin audio) por un tiempo FIJO y deja el .mp4 como archivo NUEVO en `entrada/`, listo para editar.

    Lo hace cumplir el código, no el prompt: hay que elegir QUÉ grabar. O una `ventana` (por su título exacto) o
    `escritorio_completo=True`, que puede mostrar claves, chats y datos privados y por eso nunca es el valor por defecto.
    Solo Windows (gdigrab de ffmpeg). Un solo ffmpeg a la vez (el cerrojo de este módulo), así que no se pisan dos grabaciones."""
    if runner().real and sys.platform != "win32":
        raise VideoError("La grabación de pantalla usa gdigrab de ffmpeg y solo funciona en Windows.")
    d = segundos(duracion, "duracion")
    tope = _max_grabacion()
    if d < 1 or d > tope:
        raise VideoError(f"La duración tiene que estar entre 1 y {int(tope)} segundos (se puede subir con VIDEO_GRABACION_MAX_SECONDS).")
    if ventana is not None and (not isinstance(ventana, str) or not ventana.strip() or len(ventana) > 120 or any(ord(c) < 32 for c in ventana)):
        raise VideoError("El título de la ventana no es válido.")
    if bool(ventana) == bool(escritorio_completo):
        raise VideoError("Indicá qué grabar: el título de una ventana (`ventana`) o `escritorio_completo=true`. El escritorio completo puede "
                         "mostrar claves y datos privados: usalo solo si el dueño lo pidió.")
    asegurar_carpetas()
    limpio = re.sub(r"-{2,}", "-", re.sub(r"[^\w\-]+", "-", str(nombre or "grabacion"), flags=re.UNICODE)).strip("-")[:40] or "grabacion"
    from datetime import datetime
    out = entrada_dir() / f"{limpio}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.mp4"
    origen = "desktop" if escritorio_completo else f"title={ventana.strip()}"
    _ffmpeg(["-f", "gdigrab", "-framerate", "30", "-i", origen, "-t", str(d), "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
             *_X264, "-an", "-threads", str(_hilos()), "-movflags", "+faststart", str(out)])
    return _hecho(out, grabado="escritorio completo" if escritorio_completo else f"ventana '{ventana.strip()}'",
                  nota="Archivo nuevo en entrada/: ya se puede editar. Revisá que no muestre datos privados antes de publicarlo.")
