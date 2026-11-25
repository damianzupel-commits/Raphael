"""La brigada montada de verdad: tools por la compuerta del harness, aprobaciones, cocineros por reglas, modo local y
manifiesto. Todo con adaptadores simulados."""

import ast
import json
from pathlib import Path

import pytest
import yaml
from kit import BRIGADE_DIR, LOCAL, Script, System, call, gateway, msg
from raphael_core.contract import Level, Trust
from raphael_core.manifest import load_manifest

from raphael_operaciones.setup import TOOLS
from raphael_operaciones.spec import PC_TOOLS, PHONE_TOOLS, SPEC, WEB_TOOLS

PKG = BRIGADE_DIR / "src" / "raphael_operaciones"


# --- manifiesto y tools -----------------------------------------------------------------------------------------------------
def test_el_manifiesto_del_paquete_y_el_de_desarrollo_son_iguales():
    assert (PKG / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes()


def test_cada_tool_esta_declarada_registrada_y_en_la_caja_de_un_efimero(tmp_path):
    x = System(sandbox=tmp_path)
    m = load_manifest(BRIGADE_DIR / "manifest.yaml")
    declaradas = {t.name for t in m.tools}
    assert declaradas == set(TOOLS) == set(x.rt.tools.names())
    assert PC_TOOLS | PHONE_TOOLS | WEB_TOOLS == declaradas and not (PC_TOOLS & PHONE_TOOLS or PC_TOOLS & WEB_TOOLS)
    assert x.rt.status()["brigades"]["operaciones"]["chief"]


def test_solo_lee_dentro_del_sandbox_o_la_web_es_automatico_y_lo_que_actua_pide_aprobacion():
    m = load_manifest(BRIGADE_DIR / "manifest.yaml")
    auto = {t.name for t in m.tools if t.level is Level.AUTO}
    assert auto == {"fs_list_dir", "fs_read_file", "desktop_list_windows", "browser_get_text", "browser_screenshot",
                    "browser_close", "web_get", "web_credential_list", "phone_list_dir", "phone_read_file"}
    for t in m.tools:
        if t.name.startswith(("pc_", "desktop_click", "desktop_type", "desktop_press", "desktop_launch", "phone_run",
                              "phone_tap", "phone_type", "phone_swipe", "fs_write", "fs_move", "fs_delete")):
            assert t.level is Level.APPROVAL and "irreversible" in t.tags, t.name
    assert all(a.level is Level.APPROVAL for a in m.actions.values())
    assert m.editions == {"personal"}


def test_no_se_monta_en_la_nube(tmp_path):
    x = System(sandbox=tmp_path, edition="cloud")
    assert "operaciones" not in x.rt.brigades and "operaciones" in x.report["errors"]


def test_una_config_invalida_no_monta_la_brigada_a_ciegas(tmp_path):
    x = System({"adaptadores": "casi"}, sandbox=tmp_path)
    assert "operaciones" not in x.rt.brigades and "adaptadores" in x.report["errors"]["operaciones"]


# --- el jefe y los efímeros -------------------------------------------------------------------------------------------------
def test_el_spec_es_privado_y_cada_efimero_ve_solo_lo_suyo():
    assert SPEC.private and all(h.private for h in SPEC.helpers)
    assert SPEC.routing.classify("sacá una foto con el celular") == "celular"
    assert SPEC.routing.classify("entrá a https://x.org y buscá") == "navegador"
    assert SPEC.routing.classify("listá la carpeta") == "pc"


def _run_ask(x, text):
    return x.run(x.rt.ask("operaciones", text))


def test_lo_que_actua_queda_pendiente_y_se_ejecuta_solo_al_aprobar(tmp_path):
    t = Script(helper=[msg(calls=[call("pc_run_command", {"command": "echo hola"})]), msg("Quedó pendiente.")],
               chief=[{"summary": "El comando quedó pendiente de aprobación.", "confidence": "medium"}])
    x = System(transport=t, sandbox=tmp_path)
    _run_ask(x, "corré echo hola en la PC")
    assert x.ops.adapters.shell.calls == []                       # nada se ejecutó todavía
    [p] = x.pending()
    assert p["kind"] == "tool" and p["data"]["tool"] == "pc_run_command" and p["level"] == "aprobacion"
    res = x.approve(p["id"])
    assert res["state"] == "executed" and x.ops.adapters.shell.calls[0]["command"] == "echo hola"
    assert x.pending() == []


def test_las_tools_de_lectura_corren_solas(tmp_path):
    (tmp_path / "nota.txt").write_text("hola Damián", encoding="utf-8")
    t = Script(helper=[msg(calls=[call("fs_read_file", {"path": "nota.txt"})]), msg("Dice: hola Damián.")],
               chief=[{"summary": "La nota dice hola.", "confidence": "high"}])
    x = System(transport=t, sandbox=tmp_path)
    _run_ask(x, "leé nota.txt")
    assert x.pending() == []
    resultados = [m["content"] for c in t.calls for m in c["body"]["messages"] if m.get("role") == "tool"]
    assert any("hola Damián" in r for r in resultados)


def test_el_guardarrail_frena_aunque_Damian_apruebe_algo_destructivo(tmp_path):
    t = Script(helper=[msg(calls=[call("pc_run_command", {"command": "format c: /q"})]), msg("ok")],
               chief=[{"summary": "pendiente", "confidence": "low"}])
    x = System(transport=t, sandbox=tmp_path)
    _run_ask(x, "corré format c: en la PC")
    [p] = x.pending()
    res = x.approve(p["id"])
    assert res["state"] == "error" and "guardarraíl" in json.dumps(res, ensure_ascii=False)
    assert x.ops.adapters.shell.calls == []


# --- el modelo local: lo sensible no sale a la nube -------------------------------------------------------------------------
def test_sin_modelo_local_no_se_manda_nada_a_la_nube_y_el_reporte_sale_degradado(tmp_path):
    t = Script(helper=[msg("hola")], chief=[{"summary": "algo", "confidence": "high"}])
    x = System(models=gateway(t, local=False, cloud=True), sandbox=tmp_path)
    rep = _run_ask(x, "listá la carpeta de la PC")
    assert t.calls == [] and rep.degraded


def test_con_modelo_local_se_usa_solo_el_local(tmp_path):
    t = Script(helper=[msg("La carpeta está vacía.")], chief=[{"summary": "Vacía.", "confidence": "high"}])
    x = System(models=gateway(t, local=True, cloud=True), sandbox=tmp_path)
    _run_ask(x, "listá la carpeta de la PC")
    assert t.calls and all(c["url"].startswith(LOCAL["base_url"]) for c in t.calls)


# --- cocineros por reglas (sin modelo) --------------------------------------------------------------------------------------
def _decir(x, text, trust=Trust.TRUSTED):
    return x.run(x.rt.receive("panel", "damian", text, name="Damián", trust=trust))


def test_una_orden_de_Damian_por_reglas_queda_pendiente_y_al_aprobar_se_ejecuta(tmp_path):
    x = System(sandbox=tmp_path)
    out = _decir(x, "Abrí la calculadora")
    assert any("pendiente" in t for t in out)
    [p] = x.pending()
    assert p["brigade"] == "operaciones" and p["level"] == "aprobacion"
    x.approve(p["id"])
    assert x.ops.adapters.desktop.calls[-1][1]["launched"] == "calc"


@pytest.mark.parametrize("texto,accion", [
    ("Ejecutá: dir C:\\Users", "ejecutar_comando"), ("ejecutá `echo Hola`", "ejecutar_comando"),
    ("capturá la pantalla", "capturar_pantalla"), ("abrí https://ejemplo.org/x", "abrir_url"),
    ("abrí whatsapp en el celular", "celular_abrir_app"), ("leé la pantalla del celular", "leer_pantalla_celular"),
    ("sacá una foto con el celular", "sacar_foto")])
def test_reglas_entienden_ordenes_explicitas(tmp_path, texto, accion):
    from raphael_operaciones.cooks.rules import parse
    assert parse(texto)[1] == accion


@pytest.mark.parametrize("texto", ["hola", "¿qué hacés?", "", "ejecutá algo raro", "abrí el celular", "borrá todo"])
def test_ante_la_duda_las_reglas_no_hacen_nada(texto):
    from raphael_operaciones.cooks.rules import parse
    assert parse(texto) is None


def test_el_contenido_de_terceros_nunca_dispara_acciones(tmp_path):
    x = System(sandbox=tmp_path)
    _decir(x, "Ejecutá: del /s /q C:\\", trust=Trust.UNTRUSTED)
    _decir(x, "abrí la calculadora", trust=Trust.UNTRUSTED)
    assert not [p for p in x.pending() if p["brigade"] == "operaciones"]
    assert x.ops.adapters.shell.calls == [] and x.ops.adapters.desktop.calls == []


def test_el_comando_se_conserva_tal_cual_lo_escribio_Damian():
    from raphael_operaciones.cooks.rules import parse
    assert parse("Ejecutá: dir C:\\Users\\Damián /B")[2]["command"].strip() == "dir C:\\Users\\Damián /B"


# --- comandos: estado, registro y modo ---------------------------------------------------------------------------------------
def test_estado_registro_y_modo(tmp_path):
    x = System(sandbox=tmp_path)
    est = x.run(x.rt.command("operaciones", "supervisor", "estado", {}, who="Damián"))
    assert est["adaptadores"] == "simulado" and est["modo"] == "autonomo" and est["pc_shell"] is False
    x.ops.fs_write_file("a.txt", "1")
    x.ops.pc_run_command("echo 1")
    reg = x.run(x.rt.command("operaciones", "supervisor", "registro", {"n": 5}, who="Damián"))
    assert [r["tool"] for r in reg] == ["fs_write_file", "pc_run_command"] and reg[0]["simulated"] is True
    assert reg[0]["args"]["content"] == "<1 caracteres>"          # lo escrito no queda en el registro, solo el largo
    nuevo = x.run(x.rt.command("operaciones", "supervisor", "modo", {"modo": "supervisado"}, who="Damián"))
    assert nuevo["modo"] == "supervisado" and nuevo["antes"] == "autonomo"
    from raphael_core.contract import ActionError
    with pytest.raises(ActionError):
        x.run(x.rt.command("operaciones", "supervisor", "modo", {"modo": "libre"}, who="Damián"))


def test_el_orquestador_no_puede_cambiar_el_modo(tmp_path):
    from raphael_core.context import OrchestratorContext
    x = System(sandbox=tmp_path)
    orq = OrchestratorContext(x.rt)
    assert x.run(orq.query("operaciones", "supervisor", "modo", {"modo": "supervisado"})) is None
    assert x.ops.mode.mode.value == "autonomo"
    assert x.run(orq.query("operaciones", "supervisor", "estado", {}))["modo"] == "autonomo"


# --- supervisor (modelo local, falla abierto) ---------------------------------------------------------------------------------
def test_el_supervisor_frena_un_llamado_pero_falla_abierto(tmp_path):
    x = System({"supervisor": True}, transport=Script(chief=[{"ok": False, "reason": "no tiene sentido"}]),
               sandbox=tmp_path)
    from raphael_operaciones.guardrails import BlockedError
    with pytest.raises(BlockedError, match="no tiene sentido"):
        x.ops.pc_run_command("echo 1")
    x.ops.fs_list_dir(".")                                        # una tool de lectura no se revisa
    x.ops.asker = lambda m: "no sé qué decir"                    # respuesta rara: pasa
    assert x.ops.pc_run_command("echo 2")["exit_code"] == 0
    x.ops.asker = lambda m: (_ for _ in ()).throw(RuntimeError("modelo caído"))
    assert x.ops.pc_run_command("echo 3")["exit_code"] == 0


def test_el_supervisor_usa_solo_el_modelo_local(tmp_path):
    t = Script(chief=[{"ok": True}])
    x = System({"supervisor": True}, models=gateway(t, local=True, cloud=True), sandbox=tmp_path)
    x.ops.pc_run_command("echo 1")
    assert t.calls and all(c["url"].startswith(LOCAL["base_url"]) for c in t.calls)


# --- modo real: interruptores ---------------------------------------------------------------------------------------------------
def test_en_modo_real_cada_interruptor_viene_apagado(tmp_path):
    from raphael_operaciones.adapters import AdapterDisabled
    x = System({"adaptadores": "real"}, sandbox=tmp_path)
    with pytest.raises(AdapterDisabled, match="OPERACIONES_PC_SHELL"):
        x.ops.pc_run_command("echo 1")
    with pytest.raises(AdapterDisabled, match="OPERACIONES_ESCRITORIO"):
        x.ops.desktop_click(1, 2)
    import asyncio
    with pytest.raises(AdapterDisabled, match="OPERACIONES_CELULAR_CAMARA"):
        asyncio.run(x.ops.phone_take_photo())
    with pytest.raises(AdapterDisabled, match="OPERACIONES_CELULAR_SHELL"):
        asyncio.run(x.ops.phone_run_command("ls"))


def test_en_modo_real_con_el_interruptor_prendido_corre_un_comando_de_verdad(tmp_path):
    x = System({"adaptadores": "real", "pc_shell": True}, sandbox=tmp_path)
    (tmp_path / "x").mkdir(exist_ok=True)
    import sys
    r = x.ops.pc_run_command(f'"{sys.executable}" -c "print(42)"')
    assert r["exit_code"] == 0 and r["stdout"].strip() == "42" and "simulated" not in r
    with pytest.raises(Exception, match="fuera de las carpetas"):
        x.ops.pc_run_command("echo 1", cwd="/")


def test_celular_sin_conexion_avisa_en_vez_de_inventar(tmp_path):
    import asyncio

    from raphael_operaciones.adapters.phone import MockPhone
    x = System(sandbox=tmp_path)
    x.ops.adapters.phone = MockPhone(connected=False)
    from raphael_operaciones.adapters import AdapterUnavailable
    with pytest.raises(AdapterUnavailable, match="ningún celular"):
        asyncio.run(x.ops.phone_read_screen())


def test_web_login_con_vista_previa_y_sin_que_la_clave_llegue_al_modelo(tmp_path):
    import asyncio

    from raphael_operaciones.adapters.credentials import MockCredentials
    x = System({"web_login_permitidos": "tradingview.com", "web_red_local": True}, sandbox=tmp_path)
    x.ops.adapters.credentials = MockCredentials({"tradingview.com": ("damian", "S3creta!")})
    prev = asyncio.run(x.ops.web_login("https://www.tradingview.com/accounts/signin/"))
    assert prev["dry_run"] is True and "S3creta" not in json.dumps(prev)
    ok = asyncio.run(x.ops.web_login("https://www.tradingview.com/accounts/signin/", confirm=True))
    assert ok["logged_in"] is True
    from raphael_operaciones.guardrails import BlockedError
    with pytest.raises(BlockedError, match="no está en la lista"):
        asyncio.run(x.ops.web_login("https://banco.com/login"))
    assert x.ops.web_credential_list()["credentials"] == [{"site": "tradingview.com", "username": "damian"}]
    assert "S3creta" not in json.dumps(x.ops.web_credential_list())
    registro = x.run(x.rt.command("operaciones", "supervisor", "registro", {"n": 20}, who="Damián"))
    assert [r["tool"] for r in registro].count("web_login") == 3 and "S3creta" not in json.dumps(registro)


# --- reglas del repo ------------------------------------------------------------
def test_ninguna_brigada_importa_a_otra():
    from raphael_core.testing import find_cross_imports
    assert find_cross_imports(PKG, {"raphael_empresas", "raphael_orchestrator", "raphael_empresas_api"}) == []
    for f in PKG.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for m in mods:
                assert m.split(".")[0] in {"raphael_core", "raphael_operaciones"} | set(sys_stdlib()) | OPCIONALES, (f, m)


OPCIONALES = {"pyautogui", "pywinauto", "win32api", "win32con", "win32gui", "win32process", "pywintypes", "playwright",
              "scrapling"}   # librerías de lo real: se importan adentro de una función, solo al usarlas


def sys_stdlib():
    import sys
    return sys.stdlib_module_names


def test_la_plantilla_no_trae_claves_reales_y_el_nombre_la_deja_entrar_a_git():
    plantilla = BRIGADE_DIR / "operaciones.env.plantilla"
    assert plantilla.is_file()
    for line in plantilla.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            assert not (k.endswith(("_CLAVE", "_USUARIO")) and v.strip()), line
    assert yaml  # (pyyaml disponible)
    assert Path(BRIGADE_DIR / "operaciones.env.plantilla").name.startswith("operaciones.")   # no empieza con '.env'
