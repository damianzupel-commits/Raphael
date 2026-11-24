"""Memoria episódica de Raphael (continuidad autobiográfica).

Ver docs/SPEC-memoria-episodica.md (2026-09-28). Distinta del vault (que es
memoria SEMÁNTICA, conocimiento del mundo): esto es memoria EPISÓDICA, la
experiencia del propio agente — qué vivió, qué le pidió Damian, qué decidió,
qué salió bien o mal, y por qué.

Fase 1 (este módulo): esquema de episodio (schema.py), clasificación
técnico/personal (classifier.py), destilado del historial a episodio
(distiller.py), store firmado + espejo en el grafo (store.py), y la captura
automática al cierre de turno (capture.py). El recall (recall.py) es Fase 2
pero ya está la base, usada por las tools de control (tools/memory_tools.py).

Todo es ADITIVO y defensivo: si falta una dependencia (win32crypt) o el
apagador global está en off, las funciones son no-op y JAMÁS rompen un turno.
"""

from __future__ import annotations

from . import capture, classifier, distiller, recall, schema, store  # noqa: F401

__all__ = ["capture", "classifier", "distiller", "recall", "schema", "store"]
