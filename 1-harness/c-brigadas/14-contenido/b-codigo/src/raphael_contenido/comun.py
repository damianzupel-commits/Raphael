"""Lo que comparten los cocineros de Contenido: trabajos pesados en segundo plano, ids, fechas y la base de cada cocinero.

Los trabajos pesados (render de ffmpeg, ComfyUI, subir un Reel) NO corren en el hilo del harness: se encolan y los hace un
solo hilo, uno a la vez (en el VPS de 8 GB un trabajo de video a la vez, con prioridad baja). La acción que los pide vuelve
enseguida con el número de trabajo; el estado vive en la colección `trabajos` del espacio de la brigada y el `tick` avisa por
el bus cuando uno termina.
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from raphael_core import ActionError, Cook

#: tipo de trabajo -> evento que se publica al terminar bien
EVENTO_LISTO = {"video": "video.listo", "proyecto": "video.listo", "generar_imagen": "imagen.lista", "generar_video": "imagen.lista",
                "publicar": "publicacion.publicada"}
EVENTO_FALLO = "contenido.trabajo_fallido"
TERMINADOS = ("listo", "error", "interrumpido")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def edition_of(ctx) -> str:
    """La edición de la instalación (`personal` o `cloud`). Si no se puede saber, `cloud`: lo peligroso falla cerrado."""
    try:
        return str(ctx._rt.installation.edition)   # noqa: SLF001
    except Exception:  # noqa: BLE001
        return "cloud"


def short(text: str, n: int = 80) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def need_str(data: dict, key: str, *, max_len: int = 2000) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ActionError(f"Falta «{key}».")
    if len(v) > max_len:
        raise ActionError(f"«{key}» es demasiado largo (máximo {max_len} caracteres).")
    return v.strip()


class Jobs:
    """Una cola con un solo hilo: los trabajos corren de a uno, en orden."""

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._space = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._open = 0
        self._idle = threading.Event()
        self._idle.set()
        self._clock: Callable[[], datetime] = datetime.now

    def bind(self, space, clock: Callable[[], datetime]) -> None:
        """Se llama al arrancar el cocinero. Lo que quedó `en_cola` o `en_curso` de una corrida anterior se marca interrumpido."""
        self._space, self._clock = space, clock
        for rec in space.list("trabajos"):
            if rec.get("estado") in ("en_cola", "en_curso"):
                rec.update(estado="interrumpido", terminado=clock().isoformat(timespec="seconds"), notificado=False,
                           error="se cortó antes de terminar (se reinició Raphael); revisá y pedilo de nuevo")
                space.put("trabajos", str(rec["id"]), rec)

    def submit(self, cook: str, kind: str, label: str, fn: Callable[[], dict]) -> dict:
        sp = self._space
        n = sp.next("trabajos")
        rec = {"id": n, "cook": cook, "tipo": kind, "detalle": label, "estado": "en_cola",
               "creado": self._clock().isoformat(timespec="seconds"), "notificado": False}
        sp.put("trabajos", str(n), rec)
        with self._lock:
            self._open += 1
            self._idle.clear()
            self._q.put((n, fn))
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._work, name=f"contenido-{cook}", daemon=True)
                self._thread.start()
        return rec

    def _work(self) -> None:
        sp = self._space
        while True:
            try:
                n, fn = self._q.get(timeout=2)
            except queue.Empty:
                with self._lock:
                    if self._q.empty():
                        self._thread = None
                        return
                continue
            rec = sp.get("trabajos", str(n)) or {"id": n}
            rec["estado"] = "en_curso"
            sp.put("trabajos", str(n), rec)
            try:
                result = fn()
                rec.update(estado="listo", resultado=result)
            except Exception as exc:  # noqa: BLE001 - un trabajo roto no tumba el hilo
                rec.update(estado="error", error=str(exc)[:400] or exc.__class__.__name__)
            rec.update(terminado=self._clock().isoformat(timespec="seconds"), notificado=False)
            sp.put("trabajos", str(n), rec)
            with self._lock:
                self._open -= 1
                if self._open <= 0:
                    self._idle.set()

    def join(self, timeout: float = 30.0) -> bool:
        """Espera a que no quede nada en la cola (para los tests y para apagar)."""
        return self._idle.wait(timeout)


class CocineroConTrabajos(Cook):
    """Base de los cocineros que encolan trabajos: `start` ata la cola, `tick` avisa lo terminado y `trabajos` lo muestra."""

    commands = {"trabajos": "Trabajos en segundo plano (en cola, en curso y terminados)"}

    def __init__(self) -> None:
        self.jobs = Jobs()

    def start(self, ctx) -> None:
        self.jobs.bind(ctx.shared, lambda: ctx.now())

    def enqueue(self, ctx, kind: str, label: str, fn: Callable[[], dict]) -> str:
        rec = self.jobs.submit(self.name, kind, label, fn)
        return f"Quedó en cola como trabajo #{rec['id']} ({label}). Te aviso cuando termine; se ve en «trabajos»."

    def tick(self, now, ctx) -> None:
        for rec in ctx.shared.list("trabajos", cook=self.name):
            if rec.get("estado") not in TERMINADOS or rec.get("notificado"):
                continue
            rec["notificado"] = True
            ctx.shared.put("trabajos", str(rec["id"]), rec)
            if rec["estado"] == "listo":
                ev = EVENTO_LISTO.get(rec["tipo"])
                if ev:
                    ctx.publish(ev, {"trabajo": rec["id"], "tipo": rec["tipo"], "resultado": _small(rec.get("resultado"))})
            else:
                ctx.publish(EVENTO_FALLO, {"trabajo": rec["id"], "tipo": rec["tipo"], "error": rec.get("error", "")})

    def command(self, name: str, data: dict, ctx) -> Any:
        if name == "trabajos":
            estados = data.get("estado")
            return [r for r in ctx.shared.list("trabajos", cook=self.name) if not estados or r.get("estado") == estados][-50:]
        return super().command(name, data, ctx)

    def stop(self, ctx) -> None:
        self.jobs.join(5)


def _small(result: Any) -> Any:
    """Del resultado de un trabajo, lo que va al bus: rutas y números, nunca textos largos."""
    if not isinstance(result, dict):
        return None
    return {k: v for k, v in result.items() if isinstance(v, (str, int, float, bool)) and (not isinstance(v, str) or len(v) <= 300)}
