"""La instalación de la clienta de punta a punta. Portados de `raphael-harness/tests/test_integracion.py` (3) más el
conversor del perfil 0.4 y el arranque que usa el servidor."""

from pathlib import Path

import yaml
from kit import BRIGADE_DIR, System

from raphael_empresas.boot import start
from raphael_empresas.migrate import installation_from_profile

ROOT = BRIGADE_DIR.parents[1]
INSTALL = ROOT / "infra/client-install/clienta.installation.yaml"
PROFILE = ROOT / "_reference/core/raphael-empresas/raphael-harness/ejemplos/perfil-ropa-medida.yaml"
W = "whatsapp:5493415550000"


def test_carga_todas_las_piezas_de_la_instalacion(tmp_path):
    rt, report = start(INSTALL, tmp_path, dev_dirs=[BRIGADE_DIR], installed=False, models=False)
    assert report["errors"] == {} and report["mounted"] == ["empresas"]
    assert set(rt.brigades["empresas"].cooks) == {"atencion", "encargos", "cobros", "agenda", "avisos", "tareas", "tienda"}
    assert rt.orchestrator.name == "raphael" and rt.orchestrator.cfg.mode == "secretary"
    assert rt.installation.edition == "cloud" and (tmp_path / "raphael.sqlite").is_file()
    assert "Atendemos" in rt.run(rt.receive("whatsapp", "1", "¿qué horario tienen?"))[0]


def test_la_base_queda_en_disco_y_sobrevive_un_reinicio(tmp_path):
    rt, _ = start(INSTALL, tmp_path, dev_dirs=[BRIGADE_DIR], installed=False, models=False)
    rt.run(rt.receive("whatsapp", "1", "¿hacen arreglos de ruedos?"))
    rt.store.close()
    rt2, _ = start(INSTALL, tmp_path, dev_dirs=[BRIGADE_DIR], installed=False, models=False)
    assert [p["action"]["type"] for p in rt2.approvals.list()] == ["responder_duda"]


def test_recorrido_completo_de_una_clienta():
    x = System(pilot=True)
    s = ("whatsapp", "5493415550000")
    assert "Atendemos" in x.receive("Hola! qué horario tienen?", *s)[0]

    # encargo con una pregunta en el medio que responde Atención
    x.receive("quiero un vestido largo a medida para el casamiento de mi hermana", *s, name="Cami")
    out = x.receive("¿hacen envíos?", *s)
    assert "todo el país" in out[0] and out[0].endswith("¿Para qué fecha lo necesitás? 📅")
    for m in ("el 20 de marzo", "de gasa verde", "no", "prefiero que me midan", "el jueves a las 17", "Camila Pérez"):
        out = x.receive(m, *s)
    assert "#1" in out[0]

    # la dueña: presupuesto sugerido (150.000 + 20% largo) y turno de medidas pedido por Encargos -> Agenda
    kinds = {p["action"]["type"]: p for p in x.pending()}
    assert set(kinds) == {"enviar_presupuesto", "confirmar_turno"}
    assert kinds["enviar_presupuesto"]["action"]["data"]["price"] == 180000
    x.approve(kinds["confirmar_turno"]["id"])
    assert "jueves 19 de noviembre a las 17:00" in x.out(W)[-1]
    x.approve(kinds["enviar_presupuesto"]["id"])
    assert "$ 90.000" in x.out(W)[-1]                       # seña 50%

    # pago: la clienta avisa, la dueña confirma, Avisos le escribe solo
    assert "confirme la transferencia" in x.receive("listo, ya te transferí", *s)[0]
    [pay] = x.pending()
    x.approve(pay["id"])
    assert "Recibimos tu seña" in x.out(W)[-1]
    assert x.cmd("encargos", "ver", {"number": 1})["status"] == "confirmado"

    # recordatorio del turno y aviso de "listo"
    x.tick()
    assert any("Te recordamos" in t for t in x.out(W))
    x.cmd("encargos", "estado", {"number": 1, "status": "listo"})
    assert "está listo" in x.out(W)[-1]

    # reclamo: se deriva a una persona y nadie más responde
    out = x.receive("me llegó mal el pedido", *s)
    assert "Ana" in out[0] and len(out) == 1
    assert x.pending()[-1]["level"] == "humano"

    st = x.rt.status()
    assert st["usage"]["messages"] == 11 and "Camila" not in str(st)


def test_duda_sin_respuesta_y_saludo():
    x = System(pilot=True)
    assert "Taller Ejemplo" in x.receive("hola", "instagram", "x")[0]
    assert "te lo confirma Ana" in x.receive("¿hacen arreglos de ruedos?", "instagram", "x")[0]


def test_el_perfil_04_se_convierte_a_la_instalacion_v2():
    p = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    inst, notes = installation_from_profile(p, inst_id="clienta-ropa")
    cfg = inst["brigades"]["empresas"]["config"]
    assert inst["orchestrator"]["config"]["mode"] == "secretary" and inst["edition"] == "cloud"
    assert cfg["payments"] == {"deposit_pct": 50, "alias": "taller.ejemplo", "holder": "Ana Pérez"}
    assert cfg["orders"]["surcharges"][1] == {"word": "bordado", "kind": "amount", "value": 40000}
    assert inst["autonomy"] == {"empresas.enviar_presupuesto": "aprobacion", "empresas.confirmar_pago": "aprobacion"}
    assert notes == []
    p["brigadas"] = ["atencion"]
    assert "en el v2 la brigada Empresas trae todos sus cocineros" in installation_from_profile(p)[1][0]


def test_la_instalacion_de_la_clienta_es_la_del_perfil_piloto():
    p = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    inst, _ = installation_from_profile(p, inst_id="clienta-ropa")
    file = yaml.safe_load(Path(INSTALL).read_text(encoding="utf-8"))
    store = file["brigades"]["empresas"]["config"].pop("store")
    assert file == inst and store["source"]["kind"] == "none"
