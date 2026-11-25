"""Lo común de los tres cocineros: cola de trabajo, no duplicar, resumir, guardar la nota, vigilar listas y avisar.

Cada acción procesa UN ítem (o arma la cola de una lista), así ninguna se pasa del tope de tiempo del harness. Las listas
largas se van vaciando de a pocos en cada pasada (`tick`). Lo de terceros (transcripciones, páginas, abstracts) es dato:
va al modelo entre marcas, se sanea al guardar y nunca se ejecuta ni se obedece.

Datos en el espacio de la brigada: `notas` (lo ingerido, con su origen y su contenido), `cola` (lo que falta), `fallidos`,
`vigiladas` (listas y búsquedas que se revisan solas) y `estado` (cuándo se revisó por última vez)."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta

from raphael_core import Action, ActionError, Cook, Health, Message, Reply
from raphael_core.contract import Trust

from . import adapters
from .config import Settings, settings_of
from .model import Item, NoContent, SourceError
from .summary import summarize
from .text import one_line
from .vault import FileVault, build_note, note_id

MAX_ATTEMPTS = 3
RETRY_AFTER_MIN = 15
STALE_RUNNING_MIN = 30


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _later(dt: datetime, minutes: int) -> str:
    return _iso(dt + timedelta(minutes=minutes))


def _due(stamp: str, now: datetime) -> bool:
    if not stamp:
        return True
    try:
        return datetime.fromisoformat(stamp) <= now
    except ValueError:
        return True


class Ingester(Cook):
    """Base de los cocineros de ingesta. Cada uno define `source`, qué mensajes le interesan y sus acciones propias."""

    source = ""
    commands = {
        "notas": "lo ingerido, lo más nuevo primero ({'limit': n, 'fuente': 'youtube'|'web'|'arxiv'} opcionales)",
        "cola": "lo que falta procesar",
        "fallidos": "lo que no se pudo ingerir, con el motivo",
        "vigiladas": "listas y búsquedas que se revisan solas",
        "estado": "modo de cada fuente, carpeta del vault y cuánto hay de cada cosa",
    }

    def __init__(self) -> None:
        self._adapter = None
        self.adapter_error = ""

    # --- configuración y piezas enchufables ---------------------------------------------------------------------------
    def cfg(self, ctx) -> Settings:
        return settings_of(ctx.config)

    @property
    def adapter(self):
        return self._adapter

    @adapter.setter
    def adapter(self, value) -> None:  # los tests (o una instalación a medida) pueden enchufar el suyo
        self._adapter = value

    def get_adapter(self, ctx):
        if self._adapter is None:
            self._adapter = adapters.make(self.source, self.cfg(ctx).mode_of(self.source))
        return self._adapter

    def vault(self, ctx) -> FileVault | None:
        root = self.cfg(ctx).vault_dir
        return FileVault(root) if root else None

    # --- salud ------------------------------------------------------------------------------------------------------
    def health(self, ctx) -> Health:
        return Health(True, f"{self.source}: modo {self.cfg(ctx).mode_of(self.source)}")

    # --- lectura (comandos) -----------------------------------------------------------------------------------------
    def command(self, name: str, data: dict, ctx):
        sh = ctx.shared
        if name == "notas":
            notes = [n for n in sh.list("notas") if not data.get("fuente") or n["fuente"] == data["fuente"]]
            notes.reverse()
            notes.sort(key=lambda n: n["fecha"], reverse=True)  # estable: a igual fecha, la última guardada primero
            return [
                {k: n[k] for k in ("id", "titulo", "origen", "fecha", "fuente", "categoria", "por", "veredicto")}
                for n in notes[: int(data.get("limit") or 20)]
            ]
        if name == "cola":
            return [{k: j.get(k) for k in ("id", "fuente", "titulo", "estado", "intentos", "no_antes")} for j in sh.list("cola")]
        if name == "fallidos":
            return sh.list("fallidos")
        if name == "vigiladas":
            return sh.list("vigiladas")
        if name == "estado":
            cfg = self.cfg(ctx)
            return {
                "modos": {s: cfg.mode_of(s) for s in ("youtube", "web", "arxiv")},
                "vault": cfg.vault_dir or "(sin carpeta: las notas quedan en el almacén de la brigada)",
                "notas": len(sh.list("notas")),
                "cola": len(sh.list("cola")),
                "fallidos": len(sh.list("fallidos")),
                "vigiladas": len(sh.list("vigiladas")),
            }
        return super().command(name, data, ctx)

    # --- mensajes: solo la persona dueña ordena ingerir -------------------------------------------------------------
    def interest(self, msg: Message, ctx) -> float:
        return 0.0 if msg.trust is not Trust.TRUSTED else self.wants(msg.text)

    def wants(self, text: str) -> float:
        return 0.0

    # --- ejecución -------------------------------------------------------------------------------------------------
    async def execute(self, action: Action, ctx) -> str | None:
        t, d = action.type, action.data
        if t == "ingerir_item":
            return await self.run_job(ctx, str(d.get("id", "")))
        if t == "revisar_vigiladas":
            return await self.check_watched(ctx)
        if t == "vigilar":
            return self.watch(ctx, str(d.get("ref", "")))
        if t == "dejar_de_vigilar":
            return self.unwatch(ctx, str(d.get("id", "")))
        if t == "borrar_nota":
            return self.delete_note(ctx, str(d.get("id", "")))
        return await self.execute_source(action, ctx)

    async def execute_source(self, action: Action, ctx) -> str | None:
        raise ActionError(f"{self.name} no sabe ejecutar '{action.type}'")

    # --- el pipeline: un ítem -> una nota ---------------------------------------------------------------------------
    async def ingest(self, ctx, source_id: str, load: Callable[[], Item], *, force: bool = False) -> dict:
        """Trae el ítem, lo resume y guarda la nota. Idempotente por id de fuente. Levanta `SourceError`/`NoContent`."""
        nid = f"{self.source}:{source_id}"
        have = ctx.shared.get("notas", nid)
        if have and not force:
            return {"state": "ya_estaba", "id": nid, "title": have["titulo"]}
        item = await asyncio.to_thread(load)
        cfg = self.cfg(ctx)
        s = await asyncio.to_thread(summarize, ctx, item, cfg.topics, cfg.max_text_chars)
        when = ctx.now()
        content = build_note(item, s, when)
        path = ""
        vault = self.vault(ctx)
        if vault is not None:
            path = vault.save(item, s.title, content)
        nid = note_id(item)
        ctx.shared.put(
            "notas",
            nid,
            {
                "id": nid,
                "fuente": item.source,
                "id_fuente": item.source_id,
                "titulo": s.title,
                "origen": item.url,
                "fecha": _iso(when),
                "categoria": s.category,
                "por": s.by,
                "veredicto": s.verdict,
                "baja_relevancia": s.low,
                "ruta": path,
                "resumen": s.summary,
                "contenido": content,
            },
        )
        ctx.publish(
            "nota.ingerida",
            {
                "id": nid,
                "fuente": item.source,
                "titulo": s.title,
                "origen": item.url,
                "categoria": s.category,
                "ruta": path,
                "resumen": s.summary,
                "contenido": content,
            },
        )
        return {"state": "creada", "id": nid, "title": s.title, "by": s.by, "path": path}

    def say(self, out: dict) -> str:
        if out["state"] == "ya_estaba":
            return f"Ya la tenía: «{out['title']}». No la dupliqué."
        warn = "" if out["by"] == "modelo" else " (sin modelo: resumen por reglas, sin evaluar relevancia)"
        return f"Listo, guardé «{out['title']}»{warn}."

    def fail(self, ctx, ref: str, title: str, err: SourceError, *, stop: bool) -> str:
        """Un ítem que no se pudo: si no tiene arreglo (sin contenido) o se agotaron los intentos, queda en `fallidos`."""
        reason = err.reason
        if stop:
            ctx.shared.put(
                "fallidos",
                f"{self.source}:{ref}",
                {
                    "id": f"{self.source}:{ref}",
                    "fuente": self.source,
                    "titulo": title,
                    "motivo": reason,
                    "fecha": _iso(ctx.now()),
                },
            )
            ctx.publish("ingesta.fallo", {"fuente": self.source, "ref": ref, "titulo": title, "motivo": reason})
        return reason

    async def ingest_now(self, ctx, source_id: str, title: str, load: Callable[[], Item], force: bool = False) -> str:
        """Ingesta pedida directamente por la persona: el motivo del fallo se le dice tal cual (no se encola)."""
        try:
            return self.say(await self.ingest(ctx, source_id, load, force=force))
        except NoContent as exc:
            return f"No pude ingerirlo: {self.fail(ctx, source_id, title, exc, stop=True)}."
        except SourceError as exc:
            return f"No pude ingerirlo ahora: {self.fail(ctx, source_id, title, exc, stop=not exc.retriable)}."

    # --- la cola ---------------------------------------------------------------------------------------------------
    def enqueue(self, ctx, entries, limit: int) -> tuple[int, int, int]:
        """Mete a la cola lo nuevo de una lista: (en cola, ya vistos, ya estaban en la cola). Respeta el tope.
        Lo que falló sin arreglo (`fallidos`) no vuelve a entrar solo; la persona lo puede pedir a mano."""
        queued = known = waiting = 0
        for e in entries:
            nid = f"{self.source}:{e.source_id}"
            if ctx.shared.get("notas", nid) or ctx.shared.get("fallidos", nid):
                known += 1  # ya ingerido, o ya intentado sin arreglo (sin subtítulos): no se reintenta solo
            elif ctx.shared.get("cola", nid):
                waiting += 1
            elif queued < limit:
                job = {
                    "id": nid,
                    "fuente": self.source,
                    "ref": e.source_id,
                    "titulo": one_line(e.title, 200),
                    "estado": "pendiente",
                    "intentos": 0,
                    "no_antes": "",
                    "desde": _iso(ctx.now()),
                }
                if e.item is not None:
                    job["item"] = dataclasses.asdict(e.item)
                ctx.shared.put("cola", nid, job)
                queued += 1
        return queued, known, waiting

    def load_for(self, ctx, job: dict) -> Callable[[], Item]:
        if job.get("item"):
            return lambda: Item(**job["item"])
        return lambda: self.fetch_ref(ctx, job["ref"])

    def fetch_ref(self, ctx, ref: str) -> Item:
        raise SourceError(f"{self.source} no sabe traer '{ref}'")

    async def run_job(self, ctx, job_id: str) -> str:
        job = ctx.shared.get("cola", job_id)
        if job is None or job.get("fuente") != self.source:
            return "Ese pendiente ya no está en la cola."
        job["estado"] = "en_curso"
        job["desde"] = _iso(ctx.now())
        ctx.shared.put("cola", job_id, job)
        try:
            out = await self.ingest(ctx, job["ref"], self.load_for(ctx, job))
        except SourceError as exc:
            job["intentos"] += 1
            stop = isinstance(exc, NoContent) or not exc.retriable or job["intentos"] >= MAX_ATTEMPTS
            reason = self.fail(ctx, job["ref"], job["titulo"], exc, stop=stop)
            if stop:
                ctx.shared.delete("cola", job_id)
            else:
                job.update(estado="pendiente", no_antes=_later(ctx.now(), RETRY_AFTER_MIN * job["intentos"]), error=reason)
                ctx.shared.put("cola", job_id, job)
            return f"No pude ingerir «{job['titulo']}»: {reason}."
        except Exception:
            job["estado"] = "pendiente"  # un fallo de código no deja el trabajo colgado
            ctx.shared.put("cola", job_id, job)
            raise
        ctx.shared.delete("cola", job_id)
        return self.say(out)

    def tick(self, now: datetime, ctx) -> None:
        """Cada pasada: revisa lo vigilado si toca y manda a procesar unos pocos ítems de la cola."""
        cfg = self.cfg(ctx)
        mine = [w for w in ctx.shared.list("vigiladas") if w["fuente"] == self.source]
        key = f"revision-{self.source}"
        last = (ctx.shared.get("estado", key) or {}).get("ultima", "")
        if mine and _due(last, now):
            ctx.shared.put("estado", key, {"ultima": _later(now, cfg.check_every_min)})
            ctx.request(Action("revisar_vigiladas", {}, summary=f"Revisar lo vigilado de {self.source}"))
        sent = 0
        for job in ctx.shared.list("cola", fuente=self.source):
            if sent >= cfg.per_tick:
                break
            stale = job["estado"] == "en_curso" and _due(_later(datetime.fromisoformat(job["desde"]), STALE_RUNNING_MIN), now)
            if (job["estado"] == "pendiente" and _due(job.get("no_antes", ""), now)) or stale:
                job["estado"] = "en_curso"
                job["desde"] = _iso(now)
                ctx.shared.put("cola", job["id"], job)
                ctx.request(Action("ingerir_item", {"id": job["id"]}, summary=f"Ingerir «{job['titulo']}» ({self.source})"))
                sent += 1

    # --- vigilar -----------------------------------------------------------------------------------------------------
    def watch_key(self, ref: str) -> str:
        return f"{self.source}:{hashlib.sha256(ref.encode()).hexdigest()[:12]}"

    def check_ref(self, ref: str) -> str:
        """Valida lo que se quiere vigilar (una lista, una búsqueda). Levanta `ActionError` si no sirve."""
        return ref.strip()

    def watch(self, ctx, ref: str) -> str:
        ref = self.check_ref(ref)
        key = self.watch_key(ref)
        ctx.shared.put("vigiladas", key, {"id": key, "fuente": self.source, "ref": ref, "desde": _iso(ctx.now())})
        ctx.shared.delete("estado", f"revision-{self.source}")  # que la primera revisión sea en la próxima pasada
        return f"Listo, voy a revisar «{one_line(ref, 80)}» cada {self.cfg(ctx).check_every_min} minutos."

    def unwatch(self, ctx, wid: str) -> str:
        w = ctx.shared.get("vigiladas", wid)
        if w is None or w["fuente"] != self.source:
            return "Esa no la estaba vigilando."
        ctx.shared.delete("vigiladas", wid)
        return f"Dejé de vigilar «{one_line(w['ref'], 80)}»."

    async def check_watched(self, ctx) -> str:
        total = 0
        notes: list[str] = []
        for w in ctx.shared.list("vigiladas", fuente=self.source):
            try:
                queued, _known, _waiting = await self.scan(ctx, w["ref"])
                total += queued
            except SourceError as exc:
                notes.append(f"«{one_line(w['ref'], 60)}»: {exc.reason}")
                ctx.publish("ingesta.fallo", {"fuente": self.source, "ref": w["ref"], "titulo": "", "motivo": exc.reason})
        return (
            f"Revisé lo vigilado de {self.source}: {total} nuevos en la cola."
            if not notes
            else f"Revisé lo vigilado de {self.source}: {total} nuevos en la cola. Con problemas: " + "; ".join(notes)
        )

    async def scan(self, ctx, ref: str) -> tuple[int, int, int]:
        raise SourceError(f"{self.source} no se vigila")

    # --- borrar ----------------------------------------------------------------------------------------------------
    def delete_note(self, ctx, nid: str) -> str:
        n = ctx.shared.get("notas", nid)
        if n is None or n["fuente"] != self.source:
            return "No encontré esa nota."
        gone = ""
        vault = self.vault(ctx)
        if n.get("ruta") and vault is not None and not vault.delete(n["ruta"]):
            gone = " (el archivo ya no estaba en el vault)"
        ctx.shared.delete("notas", nid)
        ctx.record("nota_borrada", id=nid)
        return f"Borré la nota «{n['titulo']}»{gone}."

    # --- armar la respuesta a un pedido de la persona ---------------------------------------------------------------
    @staticmethod
    def reply(text: str, *actions: Action) -> Reply:
        return Reply(text, list(actions))
