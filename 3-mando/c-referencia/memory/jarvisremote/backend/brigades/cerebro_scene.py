"""Escena de validación de Cerebro (declarada como dato; ver BrigadeSpec.validation).

Criterio COMPLETO (decisión de Damian 2026-11-09), contra el modelo LOCAL de Cerebro (Ollama) y los
embeddings reales (LM Studio), en un vault de PRUEBA aislado (ver validation/harness.py). Cerebro PASA
solo si cumple los 4 pasos:

  1. SEMBRAR   3 notas fijas con `remember()` (2 relacionadas + 1 distractor) y verificar que quedaron
               guardadas y con embedding.
  2. ASOCIAR   una pregunta que necesita las 2 notas relacionadas: la recuperación asociativa las trae,
               Cerebro las CITA con sus datos correctos y, ante una pregunta cuya respuesta NO está en
               las notas, admite que no lo sabe (no inventa).
  3. DIRECTRIZ fija una directriz concreta (formato verificable) y comprueba que la MISMA pregunta
               cambia de forma observable respecto del paso 2.
  4. PROACTIVA corre la pasada proactiva real (`cerebro_pass`): debe nacer una nota de CONCLUSIÓN nueva
               que enlaza sus fuentes, y quedar registrada en el feed de actividad.

Los datos son FIJOS: eso es lo que hace repetible la validación. El orden y los textos de `scene` NO se
tocan sin motivo: su hash versiona el baseline.
"""

from __future__ import annotations

from .spec import Criterion, StepSpec, ValidationSpec

N1_TITLE = "Rotación de claves del servidor Orión"
N1 = ("El servidor Orión rota sus claves SSH cada 45 días. Responsable: Valeria Quiroga. "
      "El script es rotar_orion.sh y corre los lunes a las 03:10. Si la rotación falla, se avisa por el canal #infra-orion.")
N2_TITLE = "Incidente de rotación fallida en Orión"
N2 = ("El 12 de marzo la rotación de claves del servidor Orión falló porque el disco /var estaba al 98%. "
      f"Se resolvió liberando 14 GB de logs viejos. Valeria Quiroga bajó el umbral de alerta de disco al 85%. Relacionado: [[{N1_TITLE}]].")
N3_TITLE = "Receta de alfajores de maicena"
N3 = ("Ingredientes: 200 g de maicena, 100 g de harina, 150 g de manteca, 100 g de azúcar impalpable, 3 yemas y dulce de leche. "
      "Se hornean 10 minutos a 170 grados y se rellenan con dulce de leche.")
SEEDS = [(N1_TITLE, N1), (N2_TITLE, N2), (N3_TITLE, N3)]

QUESTION = "¿Cada cuántos días se rotan las claves del servidor Orión y qué pasó cuando falló la rotación?"
UNKNOWN_QUESTION = "¿Quién aprobó el presupuesto del servidor Orión y de cuánto fue?"
DIRECTRIZ_MARKER = "FIN-DIRECTRIZ"
DIRECTRIZ = ("Respondé SIEMPRE en una sola oración de no más de 30 palabras, nombrando entre corchetes la nota fuente "
             f"principal, y terminá la respuesta con la palabra {DIRECTRIZ_MARKER}.")

_V = "validation.cerebro"

VALIDATION = ValidationSpec(
    title="VALIDACION DE CEREBRO (criterio COMPLETO) — real, supervisada, vault aislado",
    scene={"seeds": SEEDS, "question": QUESTION, "unknown_question": UNKNOWN_QUESTION, "directriz": DIRECTRIZ},
    facts={"directriz_marker": DIRECTRIZ_MARKER, "related_titles": [N1_TITLE, N2_TITLE], "distractor_title": N3_TITLE},
    steps=(
        StepSpec("sembrar", "Sembrar", f"{_V}:step_sembrar", gate=True),
        StepSpec("asociar", "Asociar y citar sin inventar", f"{_V}:step_asociar"),
        StepSpec("directriz", "Directriz cambia el comportamiento", f"{_V}:step_directriz", needs=("before_answer",)),
        StepSpec("proactiva", "Pasada proactiva -> conclusión", f"{_V}:step_proactiva", needs=("notes",)),
    ),
    criterion=Criterion("PASA si los 4 pasos pasan y no se tocó el vault ni el estado reales."),
    baseline_keys=("model", "embedding_model", "retrieval", "answer", "invention_probe", "directriz", "conclusion"),
    prerequisites=("local_stack",),
    base_metrics=f"{_V}:base_metrics",
    banner=f"{_V}:banner",
)
