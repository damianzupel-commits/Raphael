# ESTADO de Raphael

Actualizado: 24 nov 2026. Fuente de verdad junto con `CONTEXT.md` (si se contradicen, manda `CONTEXT.md` y se corrige este archivo). La versión anterior (20 nov) está en `D:\Raphael Ultimate\_archivo\docs\ESTADO.md`.

## Dónde vive todo
Todo el trabajo está en `D:\Raphael Ultimate\raphael\`, repo único `damianzupel-commits/Raphael`, ordenado en árbol a/b/c (`1-harness`, `2-entrega`, `3-mando`; ver `README.md` de la raíz). Lo viejo (`nucleo\`, `brigadas\`, `registro\`, `obra\`) quedó en `D:\Raphael Ultimate\_archivo\` y no se usa más. Los logs de sesión van en `a-historia/log.md` de cada pieza.

## Estado por pieza
| Pieza | Estado |
| --- | --- |
| Harness (`1-harness/b-codigo`) | H1 a H8 hechas, contrato 2.1, 408 tests en verde en la nube (24 nov; Windows no se volvió a correr desde que se sumó el test de imports reales); panel nativo (abre) |
| Orquestador (`1-harness/c-brigadas/00-orquestador`) | O1 a O5 hechas, 266 tests en verde en la nube y en Windows (24 nov) |
| Empresas (`1-harness/c-brigadas/15-empresas`) | Brigada nativa 2.0.0, 124 tests en verde en Windows (24 nov); API y canal de Meta (26 tests en verde); app Android 1.1.0 (APK compila, sin probar en teléfono); kit del VPS probado solo en modo "solo archivos". **24 nov:** `INTERVIEW.md` y perfil borrador creados (PR abierto, esperando aprobación de Damián); **sin respuestas de la clienta todavía**, por eso no se tocaron módulos ni se cargó su perfil real |
| Servidor, app e instalador | API y kit del VPS adoptados (24 nov): paquete, instalación "solo archivos", arranque, health y webhook probados en la nube con el árbol a/b/c; docs y rutas corregidas, checklist de montaje en `2-entrega/c-despliegue/vps/LEEME.md`. Falta montarlo en un VPS real (necesita VPS, DuckDNS y claves cargadas por Damián) |
| Cuentas y APIs | Proveedor de IA: OpenRouter (24 nov, `OPENROUTER_API_KEY`, saldo ya cargado por Damián; falta cargar la clave en el VPS): DeepSeek V4 Flash de principal y modelos `:free` rotando de alternativa en roles chicos, siempre con `data_collection=deny`. NVIDIA gratis solo para desarrollo, sus términos no permiten producción. Slugs y precios son supuestos a verificar. Pendiente: VPS Hetzner, DuckDNS, app de Meta, número de prueba, Instagram de prueba |
| Brigadas 05 a 14 y 16 | Solo spec y cocineros; código de referencia en `3-mando/c-referencia/<brigada>/` |

Tests en la PC de Damián (Windows, Python 3.12) después de la mudanza, 24 nov: core 409, orchestrator 266, business 124, server 42, ruff limpio (841 en verde). Puerta: `3-mando\b-herramientas\gate.bat`.

## Cambios recientes
- 25 nov, hilo "Dejar Raphael listo para usar con solo claves" (segunda parte): Raphael arranca sin ninguna clave y las claves se ponen o sacan desde una pantalla de Configuración web del propio servidor (`/config`, con sesión; el acceso directo la abre). Primer acceso: la clave de la app se genera sola, se muestra una vez y queda en `.data\empresas\clave-inicial.txt` hasta que se cambie. Las claves se guardan solo en `raphael.env` local (600, fuera de git), se aplican en caliente (IA y Meta, incluido mock/real) y nunca se devuelven completas (solo últimos 4). Las de la tienda piden reiniciar. Nuevo `configuracion.py`, `pagina.py`, endpoints `/api/v1/config`, `ModelGateway.set_env`. Tests: core 409, server 42, puerta 841. Probado en la nube con navegador; **no probado en Windows ni con Meta/OpenRouter reales**. Ojo: con el túnel, `/config` queda visible desde internet (pide la clave de la app, con tope de intentos). Falta: pantalla de Configuración en la app Android (hoy solo web).
- 25 nov, hilo "Servidor en la PC": Raphael Empresas corre en la PC de Damián con Tailscale Funnel (`https://damian.tail9381ba.ts.net`, webhook `/webhook/meta`), en modo mock. Acceso directo "Raphael" en el escritorio (`2-entrega/c-despliegue/windows/acceso-directo.bat`). Se corrigió `arrancar.bat`, que fallaba con espacios en la ruta. Recorrido de punta a punta (mensaje, encargo, aprobación de la dueña) probado en la PC por reglas, sin IA. Falta: `OPENROUTER_API_KEY`, claves de Meta, clave de la app y perfil real de la clienta; Meta real no probado.
- 25 nov, hilo "Dejar Raphael listo para usar con solo claves": un solo arranque y un solo archivo de claves. Nuevo `entorno.py` en el servidor (lee `raphael.env`, `meta.env` y `tienda.env` de la carpeta de datos; chequeo de arranque que dice qué falta sin mostrar valores), acciones `chequear` (con `--real`) y `servir` que imprime el chequeo, `2-entrega/c-despliegue/windows/arrancar.bat` (Windows: chequear, clave, servir), `raphael.env.plantilla` y `2-entrega/c-despliegue/QUE-CARGAR.md`. Probado en la nube: servidor levantado, mensaje de clienta por el webhook (mock), respuesta por reglas y Secretaria; con clave de IA falsa, la dueña sale por OpenRouter con `data_collection=deny`. 7 tests nuevos (server 33, puerta 831, ruff limpio). **No probado:** `arrancar.bat` en Windows, Tailscale Funnel, OpenRouter ni Meta reales. Las respuestas a clientes siguen siendo solo por reglas (decisión de la brigada); la IA entra en la charla con la dueña, el ruteo y el reporte.
- 24 nov, hilo "Corregir docs y fijar test de imports": se corrigieron los SPEC del harness, del servidor y de cuentas y el README de Empresas (desvíos 1 a 5 del informe `log/17-revisor.md`). Nuevo `1-harness/b-codigo/tests/test_imports_codigo_real.py`: verifica que el orquestador, Empresas y el servidor no se importen entre sí (core pasa de 405 a 408 tests, puerta de 821 a 824, ruff limpio, corrida en la nube). Quedan fuera a propósito: `INTERVIEW.md` (PR #3) y la decisión sobre NVIDIA (otro hilo). El servidor de Empresas corre en la PC de Damián con un túnel hasta que haya VPS.

## Pendiente (en orden)
1. ~~Versionar `raphael\` con git~~ hecho (24 nov, repo local). Falta: el repo privado y el push los hace Damián.
2. ~~Correr los tests en la PC y arreglar la mudanza; puerta en `3-mando/b-herramientas/`~~ hecho (24 nov, `3-mando\b-herramientas\gate.bat`).
3. Cuentas y APIs: VPS Hetzner (CX33), DuckDNS, app de Meta con número de prueba (proveedor de IA ya elegido: OpenRouter).
4. Entrevista a la clienta (demo de Mi Tienda IA): **preguntas listas en `1-harness/c-brigadas/15-empresas/INTERVIEW.md`** (24 nov, con supuestos marcados y revisión de alcance de Tienda). Falta: que Damián las haga, anotar sus respuestas, cargar su perfil (`a-historia/perfil-clienta.borrador.yaml` → `perfil_a_instalacion.py`) y ajustar los módulos (INTERVIEW §10).
5. Montar Empresas en el VPS y probar la app en un teléfono.
6. Recién después, una brigada por vez.

## Decisiones vigentes
Ver `CONTEXT.md` sección 6. El plan P0 a P6 y el brief de Fable 5.2 (de JarvisRemote) son planes viejos: no se usan salvo que Damián lo pida.

## Riesgos
Ver `CONTEXT.md` sección 9. Además: respaldar la clave de firma de Android fuera de git.
