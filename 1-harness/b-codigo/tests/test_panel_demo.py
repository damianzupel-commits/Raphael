"""La lógica del panel (sin ventana). No corre `run_tests` para no llamarse a sí mismo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "panel"))

from demo import EXAMPLE_MANIFEST, ORCHESTRATOR, PanelState, discover_brigades  # noqa: E402

from raphael_core import CONTRACT_VERSION  # noqa: E402


def test_harness_vacio_sin_brigadas(tmp_path):
    st = PanelState(project_root=tmp_path, data_dir=":memory:").status()
    assert st["brigades"] == [] and st["edition"] == "personal" and st["contract"] == CONTRACT_VERSION


def test_pruebas_en_vivo_dejan_rastro():
    p = PanelState(project_root=None, data_dir=":memory:")
    p.ping()
    p.broken_subscriber()
    p.cycle()
    for _ in range(3):
        p.fail()
    assert p.status()["down"] == ["pieza-rota"]
    p.revive()
    p.secret()
    whats = [e["what"] for e in p.audit.entries()]
    assert {"prueba_evento", "evento_fallido", "pieza_caida", "pieza_revivida", "prueba_secreto"} <= set(whats)
    assert "sk-ejemplo1234567890" not in str(p.audit.entries())
    assert p.status()["subscribers"] == ["eco-panel"]          # las pruebas no dejan suscriptores colgados


def test_validar_manifiesto():
    p = PanelState(project_root=None, data_dir=":memory:")
    ok, lines = p.validate_manifest(EXAMPLE_MANIFEST)
    assert ok and any("no se cargan: escanear_red" in ln for ln in lines)
    ok, lines = p.validate_manifest("id: Mal\n")
    assert not ok and lines
    assert p.validate_manifest(": : :")[0] is False


def _brigada(root, carpeta, titulo, desc, cocineros, manifiesto=None):
    d = root / "brigadas" / carpeta
    (d / "cocineros").mkdir(parents=True)
    (d / "README.md").write_text(f"# {titulo}\n\nChat 1 del proyecto Raphael. {desc}\n", encoding="utf-8")
    for c in cocineros:
        (d / "cocineros" / c).mkdir()
    if manifiesto is not None:
        (d / "codigo").mkdir()
        (d / "codigo" / "manifest.yaml").write_text(manifiesto, encoding="utf-8")
    (d / "codigo-actual").mkdir(exist_ok=True)
    (d / "codigo-actual" / "manifest.yaml").write_text("roto: [", encoding="utf-8")  # se ignora


def test_lee_las_brigadas_de_la_carpeta_del_proyecto(tmp_path):
    (tmp_path / "00-LEEME.md").write_text("x", encoding="utf-8")
    _brigada(tmp_path, "05-seguridad", "05-seguridad · Seguridad", "Auditar código.", ["auditor", "pentest"])
    _brigada(tmp_path, "15-saludo", "15-saludo · Saludo", "Saluda.", ["saludador"], EXAMPLE_MANIFEST)
    _brigada(tmp_path, "16-rota", "16-rota · Rota", "No valida.", [], "id: Mal\n")
    (tmp_path / "brigadas" / "sin-numero").mkdir()     # la estructura nueva (`1-harness/c-brigadas/15-empresas/`) no lleva número
    (tmp_path / "brigadas" / "Con Espacios").mkdir()   # un nombre que no es id se sigue ignorando
    bs = discover_brigades(tmp_path, mounted={"saludo"})
    assert [b.id for b in bs] == ["seguridad", "saludo", "rota", "sin-numero"]
    seg, sal, rota, sin = bs
    assert sin.number == "" and sin.state == "sin manifiesto"
    assert seg.name == "Seguridad" and seg.description == "Auditar código." and seg.cooks == ["auditor", "pentest"]
    assert seg.state == "sin manifiesto"
    assert sal.manifest_ok and sal.contract_ok and sal.mounted and sal.state == "montada"
    assert rota.state == "manifiesto con errores" and rota.manifest_errors
    assert discover_brigades(None) == [] and discover_brigades(tmp_path / "nada") == []


def _proyecto(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "00-LEEME.md").write_text("x", encoding="utf-8")
    _brigada(tmp_path, "09-memoria-cerebro", "09-memoria-cerebro · Memoria · Cerebro", "Vault.", ["consolidador"])
    _brigada(tmp_path, "15-raphael-empresas", "15-raphael-empresas · Raphael Empresas", "Negocio.",
             ["agenda", "atencion"])
    return tmp_path


def test_el_chat_queda_guardado_al_cerrar_y_abrir(tmp_path):
    proj, datos = _proyecto(tmp_path / "p"), tmp_path / "datos"
    p = PanelState(project_root=proj, data_dir=datos)
    p.send(ORCHESTRATOR, "hola")
    p.send("raphael-empresas", "¿turnos?")
    p.send(ORCHESTRATOR, "   ")                                    # vacío: no se guarda
    otra = PanelState(project_root=proj, data_dir=datos)           # "reabrir la app"
    orq = otra.chat(ORCHESTRATOR)
    assert [m["role"] for m in orq] == ["user", "system"] and orq[0]["text"] == "hola"
    assert "No hay brigadas montadas" in orq[1]["text"]
    assert "no está montada" in otra.chat("raphael-empresas")[1]["text"]
    assert otra.chat("raphael-empresas")[0]["text"] == "¿turnos?" and otra.chat("memoria-cerebro") == []


def test_sin_brigadas_montadas_todo_vacio(tmp_path):
    p = PanelState(project_root=_proyecto(tmp_path), data_dir=":memory:")
    assert p.mounted() == [] and p.cooks(ORCHESTRATOR) == [] and p.ephemerals(ORCHESTRATOR) == []
    assert p.tools(ORCHESTRATOR) == [] and p.tasks(ORCHESTRATOR) == []


def test_muestra_orquestador_ve_todo_y_brigada_solo_lo_suyo(tmp_path):
    p = PanelState(project_root=_proyecto(tmp_path), data_dir=":memory:")
    p.sample = True
    assert {b.id for b in p.mounted()} == {"memoria-cerebro", "raphael-empresas"}   # investigación no existe acá
    assert {c[1] for c in p.cooks(ORCHESTRATOR)} == {"Memoria · Cerebro", "Raphael Empresas"}
    assert {c[1] for c in p.cooks("raphael-empresas")} == {"Raphael Empresas"}
    assert all(t[1] == "Raphael Empresas" for t in p.tasks("raphael-empresas"))
    assert len(p.tasks(ORCHESTRATOR)) > len(p.tasks("raphael-empresas"))
    assert {e[1] for e in p.ephemerals("memoria-cerebro")} == {"Memoria · Cerebro"}
    nombres = [t[0] for t in p.tools("raphael-empresas")]
    assert "enviar_whatsapp" in nombres and "buscar_en_vault" not in nombres
    antes = dict((t[0], t[3]) for t in p.tools(ORCHESTRATOR))["transcribir_audio"]
    assert p.toggle_tool("transcribir_audio") is (not antes)
    p.send(ORCHESTRATOR, "en muestra no se guarda")
    p.sample = False
    assert p.chat(ORCHESTRATOR) == [] and p.toggle_tool("transcribir_audio") is False


# --- H5: el panel monta brigadas de verdad con el cargador -------------------------------------------------------------
def test_agregar_brigadas_monta_de_verdad_y_queda_guardado_al_reabrir(tmp_path):
    proj, datos = _proyecto(tmp_path / "p"), tmp_path / "datos"
    p = PanelState(project_root=proj, data_dir=datos, models=None)
    ej = {b.id: b for b in p.brigades if b.example}
    assert set(ej) == {"saludo", "eco"} and all(b.mountable and not b.mounted for b in ej.values())
    assert "montada" in p.mount("saludo") and "montada" in p.mount("eco")
    assert {b.id for b in p.mounted()} == {"eco", "saludo"}
    p.toggle_tool("leer_agenda")
    otra = PanelState(project_root=proj, data_dir=datos, models=None)     # "reabrir la app"
    assert {b.id for b in otra.mounted()} == {"saludo", "eco"}
    assert "desmontada" in otra.unmount("eco") and {b.id for b in otra.mounted()} == {"saludo"}
    assert "no encontré la brigada 'raphael-empresas'" in otra.mount("raphael-empresas")   # sin manifest.yaml todavía


def test_chat_cocineros_efimeros_herramientas_y_tareas_salen_del_runtime(tmp_path):
    p = PanelState(project_root=_proyecto(tmp_path), data_dir=":memory:", models=None)
    p.mount("saludo")
    p.mount("eco")
    assert ("saludador", "Brigada de saludo", "en espera") in p.cooks("saludo")
    assert any(c[0].startswith("jefe") for c in p.cooks("saludo")) and {c[1] for c in p.cooks("eco")} == {"Brigada eco"}
    orq = p.send(ORCHESTRATOR, "hola, quiero un regalo")
    assert orq[1]["text"].startswith("¡Hola, Damián!") and any("pendiente #" in m["text"] for m in orq)
    [task] = [t for t in p.tasks(ORCHESTRATOR) if "regalo" in t[0]]
    assert task[2] == "aprobación" and p.tasks("eco") == []
    pid = int(task[0].split()[0][1:])
    assert "executed" in p.approve(pid)
    eco = p.send("eco", "eco probando")
    assert eco[-1]["text"] == "probando" and eco[-1]["who"] == "Brigada eco · repetidor"
    sal = p.send("saludo", "¿qué hay en la agenda?")             # jefe sin modelo: reporte degradado, lo dice
    assert "⚠" in sal[-1]["text"] and "saludo-agenda" in sal[-1]["text"]
    assert [e[0] for e in p.ephemerals("saludo")] == ["saludo-agenda"] and p.ephemerals("eco") == []
    tools = {t[0]: t for t in p.tools("saludo")}
    assert set(tools) == {"leer_agenda", "anotar_regalo", "escanear_red", "contar_visitas"}
    assert tools["anotar_regalo"][2] == "aprobacion"
    assert p.toggle_tool("leer_agenda") is False and p.toggle_tool("no-existe") is False
    assert p.status()["brigades"] == ["eco", "saludo"] and p.status()["models"] == "sin pasarela de modelos"


# --- H6: brigadas por borrador desde el panel ---------------------------------------------------------------------------
def test_crear_revisar_activar_y_desactivar_un_borrador_desde_el_panel(tmp_path):
    from demo import EXAMPLE_DRAFT

    p = PanelState(project_root=_proyecto(tmp_path), data_dir=":memory:", models=None)
    ok, text = p.draft_create(EXAMPLE_DRAFT)
    assert not ok and "leer_agenda" in text and "no existe" in text       # sin la brigada de saludo no hay esa tool
    p.mount("saludo")
    ok, text = p.draft_create(EXAMPLE_DRAFT)
    assert ok and "Estado: borrador" in text and "NO está activo" in text
    [d] = p.draft_list()
    assert d["state"] == "borrador" and not d["mounted"] and "agenda-diaria" not in {b.id for b in p.mounted()}
    assert "No se activó" in p.draft_activate("agenda-diaria", "0" * 12)
    msg = p.draft_activate("agenda-diaria", d["hash"])
    assert "activada" in msg and "montada" in msg and {b.id for b in p.mounted()} == {"saludo", "agenda-diaria"}
    assert next(b for b in p.brigades if b.id == "agenda-diaria").number == "bor"
    assert "Estado: ACTIVA" in p.draft_review("agenda-diaria")
    assert "volvió a borrador" in p.draft_deactivate("agenda-diaria") and {b.id for b in p.mounted()} == {"saludo"}
    assert "descartado" in p.draft_discard("agenda-diaria") and p.draft_list() == []
    assert not p.draft_create("{ roto")[0]


# --- H7: jefe caído, salud y tick desde el panel ------------------------------------------------------------------------
def test_el_panel_muestra_jefe_caido_y_salud_y_deja_revivir(tmp_path):
    from raphael_core.contract import Health

    p = PanelState(project_root=_proyecto(tmp_path), data_dir=":memory:", models=None)
    p.mount("saludo")
    m = p.runtime.brigades["saludo"]
    m.chief_down = "5 errores seguidos"
    assert ("jefe (2 efímeros)", "Brigada de saludo", "caído (doble clic)") in p.cooks("saludo")
    assert "volvió a estar habilitado" in p.revive_chief("Brigada de saludo") and m.chief_down is None
    assert "No encontré" in p.revive_chief("otra")
    m.health_fn = lambda ctx: Health(False, "sin agenda")
    m.health_last = None
    p.tick()
    assert ("salud", "Brigada de saludo", "mala (1/3)") in p.cooks("saludo")
