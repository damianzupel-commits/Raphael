"""Del `perfil.yaml` de Empresas 0.4 a la instalación v2 (`installation.yaml`) de una clienta.

Lo del negocio va a `brigades.empresas.config`; plan, identidad, límites y políticas a la instalación; el orquestador
en modo `secretary` con Atención como red. Las políticas de 0.4 solo podían endurecer: se pasan tal cual a `autonomy`
(con el prefijo `empresas.`). Solo convierte: no toca datos ni bases.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from raphael_core.installation import installation_from

from .config import business_config

ORCHESTRATOR = "raphael_orchestrator.orchestrator:RaphaelOrchestrator"
V1_MODULES = {"atencion", "encargos", "cobros", "agenda", "avisos"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "clienta"


def business_from_profile(p: dict) -> dict:
    e, info = p.get("empresa") or {}, p.get("informacion") or {}
    cob, enc, ag = p.get("cobros") or {}, p.get("encargos") or {}, p.get("agenda") or {}
    cfg: dict[str, Any] = {
        "business": {"name": e.get("nombre", ""), "owner": e.get("duena", ""), "tone": e.get("tono", "voseo_emojis")},
        "info": {"hours": info.get("horarios", ""), "shipping": info.get("envios", ""),
                 "payment_methods": list(info.get("medios_pago") or []), "location": info.get("ubicacion", ""),
                 "faq": [{"question": f.get("pregunta", ""), "answer": f.get("respuesta", ""),
                          "keywords": list(f.get("palabras") or [])} for f in info.get("faq") or []]},
        "payments": {"deposit_pct": cob.get("sena_pct", 50), "alias": cob.get("alias", ""), "holder": cob.get("titular", "")},
        "orders": {"prices": [{"item": x["prenda"], "base": x["base"], **({"days": x["dias"]} if x.get("dias") else {})}
                              for x in enc.get("precios") or []],
                   "surcharges": [{"word": x["palabra"], "kind": "amount" if x["tipo"] == "monto" else "pct",
                                   "value": x["valor"]} for x in enc.get("recargos") or []]},
        "schedule": {"reminder_days_before": ag.get("recordatorio_dias_antes", 3), "slots": list(ag.get("franjas") or [])},
    }
    if enc.get("datos_obligatorios"):
        cfg["orders"]["required_steps"] = list(enc["datos_obligatorios"])
    if "urgente_si_dias_menor_a" in enc:
        cfg["orders"]["urgent_if_days_under"] = enc["urgente_si_dias_menor_a"]
    business_config(cfg)              # falla acá, con el campo, si algo no cierra
    return cfg


def installation_from_profile(p: dict, *, inst_id: str | None = None, edition: str = "cloud",
                              store_url: str = "") -> tuple[dict, list[str]]:
    """(instalación como dict, avisos). Valida el resultado contra el esquema de la instalación del harness."""
    notes: list[str] = []
    e = p.get("empresa") or {}
    config = business_from_profile(p)
    if store_url:
        config["store"] = {"source": {"kind": "feed", "url": store_url, "format": "csv" if store_url.endswith(".csv")
                                      else "json"}}
        business_config(config)
    active = set(p.get("brigadas") or [])
    missing = sorted(V1_MODULES - active)
    if missing:
        notes.append(f"el perfil no tenía {', '.join(missing)}: en el v2 la brigada Empresas trae todos sus cocineros")
    autonomy = {f"empresas.{k}": v for k, v in (p.get("politicas") or {}).items()}
    inst = {
        "id": inst_id or _slug(e.get("nombre", "")),
        "edition": edition,
        "plan": p.get("plan", "basico"),
        "identity": {"assistant": "Raphael", "user": e.get("duena", "")},
        "timezone": e.get("zona_horaria", "America/Argentina/Buenos_Aires"),
        "limits": {"messages_month": (p.get("limites") or {}).get("mensajes_mes", 3000)},
        "orchestrator": {"entry": ORCHESTRATOR,
                         "config": {"mode": "secretary", "routing": {"fallback_cook": "empresas/atencion"}}},
        "brigades": {"empresas": {"active": True, "config": config}},
        "autonomy": autonomy,
        "trust": {"enabled": True, "approvals_to_step_down": 10},
    }
    installation_from(inst)
    return inst, notes


def convert(profile_path: str | Path, out_path: str | Path, **kw: Any) -> list[str]:
    p = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8")) or {}
    inst, notes = installation_from_profile(p, **kw)
    header = ("# Instalación de Raphael Empresas (harness v2), convertida desde el perfil de Empresas 0.4.\n"
              "# Lo del negocio está en brigades.empresas.config. Revisala antes de subirla al servidor.\n")
    Path(out_path).write_text(header + yaml.safe_dump(inst, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return notes
