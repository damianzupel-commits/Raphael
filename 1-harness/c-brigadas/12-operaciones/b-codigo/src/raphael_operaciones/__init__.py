"""Brigada Operaciones de Raphael (harness v2): las manos de Raphael en la PC, el celular y el navegador.

Cocineros: pc (comandos, escritorio y archivos), phone (celular), browser-web (navegador y web) y supervisor (modo de
operación y revisión de llamados). Todo lo que declara (acciones, tools, comandos, nivel de autonomía) está en
`manifest.yaml`, la única fuente de verdad. Solo corre en la edición personal (PC y celular de Damián), nunca en el VPS.
Solo importa `raphael_core` y la stdlib: ninguna otra brigada.

Todo lo que toca el mundo real va por un adaptador enchufable (`adapters/`): uno real y uno simulado. Por defecto
corre simulado; se pasa a real con `OPERACIONES_ADAPTADORES=real` (ver `b-codigo/.env.plantilla`).
"""

__version__ = "1.0.0"
