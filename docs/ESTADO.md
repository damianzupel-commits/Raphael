# ESTADO de Raphael

Actualizado: 24 nov 2026. Fuente de verdad junto con `CONTEXT.md` (si se contradicen, manda `CONTEXT.md` y se corrige este archivo). La versión anterior (20 nov) está en `D:\Raphael Ultimate\_archivo\docs\ESTADO.md`.

## Dónde vive todo
Todo el trabajo está en `D:\Raphael Ultimate\raphael\` (monorepo). Lo viejo (`nucleo\`, `brigadas\`, `registro\`, `obra\`) quedó en `D:\Raphael Ultimate\_archivo\` y no se usa más. Los logs de sesión van en `docs/log/<pieza>.md`.

## Estado por pieza
| Pieza | Estado |
| --- | --- |
| Harness (`packages/core`) | H1 a H8 hechas, contrato 2.1, 405 tests en verde en la nube; panel nativo |
| Orquestador (`packages/orchestrator`) | O1 a O5 hechas, 266 tests en verde en la nube |
| Empresas (`brigades/business`) | Brigada nativa 2.0.0, 124 tests; API y canal de Meta (26 tests); app Android 1.1.0 (APK compila, sin probar en teléfono); kit del VPS probado solo en modo "solo archivos" |
| Servidor, app e instalador | Falta adoptar la API y el kit, montarlos en el VPS |
| Cuentas y APIs | Pendiente todo: VPS Hetzner, DuckDNS, app de Meta, número de prueba, Instagram de prueba, proveedor de IA |
| Brigadas 05 a 14 y 16 | Solo spec y cocineros; código de referencia en `_reference/<brigada>/` |

Los tests no se corrieron todavía en la PC de Damián (Python de Windows) ni después de la mudanza del 24 nov.

## Pendiente (en orden)
1. Versionar `raphael\` con git (commit inicial; el repo privado y el push los hace Damián).
2. Correr los tests de core, orchestrator y business en la PC y arreglar lo que rompió la mudanza; puerta en `tools/`.
3. Cuentas y APIs: VPS Hetzner (CX33), DuckDNS, app de Meta con número de prueba, proveedor de IA.
4. Entrevista a la clienta (demo de Mi Tienda IA) → `brigades/business/INTERVIEW.md`; ajustar Empresas.
5. Montar Empresas en el VPS y probar la app en un teléfono.
6. Recién después, una brigada por vez.

## Decisiones vigentes
Ver `CONTEXT.md` sección 6. El plan P0 a P6 y el brief de Fable 5.2 (de JarvisRemote) son planes viejos: no se usan salvo que Damián lo pida.

## Riesgos
Ver `CONTEXT.md` sección 9. Además: respaldar la clave de firma de Android fuera de git.
