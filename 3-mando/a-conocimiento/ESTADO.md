# ESTADO de Raphael

Actualizado: 25 nov 2026 (integración de los PR 11 a 26). Fuente de verdad junto con `CONTEXT.md` (si se contradicen, manda `CONTEXT.md` y se corrige este archivo). La versión anterior (20 nov) está en `D:\Raphael Ultimate\_archivo\docs\ESTADO.md`.

## Dónde vive todo
Todo el trabajo está en `D:\Raphael Ultimate\raphael\`, repo único `damianzupel-commits/Raphael`, ordenado en árbol a/b/c (`1-harness`, `2-entrega`, `3-mando`; ver `README.md` de la raíz). Lo viejo (`nucleo\`, `brigadas\`, `registro\`, `obra\`) quedó en `D:\Raphael Ultimate\_archivo\` y no se usa más. Los logs de sesión van en `a-historia/log.md` de cada pieza.

## Estado por pieza
| Pieza | Estado (25 nov; PR = pull request de la tanda) |
| --- | --- |
| Harness (`1-harness/b-codigo`) | H1 a H8 hechas, contrato 2.1, **430 tests**. Nuevo (integración): `OrchestratorContext.publish` (solo `memoria.turno`), `OrchestratorContext.audit_entries`, la auditoría de tools guarda argumentos (sin secretos) y `conv_id`, `Context.action_level`. El test de imports cruzados descubre solo las brigadas |
| 00 Orquestador | 290 tests. Voz hablada enchufable (real local, simulada, apagada), salud, avisos si falta el modelo local; ahora publica `memoria.turno` y exporta el registro de tools. PR 12. Sin probar: voz real, Ollama/LM Studio, NVIDIA, Windows |
| 05 Seguridad | Portada 2.0.0: auditor, pentest activo (solo PC, aprobación por corrida), vigilancia defensiva. 62 tests. Sin probar contra nmap, ZAP, sqlmap ni OSV reales. PR 17 |
| 06 Antimalware | Portada 2.0.0: escaneo (YARA, ClamAV, VirusTotal opt-in), vigilancia, integridad y cuarentena. 83 tests (1 se saltea como root). Sin probar en Windows ni con ClamAV/VirusTotal/Sysmon reales. PR 21 |
| 07 Investigación | Portada 2.0.0: forense, Scout con fuente y fecha, ideas y prototipos, tendencias. 68 tests. Sin probar con Brave/SearXNG ni modelo local reales. PR 25 |
| 08 Geolocalización | Portada 1.0.0 (solo personal): IPs, cripto y 13 capas, fuentes reales y simuladas. 88 tests. Sin probar con internet ni claves reales. PR 16 |
| 09 Memoria · Cerebro | Portada 2.0.0: 4 cocineros, vault, embeddings real y simulado, solo local. 149 tests. Sin probar contra LM Studio/Ollama reales. PR 24 |
| 10 Ingesta | Portada 2.0.0: YouTube, web y arXiv al vault. 73 tests. Sin probar contra fuentes reales (`probar_real.py` en la PC). PR 20 |
| 11 Trading | Portada: señales, backtest y motor; ejecutar y cerrar siempre con aprobación (también en demo). **Broker elegido: Interactive Brokers** (adaptador `ibkr.py`, cuenta paper; pasos en `a-historia/ibkr-pasos.md`); simulado por defecto. Tests en la puerta (abajo). Sin probar contra IB real. PR 15 |
| 12 Operaciones | Portada: PC, celular y navegador, 39 tools y 7 acciones, simulada por defecto, solo modelo local. 96 tests. Sin probar: escritorio real en Windows, Playwright, celular real. PR 26 |
| 13 Autorreparación | Portada 2.0.0 (solo personal): proponer, aplicar y revertir con aprobación atada a la huella. 106 tests. Sin probar en Windows ni con IA real. PR 19 |
| 14 Contenido | Portada: video, Instagram, imagen, copys, campañas y analítica; real, simulado y sin clave. 54 tests. Sin probar contra Instagram, Meta Ads ni ComfyUI. PR 22 |
| 15 Empresas | Brigada nativa 2.0.0, **141 tests**. Cobros con Mercado Pago (real + simulado) y transferencia; la dueña confirma siempre (PR 14). API y canal de Meta; app Android 1.1.0 (APK compila, sin probar en teléfono). `INTERVIEW.md` sin respuestas de la clienta todavía |
| 16 Legales | Nueva, desde cero: documentos, cumplimiento, riesgos y archivo; ninguna acción firma ni envía. 54 tests. Plantillas no validadas por un abogado. PR 18 |
| 3 Servidor, app e instalador | **97 tests.** Raphael personal cliente-servidor (`raphael_personal_api`), cerebro mixto, instalador de Windows, celular por `tailscale serve`, `/webhook/mercadopago` (PR 23). Sin probar en Windows. App Android y panel todavía no apuntan a la API personal. Falta montar el VPS real |
| 4 Cuentas y APIs | Catálogo único de 13 cuentas, `chequear` y `probar` con adaptador real y simulado, 22 tests (PR 13). Endpoints y nombres de variables sin verificar. Pendiente: VPS Hetzner (sin medio de pago), DuckDNS, app de Meta, número de prueba |
| 17 Revisor | Segunda revisión de `main` y lista de control de 9 puntos (`log/17-revisor.md`, PR 11). Sus huecos de la puerta y de imports cruzados quedaron cerrados en esta integración |

**Lo que falta poner es una sola lista: `LIENZO-DAMIAN.md`.**

**Puerta del 25 nov (nube, Python 3.13, con los PR 11 a 26 mergeados): EN VERDE, 1872 tests**: core 430, orchestrator 290, business 141, server 97, seguridad 62, antimalware 83, investigación 68, geolocalización 88, memoria 149, ingesta 73, trading 59, operaciones 96, autorreparación 106, contenido 54, legales 54, cuentas 22; ruff limpio. `gate.py` ahora corre todas las suites. En la PC de Damián (Windows, 24 nov, antes de la tanda) eran 841; la tanda no se corrió todavía en Windows.

Histórico: tests en la PC de Damián (Windows, Python 3.12) después de la mudanza, 24 nov: core 409, orchestrator 266, business 124, server 42, ruff limpio (841 en verde). Puerta: `3-mando\b-herramientas\gate.bat`.

## Cambios recientes
- 25 nov, hilo "Integrar las 16 piezas": se integraron los PR 11 a 26 en una rama. `gate.py` suma una suite por brigada (05 a 14 y 16) y la de cuentas, y el test de imports cruzados descubre las brigadas solo. `modelos.personal.yaml`: local en `127.0.0.1` (Ollama y LM Studio), NVIDIA para el resto, `private` con los ids reales (`seguridad`, `investigacion`, `memoria`, `operaciones`) y overrides a local para Operaciones y Memoria; el `modelos.yaml` del harness (Empresas, OpenRouter) suma el proveedor local y los mismos ids privados. Cambios chicos en el harness pedidos por las piezas 00, 11 y 13. Test del panel aislado de las brigadas instaladas con pip. Nuevo `LIENZO-DAMIAN.md`.
- 25 nov, hilo "Servidor en la PC": desde la PC de Damián se entra a `/config` y a la API sin clave (`RAPHAEL_LOCAL_SIN_CLAVE=1` en el acceso directo); por el túnel o el celular se sigue pidiendo. Pendiente: en Windows falla un test de permisos 600 de `raphael.env`.
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
6. ~~Una brigada por vez~~ hecho el 25 nov: las 05 a 14 y 16 están construidas (PR 11 a 26). Lo que sigue es completar `LIENZO-DAMIAN.md` (claves, cuentas, carpetas) y probar cada pieza contra su servicio real en Windows.

## Decisiones vigentes
Ver `CONTEXT.md` sección 6. El plan P0 a P6 y el brief de Fable 5.2 (de JarvisRemote) son planes viejos: no se usan salvo que Damián lo pida.

## Riesgos
Ver `CONTEXT.md` sección 9. Además: respaldar la clave de firma de Android fuera de git. Del Revisor: el acceso sin clave desde la PC (`RAPHAEL_LOCAL_SIN_CLAVE=1`) deja que cualquier proceso local apruebe acciones irreversibles; decisión tuya pendiente.
