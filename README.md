# raphael/

Monorepo de Raphael personal y Raphael Empresas. **Este es el único lugar de trabajo.** Empezá por `CONTEXT.md`.

## Qué hay acá
- `CONTEXT.md`: mapa, reglas, decisiones y estado de todo el proyecto.
- `apps/`, `packages/`, `brigades/`, `infra/`, `tests/`, `tools/`, `docs/`: la estructura de trabajo. Cada rama tiene su README.
- `_reference/`: código existente de JarvisRemote y de los repos viejos de Empresas, de solo lectura, de donde se portan las brigadas.
- `.data/` y `packages/core/.datos/`: datos locales (bases, chats, claves). Fuera de git; no se leen ni se suben.

## Historia
El 24 nov 2026 se pasó todo a esta estructura. Lo anterior (carpetas por pieza `nucleo\` y `brigadas\`, registros y trabajo en curso) quedó archivado en `D:\Raphael Ultimate\_archivo\` y no se usa más. Si algo falta, se busca ahí.

## Panel
Acceso directo "Raphael Harness v2" del escritorio: abre `packages/core/panel/abrir-panel.bat`. El entorno (`.venv`) y los datos (`.datos`) viven en `packages/core/`.
