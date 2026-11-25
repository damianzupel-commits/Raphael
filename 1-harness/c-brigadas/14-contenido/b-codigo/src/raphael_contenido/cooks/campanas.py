"""Campañas y anuncios: borradores con presupuesto y segmentación. Nada se activa ni gasta sin aprobación.

Tres pasos, cada uno con su nivel:
  1. `crear_borrador_anuncio` (automático): arma el borrador y lo valida (tope de presupuesto diario de la config, edades, días).
     Solo guarda; no habla con Meta. Se puede exportar (`exportar`) para cargarlo a mano en el Administrador de anuncios.
  2. `subir_campana_pausada` (aprobación, sale al mundo): crea la campaña en Meta en PAUSA. No gasta nada.
  3. `activar_campana` (aprobación, GASTA PLATA): la pone a correr. Gasta, así que la confianza progresiva nunca la baja sola a automático.
El presupuesto total es diario × días y se muestra en la aprobación. Sin `META_ADS_*` el borrador queda guardado y se avisa qué falta.
"""

from __future__ import annotations

import asyncio

from raphael_core import Action, ActionError, Cook, Health

from .. import entorno
from ..adapters import ServicioError
from ..comun import need_str, new_id, short
from ..config import contenido_config

OBJETIVOS = ("OUTCOME_AWARENESS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT", "OUTCOME_LEADS", "OUTCOME_SALES")


def _num(d: dict, key: str, lo: float, hi: float, what: str) -> float:
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise ActionError(f"«{key}» ({what}) tiene que ser un número entre {lo:g} y {hi:g}.")
    return float(v)


class Campanas(Cook):
    name = "campanas"
    version = "2.0.0"
    description = "Borradores de anuncios con presupuesto y segmentación; subir o activar una campaña siempre pide aprobación."
    commands = {"borradores": "Borradores de anuncios {'estado'?}", "borrador": "Un borrador {'id'}", "exportar": "El borrador listo para cargar a mano {'id'}"}

    def start(self, ctx) -> None:
        self.cfg = contenido_config(ctx.config)
        self.ads = entorno.build(self.cfg).anuncios

    async def execute(self, action: Action, ctx) -> str | None:
        t, d = action.type, action.data
        if t == "crear_borrador_anuncio":
            return self._draft(d, ctx)
        if t == "descartar_borrador":
            rec = self._load(need_str(d, "id", max_len=40), ctx)
            if rec["estado"] not in ("borrador", "subida_pausada"):
                raise ActionError(f"Un borrador {rec['estado']} no se descarta.")
            rec["estado"] = "descartado"
            ctx.shared.put("anuncios", rec["id"], rec)
            return f"Borrador {rec['id']} descartado. (Si ya estaba subido en pausa, queda ahí: borralo en Meta.)"
        if t == "subir_campana_pausada":
            rec = self._load(need_str(d, "id", max_len=40), ctx)
            if rec["estado"] != "borrador":
                raise ActionError(f"El borrador está {rec['estado']}: solo se sube uno en estado borrador.")
            try:
                out = await asyncio.to_thread(self.ads.create_paused, rec["nombre"], rec["objetivo"])
            except ServicioError as exc:
                raise ActionError(str(exc)) from None
            rec.update(estado="subida_pausada", campaign_id=out["campaign_id"], simulado=bool(out.get("simulado")))
            ctx.shared.put("anuncios", rec["id"], rec)
            ctx.publish("campana.borrador", {"id": rec["id"], "campaign_id": out["campaign_id"]})
            sim = " (SIMULADO: no se creó nada en Meta)" if out.get("simulado") else ""
            return (f"Campaña «{rec['nombre']}» creada en Meta EN PAUSA{sim} (id {out['campaign_id']}). No gasta nada. Falta armar el conjunto "
                    f"de anuncios y el anuncio en el Administrador de anuncios (usá «exportar»). Para correrla, pedí «activar_campana».")
        if t == "activar_campana":
            rec = self._load(need_str(d, "id", max_len=40), ctx)
            if rec["estado"] != "subida_pausada":
                raise ActionError(f"El borrador está {rec['estado']}: solo se activa una campaña ya subida en pausa.")
            try:
                out = await asyncio.to_thread(self.ads.activate, rec["campaign_id"])
            except ServicioError as exc:
                raise ActionError(str(exc)) from None
            rec.update(estado="activa", activada=ctx.now().isoformat(timespec="seconds"))
            ctx.shared.put("anuncios", rec["id"], rec)
            ctx.publish("campana.activada", {"id": rec["id"], "campaign_id": rec["campaign_id"], "total": rec["presupuesto_total"]})
            sim = " (SIMULADO: no se activó nada en Meta)" if out.get("simulado") else ""
            return f"Campaña «{rec['nombre']}» ACTIVADA{sim}. Presupuesto total previsto: {rec['presupuesto_total']:g} {rec['moneda']}."
        raise ActionError(f"campanas no ejecuta '{t}'")

    def _draft(self, d: dict, ctx) -> str:
        c = self.cfg.campaigns
        nombre = need_str(d, "nombre", max_len=100)
        objetivo = str(d.get("objetivo") or c.objective)
        if objetivo not in OBJETIVOS:
            raise ActionError(f"«objetivo» es uno de: {', '.join(OBJETIVOS)}.")
        diario = _num(d, "presupuesto_diario", 1, c.daily_budget_cap, f"en {c.currency}; el tope de esta instalación es {c.daily_budget_cap:g}")
        dias = int(_num(d, "dias", 1, 90, "de duración"))
        pub = dict(d.get("publico") or {})
        edad_min, edad_max = int(pub.get("edad_min", 18)), int(pub.get("edad_max", 65))
        if not 13 <= edad_min <= edad_max <= 65:
            raise ActionError("«publico»: edad_min y edad_max entre 13 y 65, con edad_min ≤ edad_max.")
        texto = d.get("texto")
        if not texto and d.get("copy_id"):
            copy = ctx.shared.get("copys", str(d["copy_id"]))
            if not copy:
                raise ActionError(f"No existe el copy {d['copy_id']}.")
            texto = copy["texto"]
        texto = need_str({"texto": texto}, "texto", max_len=2200)
        url = str(d.get("destino_url") or "")
        if url and not url.startswith("https://"):
            raise ActionError("«destino_url» tiene que empezar con https://")
        rec = {"id": new_id(), "estado": "borrador", "nombre": nombre, "objetivo": objetivo, "moneda": c.currency,
               "presupuesto_diario": diario, "dias": dias, "presupuesto_total": round(diario * dias, 2),
               "publico": {"edad_min": edad_min, "edad_max": edad_max, "ubicaciones": [str(x) for x in pub.get("ubicaciones", [])][:20],
                           "intereses": [str(x) for x in pub.get("intereses", [])][:20]},
               "texto": texto, "destino_url": url, "publicacion_id": d.get("publicacion_id"),
               "creado": ctx.now().isoformat(timespec="seconds")}
        ctx.shared.put("anuncios", rec["id"], rec)
        return (f"Borrador de anuncio {rec['id']} guardado: «{nombre}», {diario:g} {c.currency} por día durante {dias} días "
                f"(total {rec['presupuesto_total']:g} {c.currency}). No se subió ni se gastó nada.")

    @staticmethod
    def _load(aid: str, ctx) -> dict:
        rec = ctx.shared.get("anuncios", aid)
        if not rec:
            raise ActionError(f"No existe el borrador {aid}.")
        return rec

    def command(self, name: str, data: dict, ctx):
        if name == "borradores":
            return [{k: r.get(k) for k in ("id", "nombre", "estado", "presupuesto_diario", "dias", "presupuesto_total", "moneda")}
                    for r in ctx.shared.list("anuncios") if not data.get("estado") or r.get("estado") == data["estado"]]
        if name == "borrador":
            return self._load(need_str(data, "id", max_len=40), ctx)
        if name == "exportar":
            r = self._load(need_str(data, "id", max_len=40), ctx)
            return {"campana": {"nombre": r["nombre"], "objetivo": r["objetivo"]},
                    "conjunto": {"presupuesto_diario": r["presupuesto_diario"], "moneda": r["moneda"], "dias": r["dias"], "publico": r["publico"]},
                    "anuncio": {"texto": r["texto"], "destino_url": r["destino_url"], "vista": short(r["texto"], 80)}}
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        return Health(True, {"real": "cuenta de anuncios conectada", "mock": "anuncios SIMULADOS",
                             "sin_clave": "sin cuenta de anuncios: se arman borradores, no se suben"}[self.ads.mode])
