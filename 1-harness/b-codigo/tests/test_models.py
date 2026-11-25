import pytest
from pydantic import ValidationError

from raphael_core.models import ModelGateway, Usage, load_models, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

OK = {"choices": [{"message": {"content": "hola"}}], "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Transporte:
    def __init__(self, fallan=()):
        self.llamadas = []
        self.fallan = dict(fallan)            # base_url -> excepción

    def __call__(self, url, body, headers):
        self.llamadas.append((url, body, headers))
        for base, exc in self.fallan.items():
            if url.startswith(base):
                raise exc
        return OK


class Http429(Exception):
    status_code = 429


CONFIG = {
    "providers": {
        "potente": {"base_url": "https://pago.example/v1", "model": "grande", "api_key_env": "K_PAGO",
                    "usd_per_million_in": 3, "usd_per_million_out": 15},
        "g1": {"base_url": "https://g1.example/v1", "model": "m1", "api_key_env": "K_G1", "rpm": 2},
        "g2": {"base_url": "https://g2.example/v1", "model": "m2", "api_key_env": "K_G2", "tokens_per_day": 1500},
        "casa": {"base_url": "http://localhost:11434/v1", "model": "chico"},
    },
    "tiers": {"pago": ["potente"], "gratis": ["g1", "g2"], "local": ["casa"]},
    "roles": {"mando": ["pago", "gratis", "local"], "cocinero": ["gratis", "local"], "ruteo": ["local", "gratis"]},
    "overrides": {"cocinero.forense": ["local"]},
    "private": ["cerebro"],
    "paid_cap_usd_month": 0.02,
}
ENV = {"K_PAGO": "kp", "K_G1": "k1", "K_G2": "k2"}


def gw(config=None, env=None, transport=None, edition="personal", limit=1000, plan=""):
    usage = Usage(Store().space("_uso"), limit, Clock())
    reloj = Reloj()
    g = ModelGateway(models_from(config or CONFIG), usage, env=ENV if env is None else env, edition=edition,
                     transport=transport or Transporte(), monotonic=reloj, plan=plan)
    return g, usage, reloj


def test_el_yaml_de_fabrica_tiene_tres_escalones_con_openrouter_en_pago():
    c = load_models()
    assert set(c.tiers) == {"pago", "gratis", "local"}
    assert c.tiers == {"pago": ["deepseek-flash"], "gratis": ["gratis-a", "gratis-b"],
                   "local": ["local-ollama"]}
    assert c.providers["local-ollama"].is_local
    assert not c.providers["deepseek-flash"].free and not c.providers["deepseek-flash"].is_local
    # todo lo que sale por OpenRouter exige proveedores que no guarden ni entrenen con los datos
    for name in ("deepseek-flash", "gratis-a", "gratis-b"):
        assert c.providers[name].extra["provider"] == {"data_collection": "deny"}
    assert c.providers["gratis-a"].free and c.providers["gratis-b"].free
    # NVIDIA gratis es solo para desarrollo: no está en ningún escalón
    assert all("nvidia" not in ps for ps in c.tiers.values())
    # lo que habla con la persona o planifica no cae a modelos gratis
    assert all(c.roles[r] == ["pago"] for r in ("mando", "voz", "jefe"))
    assert c.canonical("secretaria") == "mando" and c.canonical("redaccion") == "cocinero"


def test_orden_de_escalones_por_rol_y_clave_solo_a_su_proveedor():
    t = Transporte()
    g, usage, _ = gw(transport=t)
    assert g.complete("mando", [{"role": "user", "content": "x"}]) == "hola"
    url, body, headers = t.llamadas[0]
    assert url == "https://pago.example/v1/chat/completions" and body["model"] == "grande"
    assert headers["Authorization"] == "Bearer kp"
    g.complete("cocinero", [])
    assert t.llamadas[1][0].startswith("https://g1.") and t.llamadas[1][2]["Authorization"] == "Bearer k1"
    s = usage.summary()
    assert s["tiers"]["pago"]["calls"] == 1 and s["cost_usd"] == pytest.approx(0.0105)


def test_el_tope_del_escalon_pago_lo_apaga():
    g, usage, _ = gw()
    g.complete("mando", [])                                    # 0.0105 USD
    g.complete("mando", [])                                    # 0.021 USD: pasó el tope de 0.02
    assert usage.spent(["pago"]) >= 0.02
    assert [c.tier for c in g.candidates("mando")][0] == "gratis"


def test_con_tope_cero_solo_proveedores_gratis_en_el_escalon_pago():
    g, _, _ = gw(config={**CONFIG, "paid_cap_usd_month": 0})
    assert g.candidates("mando")[0].tier == "gratis"


def test_rotacion_en_el_escalon_gratis():
    t = Transporte()
    g, _, _ = gw(transport=t)
    for _ in range(3):
        g.complete("cocinero", [])
    assert [u.split("//")[1][:2] for u, _, _ in t.llamadas] == ["g1", "g2", "g1"]


def test_limite_alcanzado_pausa_y_pasa_al_siguiente():
    t = Transporte(fallan={"https://g1.": Http429("429 Too Many Requests")})
    g, usage, reloj = gw(transport=t)
    assert g.complete("cocinero", []) == "hola"                # g1 dio 429, respondió g2
    assert [u.split("//")[1][:2] for u, _, _ in t.llamadas] == ["g1", "g2"]
    assert "g1" not in [c.name for c in g.candidates("cocinero")]
    reloj.t += 61
    assert "g1" in [c.name for c in g.candidates("cocinero")]
    assert usage.summary()["ai_failures"] == 1


def test_pedidos_por_minuto_y_cupo_diario():
    g, _, reloj = gw()
    for _ in range(4):
        g.complete("cocinero", [])
    names = [c.name for c in g.candidates("cocinero")]
    assert "g1" not in names                                   # 2 por minuto
    assert "g2" not in names                                   # 1500 tokens por día: 2 llamadas de 1500
    assert names == ["casa"]
    reloj.t += 61
    assert "g1" in [c.name for c in g.candidates("cocinero")]


def test_privado_solo_local_y_nube_sin_local():
    g, _, _ = gw()
    assert [c.name for c in g.candidates("mando", private=True)] == ["casa"]
    assert [c.name for c in g.candidates("cocinero", target="cerebro")] == ["casa"]
    nube, _, _ = gw(edition="cloud")
    assert [c.name for c in nube.candidates("cocinero", target="cerebro")] == []
    assert nube.complete("cocinero", [], private=True) is None
    assert "casa" not in [c.name for c in nube.candidates("ruteo")]


def test_override_por_ayudante_plan_y_preferencia():
    g, _, _ = gw()
    assert [c.tier for c in g.candidates("cocinero", target="forense")] == ["local"]
    con_plan, _, _ = gw(config={**CONFIG, "plans": {"basico": {"mando": ["gratis"]}}}, plan="basico")
    assert {c.tier for c in con_plan.candidates("mando")} == {"gratis"}
    assert g.chain("cocinero", prefer="pago") == ["pago", "gratis", "local"]


def test_sin_clave_sin_modelo_o_tope_de_mensajes_cae_a_none():
    g, _, _ = gw(env={})
    assert [c.name for c in g.candidates("mando")] == ["casa"]           # local no necesita clave
    vacio, _, _ = gw(config={"providers": {}, "tiers": {}, "roles": {}})
    assert vacio.complete("mando", []) is None and not vacio.available("mando")
    lleno, usage, _ = gw(limit=1)
    usage.record_message()
    usage.record_message()
    assert lleno.complete("mando", []) is None and not lleno.available("mando")


def test_todos_fallan_devuelve_none_y_explica():
    t = Transporte(fallan={"https://": RuntimeError("caído"), "http://": RuntimeError("caído")})
    g, usage, _ = gw(transport=t)
    assert g.complete("cocinero", []) is None and usage.summary()["ai_failures"] == 3
    rows = g.explain("cocinero")
    assert {r["provider"]: r["ok"] for r in rows} == {"g1": False, "g2": False, "casa": False}
    assert all(r["why"] == "en pausa" for r in rows)


def test_extra_del_proveedor_va_en_el_cuerpo():
    t = Transporte()
    cfg = {**CONFIG, "providers": {**CONFIG["providers"],
                                   "g1": {**CONFIG["providers"]["g1"], "extra": {"chat_template_kwargs": {"x": 1}}}}}
    g, _, _ = gw(config=cfg, transport=t)
    g.complete("cocinero", [])
    assert t.llamadas[0][1]["chat_template_kwargs"] == {"x": 1}


@pytest.mark.parametrize("cambio", [
    {"tiers": {"gratis": ["fantasma"]}},
    {"roles": {"mando": ["platino"]}},
    {"otra_cosa": 1},
])
def test_config_invalida(cambio):
    with pytest.raises(ValidationError):
        models_from({**CONFIG, **cambio})


def test_set_env_pone_y_saca_claves_en_caliente():
    t = Transporte()
    g, _, _ = gw(env={}, transport=t)
    assert g.label("mando").startswith("casa")        # sin claves solo queda el local
    g.set_env({"K_PAGO": "nueva"})
    assert g.label("mando").startswith("potente")
    g.complete("mando", [])
    assert t.llamadas[0][2]["Authorization"] == "Bearer nueva"
    g.set_env({})
    assert g.label("mando").startswith("casa")
