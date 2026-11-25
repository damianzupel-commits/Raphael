# Orquestador

Rama `1-harness/c-brigadas/00-orquestador/` de Raphael. Va con las brigadas porque también se para sobre el harness, pero no es una brigada más: es el único que habla con la persona y el que reparte el trabajo entre las demás.

## Objetivo
Recibir cada pedido, decidir qué brigada lo hace, repartir el trabajo (DAG validado por código), confirmar con un "sí" explícito lo que tiene efecto y devolver la respuesta en la voz de Raphael. En la instalación de la clienta funciona en modo `secretary` (la Secretaria habla con la dueña); en Raphael personal, en modo `master`.

## Estado
O1 a O5 hechas: config, voz con verificador, memoria de la charla, ruteo, watchdog, mando, DAG, trabajo conjunto, confirmación, Secretaria, modos `master` y `secretary`, avisos proactivos y borradores. Sumado el 25 nov (modo lienzo en blanco): voz hablada enchufable (real local y simulada), chequeo de salud, aviso de IA faltante y de modelo local apagado, plantillas de claves. 282 tests en verde.

## Estructura de esta rama (patrón a/b/c)
- `a-historia/`: `SPEC.md`, `PORTADO.md` (qué se trajo de JarvisRemote y de Empresas), `diseno.md` y `log.md`.
- `b-codigo/`: `pyproject.toml`, `src/raphael_orchestrator/`, `orquestador.env.plantilla` (lo que carga Damián), `orquestador.config.ejemplo.yaml` y `modelos.personal.ejemplo.yaml` (mixto: sensible local, resto NVIDIA). `b-codigo/README.md` es el README del código, con la tabla de tandas.
- `c-salud/`: `pruebas/` (266 tests), `monitoreo/` y `mantenimiento/`.

## Cómo se trabaja en esta rama
1. Leé `CONTEXT.md` en la raíz y este README; después `a-historia/log.md`.
2. No importa ninguna brigada: todo lo que sabe de ellas sale del catálogo del harness.
3. Antes de cerrar: `3-mando\b-herramientas\gate.bat` en verde y un "Resumen de cierre" en `a-historia/log.md`.

## Lo que el orquestador necesita de Damián (todo enchufable, nada obligatorio)
Ver `b-codigo/orquestador.env.plantilla`. Resumen: claves de IA (`NVIDIA_API_KEY` para el resto, `OPENROUTER_API_KEY` para Empresas), un modelo local prendido (Ollama o LM Studio) para lo sensible y, si quiere voz hablada, `faster-whisper`, `piper-tts` y la voz es-AR. Sin nada de eso responde por reglas y plantilla y **lo avisa**; lo sensible nunca se manda a la nube para compensar.
Esta pieza no es una brigada: no tiene `manifest.yaml` ni cocineros. Se monta por `installation.orchestrator` (entry point `raphael`), así que "su manifiesto" es la config (`orquestador.config.ejemplo.yaml`) y su salud es `raphael_orchestrator.health.report`.
