# tests/

Pruebas que cruzan piezas. Las de cada pieza viven en su propia carpeta (`packages/*/tests`, `brigades/*/tests`).

- `contract/`: la suite de contrato del harness aplicada a todas las brigadas (manifiesto válido, healthcheck, montar y desmontar sin romper nada, ningún import de otra brigada).
- `e2e/`: flujos de punta a punta (pedido de la persona -> orquestador -> brigada -> aprobación -> resultado).
- Regresión de Empresas sobre el harness v2: `packages/core/scripts/regresion_empresas.py` (74 tests).
