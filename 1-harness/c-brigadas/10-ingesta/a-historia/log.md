# Registro · 10-ingesta · Ingesta

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 2026-11-25 · Portar Ingesta al harness v2
**Resumen de cierre**
- Se portó la brigada (hilo "Construir pieza 10 Ingesta"): `ingesta` 2.0.0 con cocineros YouTube, Web y arXiv, 10 acciones con nivel, 5 comandos de lectura, `health`/`setup`, y tests en `c-salud/pruebas/` (73 en verde, ruff limpio, suite de contrato en personal y cloud).
- Adaptadores enchufables: real y simulado por fuente (`modo: real|simulado`); los tests corren con el simulado y sin clave. Sin modelo el resumen sale por reglas y la nota lo marca. El vault es una carpeta Markdown (`RAPHAEL_VAULT_DIR`); sin carpeta, la nota queda en el almacén y viaja en el evento `nota.ingerida`.
- Decisiones: ingerir es automático (lee público, escribe notas reversibles); `vigilar` y `borrar_nota` piden aprobación; solo la persona dueña dispara ingestas; una acción = un ítem y las listas se encolan (el harness corta a los 60 s); solo URLs públicas (SSRF); lo de terceros es dato; lo que falla sin arreglo no se reintenta solo.
- Cambios contra el código viejo: el vigilante de playlist pasó de tarea suelta a `tick` + acción `vigilar`; el LLM y el vault ya no son los de JarvisRemote; la relevancia sale en la misma llamada del resumen y sigue siendo solo etiqueta; `web_ingest.py` no vino en la referencia y se escribió de nuevo.
- Quedó: probar los reales en la PC (`probar_real.py`, con `--video` y `--lista`); sumar la suite a `gate.py`; pendiente para Memoria: tomar `nota.ingerida` (lleva el contenido de la nota) y definir si el vault de Ingesta es el suyo; la playlist por defecto "Info para Jarvis" del código viejo no se portó (la URL no estaba completa): se vigila con `vigilar`.

## 2026-11-25 · hilo "Dar jefe a las 9 brigadas restantes"
**Resumen de cierre.** Ingesta ahora tiene jefe con tres efímeros (YouTube, Web, arXiv), así que el orquestador le puede derivar pedidos. Nueve tools nuevas (`ingesta_*`, registradas en `validate`), todas sin efecto: cuatro leen contenido de afuera (página, video, paper, búsqueda en arXiv) y NO guardan nada; cinco leen el estado (notas, cola, fallidos, vigiladas, estado). Guardar la nota en el vault y publicar `nota.ingerida` (que escucha Memoria) sigue siendo del cocinero de la fuente cuando la persona lo pide: una tool no puede publicar eventos. No son privados (contenido público). 78 tests, ruff limpio.
