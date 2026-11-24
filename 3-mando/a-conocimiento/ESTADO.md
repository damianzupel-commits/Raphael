# ESTADO de Raphael

Actualizado: 24 nov 2026. Fuente de verdad junto con `CONTEXT.md` (si se contradicen, manda `CONTEXT.md` y se corrige este archivo). La versión anterior (20 nov) está en `D:\Raphael Ultimate\_archivo\docs\ESTADO.md`.

## Dónde vive todo
Todo el trabajo está en `D:\Raphael Ultimate\raphael\`, repo único `damianzupel-commits/Raphael`, ordenado en árbol a/b/c (`1-harness`, `2-entrega`, `3-mando`; ver `README.md` de la raíz). Lo viejo (`nucleo\`, `brigadas\`, `registro\`, `obra\`) quedó en `D:\Raphael Ultimate\_archivo\` y no se usa más. Los logs de sesión van en `a-historia/log.md` de cada pieza.

## Estado por pieza
| Pieza | Estado |
| --- | --- |
| Harness (`1-harness/b-codigo`) | H1 a H8 hechas, contrato 2.1, 405 tests en verde en la nube y en Windows (24 nov); panel nativo (abre) |
| Orquestador (`1-harness/c-brigadas/00-orquestador`) | O1 a O5 hechas, 266 tests en verde en la nube y en Windows (24 nov) |
| Empresas (`1-harness/c-brigadas/15-empresas`) | Brigada nativa 2.0.0, 124 tests en verde en Windows (24 nov); API y canal de Meta (26 tests en verde); app Android 1.1.0 (APK compila, sin probar en teléfono); kit del VPS probado solo en modo "solo archivos" |
| Servidor, app e instalador | API y kit del VPS adoptados (24 nov): paquete, instalación "solo archivos", arranque, health y webhook probados en la nube con el árbol a/b/c; docs y rutas corregidas, checklist de montaje en `2-entrega/c-despliegue/vps/LEEME.md`. Falta montarlo en un VPS real (necesita VPS, DuckDNS y claves cargadas por Damián) |
| Cuentas y APIs | Proveedor de IA: OpenRouter (24 nov, `OPENROUTER_API_KEY`, saldo ya cargado por Damián; falta cargar la clave en el VPS): DeepSeek V4 Flash de principal y modelos `:free` rotando de alternativa en roles chicos, siempre con `data_collection=deny`. NVIDIA gratis solo para desarrollo, sus términos no permiten producción. Slugs y precios son supuestos a verificar. Pendiente: VPS Hetzner, DuckDNS, app de Meta, número de prueba, Instagram de prueba |
| Brigadas 05 a 14 y 16 | Solo spec y cocineros; código de referencia en `3-mando/c-referencia/<brigada>/` |

Tests en la PC de Damián (Windows, Python 3.12) después de la mudanza, 24 nov: core 405, orchestrator 266, business 124, server 26, ruff limpio (821 en verde). Puerta: `3-mando\b-herramientas\gate.bat`.

## Pendiente (en orden)
1. ~~Versionar `raphael\` con git~~ hecho (24 nov, repo local). Falta: el repo privado y el push los hace Damián.
2. ~~Correr los tests en la PC y arreglar la mudanza; puerta en `3-mando/b-herramientas/`~~ hecho (24 nov, `3-mando\b-herramientas\gate.bat`).
3. Cuentas y APIs: VPS Hetzner (CX33), DuckDNS, app de Meta con número de prueba (proveedor de IA ya elegido: OpenRouter).
4. Entrevista a la clienta (demo de Mi Tienda IA) → `1-harness/c-brigadas/15-empresas/INTERVIEW.md`; ajustar Empresas.
5. Montar Empresas en el VPS y probar la app en un teléfono.
6. Recién después, una brigada por vez.

## Decisiones vigentes
Ver `CONTEXT.md` sección 6. El plan P0 a P6 y el brief de Fable 5.2 (de JarvisRemote) son planes viejos: no se usan salvo que Damián lo pida.

## Riesgos
Ver `CONTEXT.md` sección 9. Además: respaldar la clave de firma de Android fuera de git.
