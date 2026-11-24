# Mando · b-herramientas

## Puerta del repo: `gate.bat` / `gate.py`
Corre las cuatro suites, cada una en su carpeta, y `ruff check` sobre `1-harness` y `2-entrega/b-codigo/servidor`. Imprime una línea por suite y el total. Sale con **0** si todo pasa y **2** si algo falla.

| Suite | Carpeta |
|---|---|
| core | `1-harness/b-codigo` |
| orchestrator | `1-harness/c-brigadas/00-orquestador/c-salud/pruebas` |
| business | `1-harness/c-brigadas/15-empresas/c-salud/pruebas` |
| server | `2-entrega/b-codigo/servidor/api` |

Uso, desde la carpeta `raphael`:
```
3-mando\b-herramientas\gate.bat
3-mando\b-herramientas\gate.bat --solo core business
```
Usa `.venv\Scripts\python.exe` de la raíz si existe. Para armarlo o rearmarlo después de mover carpetas (Python 3.12):
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e "1-harness/b-codigo[dev]" -e "1-harness/c-brigadas/00-orquestador/b-codigo[dev]" -e "1-harness/c-brigadas/15-empresas/b-codigo[dev]" -e "2-entrega/b-codigo/servidor/api[dev]" pytest ruff
```
Cuando una brigada nueva tenga tests, se suma una línea a `SUITES` en `gate.py`.

## Pruebas que cruzan piezas
- `pruebas-contrato/` y `pruebas-e2e/` (ver su README).
- Regresión de Empresas 0.4 sobre el harness v2 (74 tests): `1-harness/b-codigo/scripts/regresion_empresas.py`.
