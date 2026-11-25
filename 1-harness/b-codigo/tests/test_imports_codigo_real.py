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
# Las brigadas (orquestador incluido) se descubren solas: cada carpeta `c-brigadas/<NN>/b-codigo/src/<paquete>` es una,
# así una brigada nueva queda cubierta sin tocar este archivo.
BRIGADAS = {
    paquete.name: paquete
    for paquete in sorted((RAIZ / "1-harness/c-brigadas").glob("*/b-codigo/src/*"))
    if (paquete / "__init__.py").is_file()
}
PAQUETES.update(BRIGADAS)
# paquete -> paquetes que NO puede importar
PROHIBIDOS = {
    "raphael_orchestrator": {"raphael_empresas_api"},
    "raphael_empresas": {"raphael_empresas_api"},
    "raphael_empresas_api": {"raphael_orchestrator"},
}
for _nombre in BRIGADAS:
    otras = set(BRIGADAS) - {_nombre}
    PROHIBIDOS[_nombre] = {*PROHIBIDOS.get(_nombre, set()), *otras, "raphael_empresas_api", "raphael_personal_api"}


def test_se_descubrieron_las_brigadas():
    # 00 y 05 a 16: si un cambio de carpetas deja esto vacío, el test de abajo no estaría probando nada
    assert len(BRIGADAS) >= 13, sorted(BRIGADAS)


@pytest.mark.parametrize("nombre", sorted(PAQUETES))
def test_sin_imports_cruzados_en_codigo_real(nombre):
    carpeta = PAQUETES[nombre]
    assert any(carpeta.rglob("*.py")), f"no encuentro código en {carpeta}: el test no estaría probando nada"
    assert find_cross_imports(carpeta, PROHIBIDOS[nombre]) == []
