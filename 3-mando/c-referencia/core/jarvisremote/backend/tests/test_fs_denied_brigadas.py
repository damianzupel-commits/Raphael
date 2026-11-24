"""El almacén de brigadas creadas está denegado por default para las tools fs_* (defensa en profundidad del gate)."""
from pathlib import Path

import pytest

from app.config import settings
from app.tools import filesystem


def _store() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "brigades_creadas"


def test_store_in_denied_paths_by_default():
    denied = {Path(p).resolve() for p in settings.fs_denied_paths}
    assert _store().resolve() in denied


@pytest.mark.parametrize("name", ["radar.json", "_claves/clave.bin", "../brigades_creadas/x.json"])
def test_fs_resolve_rejects_store(name):
    with pytest.raises(PermissionError):
        filesystem._resolve(str(_store() / name))
