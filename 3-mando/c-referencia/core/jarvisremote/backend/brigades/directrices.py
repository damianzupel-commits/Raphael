"""Directrices de Cerebro — la carta editable que gobierna su autonomía (paso 4).

Damian escribe acá (desde la Suite) qué debe priorizar Cerebro, qué NO tocar, y cómo
decidir. Se inyecta en su system prompt (y, más adelante, condiciona la tarea
proactiva). Es el mecanismo con el que Damian acota la libertad del jefe sin tocar
código (decisión 2026-11-03: "actúa solo en base a directrices que le dé yo mismo").

Persistido en data/cerebro_directrices.md. Best-effort.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("brigades.directrices")

_PATH = Path(__file__).resolve().parent.parent / "data" / "cerebro_directrices.md"

_DEFAULT = """# Directrices de Cerebro

(Editá esto desde la Suite. Gobierna qué prioriza Cerebro, qué no toca y cómo decide.)

- Priorizá conectar y consolidar notas de los temas que estoy trabajando ahora.
- NO reorganices ni toques las notas de las carpetas sensibles (Fénix, Biotecnología,
  Conciencia); leelas solo si te pregunto algo puntual.
- Cuando saques una conclusión, dejala como nota propia con las fuentes que la sustentan,
  nunca como un hecho sin respaldo.
- Ante la duda, avisá antes de reorganizar algo grande. Nunca borres.
"""


def load_directrices() -> str:
    try:
        return _PATH.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return _DEFAULT


def save_directrices(text: str) -> bool:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(text, encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        logger.warning("no se pudo guardar las directrices de Cerebro", exc_info=True)
        return False
