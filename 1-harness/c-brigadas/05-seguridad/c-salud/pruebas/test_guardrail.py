"""El guardrail del pentest: rechazo duro, lista a mano de Damián, DNS rebinding y nada que escriba la lista."""

from __future__ import annotations

import inspect

import pytest

from raphael_seguridad import guardrail
from raphael_seguridad.guardrail import TargetNotAuthorized, authorize


@pytest.mark.parametrize("t", ["192.168.1.10", "10.0.0.0/8", "127.0.0.1", "100.64.3.4", "http://192.168.0.5:8080/x", "::1"])
def test_alcance_por_defecto(t):
    assert authorize(t)


@pytest.mark.parametrize("t", ["8.8.8.8", "203.0.113.10", "192.168.0.0/8", "0.0.0.0/0", "", "10.0.0.1; rm -rf /", "a b", "10.0.0.1\0"])
def test_fuera_de_alcance_o_basura(t):
    with pytest.raises(TargetNotAuthorized):
        authorize(t, resolver=lambda h: (_ for _ in ()).throw(OSError("no resuelve")))


def test_la_lista_de_damian_amplia(tmp_path):
    f = tmp_path / "authorized_targets.yaml"
    f.write_text("targets:\n  - {target: '203.0.113.0/28', label: vm}\n  - {target: basura}\n")
    assert authorize("203.0.113.10", f) == "203.0.113.10"
    with pytest.raises(TargetNotAuthorized):
        authorize("203.0.113.0/24", f)      # el CIDR se valida entero


def test_archivo_roto_o_ausente_no_abre_el_alcance(tmp_path):
    bad = tmp_path / "x.yaml"
    bad.write_text("targets: [: :")
    for f in (bad, tmp_path / "no-existe.yaml", None):
        with pytest.raises(TargetNotAuthorized):
            authorize("8.8.8.8", f)


def test_hostname_devuelve_la_ip_ya_validada_y_resuelve_una_vez():
    calls = []

    def resolver(h):
        calls.append(h)
        return "192.168.1.50" if len(calls) == 1 else "8.8.8.8"   # rebinding: la segunda vez apuntaría afuera

    assert authorize("lab.local", resolver=resolver) == "192.168.1.50" and calls == ["lab.local"]
    with pytest.raises(TargetNotAuthorized):
        authorize("malo.example", resolver=lambda h: "8.8.8.8")


def test_el_modulo_solo_lee_la_lista(tmp_path):
    src = inspect.getsource(guardrail)
    assert ".write" not in src and "open(" not in src and "dump(" not in src
    f = tmp_path / "t.yaml"
    f.write_text("targets: []\n")
    before = f.read_bytes()
    with pytest.raises(TargetNotAuthorized):
        authorize("8.8.8.8", f)
    assert f.read_bytes() == before
