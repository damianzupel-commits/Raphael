# Registro · 0 · Mando

Decisiones y consolidación del estado.

## 24 nov 2026 · Resumen de cierre · traspaso a la estructura nueva
- Todo el trabajo pasó a `D:\Raphael Ultimate\raphael\` (monorepo: apps, packages, brigades, infra, tests, tools, docs, `_reference`). Lo anterior quedó archivado en `D:\Raphael Ultimate\_archivo\`.
- `.venv` y `.datos` del panel se movieron a `packages/core/`; el acceso directo "Raphael Harness v2" apunta a `packages/core/panel/abrir-panel.bat`.
- Rutas ajustadas en el código copiado (conftest del orquestador, de la brigada Empresas y de la API; `armar_paquete.py`; `regresion_empresas.py`; el panel acepta `brigades/` y ahora `CONTEXT.md` como raíz). Todo compila, pero NO se corrieron los tests (la VM tiene Python 3.10): falta correrlos en la PC.
- Cada chat debe trabajar solo en `raphael\`; las rutas viejas (`nucleo\`, `brigadas\`, `registro\`) ya no existen. Los logs de sesión van en `docs/log/<pieza>.md`.
