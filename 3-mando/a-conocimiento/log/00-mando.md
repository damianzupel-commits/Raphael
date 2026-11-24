# Registro · 0 · Mando

Decisiones y consolidación del estado.

## 24 nov 2026 · Resumen de cierre · traspaso a la estructura nueva
- Todo el trabajo pasó a `D:\Raphael Ultimate\raphael\` (monorepo: apps, packages, brigades, infra, tests, tools, docs, `_reference`; el 24 nov a la tarde pasó al árbol a/b/c). Lo anterior quedó archivado en `D:\Raphael Ultimate\_archivo\`.
- `.venv` y `.datos` del panel se movieron a `1-harness/b-codigo/`; el acceso directo "Raphael Harness v2" apunta a `1-harness/b-codigo/panel/abrir-panel.bat`.
- Rutas ajustadas en el código copiado (conftest del orquestador, de la brigada Empresas y de la API; `armar_paquete.py`; `regresion_empresas.py`; el panel acepta `1-harness/c-brigadas/` y ahora `CONTEXT.md` como raíz). Todo compila, pero NO se corrieron los tests (la VM tiene Python 3.10): falta correrlos en la PC.
- Cada chat debe trabajar solo en `raphael\`; las rutas viejas (`nucleo\`, `brigadas\`, `registro\`) ya no existen. Los logs de sesión van en `a-historia/log.md` de cada pieza.

## 24 nov 2026 · Resumen de cierre · git, tests en la PC y puerta
- `raphael\` ya es repo git local (rama `main`, sin remoto); `.gitignore` cubre `.env*`, claves, `.venv`, `.datos`, `.data`, bases, APK y `*.egg-info`. Revisión de `3-mando\c-referencia\`: sin secretos (las plantillas `.env` tienen los valores vacíos).
- Tests en Windows con Python 3.12 (`.venv` nuevo en la raíz): core 405, orchestrator 266, business 124, server 26; ruff limpio. Total 821 en verde.
- Arreglos de la mudanza: ruta de `clienta.installation.yaml` (ahora en `2-entrega/c-despliegue/instalacion-clienta/`), test del panel para brigadas sin número, una línea larga, y el `bash -n` del kit del VPS usa el bash de Git en Windows (no el de WSL).
- Puerta nueva: `3-mando\b-herramientas\gate.bat` (o `python 3-mando\b-herramientas\gate.py`), sale 0 en verde y 2 en rojo.
- El panel abre con el `.venv` viejo de `1-harness/b-codigo/` (no necesita reinstalarse).
