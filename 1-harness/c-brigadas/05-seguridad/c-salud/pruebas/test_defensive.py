"""Vigilancia defensiva: lógica pura de los chequeos y las sondas simuladas."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from raphael_seguridad.defensive import MockProbes, failed_login_alerts, run_watch, token_alerts

NOW = datetime(2026, 11, 25, 10, 0)


def _ev(n, mins_ago, src="1.2.3.4"):
    return [{"at": (NOW - timedelta(minutes=mins_ago)).isoformat(), "source": src}] * n


def test_logins_fallidos_umbral_y_ventana():
    assert failed_login_alerts(_ev(4, 1), NOW) == []
    a = failed_login_alerts(_ev(5, 1) + _ev(9, 60, "9.9.9.9"), NOW)
    assert [x.file for x in a] == ["1.2.3.4"] and a[0].severity == "medium"
    assert failed_login_alerts(_ev(15, 1), NOW)[0].severity == "high"


def test_tokens_por_vencer():
    out = token_alerts([{"name": "Meta", "expires": "2026-11-27"}, {"name": "Viejo", "expires": "2026-11-20"},
                        {"name": "Lejos", "expires": "2027-06-01"}, {"name": "Roto", "expires": "mañana"}], date(2026, 11, 25))
    assert {f.file: f.severity for f in out} == {"Meta": "high", "Viejo": "high"}
    assert "venció hace 5 días" in [f.message for f in out if f.file == "Viejo"][0]


def test_certificado_servicio_y_backups():
    cfg = {"tls_hosts": ["a.com", "b.com:8443", "c.com"], "services": ["http://x/health", "http://y/health"],
           "backups": ["/b1", "/b2", "/b3"]}
    p = MockProbes(tls={"a.com": 2, "b.com": 90}, up={"http://x/health": False}, backups={"/b1": 80.0, "/b2": 3.0})
    got = {(f.rule_id, f.file): f.severity for f in run_watch(cfg, p, NOW, [])}
    assert got == {("tls-por-vencer", "a.com"): "high", ("tls-ilegible", "c.com"): "high",
                   ("servicio-caido", "http://x/health"): "critical", ("backup-viejo", "/b1"): "medium",
                   ("backup-ausente", "/b3"): "high"}
    assert all(f.simulated for f in run_watch(cfg, p, NOW, []))


def test_sin_config_no_mira_nada_ni_inventa():
    assert run_watch({}, MockProbes(), NOW, []) == []
