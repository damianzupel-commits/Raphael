"""Ideas, evaluación, specs, prototipos y el espacio aislado."""

import json
import os
import sys

import pytest
from kit import make_env

from raphael_investigacion import ideas
from raphael_investigacion.casefile import CaseError
from raphael_investigacion.sandbox import review_code, run_python


def test_sin_modelo_no_inventa_ideas():
    env = make_env()
    r = ideas.generate(env, "- app de turnos\n- bot de stock")
    assert [i["title"] for i in r["ideas"]] == ["app de turnos", "bot de stock"] and not r["modelo"] and "no invento" in r["aviso"]


def test_con_modelo_marca_origen():
    env = make_env(ask=lambda p, m: json.dumps([{"title": "Alertas de precios", "problem": "p", "pitch": "q"}]))
    r = ideas.generate(env, "comercio")
    assert r["modelo"] and r["ideas"][0]["origin"] == "modelo"


def test_evaluar_es_una_cuenta():
    env = make_env()
    i = ideas.add_idea(env, "Idea buena")
    e = ideas.evaluate(env, i["id"], {"impacto": 5, "encaje": 5, "esfuerzo": 1, "riesgo": 1})
    assert e["puntaje"] == 100 and e["status"] == "evaluada"
    j = ideas.add_idea(env, "Idea mala")
    assert ideas.evaluate(env, j["id"], {"impacto": 1, "encaje": 1, "esfuerzo": 5, "riesgo": 5})["puntaje"] == 0
    assert [x["id"] for x in ideas.ranking(env)] == [i["id"], j["id"]]
    with pytest.raises(CaseError, match="entre 1 y 5"):
        ideas.evaluate(env, i["id"], {"impacto": 9, "encaje": 1, "esfuerzo": 1, "riesgo": 1})
    with pytest.raises(CaseError, match="pasá los puntajes"):
        ideas.evaluate(env, i["id"])


def test_puntajes_sugeridos_por_modelo_quedan_marcados():
    env = make_env(ask=lambda p, m: '{"impacto":4,"encaje":3,"esfuerzo":2,"riesgo":2}')
    i = ideas.add_idea(env, "x")
    assert "sugerido" in ideas.evaluate(env, i["id"])["scores_by"]


def test_spec_marca_lo_que_falta():
    env = make_env()
    i = ideas.add_idea(env, "Bot", problem="Se pierden turnos")
    s = ideas.write_spec(env, i["id"])
    assert "Se pierden turnos" in s["text"] and "por definir" in s["text"] and ideas.get(env, i["id"])["status"] == "con spec"


def test_revision_estatica():
    assert review_code("print(1)") == []
    bad = review_code("import socket\nfrom subprocess import run\nimport os\nos.system('x')\neval('1')")
    assert any("socket" in b for b in bad) and any("subprocess" in b for b in bad) and any("system" in b for b in bad)
    assert any("eval" in b for b in bad) and review_code("def (")[0].startswith("no compila")


def test_prototipo_guarda_sin_correr_y_corre_aislado():
    env = make_env()
    i = ideas.add_idea(env, "p")
    p = ideas.save_prototype(env, i["id"], "import os\nprint(sorted(os.environ))\nprint(os.getcwd())\nopen('f.txt','w').write('x')")
    assert p["runs"] == 0 and p["review"] == []
    r = ideas.run_prototype(env, p["id"])
    assert r["ran"] and r["exit_code"] == 0 and "raphael-proto-" in r["stdout"]
    assert "HOME" not in r["stdout"] and "PATH" not in r["stdout"]          # entorno vacío
    assert not os.path.exists("f.txt")


def test_prototipo_con_problemas_no_corre():
    env = make_env()
    i = ideas.add_idea(env, "p")
    p = ideas.save_prototype(env, i["id"], "import subprocess\nsubprocess.run(['ls'])")
    assert p["review"]
    r = ideas.run_prototype(env, p["id"])
    assert not r["ran"] and r["problems"]


def test_timeout_y_salida_acotada():
    r = run_python("while True: pass", timeout=1)
    assert r["ran"] and r["timed_out"]
    r = run_python("print('x' * 100000)")
    assert len(r["stdout"]) <= 20000


@pytest.mark.skipif(os.name != "posix", reason="topes de memoria solo en posix")
def test_tope_de_memoria():
    r = run_python("x = bytearray(900 * 1024 * 1024)\nprint('ok')", memory_mb=128)
    assert r["exit_code"] != 0 and "ok" not in r["stdout"]


def test_usa_el_interprete_actual():
    assert run_python("import sys\nprint(sys.version_info[0])")["stdout"].strip() == str(sys.version_info[0])
