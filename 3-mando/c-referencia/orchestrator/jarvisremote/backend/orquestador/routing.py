"""Ruteo del Orquestador: a qué brigada va un pedido.

Hoy el "orquestador" del monolito no rutea a jefes (el blueprint lo deja pendiente:
`skills.classify → jefe`). Acá vive la versión mínima, pura y testeable. Orden de decisión:

  1. Override explícito:  "/cerebro ..."  o  "/investigacion ..."  (o `brigade` en el request).
  2. Reglas por palabras clave con peso (determinístico, gratis, privado). Si una brigada gana
     con claridad, se usa.
  3. Sin señal clara (nada o empate) → un clasificador LLM del orquestador (nemotron en NVIDIA NIM,
     ORQUESTADOR_LLM_MODEL) con timeout corto. Si no está disponible o falla → paso 4.
  4. Default: Cerebro — es local y de solo lectura, la opción que no puede mandar nada a la nube
     ni escribir por error.

Por qué LLM solo en el caso ambiguo: el clasificador es CLOUD (decisión de Damian 2026-11-11, antes era local):
manda el texto de pedidos que pueden ser sobre notas personales al endpoint de NVIDIA, que puede
registrar prompts. Reversible por .env (ver llm_classify).
"""

from __future__ import annotations

import os
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger("orquestador.routing")

BRIGADES = ("cerebro", "investigacion")
DEFAULT_BRIGADE = "cerebro"
# Brigadas que NO compiten en el puntaje de arriba: se llega por su pestaña, por `/<id> pedido`, o por una regla propia y
# explícita (abajo). Hoy: Video (edición). No entran al clasificador LLM ni al trabajo conjunto.
DIRECTAS = ("video",)
# nemotron razona antes de responder: 10 s / 8 tokens (pensado para un modelo local sin razonamiento) devolvían content vacío.
LLM_TIMEOUT_SECONDS = float(os.getenv("ORQUESTADOR_ROUTING_TIMEOUT_SECONDS", "45"))
LLM_MAX_TOKENS = int(os.getenv("ORQUESTADOR_ROUTING_MAX_TOKENS", "1024"))
MAX_PALABRAS_SIN_LLM = 3  # hasta acá, un pedido sin señales no se le consulta al clasificador LLM

_OVERRIDE = re.compile(r"^\s*/(cerebro|investigacion|investigación)\b[:\s]*", re.IGNORECASE)
# Brigadas CREADAS por borrador (Etapa 2): se alcanzan solo con "/<id> pedido" o desde su pestaña; NUNCA entran al
# auto-ruteo (reglas ni clasificador): activar una brigada no cambia adónde van los pedidos de las demás.
_DIRECTA_OVERRIDE = re.compile(r"^\s*/(" + "|".join(DIRECTAS) + r")\b[:\s]*", re.IGNORECASE)
# Video por reglas: hace falta un VERBO de edición Y un objeto de video en el mismo pedido ("recortá el video", "subtitulá
# charla.mp4"). "Buscá videos de Rust en la web" no tiene verbo de edición: no entra acá.
_VIDEO_VERBO = re.compile(r"recort|\bcort[ae]|\buni\b|\bunir|\bjunt[ae]|subtitul|transcrib|\bedit[ae]|convert|normaliz|estabiliz|"
                          r"\bacelera|ralenti|camara (?:lenta|rapida)|quita(?:r|le|me)? (?:los )?silencios|pone(?:le|r)? (?:un )?(?:titulo|texto|logo|musica)|"
                          r"sacame clips|hace(?:me)? (?:un|unos) (?:clips?|reels?|shorts?|gif)|pasa(?:lo|r)? a (?:vertical|blanco y negro)|"
                          r"\barma(?:r|me|le)? (?:el |un |mi )?video|\bmonta(?:r|me|le)? (?:el |un |mi )?video|"
                          r"\bgraba(?:r|me|le)? (?:la |mi |una )?pantalla|\bcaptura(?:r|me)? (?:la |mi |una )?pantalla|"
                          r"\bpublica(?:r|lo|le)? (?:el |un |mi |este )?(?:video|reel)|\bsubi(?:r|lo)? (?:el |un |este )?(?:video|reel) a (?:instagram|insta)")
_VIDEO_OBJETO = re.compile(r"\bvideos?\b|\bclips?\b|\bgrabacion|\bpantalla\b|\blinea de tiempo\b|\bproyecto de (?:edicion|video)\b|\breels?\b|\bshorts?\b|\.(?:mp4|mov|mkv|webm|avi)\b|\bfilmacion")


def pide_video(message: str) -> bool:
    t = _norm(message)
    return bool(_VIDEO_VERBO.search(t) and _VIDEO_OBJETO.search(t))


_CREATED_OVERRIDE = re.compile(r"^\s*/([a-z][a-z0-9-]{2,30})\b[:\s]*", re.IGNORECASE)


def _created_active() -> set[str]:
    try:
        from brigades.registry import created_active_ids

        return set(created_active_ids())
    except Exception:  # noqa: BLE001 — un almacén ilegible no rompe el ruteo
        return set()


@dataclass(frozen=True)
class Route:
    brigade: str
    via: str      # "override" | "reglas" | "llm" | "default"
    reason: str
    message: str  # el pedido a entregar al jefe (sin el prefijo /brigada)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


# Charla social (saludo, agradecimiento, despedida): la contesta el ORQUESTADOR directo, sin despertar a una brigada.
# Lista CERRADA y el mensaje ENTERO tiene que ser charla: una sola palabra fuera de la lista y el pedido va a una brigada.
_CHARLA = frozenset(
    "hola holaa holis buenas buen buenos dia dias tarde tardes noche noches hey ey che raphael rafael como estas andas va todo "
    "bien que tal gracias muchas mil genial perfecto dale ok okay oka listo joya barbaro buenisimo excelente chau adios hasta "
    "luego manana pronto nos vemos saludos de nada y vos tanto quedo claro entendido".split())
MAX_PALABRAS_CHARLA = 8


# Preguntas sobre RAPHAEL MISMO (qué brigadas tiene, qué puede hacer, con qué modelo corre). La respuesta no está en el vault
# ni en la web: está en el registro. La contesta el orquestador con datos que arma CÓDIGO (server: `agentes.reporte_del_sistema`).
_SOBRE_RAPHAEL = re.compile(
    r"\bbrigadas?\b|\bayudantes?\b|\befimeros?\b|\bcocineros?\b|que (?:podes|puedes|sabes) hacer|para que servis|"
    r"(?:tus|sus) (?:capacidades|funciones|habilidades|herramientas)|que (?:modelos?|ia) usas|con que modelo|como funcionas|quien sos")


def pregunta_por_raphael(message: str) -> bool:
    """True si el pedido es sobre el propio sistema y no trae una señal explícita de trabajo para una brigada."""
    if not (message or "").strip() or (message or "").lstrip().startswith("/"):
        return False
    if not _SOBRE_RAPHAEL.search(_norm(message)) or pide_video(message):
        return False
    return not any(_senales(message)[2].values())  # «buscá en mis notas lo de las brigadas» sí es trabajo de Cerebro


def es_charla(message: str) -> bool:
    """True si el mensaje es SOLO charla social. No hay nada que buscar ni que hacer: no justifica un turno de brigada."""
    palabras = re.findall(r"[a-z]+", _norm(message))
    return bool(palabras) and len(palabras) <= MAX_PALABRAS_CHARLA and not re.search(r"\d|/", message or "") \
        and all(p in _CHARLA for p in palabras)


# (patrón sobre texto sin acentos y en minúsculas, brigada, peso). Peso 2 = señal fuerte.
_RULES: tuple[tuple[re.Pattern, str, int], ...] = tuple(
    (re.compile(p), b, w)
    for p, b, w in (
        # Investigación: salir a la web / trabajar evidencia de un caso
        (r"en la web|en internet|\binternet\b|\bonline\b|en linea|\bgoogle|arxiv|https?://", "investigacion", 2),
        # "caso" como caso forense; no cuenta en giros del habla ("en qué caso", "en ese caso", "en todo caso", "en caso de")
        (r"(?<!en )(?<!en que )(?<!en ese )(?<!en todo )(?<!en cualquier )\bcasos?\b(?! de que)|evidencia|forens|\bexif\b|whatsapp|telegram|"
         r"\bcsv\b|artefactos?|\.(?:pdf|docx|jpe?g|png|log)\b", "investigacion", 2),
        (r"\binvestig|\bresearch\b|\bscout\b|noticias|novedades|ultimas? |ultimos? |se publico|estado del arte|\bfusion(?:es)?\b|entidades",
         "investigacion", 1),
        # Cerebro: lo que ya está en el vault / la memoria
        (r"que se de|que sabes de|que sabemos|que tengo (?:sobre|de|guardado)|mis notas|mi vault|en el vault|\bcerebro\b", "cerebro", 2),
        (r"\bvault\b|memoria|\bnotas?\b|recorda|conclusion|conecta|asocia|segun mis|lo que guarde|\banote\b|apunt|"
         r"te acordas|decidimos|aprendiste|repasame|que hablamos", "cerebro", 1),
    )
)


def _senales(message: str) -> tuple[dict[str, int], dict[str, list[str]], dict[str, bool]]:
    """(puntaje, palabras que matchearon, ¿hubo señal de peso 2?) por brigada."""
    text = _norm(message)
    score = {b: 0 for b in BRIGADES}
    hits: dict[str, list[str]] = {b: [] for b in BRIGADES}
    fuerte = {b: False for b in BRIGADES}
    for pat, brigade, weight in _RULES:
        for m in pat.finditer(text):
            score[brigade] += weight
            hits[brigade].append(m.group(0).strip())
            fuerte[brigade] = fuerte[brigade] or weight >= 2
    return score, hits, fuerte


def brigadas_conjuntas(message: str) -> tuple[tuple[str, ...], str]:
    """Trabajo CONJUNTO: (brigadas, motivo) si el pedido trae una señal EXPLÍCITA (peso 2) de más de una brigada; ((), "") si no.

    Lo decide CÓDIGO, nunca un modelo, y solo en el auto-ruteo: un prefijo `/brigada` o una pestaña elegida mandan. Las
    brigadas no se enteran: cada una recibe el pedido y hace SU parte; el orquestador junta los reportes y comunica."""
    if not (message or "").strip() or (message or "").lstrip().startswith("/"):
        return (), ""
    _score, hits, fuerte = _senales(message)
    varias = tuple(b for b in BRIGADES if fuerte[b])
    if len(varias) < 2:
        return (), ""
    return varias, "el pedido pide trabajo de más de una brigada · " + " · ".join(
        f"{b}: {', '.join(dict.fromkeys(hits[b]))[:40]}" for b in varias)


def route_by_rules(message: str) -> tuple[str | None, str]:
    """(brigada | None, motivo). None = sin señal o empate."""
    score, hits, fuerte = _senales(message)
    inv, cer = score["investigacion"], score["cerebro"]
    if inv == cer and inv > 0 and fuerte["investigacion"]:
        # El pedido toca las DOS brigadas y trae una señal EXPLÍCITA de trabajo (salir a la web / un caso): eso es lo que el
        # usuario pidió hacer; lo de "mis notas" queda como contexto. Sin señal fuerte, el empate sigue yendo al LLM/default.
        return "investigacion", (f"pide web/caso y también menciona tus notas ({inv}-{cer}): va la señal explícita · "
                                 f"palabras: {', '.join(dict.fromkeys(hits['investigacion']))[:60]}")
    if inv == cer:
        return None, ("sin señales" if inv == 0 else f"empate ({inv}-{cer})")
    winner = "investigacion" if inv > cer else "cerebro"
    return winner, f"palabras: {', '.join(dict.fromkeys(hits[winner]))[:80]}"


LlmClassifier = Callable[[str], Awaitable["str | None"]]

_LLM_PROMPT = (
    "Clasificá el pedido del usuario en UNA brigada y respondé SOLO con la palabra:\n"
    "- cerebro: preguntas sobre lo que ya está guardado en sus notas/memoria/vault.\n"
    "- investigacion: SOLO si el pedido pide EXPLÍCITAMENTE salir a buscar algo nuevo en la web/internet, o trabajar la evidencia de un "
    "caso (archivos, chats, CSV, imágenes).\n"
    "Ante la duda, cerebro: una pregunta general, un pedido de explicación u opinión, un saludo o cualquier cosa que no pida de forma "
    "explícita la web ni un caso es 'cerebro' (es de solo lectura; 'investigacion' sale a la web o crea cosas).\n"
    "Respondé exactamente 'cerebro' o 'investigacion'."
)


async def llm_classify(message: str) -> str | None:
    """Clasificador LLM del ORQUESTADOR: nemotron en NVIDIA NIM (`load_orquestador_client_model`,
    `ORQUESTADOR_LLM_MODEL`). None si no hay key/modelo, hay 429 o no responde (cae a reglas/default).

    ⚠ PRIVACIDAD (decisión consciente de Damian, 2026-11-11): hasta 1500 caracteres de cada mensaje que las
    reglas no resuelven salen al endpoint de NVIDIA, que puede registrar prompts. Esos mensajes pueden
    mencionar notas personales. Reversible por .env: ORQUESTADOR_LLM_BASE_URL/ORQUESTADOR_LLM_MODEL apuntando a
    un modelo local (ej. Ollama), o ORQUESTADOR_ROUTING_LLM=0 para rutear solo por reglas (sin ningún LLM)."""
    if os.getenv("ORQUESTADOR_ROUTING_LLM", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    try:
        from brigades.config import completar, load_orquestador_client_model, razonamiento

        client, model = load_orquestador_client_model()
        # Clasificar en UNA palabra no necesita que el modelo razone (medido: ~1 s en vez de ~4-5 s, y una fracción de los
        # tokens). `ORQUESTADOR_ROUTING_RAZONAMIENTO=on` lo vuelve a prender.
        answer = _norm(await completar(
            client, model, [{"role": "system", "content": _LLM_PROMPT}, {"role": "user", "content": message[:1500]}],
            temperature=0, timeout=LLM_TIMEOUT_SECONDS, max_tokens=LLM_MAX_TOKENS,
            razonar=razonamiento("ORQUESTADOR_ROUTING_RAZONAMIENTO", False)))
        for b in BRIGADES:
            if b in answer:
                return b
    except Exception as exc:  # noqa: BLE001 — sin LLM del orquestador se cae a las reglas/default
        logger.info("clasificador LLM del orquestador no disponible (%s)", type(exc).__name__)
    return None


_USE_DEFAULT: Any = object()


async def route(message: str, brigade: str | None = None, llm: LlmClassifier | None = _USE_DEFAULT) -> Route:
    """Decide la brigada de un pedido. `brigade`: forzada desde la UI (vale como override)."""
    if brigade in BRIGADES or brigade in DIRECTAS:
        return Route(brigade, "override", "elegida a mano", message)
    created = _created_active()
    if brigade and brigade in created:
        return Route(brigade, "override", "elegida a mano", message)
    m = _OVERRIDE.match(message or "")
    if m:
        forced = "investigacion" if m.group(1).lower().startswith("investig") else "cerebro"
        return Route(forced, "override", f"prefijo /{m.group(1).lower()}", message[m.end():].strip() or message)
    m = _DIRECTA_OVERRIDE.match(message or "")
    if m:
        return Route(m.group(1).lower(), "override", f"prefijo /{m.group(1).lower()}", message[m.end():].strip() or message)
    m = _CREATED_OVERRIDE.match(message or "")
    if m and m.group(1).lower() in created:  # brigada creada y ACTIVA: solo por prefijo explícito, nunca por reglas
        return Route(m.group(1).lower(), "override", f"prefijo /{m.group(1).lower()}", message[m.end():].strip() or message)

    if pide_video(message):
        return Route("video", "reglas", "pide editar un video (verbo de edición + un video en el pedido)", message)
    winner, reason = route_by_rules(message)
    if winner:
        return Route(winner, "reglas", reason, message)
    if llm is _USE_DEFAULT:
        llm = llm_classify  # se resuelve al llamar (no al definir) para poder reemplazarlo en tests
    if reason == "sin señales" and len((message or "").split()) <= MAX_PALABRAS_SIN_LLM:
        # Un saludo o un pedido de dos o tres palabras sin ninguna señal no justifica una llamada al modelo (latencia y un
        # mensaje más saliendo a la nube): va directo a la opción de menor daño.
        return Route(DEFAULT_BRIGADE, "default", "pedido muy corto y sin señales → Cerebro (solo lectura), sin consultar al modelo", message)
    if llm is not None:
        guess = await llm(message)
        if guess in BRIGADES:
            return Route(guess, "llm", f"reglas sin señal clara ({reason}); clasificó el modelo del orquestador", message)
    return Route(DEFAULT_BRIGADE, "default", f"{reason}; sin LLM → Cerebro (local, solo lectura)", message)
