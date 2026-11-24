# tools/

Scripts del proyecto y las puertas de fase (`puerta-fase-N.sh`: corren los tests y terminan con código 0 si pasan o 2 si fallan; no se pasa a la fase siguiente hasta que terminen en 0).

## Puerta del monorepo: `gate.py` / `gate.bat`

Corre las cuatro suites, cada una en su carpeta, y `ruff check` sobre `packages`, `brigades/business` y `apps/server`. Imprime una línea por suite (passed / failed / tiempo) y el total. Sale con **0** si todo pasa y **2** si algo falla.

| Suite | Carpeta |
|---|---|
| core | `packages/core` |
| orchestrator | `packages/orchestrator` |
| business | `brigades/business` |
| server | `apps/server/api` |

Uso, desde `raphael\`:

```
tools\gate.bat
tools\gate.bat --solo core business
python tools\gate.py --python C:\ruta\python.exe
```

Usa `.venv\Scripts\python.exe` de la raíz si existe. Para armarlo (Python 3.12):

```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e "packages/core[dev]" -e "packages/orchestrator[dev]" -e "brigades/business[dev]" -e "apps/server/api[dev]" pytest ruff
```

La puerta de la brigada sola sigue siendo `brigades/business/scripts/puerta.py`.
