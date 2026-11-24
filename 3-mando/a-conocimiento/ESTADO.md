# ESTADO de Raphael

Actualizado: 24 nov 2026. Fuente de verdad junto con `CONTEXT.md` (si se contradicen, manda `CONTEXT.md` y se corrige este archivo). La versión anterior (20 nov) está en `D:\Raphael Ultimate\_archivo\docs\ESTADO.md`.

## Dónde vive todo
Todo el trabajo está en `D:\Raphael Ultimate\raphael\`, repo único `damianzupel-commits/Raphael`, ordenado en árbol a/b/c (`1-harness`, `2-entrega`, `3-mando`; ver `README.md` de la raíz). Lo viejo (`nucleo\`, `brigadas\`, `registro\`, `obra\`) quedó en `D:\Raphael Ultimate\_archivo\` y no se usa más. Los logs de sesión van en `a-historia/log.md` de cada pieza.

## Estado por pieza
| Pieza | Estado |
| --- | --- |
| Harness (`1-harness/b-codigo`) | H1 a H8 hechas, contrato 2.1, 405 tests en verde en la nube y en Windows (24 nov); panel nativo (abre) |
| Orquestador (`1-harness/c-brigadas/00-orquestador`) | O1 a O5 hechas, 266 tests en verde en la nube y en Windows (24 nov) |
| Empresas (`1-harness/c-brigadas/15-empresas`) | Brigada nativa 2.0.0, 124 tests en verde en Windows (24 nov); API y canal de Meta (26 tests en verde); app Android 1.1.0 (APK compila, sin probar en teléfono); kit del VPS probado solo en modo "solo archivos". **24 nov:** `INTERVIEW.md` y perfil borrador creados (PR abierto, esperando aprobación de Damián); **sin respuestas de la clienta todavía**, por eso no se tocaron módulos ni se cargó su perfil real |
| Servidor, app e instalador | Falta adoptar la API y el kit, montarlos en el VPS |
| Cuentas y APIs | Proveedor de IA elegido: NVIDIA para la v1 (24 nov, `NVIDIA_API_KEY`; falta cargar la clave en el VPS). Pendiente: VPS Hetzner, DuckDNS, app de Meta, número de prueba, Instagram de prueba |
| Brigadas 05 a 14 y 16 | Solo spec y cocineros; código de referencia en `3-mando/c-referencia/<brigada>/` |

Tests en la PC de Damián (Windows, Python 3.12) después de la mudanza, 24 nov: core 405, orchestrator 266, business 124, server 26, ruff limpio (821 en verde). Puerta: `3-mando\b-herramientas\gate.bat`. El PR de la entrevista solo agrega documentos: no se corrieron tests en este cambio.

## Pendiente (en orden)
1. ~~Versionar `raphael\` con git~~ hecho (24 nov, repo local). Falta: el repo privado y el push los hace Damián.
2. ~~Correr los tests en la PC y arreglar la mudanza; puerta en `3-mando/b-herramientas/`~~ hecho (24 nov, `3-mando\b-herramientas\gate.bat`).
3. Cuentas y APIs: VPS Hetzner (CX33), DuckDNS, app de Meta con número de prueba (proveedor de IA ya elegido: NVIDIA).
4. Entrevista a la clienta (demo de Mi Tienda IA): **preguntas listas en `1-harness/c-brigadas/15-empresas/INTERVIEW.md`** (24 nov, con supuestos marcados y revisión de alcance de Tienda). Falta: que Damián las haga, anotar sus respuestas, cargar su perfil (`a-historia/perfil-clienta.borrador.yaml` → `perfil_a_instalacion.py`) y ajustar los módulos (INTERVIEW §10).
5. Montar Empresas en el VPS y probar la app en un teléfono.
6. Recién después, una brigada por vez.

## Decisiones vigentes
Ver `CONTEXT.md` sección 6. El plan P0 a P6 y el brief de Fable 5.2 (de JarvisRemote) son planes viejos: no se usan salvo que Damián lo pida.

## Riesgos
Ver `CONTEXT.md` sección 9. Además: respaldar la clave de firma de Android fuera de git.
