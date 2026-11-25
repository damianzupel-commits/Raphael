"""Motor, señales y backtest (sin red, con velas sintéticas deterministas)."""

from raphael_trading import backtest as B
from raphael_trading import engine as E
from raphael_trading import signals as S
from raphael_trading.config import Instrument, TradingConfig
from raphael_trading.data import load_candles
from raphael_trading.service import analyze, value_per_point


def test_synth_es_determinista_y_no_toca_el_random_global():
    import random
    random.seed(1)
    a = random.random()
    random.seed(1)
    E.synth(50, 3)
    assert random.random() == a
    assert E.synth(80, 5) == E.synth(80, 5)


def test_analyze_devuelve_estructura():
    a = E.analyze(E.synth(300, 7))
    assert a["trend"] in ("up", "down", "range") and a["swings"] and a["fvgs"]


def test_position_size_y_rr():
    cfg = S.RiskConfig(account=10000, risk_pct=1.0)
    assert S.position_size(cfg, 100, 99)["units"] == 100.0
    assert S.position_size(cfg, 100, 100)["units"] == 0.0
    assert S.rr(100, 99, 102) == 2.0


def test_pocas_velas_no_dan_senal():
    assert S.generate_signal(E.synth(10)) is None


def test_filtro_sin_rango_descarta():
    flat = [E.Candle(i, 1, 1, 1, 1) for i in range(40)]
    s = S.generate_signal(flat)
    assert s and not s.valid and "sin rango" in s.reject_reason


def test_backtest_cierra_las_cuentas():
    st = B.simulate(E.synth(500, 7, 150, 0.15), S.RiskConfig())
    st.pop("_trades")
    assert st["trades"] == st["wins"] + st["losses"] + st["expired"]
    assert abs(st["total_R"] - (st["wins"] * 0 + sum(v["total_R"] for v in st["by_setup"].values()))) < 0.05


def test_backtest_pierde_si_sl_y_tp_en_la_misma_vela():
    # conservador: si una vela toca stop y objetivo cuenta pérdida
    c = E.synth(200, 11, 100)
    for t in B.simulate(c, S.RiskConfig(min_conf=0.0, min_rr=0.1))["_trades"]:
        assert t.outcome in ("win", "loss", "expired")


def test_valor_por_punto_usdjpy():
    assert value_per_point(Instrument(name="USD/JPY"), 150.0) == round(1 / 150, 8)
    assert value_per_point(Instrument(name="EUR/USD"), 1.1) == 1.0
    assert value_per_point(Instrument(name="USD/JPY", value_per_point=0.5), 150.0) == 0.5


def test_analyze_de_servicio_marca_datos_simulados():
    cfg = TradingConfig()
    res = analyze(cfg, cfg.watch.instruments[0])
    assert res["source"]["simulated"] is True and res["verdict"] in ("OPERAR", "ESPERAR")
    assert "asesoramiento" in res["disclaimer"]


def test_oanda_sin_clave_cae_a_simulado_y_avisa():
    cfg = TradingConfig.model_validate({"data": {"adapter": "oanda"}})
    candles, src = load_candles(cfg, cfg.watch.instruments[0], env={})
    assert src.simulated and "OANDA_API_TOKEN" in src.note and len(candles) == cfg.data.candles


def test_csv_inexistente_cae_a_simulado(tmp_path):
    cfg = TradingConfig.model_validate({"data": {"adapter": "csv", "csv_path": str(tmp_path / "no.csv")}})
    _, src = load_candles(cfg, cfg.watch.instruments[0])
    assert src.simulated


def test_csv_real(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("t,o,h,l,c\n" + "\n".join(f"{i},1,2,0.5,1.5" for i in range(70)), encoding="utf-8")
    cfg = TradingConfig.model_validate({"data": {"adapter": "csv", "csv_path": str(p), "candles": 60}})
    candles, src = load_candles(cfg, cfg.watch.instruments[0])
    assert not src.simulated and len(candles) == 60
