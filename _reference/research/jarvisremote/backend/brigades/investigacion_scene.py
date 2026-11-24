"""Escena de validación de la brigada de Investigación (declarada como dato; ver BrigadeSpec.validation).

Spec de Damian (2026-11-10): Forense es el ESTÁNDAR (manejador por defecto) y Scout TAMBIÉN tiene que
funcionar, los dos de punta a punta y reales. Escena de 4 pasos; Investigación PASA solo si los 4 dan bien:

  1. RUTEO POR DEFECTO -> FORENSE   un pedido neutro/ambiguo o con señal de evidencia/caso debe delegar en
                                    `delegar:investigacion-forense` (el jefe real, con el ayudante simulado).
  2. FORENSE de punta a punta       modelo LOCAL (Ollama): crea un caso y guía la ingesta. Se verifica el
                                    artefacto concreto (carpeta del caso, repo git con su commit) en un store
                                    AISLADO, y que no invente (no dice que ingestó lo que no ingestó).
  3. RUTEO WEB -> SCOUT             un pedido claro de research web delega en `delegar:investigacion-scout`.
  4. SCOUT de punta a punta         Groq + búsqueda web real (Brave/SearXNG): `research_topic` debe dejar una NOTA
                                    en el vault de Scout (aislado) con contenido y fuentes (URLs). Si falta la key
                                    de búsqueda o de Groq, este paso queda SIN VALIDAR (no rojo); los demás corren.

El orden y los textos de `scene` NO se tocan sin motivo: su hash versiona el baseline.
"""

from __future__ import annotations

from .spec import Criterion, StepSpec, ValidationSpec

NEUTRAL = ["Necesito ayuda con una cosa", "Tengo un archivo y quiero entender qué hay adentro", "¿Me ayudás con esto?"]
EVIDENCIA = ["Creá un caso nuevo para analizar unos mensajes", "Ingestá este CSV de evidencia"]
WEB = ["Investigá en la web las novedades de los modelos de lenguaje locales",
       "Buscá en internet qué es el protocolo ActivityPub",
       "Hacé research en la web sobre el estado del arte en embeddings multilingües"]
CASE_ID, CASE_TITLE = "validacion-orion", "Caso de validación Orión"
FORENSE_MSG = (f"Creá un caso nuevo con id {CASE_ID} y título «{CASE_TITLE}». Después decime en pocas palabras "
               "cómo seguirías para ingestar un CSV de evidencia en ese caso.")
SCOUT_TOPIC = "el protocolo ActivityPub"
SCOUT_MSG = f"Investigá en la web qué es {SCOUT_TOPIC} y guardá lo que encuentres como nota."

# Stores que esta brigada toca y que se redirigen a un temporal (ver validation/harness.isolated_environment).
ISOLATE_SETTINGS = {
    "investigation_cases_dir": "investigation_cases",          # los casos (un repo git cada uno)
    "investigation_artifact_store_dir": "investigation_artifacts",
    "investigation_keys_dir": "investigation_keys",            # clave de firma Ed25519 del log
    "research_vault_path": "vault_scout",                      # el vault donde Scout deja sus notas
    "research_embeddings_path": "data/research_embeddings.json",
    "research_working_dir": "capture",                         # carpeta de captura (fs_*)
}
ISOLATE_ENV = {"SCOUT_VAULT_PATH": "vault_scout", "SCOUT_EMBEDDINGS_PATH": "data/research_embeddings.json",
               "SCOUT_CAPTURE_DIR": "capture"}

_V = "validation.investigacion"

VALIDATION = ValidationSpec(
    title="VALIDACION DE INVESTIGACION (Forense por defecto + Scout) — real, supervisada, stores aislados",
    scene={"neutral": NEUTRAL, "evidencia": EVIDENCIA, "web": WEB, "forense_msg": FORENSE_MSG, "scout_msg": SCOUT_MSG},
    facts={"case_id": CASE_ID, "case_title": CASE_TITLE, "scout_topic": SCOUT_TOPIC},
    steps=(
        StepSpec("ruteo_forense", "Ruteo por defecto -> Forense", f"{_V}:step_ruteo_forense"),
        StepSpec("forense", "Forense de punta a punta", f"{_V}:step_forense"),
        StepSpec("ruteo_scout", "Ruteo web -> Scout", f"{_V}:step_ruteo_scout"),
        StepSpec("scout", "Scout de punta a punta", f"{_V}:step_scout", prereq=f"{_V}:check_scout_prerequisites"),
    ),
    criterion=Criterion("PASA si los 4 pasos pasan y no se tocó nada real; un paso SIN VALIDAR deja la corrida INCOMPLETA."),
    baseline_keys=("model", "scout_model", "routing", "forense", "scout"),
    prerequisites=("local_stack",),
    isolate_settings=ISOLATE_SETTINGS,
    isolate_env=ISOLATE_ENV,
    base_metrics=f"{_V}:base_metrics",
    banner=f"{_V}:banner",
    teardown=f"{_V}:teardown",
)
