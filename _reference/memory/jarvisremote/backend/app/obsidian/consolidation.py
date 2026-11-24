"""Consolidación de memoria -- el "sueño" de Raphael (Fase 3 de la estructura
informacional cerebro-símil, ver docs/SPEC-estructura-informacional-cerebro.md §3.4).

El cerebro, durmiendo, REPITE lo del día y lo integra: abstrae patrones, funde lo
redundante, refuerza lo importante. Esto hace el análogo sobre el vault: agarra notas
recientes RELACIONADAS (clusters por similitud de embedding), y por cada cluster:
  1. escribe una nota de SÍNTESIS que abstrae la lección común (con el LLM local), y
  2. REFUERZA las aristas Hebbianas entre las notas del cluster (se repasaron juntas
     -> se cablean juntas, [[hebbian]]).

CONSERVADOR A PROPÓSITO (el vault tiene material real y personal de Damian):
- Es ADITIVO y REVERSIBLE: NUNCA modifica ni borra las notas originales. Solo crea
  notas nuevas de síntesis (autor 'jarvis', tag 'consolidacion') que enlazan a las
  fuentes. Si no gustan, se borran y listo. El olvido de lo irrelevante NO lo hace
  esto: lo hace la Fase 4 ([[strength]]) bajando el ranking, sin tocar el crudo.
- Idempotente: cada síntesis lleva un `consolidation-id` (hash de las notas fuente);
  un cluster ya consolidado no se vuelve a sintetizar.
- Dry-run por default en la tool manual: muestra QUÉ consolidaría sin escribir nada.
- El job automático arranca APAGADO (CONSOLIDATION_ENABLED=false): escribe en el vault
  con el LLM, así que se prende a conciencia.

PROCESADOR (§3-bis): el clustering/refuerzo es tier 0 (cómputo de grafo, puro); la
SÍNTESIS la escribe el modelo barato/local (tier 1), offline/batch -- no el caro.

El core de clustering (`_components`, `find_clusters`) es puro y testeable con grafos
sintéticos, sin tocar vault, embeddings ni LLM.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from itertools import combinations

from ..config import settings
from . import embeddings, hebbian, vault

logger = logging.getLogger("jarvis.obsidian.consolidation")

_STARTUP_DELAY_SECONDS = 120.0


# --- core de clustering (PURO) ---------------------------------------------------

def _components(adjacency: dict[str, set[str]]) -> list[set[str]]:
    """Componentes conexas de un grafo no dirigido (BFS). Puro."""
    seen: set[str] = set()
    comps: list[set[str]] = []
    for start in adjacency:
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            node = stack.pop()
            if node in comp:
                continue
            comp.add(node)
            seen.add(node)
            stack.extend(adjacency.get(node, ()) - comp)
        comps.append(comp)
    return comps


def _cluster_from_pairs(pairs: list[tuple[str, str]], min_size: int = 2, max_size: int = 6) -> list[list[str]]:
    """Dada una lista de pares (notas suficientemente similares), arma clusters por
    componentes conexas y los filtra por tamaño. Puro. Clusters ordenados y estables."""
    adj: dict[str, set[str]] = {}
    for a, b in pairs:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    out = []
    for comp in _components(adj):
        if min_size <= len(comp) <= max_size:
            out.append(sorted(comp))
    return sorted(out, key=lambda c: (-len(c), c[0]))


def _consolidation_id(note_ids: list[str]) -> str:
    return hashlib.sha1("|".join(sorted(note_ids)).encode("utf-8")).hexdigest()[:12]


def schema_fit(cluster: list[str], weights: dict[str, float]) -> float:
    """Fase 8 -- cuán 'encajado en un esquema existente' está un cluster: el peso
    Hebbiano PROMEDIO entre sus notas. Si ya se usaron juntas (aristas reforzadas > 1),
    el patrón está establecido -> integrar rápido. Si todas están neutras (1.0), es
    genuinamente nuevo -> conviene dejarlo madurar en episódico antes de consolidar.
    Puro. Devuelve >= 1.0 (1.0 = nada establecido)."""
    pairs = list(combinations(sorted(cluster), 2))
    if not pairs:
        return 1.0

    def w(a: str, b: str) -> float:
        key = f"{a}\t{b}" if a <= b else f"{b}\t{a}"
        return weights.get(key, 1.0)

    return sum(w(a, b) for a, b in pairs) / len(pairs)


def _existing_consolidation_ids() -> set[str]:
    rx = re.compile(r"consolidation-id:\s*([0-9a-f]{12})")
    ids: set[str] = set()
    for note in vault.list_notes(author="jarvis"):
        for m in rx.finditer(note.content):
            ids.add(m.group(1))
    return ids


# --- selección de notas recientes + clusters por embedding ----------------------

def _recent_ids(days: int) -> list[str]:
    """IDs de notas con `updated` dentro de los últimos `days` días. Si no hay fechas
    parseables, cae a todas las notas (para no quedar sin candidatos)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    recent, total = [], 0
    for n in vault.list_notes():
        total += 1
        try:
            u = datetime.fromisoformat(n.updated)
            if u.tzinfo is None:
                u = u.replace(tzinfo=timezone.utc)
            if u >= cutoff:
                recent.append(n.id)
        except (ValueError, TypeError):
            continue
    return recent or [n.id for n in vault.list_notes()]


def select_pairs(sims: dict[tuple[str, str], float], threshold: float, gap: float | None) -> list[tuple[str, str]]:
    """Qué pares de notas se consideran vecinas. Puro (sin embeddings, testeable).

    Dos criterios, AMBOS tienen que cumplirse (fix 2026-11-12, hallazgo de la Ronda 2 de Cerebro: con el modelo de
    embeddings actual un distractor sin relación puntuaba 0.74-0.77 contra las notas correctas, que puntuaban 0.91
    entre sí; con el umbral viejo de 0.6 se agrupaba y mezclaba temas en la conclusión):
      1. absoluto:  coseno >= `threshold`.
      2. relativo (brecha): el par tiene que estar a lo sumo `gap` por debajo de la MEJOR similitud de cualquiera de sus
         dos notas. Una nota que es claramente más parecida a otras no se une a una vecina mucho más lejana. `gap=None`
         lo desactiva."""
    best: dict[str, float] = {}
    for (a, b), s in sims.items():
        best[a] = max(best.get(a, -1.0), s)
        best[b] = max(best.get(b, -1.0), s)
    out = []
    for (a, b), s in sims.items():
        if s < threshold:
            continue
        if gap is not None and s < max(best[a], best[b]) - gap:
            continue
        out.append((a, b))
    return out


def evaluar_agrupamiento(sims: dict[tuple[str, str], float], grupos: list[list[str]], threshold: float, gap: float | None) -> dict:
    """Qué tan bien agrupa (`threshold`, `gap`) contra una verdad etiquetada a mano. Puro (O-2: calibrar con varias escenas y
    con el vault real, no con una sola). `grupos` = listas de ids que DEBERÍAN quedar juntas; todo otro par es "no va junto".
    Mide sobre PARES: precisión (de los pares que agrupó, cuántos iban juntos: baja = mezcla temas), recall (de los que iban
    juntos, cuántos agrupó) y F1. La precisión es la que más importa acá: un grupo mal armado mezcla temas en la conclusión."""
    juntos = {frozenset((a, b)) for g in grupos for i, a in enumerate(g) for b in g[i + 1:]}
    dichos = {frozenset(p) for p in select_pairs(sims, threshold, gap)}
    bien = len(dichos & juntos)
    precision = bien / len(dichos) if dichos else 1.0
    recall = bien / len(juntos) if juntos else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"threshold": threshold, "gap": gap, "pares_agrupados": len(dichos), "pares_esperados": len(juntos), "correctos": bien,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def barrer_umbrales(sims: dict[tuple[str, str], float], grupos: list[list[str]],
                    thresholds: tuple[float, ...] = (0.70, 0.75, 0.80, 0.85, 0.90), gaps: tuple[float | None, ...] = (None, 0.04, 0.08, 0.12)) -> list[dict]:
    """Todas las combinaciones (umbral, brecha) evaluadas, la mejor primero: precisión 1.0 antes que nada (no mezclar temas),
    después el mayor recall y, a igualdad, el umbral más alto (más conservador)."""
    filas = [evaluar_agrupamiento(sims, grupos, t, g) for t in thresholds for g in gaps]
    return sorted(filas, key=lambda r: (-(r["precision"] >= 1.0), -r["recall"], -r["precision"], -r["threshold"]))


def find_clusters(ids: list[str], threshold: float, min_size: int = 2, max_size: int = 6,
                  gap: float | None = None) -> list[list[str]]:
    """Clusters de notas similares entre las `ids` dadas, usando los embeddings. Dos
    notas son vecinas si pasan `select_pairs` (umbral absoluto + brecha relativa `gap`;
    por default `settings.consolidation_similarity_gap`). None de embeddings -> []."""
    gap = settings.consolidation_similarity_gap if gap is None else gap
    index = embeddings.load_index()
    vecs = {nid: index[nid] for nid in ids if nid in index}
    items = list(vecs.items())
    sims: dict[tuple[str, str], float] = {}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            sims[(items[i][0], items[j][0])] = embeddings.cosine_similarity(items[i][1], items[j][1])
    return _cluster_from_pairs(select_pairs(sims, threshold, gap), min_size=min_size, max_size=max_size)


# --- síntesis con el LLM (tier 1) -----------------------------------------------

_MAX_NOTE_CHARS = 2500


def _synthesis_messages(notes: list[vault.VaultNote]) -> list[dict]:
    system = (
        "Sos Raphael consolidando tu propia memoria (como el cerebro al dormir): te paso "
        "varias notas relacionadas de tu vault y tenés que ABSTRAER lo común en una síntesis. "
        "Respondé SOLO un objeto JSON válido (sin markdown, sin ```), claves exactas:\n"
        '  "title": título corto y descriptivo de la síntesis (en español).\n'
        '  "category": una palabra/frase corta de categoría temática (minúsculas).\n'
        '  "synthesis": 3-6 oraciones en un párrafo que capten el patrón/lección común a '
        "todas las notas (no un resumen de cada una por separado: la IDEA que las une).\n"
        '  "lessons": lista de 2-5 strings con las lecciones/insights concretos.'
    )
    partes = []
    for n in notes:
        partes.append(f"### {n.title}\n{n.content[:_MAX_NOTE_CHARS]}")
    user = "Notas a consolidar:\n\n" + "\n\n".join(partes)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_synthesis(raw: str) -> dict:
    text = raw.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}
    title = (data.get("title") or "").strip() or "Síntesis de notas relacionadas"
    category = (data.get("category") or "").strip().lower() or "consolidacion"
    synthesis = (data.get("synthesis") or "").strip() or "(sin síntesis generada)"
    lessons = data.get("lessons") or []
    if not isinstance(lessons, list):
        lessons = []
    lessons = [str(x).strip() for x in lessons if str(x).strip()]
    return {"title": title, "category": category, "synthesis": synthesis, "lessons": lessons}


def _build_synthesis_content(parsed: dict, sources: list[vault.VaultNote], cons_id: str) -> str:
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        f"Síntesis automática (consolidación / 'sueño') de {len(sources)} notas relacionadas.",
        "",
        "## Síntesis",
        parsed["synthesis"],
        "",
        "## Lecciones",
    ]
    parts += [f"- {l}" for l in parsed["lessons"]] or ["- (no se extrajeron lecciones)"]
    parts += [
        "",
        "## Notas consolidadas",
        *[f"- [[{n.title}]]" for n in sources],
        "",
        "## Meta",
        f"- generado: {fecha}",
        f"- consolidation-id: {cons_id}",
    ]
    return "\n".join(parts)


async def _default_call_llm(messages: list[dict]) -> str:
    # El "sueño" es una tarea PROGRAMADA -> tier 1 (modelo LOCAL). Es lo correcto por
    # diseño (corre de fondo, no importa que sea lento) y por PRIVACIDAD: sintetiza
    # notas del vault personal, que así nunca salen de la PC.
    from ..harness import model_registry

    tier_client, tier_model = model_registry.client_and_model_for_tier(1)
    response = await tier_client.chat.completions.create(
        model=tier_model,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.reserved_response_tokens,
    )
    return response.choices[0].message.content or ""


async def run_once(
    *,
    dry_run: bool = True,
    max_clusters: int | None = None,
    lookback_days: int | None = None,
    threshold: float | None = None,
    call_llm=None,
    save_note=None,
) -> dict:
    """Una pasada de consolidación. `dry_run=True` (default) NO escribe: solo devuelve
    qué clusters consolidaría. `dry_run=False` crea las notas de síntesis y refuerza
    las aristas. Todo lo externo es inyectable para testear."""
    call_llm = call_llm or _default_call_llm
    save_note = save_note or vault.save_note
    max_clusters = max_clusters if max_clusters is not None else settings.consolidation_max_clusters_per_run
    lookback_days = lookback_days if lookback_days is not None else settings.consolidation_lookback_days
    threshold = threshold if threshold is not None else settings.consolidation_similarity_threshold

    ids = _recent_ids(lookback_days)
    clusters = find_clusters(ids, threshold)
    if not clusters:
        return {"status": "sin_clusters", "candidatas": len(ids), "dry_run": dry_run}

    # Fase 8 -- consolidación dependiente de esquema: ordená por schema_fit (lo que ya
    # encaja en un esquema establecido va PRIMERO; con el tope por corrida, lo
    # genuinamente nuevo queda para una pasada futura, cuando haya madurado).
    weights = hebbian.load_weights()
    clusters = sorted(clusters, key=lambda c: schema_fit(c, weights), reverse=True)

    already = _existing_consolidation_ids()
    by_id = {n.id: n for n in vault.list_notes()}
    procesados, creados, saltados = [], [], 0

    for cluster in clusters:
        if max_clusters and len(procesados) >= max_clusters:
            break
        cons_id = _consolidation_id(cluster)
        titulos = [by_id[c].title for c in cluster if c in by_id]
        if cons_id in already:
            saltados += 1
            continue
        procesados.append({"consolidation_id": cons_id, "notas": titulos, "schema_fit": round(schema_fit(cluster, weights), 3)})
        if dry_run:
            continue
        sources = [by_id[c] for c in cluster if c in by_id]
        raw = await call_llm(_synthesis_messages(sources))
        parsed = _parse_synthesis(raw)
        content = _build_synthesis_content(parsed, sources, cons_id)
        note = save_note(
            title=parsed["title"],
            content=content,
            author="jarvis",
            tags=["consolidacion", "sueño", parsed["category"]],
            category=parsed["category"],
            extra={"origen": "consolidacion", "consolidation_id": cons_id, "n_fuentes": len(sources)},
        )
        hebbian.reforzar(cluster)  # repasadas juntas -> se cablean juntas
        creados.append({"note_id": getattr(note, "id", None), "title": getattr(note, "title", parsed["title"])})

    return {
        "status": "ok",
        "dry_run": dry_run,
        "candidatas": len(ids),
        "clusters_encontrados": len(clusters),
        "ya_consolidados": saltados,
        "a_consolidar" if dry_run else "consolidados": procesados if dry_run else creados,
    }


async def consolidation_loop() -> None:
    """Job de vida larga (arrancado desde el startup de FastAPI, como el watcher y el
    scan de malware). Default APAGADO. Cuando está prendido, consolida cada
    CONSOLIDATION_INTERVAL_HOURS. Un fallo se loguea y no corta el loop."""
    import asyncio

    if not settings.consolidation_enabled:
        logger.info("consolidación ('sueño') deshabilitada (CONSOLIDATION_ENABLED=false)")
        return
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            summary = await run_once(dry_run=False)
            logger.info("consolidación: %s", summary)
            # Centro de Mando: reporta a la brigada Memoria (2026-10-13). Best-effort.
            try:
                from .. import mission_control

                creados = summary.get("consolidados") or []
                n = len(creados) if isinstance(creados, list) else 0
                await mission_control.report(
                    "mem",
                    f"🧠 {n} nota(s) de síntesis" if n else "consolidación · sin clusters nuevos",
                    inc=n,
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception:
            logger.exception("la consolidación falló")
        await asyncio.sleep(max(3600.0, settings.consolidation_interval_hours * 3600))
