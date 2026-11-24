"""Imports cruzados sobre el código real del repo (no sobre paquetes de juguete).

`test_ast_imports.py` prueba el detector. Este test lo corre sobre el orquestador, Empresas y el servidor.
Regla (CONTEXT §3): nadie se habla directo; todo pasa por el harness y el orquestador.
El servidor sí puede importar `raphael_empresas` (su arranque, `boot.start`): es la entrega de esa brigada.
"""

from pathlib import Path

import pytest

from raphael_core.testing import find_cross_imports

RAIZ = Path(__file__).resolve().parents[3]   # raphael/
PAQUETES = {
    "raphael_orchestrator": RAIZ / "1-harness/c-brigadas/00-orquestador/b-codigo/src/raphael_orchestrator",
    "raphael_empresas": RAIZ / "1-harness/c-brigadas/15-empresas/b-codigo/src/raphael_empresas",
    "raphael_empresas_api": RAIZ / "2-entrega/b-codigo/servidor/api/src/raphael_empresas_api",
}
# paquete -> paquetes que NO puede importar
PROHIBIDOS = {
    "raphael_orchestrator": {"raphael_empresas", "raphael_empresas_api"},
    "raphael_empresas": {"raphael_orchestrator", "raphael_empresas_api"},
    "raphael_empresas_api": {"raphael_orchestrator"},
}


@pytest.mark.parametrize("nombre", sorted(PAQUETES))
def test_sin_imports_cruzados_en_codigo_real(nombre):
    carpeta = PAQUETES[nombre]
    assert any(carpeta.rglob("*.py")), f"no encuentro código en {carpeta}: el test no estaría probando nada"
    assert find_cross_imports(carpeta, PROHIBIDOS[nombre]) == []
