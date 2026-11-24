# Orquestador

Rama `1-harness/c-brigadas/00-orquestador/` de Raphael. Va con las brigadas porque también se para sobre el harness, pero no es una brigada más: es el único que habla con la persona y el que reparte el trabajo entre las demás.

## Objetivo
Recibir cada pedido, decidir qué brigada lo hace, repartir el trabajo (DAG validado por código), confirmar con un "sí" explícito lo que tiene efecto y devolver la respuesta en la voz de Raphael. En la instalación de la clienta funciona en modo `secretary` (la Secretaria habla con la dueña); en Raphael personal, en modo `master`.

## Estado
O1 a O5 hechas: config, voz con verificador, memoria de la charla, ruteo, watchdog, mando, DAG, trabajo conjunto, confirmación, Secretaria, modos `master` y `secretary`, avisos proactivos y borradores. 266 tests en verde (24 nov 2026, Windows y nube).

## Estructura de esta rama (patrón a/b/c)
- `a-historia/`: `SPEC.md`, `PORTADO.md` (qué se trajo de JarvisRemote y de Empresas), `diseno.md` y `log.md`.
- `b-codigo/`: `pyproject.toml` y `src/raphael_orchestrator/`. `b-codigo/README.md` es el README del código, con la tabla de tandas.
- `c-salud/`: `pruebas/` (266 tests), `monitoreo/` y `mantenimiento/`.

## Cómo se trabaja en esta rama
1. Leé `CONTEXT.md` en la raíz y este README; después `a-historia/log.md`.
2. No importa ninguna brigada: todo lo que sabe de ellas sale del catálogo del harness.
3. Antes de cerrar: `3-mando\b-herramientas\gate.bat` en verde y un "Resumen de cierre" en `a-historia/log.md`.
