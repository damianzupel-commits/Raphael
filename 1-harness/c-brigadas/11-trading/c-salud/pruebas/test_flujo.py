"""Flujo completo: escanear -> señal -> aviso -> proponer -> aprobación de Damián -> orden. Y todo lo que lo frena."""

import httpx
import pytest
from kit import System, find_signal_config
from raphael_core import ActionError

from raphael_trading.broker import BrokerError, OandaBroker, Order, SimulatedBroker, make_broker


def with_signal(**cfg):
    cfg = {**find_signal_config(), **cfg}
    x = System(cfg)
    got = x.cmd("engine-watch", "escanear")["nuevas"]
    return x, got


def test_escanear_guarda_la_senal_avisa_y_no_ejecuta_nada():
    x, got = with_signal()
    assert got, "el simulado de USD/JPY tendría que dar al menos una señal con riesgo permisivo"
    assert x.events("trading.senal_nueva")
    assert x.cmd("engine-watch", "ordenes") == []          # avisar no es operar
    assert x.pending("ejecutar_orden") == []               # ni siquiera propone solo (por defecto)


def test_escanear_dos_veces_no_duplica():
    x, got = with_signal()
    assert x.cmd("engine-watch", "escanear")["nuevas"] == []


def test_ejecutar_exige_aprobacion_y_con_el_ok_deja_la_orden_simulada():
    x, [sid, *_] = with_signal()
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    [p] = x.pending("ejecutar_orden")
    assert p["level"] == "aprobacion"
    assert x.cmd("engine-watch", "ordenes") == []          # pendiente: todavía no pasó nada
    x.approve(p["id"])
    [o] = x.cmd("engine-watch", "ordenes")
    assert o["simulated"] and o["broker"] == "simulado" and o["signal_id"] == sid
    assert x.events("trading.orden_ejecutada")
    assert x.cmd("signals", "senales")[0]["status"] == "ejecutada"


def test_si_damian_rechaza_no_hay_orden():
    x, [sid, *_] = with_signal()
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    x.reject(x.pending("ejecutar_orden")[0]["id"], "no me gusta")
    assert x.cmd("engine-watch", "ordenes") == []


def test_senal_inexistente_no_se_propone():
    x, _ = with_signal()
    with pytest.raises(ActionError):
        x.cmd("engine-watch", "proponer", {"signal_id": "nada"})


def test_la_senal_vieja_vence():
    x, [sid, *_] = with_signal()
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    x.clock.advance(minutes=121)
    x.approve(x.pending("ejecutar_orden")[0]["id"])
    assert x.cmd("engine-watch", "ordenes") == []
    assert x.cmd("signals", "senales")[0]["status"] == "vencida"


def test_techo_de_riesgo_aunque_se_edite_al_aprobar():
    x, [sid, *_] = with_signal()
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    [p] = x.pending("ejecutar_orden")
    x.approve(p["id"], {"units": 10_000_000})
    [o] = x.cmd("engine-watch", "ordenes")
    sig = x.cmd("signals", "senales")[0]
    risk = o["units"] * abs(sig["entry"] - sig["sl"]) / sig["entry"]       # USD/JPY: 1/precio por punto
    assert risk <= 10000 * 0.02 + 0.01


def test_tope_de_ordenes_por_dia():
    x, sids = with_signal(risk={"min_conf": 0.0, "max_orders_per_day": 0})
    x.cmd("engine-watch", "proponer", {"signal_id": sids[0]})
    x.approve(x.pending("ejecutar_orden")[0]["id"])
    assert x.cmd("engine-watch", "ordenes") == []


def test_pausa_frena_todo():
    x, [sid, *_] = with_signal()
    x.cmd("engine-watch", "pausar")
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    x.approve(x.pending("ejecutar_orden")[0]["id"])
    assert x.cmd("engine-watch", "ordenes") == []
    assert x.cmd("engine-watch", "estado")["pausado"] is True
    x.cmd("engine-watch", "reanudar")
    assert x.cmd("engine-watch", "estado")["pausado"] is False


def test_proponer_automatico_deja_pendiente_pero_nunca_ejecuta():
    x = System({**find_signal_config(), "watch": {"propose_automatically": True}})
    x.cmd("engine-watch", "escanear")
    assert x.pending("ejecutar_orden") and x.cmd("engine-watch", "ordenes") == []


def test_tick_vigila_solo_si_esta_activado_y_respeta_el_intervalo():
    x = System({**find_signal_config(), "watch": {"enabled": True, "interval_minutes": 30}})
    x.tick()
    assert x.cmd("signals", "senales")
    n = len(x.events("trading.senal_nueva"))
    x.clock.advance(minutes=5)
    x.tick()
    assert len(x.events("trading.senal_nueva")) == n
    y = System(find_signal_config())
    y.tick()
    assert y.cmd("signals", "senales") == []


def test_agregar_y_quitar_instrumento():
    x = System()
    x.cmd("engine-watch", "agregar", {"instrument": "eur/usd"})
    assert {i["name"] for i in x.cmd("engine-watch", "vigilados")} == {"EUR/USD"}
    assert x.cmd("engine-watch", "quitar", {"instrument": "EUR/USD"})["quitado"] is True
    with pytest.raises(ActionError):
        x.cmd("engine-watch", "agregar", {"instrument": "basura"})


def test_analizar_y_backtest_solo_leen():
    x = System()
    r = x.cmd("signals", "analizar", {"instrument": "USD/JPY"})
    assert r["verdict"] in ("OPERAR", "ESPERAR") and r["source"]["simulated"]
    b = x.cmd("backtest", "backtest", {"candles": 300})
    assert b["stats"] and any("SIMULADOS" in w for w in b["warnings"])
    assert x.cmd("engine-watch", "ordenes") == [] and not x.pending()
    with pytest.raises(ActionError):
        x.cmd("signals", "analizar", {"instrument": "XAU/USD"})


def test_config_invalida_no_monta_y_dice_cual():
    with pytest.raises(AssertionError) as e:
        System({"risk": {"risk_pct": 50}})
    assert "risk" in str(e.value)


def test_estado_avisa_si_el_real_cae_a_simulado(monkeypatch):
    monkeypatch.delenv("OANDA_API_TOKEN", raising=False)
    x = System({"data": {"adapter": "oanda"}, "broker": {"adapter": "oanda"}})
    e = x.cmd("engine-watch", "estado")
    assert e["broker_simulado"] is True and any("OANDA" in a for a in e["avisos"])


# --- adaptadores de broker (sin red: transporte falso)
def oanda(handler, **env):
    base = {"OANDA_API_TOKEN": "t", "OANDA_ACCOUNT_ID": "101-001-1-001"}
    return OandaBroker(env={**base, **env}, transport=httpx.MockTransport(handler))


def test_oanda_arma_la_orden_con_stop_y_objetivo():
    seen = {}

    def h(req):
        seen["url"], seen["body"], seen["auth"] = str(req.url), req.read().decode(), req.headers["authorization"]
        return httpx.Response(201, json={"orderFillTransaction": {"id": "9", "price": "150.12"}})
    f = oanda(h).place(Order("USD/JPY", "short", 1000, 150.5, 149.0, "s1"))
    assert "api-fxpractice.oanda.com" in seen["url"] and '"units":"-1000"' in seen["body"].replace(" ", "")
    assert "USD_JPY" in seen["body"] and "stopLossOnFill" in seen["body"] and seen["auth"] == "Bearer t"
    assert f.id == "9" and f.simulated is False


def test_oanda_rechazo_se_convierte_en_error_claro():
    with pytest.raises(BrokerError):
        oanda(lambda r: httpx.Response(400, json={"errorMessage": "x"})).place(Order("USD/JPY", "long", 5, 1, 2))
    with pytest.raises(BrokerError):
        oanda(lambda r: httpx.Response(201, json={"orderCancelTransaction": {"reason": "MARKET_HALTED"}})).place(
            Order("USD/JPY", "long", 5, 1, 2))


def test_la_cuenta_real_exige_permiso_explicito():
    env = {"OANDA_API_TOKEN": "t", "OANDA_ACCOUNT_ID": "a"}
    with pytest.raises(BrokerError, match="TRADING_ALLOW_LIVE"):
        OandaBroker(environment="live", env=env)
    OandaBroker(environment="live", env={**env, "TRADING_ALLOW_LIVE": "1"})


def test_sin_claves_el_broker_cae_al_simulado():
    b, note = make_broker("oanda", "practice", env={})
    assert isinstance(b, SimulatedBroker) and "simulado" in note
    f = b.place(Order("USD/JPY", "long", 10, 1, 2), price=1.5)
    assert b.positions()[0]["id"] == f.id and b.close(f.id)["closed"]
    with pytest.raises(BrokerError):
        b.close("nada")


def test_el_token_no_aparece_en_los_errores():
    with pytest.raises(BrokerError) as e:
        oanda(lambda r: httpx.Response(401, text="no autorizado")).place(Order("USD/JPY", "long", 5, 1, 2))
    assert "Bearer" not in str(e.value) and "t" != str(e.value)


def test_velas_de_oanda_ignoran_la_vela_en_curso():
    from raphael_trading.config import TradingConfig
    from raphael_trading.data import load_candles
    body = {"candles": [{"complete": True, "time": f"2026-11-25T{h:02d}:00:00.000000000Z", "volume": 5,
                         "mid": {"o": "150", "h": "151", "l": "149", "c": "150.5"}} for h in range(10)]
            + [{"complete": False, "time": "2026-11-25T10:00:00.000000000Z", "mid": {"o": "1", "h": "1", "l": "1", "c": "1"}}]}
    cfg = TradingConfig.model_validate({"data": {"adapter": "oanda"}})
    c, src = load_candles(cfg, cfg.watch.instruments[0], env={"OANDA_API_TOKEN": "t"},
                          transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    assert len(c) == 10 and not src.simulated and c[0].t < c[1].t


def test_aunque_la_instalacion_diga_automatico_no_se_ejecuta_sin_aprobacion():
    """El harness deja fijar el nivel por instalación (sin pisos); Trading igual se niega: regla de Damián."""
    auto = {"trading.ejecutar_orden": {"level": "automatico", "confirmed_by": "Damián"}}
    x = System(find_signal_config(), autonomy=auto)
    [sid, *_] = x.cmd("engine-watch", "escanear")["nuevas"]
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    assert x.cmd("engine-watch", "ordenes") == []


def test_sin_confirmacion_el_harness_no_baja_a_automatico():
    x = System(find_signal_config(), autonomy={"trading.ejecutar_orden": {"level": "automatico"}})
    [sid, *_] = x.cmd("engine-watch", "escanear")["nuevas"]
    x.cmd("engine-watch", "proponer", {"signal_id": sid})
    assert x.pending("ejecutar_orden") and x.cmd("engine-watch", "ordenes") == []
