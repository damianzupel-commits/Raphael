"""Captura de campo: notas, voz y fotos tomadas en un negocio, con resumen del día y expediente consultable.

Pensado para el piloto del bodegón: Damián va anotando desde el celular durante el turno y Raphael lo ordena por tema
(salón, cocina, caja, personal, clientes). Todo vive en archivos de la PC, en `<datos>/campo/<negocio>/`:

    negocio.json                nombre del negocio
    diario/AAAA-MM-DD.jsonl     una línea por nota (texto, tema, hora, fuente, archivo adjunto)
    media/<id>.<ext>            audios y fotos tal como llegaron
    resumenes/AAAA-MM-DD.md     el resumen del día, cuando se pide

Reglas: los datos de un cliente son sensibles, así que la IA que resume o contesta se pide siempre como privada (solo un
modelo que corre en la PC; sin modelo cae a reglas y lo dice). Nada de esto sale a la nube ni a terceros. No escribe
fuera de su carpeta y los nombres de archivo los pone el código, nunca el cliente.
"""

from __future__ import annotations

import json
import re
import secrets
import unicodedata
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

TEMAS: dict[str, str] = {
    "salon": "Salón y comandas",
    "cocina": "Cocina y stock",
    "caja": "Caja y plata",
    "personal": "Personal",
    "clientes": "Clientes",
    "otro": "Otros",
}
# Palabras que delatan el tema cuando no se elige uno (sin tildes, en minúscula).
CLAVES_TEMA: dict[str, tuple[str, ...]] = {
    "salon": ("mesa", "comanda", "pedido", "mozo", "salon", "espera", "cuenta", "reserva de mesa", "plato volvio"),
    "cocina": ("cocina", "stock", "faltante", "falto", "vencid", "sobrante", "proveedor", "insumo", "tire", "merma",
               "heladera", "ingrediente", "receta"),
    "caja": ("caja", "cobro", "cobrar", "efectivo", "tarjeta", "transferencia", "mercado pago", "mercadopago", "cierre",
             "propina", "descuento", "fiado", "diferencia", "precio", "margen", "factura"),
    "personal": ("turno", "sueldo", "horas", "empleado", "mozo falto", "cocinero", "lavacopas", "franco", "personal"),
    "clientes": ("cliente", "reserva", "whatsapp", "queja", "reseña", "resena", "google", "instagram", "delivery",
                 "vuelve", "volvio", "telefono"),
}
# Señales de que algo hizo perder tiempo o plata (para ordenar el resumen cuando no hay IA local).
PERDIDA = ("falto", "faltante", "se perdio", "perdimos", "error", "equivocad", "volvio", "devolvi", "espero", "espera",
           "demora", "tarde", "tire", "vencid", "merma", "sobrante", "diferencia", "queja", "enojo", "se fue", "sin ",
           "no hay", "se termino", "se cayo", "doble", "olvid", "a mano", "reclamo", "fiado")
FUENTES = {"texto", "voz", "foto"}
AUDIO = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/wav": ".wav",
         "audio/x-wav": ".wav", "audio/aac": ".aac", "video/webm": ".webm"}
FOTO = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}
MAX_TEXTO = 4000
MAX_MEDIA = 15 * 1024 * 1024
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IDNOTA = re.compile(r"^[0-9]{8}-[0-9]{6}-[a-f0-9]{4}$")

Ask = Callable[[list[dict]], str | None]   # (mensajes) -> texto de un modelo privado o None


class CampoError(ValueError):
    """Un pedido que no se puede cumplir; el mensaje es para mostrarle a la persona."""


def norm(s: str) -> str:
    """Minúscula y sin tildes, para comparar."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def slug(nombre: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm(nombre)).strip("-")[:40].strip("-")
    if not SLUG.match(s):
        raise CampoError("poné un nombre para el negocio (letras o números)")
    return s


def elegir_tema(texto: str) -> str:
    t = norm(texto)
    puntos = {k: sum(t.count(w) for w in ws) for k, ws in CLAVES_TEMA.items()}
    mejor = max(puntos, key=lambda k: puntos[k])
    return mejor if puntos[mejor] else "otro"


def puntaje_perdida(texto: str) -> int:
    t = norm(texto)
    return sum(1 for w in PERDIDA if w in t)


def palabras(q: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]{3,}", norm(q)) if w not in {"cuantas", "cuantos", "veces", "esta", "semana", "que",
                                                                             "los", "las", "una", "del", "por", "con", "hubo"}]


def raiz(w: str) -> str:
    """Una raíz tosca para que «faltó» encuentre «faltante» y «mesas» encuentre «mesa»."""
    return w[:4] if len(w) >= 5 else (w[:-1] if w.endswith("s") and len(w) > 3 else w)


class Campo:
    def __init__(self, root: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self.root = Path(root)
        self.clock = clock

    # --- negocios
    def _dir(self, negocio: str) -> Path:
        if not SLUG.match(negocio or ""):
            raise CampoError("negocio inválido")
        return self.root / negocio

    def negocios(self) -> list[dict]:
        out = []
        for d in sorted(self.root.glob("*/negocio.json")) if self.root.is_dir() else []:
            try:
                out.append({"id": d.parent.name, "nombre": json.loads(d.read_text("utf-8")).get("nombre", d.parent.name)})
            except (OSError, ValueError):
                continue
        return out

    def crear_negocio(self, nombre: str) -> dict:
        nombre = " ".join(nombre.split())[:80]
        sid = slug(nombre)
        d = self._dir(sid)
        d.mkdir(parents=True, exist_ok=True)
        f = d / "negocio.json"
        if not f.exists():
            f.write_text(json.dumps({"nombre": nombre, "creado": self.clock().isoformat(timespec="seconds")},
                                    ensure_ascii=False), "utf-8")
        return {"id": sid, "nombre": json.loads(f.read_text("utf-8"))["nombre"]}

    def _existente(self, negocio: str) -> Path:
        d = self._dir(negocio)
        if not (d / "negocio.json").is_file():
            raise CampoError("ese negocio no existe: creálo primero")
        return d

    # --- notas
    def _id(self, now: datetime) -> str:
        return f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"

    def _append(self, d: Path, nota: dict) -> dict:
        f = d / "diario" / f"{nota['dia']}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(nota, ensure_ascii=False) + "\n")
        return nota

    def agregar(self, negocio: str, *, texto: str = "", tema: str = "auto", fuente: str = "texto",
                media: bytes | None = None, mime: str = "", estado: str = "ok", etiquetas: tuple[str, ...] = ()) -> dict:
        d = self._existente(negocio)
        if fuente not in FUENTES:
            raise CampoError("fuente desconocida")
        texto = texto.strip()[:MAX_TEXTO]
        if fuente == "texto" and not texto:
            raise CampoError("la nota está vacía")
        if tema != "auto" and tema not in TEMAS:
            raise CampoError("tema desconocido: " + ", ".join(TEMAS))
        now = self.clock()
        nid = self._id(now)
        archivo = ""
        if media is not None:
            tabla = AUDIO if fuente == "voz" else FOTO
            ext = tabla.get((mime or "").split(";")[0].strip().lower())
            if ext is None:
                raise CampoError("formato no admitido: " + (mime or "sin tipo"))
            if not media:
                raise CampoError("el archivo llegó vacío")
            if len(media) > MAX_MEDIA:
                raise CampoError("el archivo pasa los 15 MB")
            (d / "media").mkdir(exist_ok=True)
            archivo = nid + ext
            (d / "media" / archivo).write_bytes(media)
        t = tema if tema != "auto" else (elegir_tema(texto) if texto else "otro")
        return self._append(d, {"id": nid, "dia": f"{now:%Y-%m-%d}", "hora": f"{now:%H:%M}", "tema": t,
                                "tema_elegido": tema != "auto", "fuente": fuente, "texto": texto, "archivo": archivo,
                                "estado": estado, "etiquetas": list(etiquetas)})

    def cierre(self, negocio: str, cosas: list[str], dia: str | None = None) -> list[dict]:
        """Las tres cosas que más tiempo o plata hicieron perder ese día."""
        cosas = [c.strip()[:500] for c in cosas if c and c.strip()][:3]
        if not cosas:
            raise CampoError("escribí al menos una cosa")
        out = []
        for i, c in enumerate(cosas, 1):
            n = self.agregar(negocio, texto=c, tema="otro", etiquetas=("cierre", f"perdida-{i}"))
            if dia:
                n = self._mover(negocio, n, dia)
            out.append(n)
        return out

    def _mover(self, negocio: str, nota: dict, dia: str) -> dict:
        self._dia(dia)
        d = self._dir(negocio)
        viejo = d / "diario" / f"{nota['dia']}.jsonl"
        lineas = [ln for ln in viejo.read_text("utf-8").splitlines() if json.loads(ln)["id"] != nota["id"]]
        viejo.write_text("".join(ln + "\n" for ln in lineas), "utf-8")
        return self._append(d, {**nota, "dia": dia})

    @staticmethod
    def _dia(dia: str) -> str:
        if not DIA.match(dia or ""):
            raise CampoError("la fecha va como AAAA-MM-DD")
        try:
            date.fromisoformat(dia)
        except ValueError:
            raise CampoError("esa fecha no existe") from None
        return dia

    def actualizar(self, negocio: str, nid: str, **cambios: Any) -> dict:
        """Cambia texto, tema o estado de una nota (la transcripción de un audio llega por acá)."""
        d = self._existente(negocio)
        if not IDNOTA.match(nid or ""):
            raise CampoError("id de nota inválido")
        if cambios.get("tema") not in (None, *TEMAS):
            raise CampoError("tema desconocido")
        for f in sorted((d / "diario").glob("*.jsonl")) if (d / "diario").is_dir() else []:
            lineas = f.read_text("utf-8").splitlines()
            for i, ln in enumerate(lineas):
                n = json.loads(ln)
                if n["id"] == nid:
                    for k in ("texto", "tema", "estado"):
                        if cambios.get(k) is not None:
                            n[k] = cambios[k][:MAX_TEXTO] if k == "texto" else cambios[k]
                    if "tema" in cambios and cambios["tema"]:
                        n["tema_elegido"] = True
                    lineas[i] = json.dumps(n, ensure_ascii=False)
                    f.write_text("".join(x + "\n" for x in lineas), "utf-8")
                    return n
        raise CampoError("esa nota no existe")

    def notas(self, negocio: str, *, dia: str | None = None, tema: str | None = None, desde: str | None = None,
              hasta: str | None = None) -> list[dict]:
        d = self._existente(negocio)
        if dia:
            self._dia(dia)
        out: list[dict] = []
        for f in sorted((d / "diario").glob("*.jsonl")) if (d / "diario").is_dir() else []:
            fecha = f.stem
            if dia and fecha != dia or desde and fecha < desde or hasta and fecha > hasta:
                continue
            for ln in f.read_text("utf-8").splitlines():
                try:
                    n = json.loads(ln)
                except ValueError:
                    continue
                if tema and n.get("tema") != tema:
                    continue
                out.append(n)
        return out   # en el orden en que se anotaron (el id solo desempata por segundo, no por orden)

    def media(self, negocio: str, archivo: str) -> tuple[Path, str]:
        d = self._existente(negocio)
        if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-f0-9]{4}\.[a-z0-9]{2,4}", archivo or ""):
            raise CampoError("archivo inválido")
        p = d / "media" / archivo
        if not p.is_file():
            raise CampoError("ese archivo no existe")
        inv = {**{v: k for k, v in AUDIO.items()}, **{v: k for k, v in FOTO.items()}}
        return p, inv.get(p.suffix, "application/octet-stream")

    # --- búsqueda
    def buscar(self, negocio: str, q: str, *, limite: int = 30) -> dict:
        """Notas con todas las palabras de `q`, con el conteo total y por día («¿cuántas veces faltó stock?»)."""
        ws = [raiz(w) for w in palabras(q)]
        if not ws:
            raise CampoError("escribí qué buscar")
        hits = []
        for n in self.notas(negocio):
            t = norm(n["texto"])
            if all(w in t for w in ws):
                hits.append(n)
        por_dia = Counter(n["dia"] for n in hits)
        return {"total": len(hits), "dias": dict(sorted(por_dia.items())), "notas": hits[-limite:]}

    # --- resumen del día
    def _reglas(self, notas: list[dict], dia: str) -> dict:
        por_tema = Counter(n["tema"] for n in notas)
        cierre = [n["texto"] for n in sorted((n for n in notas if "cierre" in n.get("etiquetas", [])),
                                             key=lambda n: n.get("etiquetas", [""])[-1])]
        # Criterio de Damián: el material no apunta a empleados. Lo del tema Personal no entra a las pérdidas: va aparte, a él.
        cand = [n for n in notas if "cierre" not in n.get("etiquetas", []) and n["texto"] and n["tema"] != "personal"]
        personas = [f"{n['hora']} · {n['texto']}" for n in notas if n["tema"] == "personal" and n["texto"]]
        cand.sort(key=lambda n: (-puntaje_perdida(n["texto"]), n["hora"]))
        perdidas = cierre[:3] or [f"{n['hora']} · {TEMAS[n['tema']]}: {n['texto']}" for n in cand[:3]
                                  if puntaje_perdida(n["texto"]) > 0]
        pend = [n for n in notas if n["fuente"] == "voz" and n["estado"] != "ok"]
        mirar = []
        for tema, cant in por_tema.most_common(2):
            if tema != "otro":
                mirar.append(f"{TEMAS[tema]}: {cant} nota(s) hoy; mirá si se repite mañana a la misma hora.")
        if pend:
            mirar.append(f"Hay {len(pend)} audio(s) sin transcribir: no entran al resumen hasta que se transcriban.")
        if not [t for t in por_tema if t != "otro"] or len(notas) < 5:
            mirar.append("Pocas notas: anotá más en el turno pico para que el diagnóstico tenga de dónde agarrarse.")
        return {"dia": dia, "total": len(notas), "por_tema": dict(por_tema), "perdidas": perdidas,
                "origen_perdidas": "cierre del día" if cierre else "reglas (palabras de pérdida)", "mirar_manana": mirar,
                "solo_para_damian": personas}

    def resumen(self, negocio: str, dia: str | None = None, *, ask: Ask | None = None, guardar: bool = True) -> dict:
        dia = self._dia(dia) if dia else f"{self.clock():%Y-%m-%d}"
        notas = self.notas(negocio, dia=dia)
        r = self._reglas(notas, dia)
        r["ia"] = False
        if notas and ask is not None:
            cuerpo = "\n".join(f"[{n['id']}] {n['hora']} ({TEMAS[n['tema']]}) {n['texto']}" for n in notas if n["texto"])[:12000]
            msg = [{"role": "system", "content": (
                "Sos el asistente de un consultor que observa un restaurante. Con las notas del día armás un resumen corto en "
                "español rioplatense. Usá SOLO lo que dicen las notas; si algo no está, no lo inventes ni lo estimes. Formato:\n"
                "PÉRDIDAS: las 3 cosas que más tiempo o plata hicieron perder, una por línea, citando el [id] de la nota.\n"
                "MIRAR MAÑANA: hasta 3 cosas concretas para observar.\n"
                "REGLA: el resumen puede llegar al dueño, así que no nombres ni señales a empleados. Redactá cada problema como "
                "falla de proceso, de herramienta o de organización (ej. «el pedido llega a cocina sin orden claro», no «el mozo "
                "se equivocó»). Si una nota solo habla de una persona, omitila.")},
                {"role": "user", "content": f"Notas del {dia}:\n{cuerpo}"}]
            txt = ask(msg)
            if txt:
                r["ia"], r["texto_ia"] = True, txt.strip()
        if guardar and notas:
            (self._dir(negocio) / "resumenes").mkdir(exist_ok=True)
            (self._dir(negocio) / "resumenes" / f"{dia}.md").write_text(self.render_resumen(r), "utf-8")
        return r

    @staticmethod
    def render_resumen(r: dict) -> str:
        L = [f"# Resumen del {r['dia']}", "", f"{r['total']} nota(s). " + ", ".join(
            f"{TEMAS[k]}: {v}" for k, v in sorted(r["por_tema"].items(), key=lambda kv: -kv[1])), ""]
        if r.get("ia"):
            L += ["## Según la IA local", r["texto_ia"], ""]
        L += [f"## Las pérdidas del día ({r['origen_perdidas']})"] + [f"{i}. {p}" for i, p in enumerate(r["perdidas"], 1)]
        if not r["perdidas"]:
            L.append("Sin pérdidas marcadas: anotá el cierre del día para que queden.")
        L += ["", "## Para mirar mañana"] + [f"- {m}" for m in r["mirar_manana"]]
        return "\n".join(L) + "\n"

    # --- expediente
    def expediente(self, negocio: str, *, para_dueno: bool = False) -> str:
        """El expediente en Markdown: notas por tema y resúmenes diarios (lo que se lleva al diagnóstico).
        `para_dueno`: sin el tema Personal ni lo que sea sobre personas; ese material es solo de Damián."""
        d = self._existente(negocio)
        nombre = json.loads((d / "negocio.json").read_text("utf-8"))["nombre"]
        notas = [n for n in self.notas(negocio) if not (para_dueno and n["tema"] == "personal")]
        dias = sorted({n["dia"] for n in notas})
        L = [f"# Expediente: {nombre}", "",
             f"{len(notas)} nota(s) en {len(dias)} día(s)" + (f", del {dias[0]} al {dias[-1]}." if dias else "."), ""]
        for tema, titulo in TEMAS.items():
            ns = [n for n in notas if n["tema"] == tema]
            if not ns:
                continue
            L += [f"## {titulo} ({len(ns)})", ""]
            for n in ns:
                adj = f" _(adjunto: {n['archivo']})_" if n["archivo"] else ""
                est = "" if n["estado"] == "ok" else f" _[{n['estado']}]_"
                L.append(f"- {n['dia']} {n['hora']} · {n['texto'] or '(sin texto)'}{adj}{est}")
            L.append("")
        res = sorted((d / "resumenes").glob("*.md")) if (d / "resumenes").is_dir() else []
        if res:
            L += ["## Resúmenes diarios", ""]
            for f in res:
                L += [f.read_text("utf-8").replace("# ", "### ", 1), ""]
        return "\n".join(L)

    def preguntar(self, negocio: str, pregunta: str, *, ask: Ask | None = None) -> dict:
        """Responde sobre el expediente. Con IA local redacta citando notas; sin ella devuelve las notas y el conteo."""
        enc = self.buscar(negocio, pregunta, limite=40) if palabras(pregunta) else {"total": 0, "dias": {}, "notas": []}
        r: dict[str, Any] = {"coincidencias": enc["total"], "por_dia": enc["dias"], "notas": enc["notas"], "ia": False,
                             "respuesta": (f"Encontré {enc['total']} nota(s) que mencionan eso." if enc["total"] else
                                           "No encontré notas que mencionen eso.")}
        todas = self.notas(negocio)
        if ask is not None and todas:
            base = enc["notas"] or todas[-40:]
            ctx = "\n".join(f"[{n['id']}] {n['dia']} ({TEMAS[n['tema']]}) {n['texto']}" for n in base if n["texto"])[:12000]
            txt = ask([{"role": "system", "content": (
                "Contestá la pregunta sobre un restaurante usando SOLO estas notas del observador. Citá el [id] de cada nota "
                "que uses. Si las notas no alcanzan, decilo. No inventes cifras ni hechos. No culpes a personas: "
                "hablá de procesos y herramientas. Español rioplatense, corto.")},
                {"role": "user", "content": f"Notas:\n{ctx}\n\nPregunta: {pregunta}"}])
            if txt:
                r["ia"], r["respuesta"] = True, txt.strip()
        return r
