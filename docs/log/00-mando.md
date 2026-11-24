# Registro · 0 · Mando

Decisiones y consolidación del estado.

## 24 nov 2026 · Resumen de cierre · traspaso a la estructura nueva
- Todo el trabajo pasó a `D:\Raphael Ultimate\raphael\` (monorepo: apps, packages, brigades, infra, tests, tools, docs, `_reference`). Lo anterior quedó archivado en `D:\Raphael Ultimate\_archivo\`.
- `.venv` y `.datos` del panel se movieron a `packages/core/`; el acceso directo "Raphael Harness v2" apunta a `packages/core/panel/abrir-panel.bat`.
- Rutas ajustadas en el código copiado (conftest del orquestador, de la brigada Empresas y de la API; `armar_paquete.py`; `regresion_empresas.py`; el panel acepta `brigades/` y ahora `CONTEXT.md` como raíz). Todo compila, pero NO se corrieron los tests (la VM tiene Python 3.10): falta correrlos en la PC.
- Cada chat debe trabajar solo en `raphael\`; las rutas viejas (`nucleo\`, `brigadas\`, `registro\`) ya no existen. Los logs de sesión van en `docs/log/<pieza>.md`.

## 24 nov 2026 · Resumen de cierre · git, tests en la PC y puerta
- `raphael\` ya es repo git local (rama `main`, sin remoto); `.gitignore` cubre `.env*`, claves, `.venv`, `.datos`, `.data`, bases, APK y `*.egg-info`. Revisión de `_reference\`: sin secretos (las plantillas `.env` tienen los valores vacíos).
- Tests en Windows con Python 3.12 (`.venv` nuevo en la raíz): core 405, orchestrator 266, business 124, server 26; ruff limpio. Total 821 en verde.
- Arreglos de la mudanza: ruta de `clienta.installation.yaml` (ahora en `infra/client-install/`), test del panel para brigadas sin número, una línea larga, y el `bash -n` del kit del VPS usa el bash de Git en Windows (no el de WSL).
- Puerta nueva: `tools\gate.bat` (o `python tools\gate.py`), sale 0 en verde y 2 en rojo.
- El panel abre con el `.venv` viejo de `packages/core/` (no necesita reinstalarse).
