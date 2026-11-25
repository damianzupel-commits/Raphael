"""Brigada Autorreparación de Raphael (harness v2): propone y aplica arreglos al propio código.

Cocineros: proponer (siempre dry-run), aplicar (solo con aprobación de la persona, línea roja y vuelta atrás) e
introspección (detecta patrones de falla en el comportamiento y guarda reflexiones).
Todo lo que declara (acciones con su nivel, eventos, comandos) está en `manifest.yaml`, la única fuente de verdad.
Solo importa `raphael_core` y la stdlib (más pydantic): ninguna otra brigada.
"""

__version__ = "2.0.0"
