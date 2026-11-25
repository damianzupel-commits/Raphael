"""Ruteo del orquestador: puerta de O2 (parte 2).

  - Pedidos de la persona: portados de JarvisRemote `tests/test_orquestador.py` (sección de ruteo) y el banco de
    `orquestador/banco_ruteo.py`, con las reglas de JR pasadas a señales de manifiesto (`kit.JR_CATALOG`). El motor ya no
    sabe de Cerebro ni de Investigación: si con esas señales da lo mismo que JR, la generalización está bien.
  - Mensajes de clientes: portados de Empresas `raphael-orquestador/tests/test_orquestador.py`. "Un reclamo va primero a
    Atención" deja de ser regla del orquestador (es conocimiento del negocio): pasa al `interest` del cocinero de
    Atención (pendiente para 15); acá se prueba que el que más interés declara va primero.
"""

from __future__ import annotations

import asyncio

import pytest
from kit import JR_CATALOG, Script, catalog_entry, emitter, owner, runtime
from raphael_core import Cook, Reply, Runtime
from raphael_core.context import OrchestratorContext
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_orchestrator import config_from
from raphael_orchestrator.ports import routing_llm
from raphael_orchestrator.routing import by_rules, candidates, order_cooks, pick, route

CANDS = candidates(JR_CATALOG)


def run(coro):
    return asyncio.run(coro)


def decide(text, **kw):
    kw.setdefault("llm", None)
    return run(route(text, JR_CATALOG, **kw))


class Model:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    async def __call__(self, messages):
        self.calls.append(messages)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


# --- banco de JarvisRemote (sin modelo, sin trabajo conjunto, sin charla ni autoconocimiento) --------------------------------
BANCO = [
    ("¿Qué sé de ransomware?", "memoria-cerebro"),
    ("¿Qué tengo guardado sobre la rotación de claves del servidor?", "memoria-cerebro"),
    ("Buscá en mis notas lo que anoté de CRISPR", "memoria-cerebro"),
    ("¿Qué dice mi vault sobre el plan de migración a Linux?", "memoria-cerebro"),
    ("Recordame qué decidimos sobre el umbral de consolidación", "memoria-cerebro"),
    ("¿Cada cuántos días se rotan las claves del servidor Orión?", "memoria-cerebro"),
    ("¿Qué anoté la semana pasada sobre el watchdog?", "memoria-cerebro"),
    ("Conectá lo que sé de embeddings con lo que sé de spreading activation", "memoria-cerebro"),
    ("¿Tengo alguna nota sobre Tailscale?", "memoria-cerebro"),
    ("Resumime lo que guardé de la charla de midudev", "memoria-cerebro"),
    ("¿Qué conclusiones saqué del experimento JEV?", "memoria-cerebro"),
    ("Según mis notas, ¿quién es el responsable del script de rotación?", "memoria-cerebro"),
    ("¿Qué sabemos del modelo de delegación de las brigadas?", "memoria-cerebro"),
    ("Decime qué hay en la memoria sobre el proyecto Fénix", "memoria-cerebro"),
    ("¿Dónde dejé apuntado lo del cyber range?", "memoria-cerebro"),
    ("¿Qué aprendiste de la playlist de esta semana?", "memoria-cerebro"),
    ("Repasame mis apuntes de transformers", "memoria-cerebro"),
    ("¿Qué relación hay entre mis notas de hebbiano y las de olvido?", "memoria-cerebro"),
    ("¿Te acordás de lo que hablamos del gate firmado?", "memoria-cerebro"),
    ("¿Cuál era el puerto del orquestador?", "memoria-cerebro"),
    ("hola", "memoria-cerebro"),
    ("¿Cómo venimos?", "memoria-cerebro"),
    ("Necesito ayuda con algo", "memoria-cerebro"),
    ("Explicame qué es un transformer", "memoria-cerebro"),
    ("¿Qué opinás de pasar todo a un modelo local?", "memoria-cerebro"),
    ("Dame ideas para ordenar la semana", "memoria-cerebro"),
    ("¿Qué es mejor, Semgrep o Bandit?", "memoria-cerebro"),
    ("gracias, quedó claro", "memoria-cerebro"),
    ("¿En qué caso conviene usar un índice hebbiano?", "memoria-cerebro"),
    ("Contame de Rust", "memoria-cerebro"),
    ("Investigá en la web qué es ActivityPub", "investigacion"),
    ("Buscá en internet las novedades de Rust", "investigacion"),
    ("¿Qué salió en arxiv esta semana sobre agentes?", "investigacion"),
    ("Investigá el estado del arte en memoria para LLMs", "investigacion"),
    ("Buscame noticias de hoy sobre NVIDIA", "investigacion"),
    ("Hacé un research de vLLM contra Ollama", "investigacion"),
    ("Fijate qué dice https://ejemplo.org/articulo sobre el tema", "investigacion"),
    ("Averiguá online cuánto sale una GPU de 24 GB", "investigacion"),
    ("Investigame las últimas versiones de FastAPI", "investigacion"),
    ("Que Scout busque información sobre Piper TTS", "investigacion"),
    ("Buscá en Google si hay CVEs nuevos de OpenSSH", "investigacion"),
    ("Googleá qué es el protocolo MCP", "investigacion"),
    ("¿Hay novedades de faster-whisper?", "investigacion"),
    ("Traeme lo último que se publicó sobre spreading activation", "investigacion"),
    ("Investigá qué alternativas hay a Brave Search", "investigacion"),
    ("Creá un caso nuevo para la estafa del alquiler", "investigacion"),
    ("Ingestá el CSV de transferencias en el caso 3", "investigacion"),
    ("Analizá el chat de WhatsApp que exporté", "investigacion"),
    ("Sacale los metadatos EXIF a foto_recibo.jpg", "investigacion"),
    ("¿Qué entidades aparecen en la evidencia del caso orion?", "investigacion"),
    ("Proponé fusiones entre las personas del caso", "investigacion"),
    ("Exportá el informe del caso en PDF", "investigacion"),
    ("Revisá el log del servidor access.log del caso 7", "investigacion"),
    ("Ingestá este export de Telegram al caso", "investigacion"),
    ("¿Qué propuestas quedaron pendientes en el caso de la estafa?", "investigacion"),
    ("Mapeá las columnas de movimientos.csv", "investigacion"),
    ("Hacé el análisis forense del documento contrato.docx", "investigacion"),
    ("Listame los artefactos del caso 2", "investigacion"),
    ("Investigá en la web qué es Orión y comparalo con mis notas", "investigacion"),
    ("Buscá en internet sobre ransomware y fijate qué tengo guardado", "investigacion"),
    ("Con la evidencia del caso 3, ¿qué dicen mis notas del banco?", "investigacion"),
]


@pytest.mark.parametrize("text,expected", BANCO)
def test_el_banco_de_jarvisremote_rutea_igual_con_senales_de_manifiesto(text, expected):
    r = decide(text, chat_direct=False, self_knowledge=False)
    assert r.kind == "brigade" and r.brigade == expected, (r.reason, r.scores)


def test_en_caso_de_no_es_un_caso_forense_y_sin_senal_o_empate_no_decide():
    assert by_rules("en caso de duda, qué sé de mis notas", CANDS)[0] == "memoria-cerebro"
    assert by_rules("hola", CANDS)[0] is None
    assert by_rules("noticias y memoria", CANDS)[0] is None            # 1 contra 1, sin señal fuerte: empate
    assert by_rules("investigá en mis notas", CANDS)[0] == "memoria-cerebro"


# --- override, charla, autoconocimiento, conjunto ----------------------------------------------------------------------------
def test_override_por_prefijo_saca_el_prefijo_y_la_pestana_gana_a_las_reglas():
    r = decide("/investigacion qué sé de X")
    assert (r.kind, r.brigade, r.via, r.request) == ("brigade", "investigacion", "override", "qué sé de X")
    r = decide("/memoria-cerebro: investigá algo en la web")
    assert (r.brigade, r.via) == ("memoria-cerebro", "override")
    r = decide("investigá en la web", brigade="memoria-cerebro")
    assert (r.brigade, r.via) == ("memoria-cerebro", "override")
    assert decide("/inexistente hola").kind != "missing"   # un /algo que no es brigada no es un prefijo


def test_las_brigadas_directas_solo_se_alcanzan_a_mano():
    assert decide("editá el video de ayer").brigade != "video"
    assert decide("/video editá el de ayer").brigade == "video"


def test_una_brigada_caida_o_sin_montar_se_explica_y_no_es_candidata():
    cat = [*JR_CATALOG, catalog_entry("seguridad", {"signals": [{"pattern": "escane", "weight": 2}]}, down=True),
           catalog_entry("trading", {}, mounted=False)]
    r = run(route("escaneá la red", cat))
    assert r.kind == "brigade" and r.brigade == "memoria-cerebro"     # no va a la caída
    r = run(route("/seguridad escaneá", cat))
    assert r.kind == "missing" and "está caída" in r.reason
    r = run(route("hola", cat, brigade="trading"))
    assert r.kind == "missing" and "no está montada" in r.reason
    r = run(route("x", cat, brigade="nada"))
    assert r.kind == "missing" and "no existe" in r.reason


def test_charla_y_preguntas_sobre_el_asistente_no_despiertan_a_una_brigada():
    for text in ("hola", "gracias, quedó claro", "chau Rafa"):
        assert decide(text, assistant="Rafa").kind == "chat"
    assert decide("hola, ¿qué sé de Rust?").kind == "brigade"         # una palabra fuera de la lista y no es charla
    assert decide("¿qué brigadas tenés?").kind == "self"
    assert decide("buscá en mis notas lo de las brigadas").kind == "brigade"   # con señal fuerte es trabajo
    assert decide("hola", chat_direct=False).kind == "brigade"


def test_dos_brigadas_con_senal_fuerte_es_trabajo_conjunto_si_esta_prendido():
    r = decide("Investigá en la web qué es Orión y comparalo con mis notas", joint_enabled=True)
    assert r.kind == "joint" and set(r.brigades) == {"memoria-cerebro", "investigacion"}
    assert decide("¿Qué sé de ransomware?", joint_enabled=True).kind == "brigade"


# --- el clasificador ---------------------------------------------------------------------------------------------------------
def test_ambiguo_usa_el_clasificador_y_valida_lo_que_devuelve():
    m = Model("investigacion")
    r = decide("Explicame bien cómo viene el tema ese", llm=m)
    assert (r.brigade, r.via) == ("investigacion", "model")
    system, user = m.calls[0]
    assert "memoria-cerebro" in system["content"] and "Ante la duda, respondé memoria-cerebro" in system["content"]
    assert "video" not in system["content"] and "<<<DATO" in user["content"]


@pytest.mark.parametrize("answer", [None, "ninguna", "cocina", RuntimeError("429"), "video"])
def test_si_el_clasificador_falla_o_inventa_va_al_destino_seguro(answer):
    r = decide("Explicame bien cómo viene el tema ese", llm=Model(answer))
    assert (r.brigade, r.via) == ("memoria-cerebro", "default")


def test_un_pedido_muy_corto_sin_senales_no_consulta_al_modelo_y_las_reglas_claras_tampoco():
    m = Model("investigacion")
    for short in ("hola", "gracias, quedó claro", "¿Cómo venimos?"):
        r = decide(short, llm=m, chat_direct=False)
        assert (r.brigade, r.via) == ("memoria-cerebro", "default") and "sin consultar al modelo" in r.reason
    assert decide("¿Qué sé de ransomware?", llm=m).via == "rules"
    assert m.calls == []


def test_sin_destino_seguro_dice_que_no_hay_y_el_configurado_gana():
    cat = [catalog_entry("a", {"signals": [{"pattern": "alfa", "weight": 1}]}), catalog_entry("b", {})]
    assert run(route("algo sin señales largo de verdad", cat)).kind == "none"
    assert run(route("algo sin señales largo", cat, default_brigade="b")).brigade == "b"
    assert run(route("algo sin señales largo", cat, default_brigade="zeta")).kind == "none"


def test_el_clasificador_respeta_la_config_de_privacidad():
    bodies = []

    def transport(url, body, headers):
        bodies.append(body)
        return {"choices": [{"message": {"content": "osint"}}], "usage": {}}

    rt = Runtime(installation_from({"id": "pc", "edition": "personal"}), clock=Clock(),
                 models=ModelGateway(models_from({"providers": {"n": {"base_url": "https://n.example/v1", "model": "m"}},
                                                  "tiers": {"pago": [], "gratis": ["n"], "local": []},
                                                  "roles": {"ruteo": ["gratis"]}}),
                                     Usage(Store().space("_uso"), 1000, Clock()), transport=transport))
    ctx = OrchestratorContext(rt)
    assert routing_llm(ctx, config_from({"routing": {"classifier": False}})) is None
    assert run(routing_llm(ctx, config_from({}))([{"role": "user", "content": "x"}])) == "osint" and len(bodies) == 1
    local_only = routing_llm(ctx, config_from({"routing": {"classifier_cloud": False}}))
    assert run(local_only([{"role": "user", "content": "x"}])) is None and len(bodies) == 1   # no sale a la nube


def test_con_el_harness_real_el_ruteo_lee_las_senales_del_manifiesto():
    from raphael_orchestrator.turn import decide as decide_rt

    rt = runtime(Script(), brigades=("notas", "web"), routing={
        "notas": {"safe_default": True, "signals": [{"pattern": r"mis notas", "weight": 2}]},
        "web": {"signals": [{"pattern": r"en la web", "weight": 2}]}})
    ctx = OrchestratorContext(rt)
    cfg = config_from({"routing": {"classifier": False}})
    assert run(decide_rt(ctx, "buscá en la web X", cfg)).brigade == "web"
    assert run(decide_rt(ctx, "qué hay en mis notas", cfg)).brigade == "notas"
    assert run(decide_rt(ctx, "algo que no matchea con nada de nada", cfg)).brigade == "notas"
    rt.brigades["web"].chief_down = "5 errores"
    assert run(decide_rt(ctx, "buscá en la web X", cfg)).brigade == "notas"


# --- mensajes de clientes (Empresas) ------------------------------------------------------------------------------------------
class B(Cook):
    def __init__(self, name, interest=0.0, open_=False, fail=False, description=""):
        self.name, self._i, self._a, self._fail, self.description = name, interest, open_, fail, description
        self.saw: list[str] = []

    def interest(self, msg, ctx):
        if self._fail:
            raise RuntimeError("roto")
        return self._i

    def in_progress(self, msg, ctx):
        return self._a

    def handle(self, msg, ctx):
        self.saw.append(msg.text)
        return Reply(f"{self.name} acá")


def shop(*cooks: B, models=None):
    rt = Runtime(installation_from({"id": "c", "edition": "cloud"}), clock=Clock(), models=models)
    for c in cooks:
        rt.run(rt.mount(manifest_from({"id": c.name, "name": c.name, "version": "1.0.0", "contract": ">=2.0,<3",
                                       "description": c.description, "cooks": [{"id": "c", "entry": "x:B"}]}), {"c": c}))
    return rt


def order(*cooks: B, text="hola", fallback=None, llm=None):
    rt = shop(*cooks)
    from raphael_core.contract import Message

    out = run(order_cooks(Message("whatsapp", "1", text), OrchestratorContext(rt), list(cooks), llm=llm,
                          fallback=fallback))
    return [c.name for c in out]


def test_el_que_mas_interes_declara_va_primero():
    assert order(B("encargos", 0.4, open_=True), B("atencion", 0.9), text="me llegó roto")[:2] == ["encargos", "atencion"]
    assert order(B("agenda", 0.9), B("encargos", 0.1, open_=True), B("atencion"), fallback="atencion/c")[:2] == [
        "encargos", "agenda"]


def test_la_red_queda_siempre_al_final_y_sin_red_van_todos():
    assert order(B("atencion", 0.99), B("cobros", 0.2), B("agenda", 0.0), fallback="atencion/c") == ["cobros", "atencion"]
    assert order(B("cobros", 0.5)) == ["cobros"]
    assert order(B("cobros", 0.0), B("agenda", 0.0)) == ["cobros", "agenda"]   # sin red: que alguno pueda tomarlo


def test_un_cocinero_que_falla_al_ordenar_cuenta_como_no_es_mio():
    assert order(B("roto", fail=True), B("cobros", 0.3), fallback="roto/c") == ["cobros", "roto"]


def test_si_nadie_lo_reclama_el_modelo_elige_y_lo_que_inventa_se_ignora():
    enc, atn = B("encargos", description="pedidos a medida"), B("atencion", description="dudas y reclamos")
    m = Model("encargos/c")
    assert order(enc, atn, text="¿me harías una campera igual a la de la foto?", fallback="atencion/c", llm=m) == [
        "encargos", "atencion"]
    system, user = m.calls[0]
    assert "pedidos a medida" in system["content"] and "<<<DATO" in user["content"]
    for answer in ("ninguna", "cocina/c", None, "no sé"):
        assert order(B("encargos"), B("atencion"), fallback="atencion/c", llm=Model(answer)) == ["atencion"]


def test_de_punta_a_punta_con_el_harness_atiende_el_elegido():
    enc, atn = B("encargos", description="pedidos a medida"), B("atencion", description="dudas y reclamos")
    rt = shop(enc, atn)

    from raphael_core import Orchestrator

    class Mini(Orchestrator):
        name, version = "mini", "0"

        async def route(self, msg, ctx, cooks):
            return await order_cooks(msg, ctx, cooks, llm=Model("encargos/c"), fallback="atencion/c")

    rt.set_orchestrator(Mini())
    out = rt.run(rt.receive("whatsapp", "w1", "buenas! ¿me harías una campera?", "Eva"))
    assert out == ["encargos acá"] and enc.saw and not atn.saw


def test_el_feed_y_la_auditoria_dicen_por_que_se_ruteo():
    from raphael_orchestrator.turn import run_route

    rt = runtime(Script(), brigades=("web",), routing={"web": {"signals": [{"pattern": "web", "weight": 2}]}})
    evs = []
    ctx = owner(rt, evs)
    r = run(route("buscá en la web", ctx.catalog()))
    run(run_route(ctx, r, emitter(evs), config_from({})))
    assert evs[0] == {"type": "route", "kind": "brigade", "via": "rules", "reason": r.reason, "brigade": "web"}
    assert any(e["what"] == "ruteo" and e["who"] == "orquestador" for e in rt.audit.entries())


# --- "revisa mi red wifi" (25 nov 2026): con el manifiesto REAL de Seguridad tiene que ir a Seguridad --------------------------
def _seguridad_real():
    from pathlib import Path

    import yaml

    ruta = Path(__file__).resolve().parents[3] / "05-seguridad" / "b-codigo" / "manifest.yaml"
    m = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return catalog_entry("seguridad", m["routing"])


@pytest.mark.parametrize(
    "texto", ["revisa mi red wifi", "revisa mi wifi", "¿qué puertos abiertos tiene mi red?", "revisá el firewall del router"]
)
def test_los_pedidos_de_red_van_a_seguridad_sin_consultar_a_un_modelo(texto):
    r = run(route(texto, [_seguridad_real(), catalog_entry("memoria-cerebro", {"safe_default": True})], llm=None))
    assert (r.brigade, r.via) == ("seguridad", "rules"), (r.reason, r.scores)


@pytest.mark.parametrize("answer", ["<think>veamos, es un tema de red…</think>\nseguridad", "  <think>\n…\n</think> seguridad."])
def test_un_modelo_que_razona_se_lee_despues_del_pensamiento(answer):
    assert pick(answer, ["seguridad", "memoria-cerebro"]) == "seguridad"


def test_un_razonamiento_cortado_no_es_una_respuesta():
    cortado = "<think>Veamos: el pedido habla de seguridad y de memoria-cerebro, así que"
    assert pick(cortado, ["seguridad", "memoria-cerebro"]) is None
