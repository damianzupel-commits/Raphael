"""Diseñador de brigadas (Etapa 2): de una DESCRIPCIÓN en lenguaje natural a un BORRADOR.

Un modelo (modelo del orquestador, nemotron por default: la descripción puede mencionar datos personales) propone el JSON del borrador a partir de
lo que Damian describe. Esa propuesta es DATO NO CONFIABLE:

  - pasa por `draft_store.create_draft` -> `factory.validate_draft` (esquema cerrado, catálogo y política de tools, regex
    seguras, ids sin choques, validación obligatoria). Si no valida, se le devuelven los errores al modelo para que corrija
    (hasta `MAX_INTENTOS`); si sigue sin validar, se informa y NO se guarda nada.
  - lo único que puede producir es un BORRADOR. Este módulo no importa ni llama a `activate`: el modelo no tiene ningún
    camino hacia la activación (eso es de Damian, con el hash que revisó).
  - al modelo ni siquiera se le ofrecen las tools que la política deniega.

`llm` es inyectable (`async (messages) -> str`): los tests usan uno falso; en producción es el modelo local de los jefes.
"""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from . import draft_store, factory, tool_catalog
from .ejemplos import EJEMPLO_DELEGA

MAX_INTENTOS = 3
MAX_DESCRIPCION = 3000
LLM = Callable[[list[dict]], Awaitable[str]]

_ESQUEMA = """\
Un borrador es un objeto JSON con estos campos (NO agregues otros):
- "id": minúsculas, números y guiones, empieza con letra, 3 a 31 caracteres (ej. "notas-reuniones").
- "nombre" (3-60), "proposito" (10-400), "prompt" (20-4000 caracteres): el prompt del JEFE de la brigada. El jefe NO hace el
  trabajo, NO tiene tools y NO le habla al usuario: coordina a sus ayudantes, SINTETIZA lo que traen y le reporta al orquestador.
  Su prompt es su ESPECIALIZACIÓN: con qué criterio de su dominio sintetiza (qué cita, qué distingue, qué reporta como no encontrado).
- "modelo" (del jefe y de CADA ayudante; cada rol tiene su propio LLM): "shared" (modelo compartido en la nube, nemotron: el DEFAULT,
  usalo normalmente) o "local" (privado: SOLO si el rol lee notas personales del vault, o Damian pide privacidad). Declaralo en cada rol.
- "ayudantes" (OBLIGATORIO, 1 a 4; no existe la brigada sin ayudantes): [{"modo","descripcion","prompt","modelo","tools":[...]}]. Los
  ayudantes hacen el trabajo real; cada uno con el menor privilegio posible. El jefe NO lleva "tools".
- "ruteo" (OBLIGATORIO): {"reglas":[{"modo","patron"}], "default": "<modo>"}. Las reglas son regex (sin distinguir mayúsculas), se evalúan
  EN ORDEN (el orden es la prioridad); si ninguna matchea va a "default", que debe ser el ayudante MÁS PASIVO (el de menos privilegio).
  Un ayudante que actúa o sale a la web solo se usa si su regla matchea: poné reglas explícitas para él. Con un solo ayudante: "reglas": [].
- "validacion" (OBLIGATORIA): {"criterio": texto, "prerequisitos": [subconjunto de "ollama_local","embeddings"; "ollama_local" SOLO si algún rol es "local"],
  "pasos": [...]}, con pasos de dos tipos:
    {"id","tipo":"ruteo","casos":[{"mensaje","modo"}]}   (OBLIGATORIO al menos uno; cubrí cada ayudante y un pedido ambiguo)
    {"id","tipo":"respuesta","mensaje","debe_contener":[regex],"debe_usar_tools":[tools de la brigada]}  (al menos un criterio)
  Los ids de paso: minúsculas/números/guion bajo; "alcance" está reservado.
- "watch" (OPCIONAL; omitilo salvo que la brigada lo necesite): {"max_seconds","stall_seconds","max_repeats","max_errors"} para la
  vigilancia del watchdog (ej. "stall_seconds": 900 si un ayudante corre escaneos largos que no emiten nada).
Usá SOLO tools de la lista de abajo, con el menor privilegio que alcance. No inventes tools. No uses regex con cuantificadores
anidados. Respondé ÚNICAMENTE con el JSON del borrador, sin explicaciones ni bloques de código."""


def _tool_lines() -> str:
    normales, sensibles = [], []
    for name in sorted(tool_catalog.catalog()):
        nivel = tool_catalog.classify(name)["nivel"]
        if nivel == "ok":
            normales.append(name)
        elif nivel == "sensible":
            sensibles.append(name)
    return (f"TOOLS NORMALES: {', '.join(normales)}\n"
            f"TOOLS SENSIBLES (alto privilegio; usalas solo si el pedido lo exige y avisalo en el propósito): {', '.join(sensibles)}")


def build_messages(descripcion: str, errores: list[str] | None = None, anterior: str | None = None) -> list[dict]:
    system = ("Sos el diseñador de brigadas de Raphael. Convertís la descripción de Damian en el JSON de un BORRADOR de brigada "
              "(que él va a revisar y aprobar antes de que funcione).\n\n" + _ESQUEMA + "\n\n" + _tool_lines()
              + "\n\nEJEMPLO de borrador válido (brigada que delega):\n" + json.dumps(EJEMPLO_DELEGA, ensure_ascii=False))
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": "DESCRIPCIÓN DE LA BRIGADA (de Damian):\n" + descripcion[:MAX_DESCRIPCION]}]
    if errores:
        msgs += [{"role": "assistant", "content": anterior or ""},
                 {"role": "user", "content": "Ese borrador no es válido. Corregí SOLO estos errores y devolvé el JSON completo:\n- "
                  + "\n- ".join(errores[:20])}]
    return msgs


def extract_json(text: str) -> object:
    """Saca el objeto JSON de la respuesta del modelo (tolera ```json ... ``` y texto alrededor). ValueError si no hay."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(text[start:end + 1])


async def local_llm(messages: list[dict]) -> str:
    """El modelo del ORQUESTADOR (nemotron en NVIDIA NIM por default, ver `load_orquestador_client_model`; sin GPU).
    Solo se llama cuando Damian pide crear una brigada."""
    from .config import load_orquestador_client_model

    client, model = load_orquestador_client_model()
    resp = await client.chat.completions.create(model=model, messages=messages, temperature=0.2)
    return resp.choices[0].message.content or ""


async def design_from_description(descripcion: str, llm: LLM | None = None) -> dict:
    """Descripción -> BORRADOR guardado (nunca activo). `DraftInvalid` si el modelo no logra un borrador válido en
    `MAX_INTENTOS`; `DraftError` si el id ya tiene una brigada activa."""
    descripcion = (descripcion or "").strip()
    if len(descripcion) < 15:
        raise draft_store.DraftError("Describí la brigada con un poco más de detalle (qué hace, con qué herramientas, cómo se ruteaen los pedidos).")
    llm = llm or local_llm
    errores: list[str] | None = None
    anterior: str | None = None
    for _ in range(MAX_INTENTOS):
        raw_text = await llm(build_messages(descripcion, errores, anterior))
        anterior = raw_text
        try:
            raw = extract_json(raw_text)
        except ValueError as exc:
            errores = [f"La respuesta no es un JSON válido ({exc}). Devolvé solo el objeto JSON."]
            continue
        try:
            return draft_store.create_draft(raw, origen="descripcion", descripcion=descripcion)
        except draft_store.DraftInvalid as exc:
            errores = exc.errors
    raise draft_store.DraftInvalid(errores or ["el modelo no produjo un borrador"])
