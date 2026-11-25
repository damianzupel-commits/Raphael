"""Introspección: patrones de falla con evidencia, reflexiones que no se borran, sin tocar código."""

import json
from datetime import datetime, timedelta

import pytest
from kit import System, answers, make_project
from raphael_core import ActionError

from raphael_selfrepair import analyzer


def w(path="a.py", sha="h1", ok=True, conv="c1", error="", tool="fs_write_file", n=0):
    return {"timestamp": f"2026-11-25T10:00:{n:02d}", "conversation_id": conv, "tool": tool, "ok": ok, "error": error,
            "arguments": {"path": path, "content_sha256": sha}}


def test_reescritura_identica():
    f = analyzer.analyze([w(n=i) for i in range(4)])
    assert [x["pattern"] for x in f] == ["reescritura_identica_repetida"]
    assert len(f[0]["evidence"]) == 4 and "4 veces" in f[0]["summary"]


def test_dos_repeticiones_no_son_patron():
    assert analyzer.analyze([w(n=0), w(n=1)]) == []


def test_contenido_distinto_corta_la_corrida():
    es = [w(sha="a", n=0), w(sha="a", n=1), w(sha="b", n=2), w(sha="b", n=3)]
    assert analyzer.analyze(es) == []


def test_archivo_bloqueado_y_abandonado():
    es = [w("x.java", ok=False, error="bloqueado por el guardarraíl", n=0), w("otro.py", n=1)]
    f = analyzer.analyze(es)
    assert [x["pattern"] for x in f] == ["archivo_bloqueado_abandonado"] and f[0]["path"] == "x.java"


def test_bloqueado_y_reintentado_no_es_hallazgo():
    assert analyzer.analyze([w("x.java", ok=False, n=0), w("x.java", ok=True, n=1)]) == []


def test_error_repetido():
    es = [w(tool="http_get", ok=False, error="timeout", sha=None, n=i) for i in range(3)]
    f = analyzer.analyze(es)
    assert [x["pattern"] for x in f] == ["error_repetido"] and "timeout" in f[0]["summary"]


def test_entradas_sin_conversacion_se_ignoran():
    assert analyzer.analyze([{**w(n=i), "conversation_id": None} for i in range(5)]) == []


def test_ids_estables():
    a = analyzer.analyze([w(n=i) for i in range(3)])[0]["id"]
    b = analyzer.analyze([w(n=i) for i in range(5)])[0]["id"]
    assert a == b


def test_read_log_saltea_basura(tmp_path):
    p = tmp_path / "audit.jsonl"
    p.write_text("\n".join([json.dumps(w(n=0)), "{roto", "", "[1,2]", json.dumps(w(n=1))]))
    assert len(analyzer.read_log(p)) == 2
    assert analyzer.read_log(tmp_path / "no-existe.jsonl") == []


def test_analizar_guarda_hallazgos_sin_duplicar_y_publica(tmp_path):
    s = System(make_project(tmp_path))
    es = [w(n=i) for i in range(3)]
    r = s.cmd("introspeccion", "analizar", {"entries": es})
    assert r["nuevos"] == 1
    assert s.cmd("introspeccion", "analizar", {"entries": es})["nuevos"] == 0
    assert len(s.cmd("introspeccion", "hallazgos", {})) == 1
    assert len(s.events("autodiagnostico.hallazgo")) == 1


def test_analizar_lee_el_registro_configurado(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("\n".join(json.dumps(w(n=i)) for i in range(3)))
    s = System(make_project(tmp_path / "p"), {"audit_log_path": str(log)})
    assert s.cmd("introspeccion", "analizar", {})["nuevos"] == 1


def test_analizar_sin_registro_dice_que_falta(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError, match="audit_log_path"):
        s.cmd("introspeccion", "analizar", {})
    with pytest.raises(ActionError):
        s.cmd("introspeccion", "analizar", {"entries": "no es lista"})


def test_tick_analiza_solo_cada_tanto(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("\n".join(json.dumps(w(n=i)) for i in range(3)))
    s = System(make_project(tmp_path / "p"), {"audit_log_path": str(log), "analyze_every_minutes": 30})
    t0 = datetime(2026, 11, 25, 12, 0)
    s.tick(t0)
    assert len(s.cmd("introspeccion", "hallazgos", {})) == 1
    log.write_text(log.read_text() + "\n" + "\n".join(json.dumps(w("z.py", "q", conv="c2", n=i)) for i in range(3)))
    s.tick(t0 + timedelta(minutes=10))
    assert len(s.cmd("introspeccion", "hallazgos", {})) == 1               # todavía no toca
    s.tick(t0 + timedelta(minutes=31))
    assert len(s.cmd("introspeccion", "hallazgos", {})) == 2


def test_tick_apagado_por_defecto(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("\n".join(json.dumps(w(n=i)) for i in range(3)))
    s = System(make_project(tmp_path / "p"), {"audit_log_path": str(log)})
    s.tick(datetime(2026, 11, 25, 12, 0))
    assert s.cmd("introspeccion", "hallazgos", {}) == []


def test_explicar_sin_modelo_lo_dice(tmp_path):
    s = System(make_project(tmp_path))
    r = s.cmd("introspeccion", "analizar", {"entries": [w(n=i) for i in range(3)], "explicar": True})
    assert "Sin modelo" in r["explicacion"]


def test_explicar_con_modelo(tmp_path):
    s = System(make_project(tmp_path), transport=answers(["Se trabó repitiendo la misma escritura."]))
    r = s.cmd("introspeccion", "analizar", {"entries": [w(n=i) for i in range(3)], "explicar": True})
    assert r["explicacion"].startswith("Se trabó")


def test_analizar_nunca_toca_el_proyecto(tmp_path):
    root = make_project(tmp_path)
    antes = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    s = System(root)
    s.cmd("introspeccion", "analizar", {"entries": [w(n=i) for i in range(5)]})
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == antes


def test_reflexiones_guardar_buscar_retractar(tmp_path):
    s = System(make_project(tmp_path))
    r1 = s.cmd("introspeccion", "reflexionar", {"insight": "Damián prefiere diffs chicos", "tipo": "preferencia_usuario",
                                               "contexto": "codigo"})
    s.cmd("introspeccion", "reflexionar", {"insight": "los diffs grandes se rechazan"})
    q = s.cmd("introspeccion", "reflexiones", {"topic": "diffs"})
    assert len(q["results"]) == 2
    por_tipo = s.cmd("introspeccion", "reflexiones", {"topic": "diffs", "tipo": "preferencia_usuario"})["results"]
    assert [r["n"] for r in por_tipo] == [r1["n"]]
    s.cmd("introspeccion", "retractar_reflexion", {"n": r1["n"]})
    assert len(s.cmd("introspeccion", "reflexiones", {"topic": "diffs"})["results"]) == 1
    assert len(s.cmd("introspeccion", "reflexiones", {"topic": "diffs", "vigente": False})["results"]) == 1
    assert len(s.cmd("introspeccion", "reflexiones", {"topic": "diffs", "vigente": None})["results"]) == 2


def test_reflexion_invalida(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError):
        s.cmd("introspeccion", "reflexionar", {"insight": ""})
    with pytest.raises(ActionError, match="tipo"):
        s.cmd("introspeccion", "reflexionar", {"insight": "algo", "tipo": "inventado"})
    with pytest.raises(ActionError):
        s.cmd("introspeccion", "retractar_reflexion", {"n": 99})


def test_autoconocimiento_es_honesto(tmp_path):
    r = System(make_project(tmp_path)).cmd("introspeccion", "autoconocimiento", {})
    assert r["modelo"].startswith("sin modelo") and r["limites_honestos"] and r["lineas_rojas"]
