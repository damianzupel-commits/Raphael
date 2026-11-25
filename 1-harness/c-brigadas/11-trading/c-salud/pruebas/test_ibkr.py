"""Adaptador de Interactive Brokers con un `ib_async` FALSO (no hay IB real todavía): verifica qué se le pide a IB."""

from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest

from raphael_trading.broker import BrokerError, IbkrBroker, Order, SimulatedBroker, make_broker
from raphael_trading.config import TradingConfig
from raphael_trading.data import load_candles
from raphael_trading.ibkr import IbkrError, IbkrSession, IbkrSettings, fetch_candles


class FakeIB:
    def __init__(self, accounts=("DU123456",), connect_error=None, status="Filled"):
        self.accounts, self.connect_error, self.status = list(accounts), connect_error, status
        self.placed, self.connected, self.client = [], False, NS(getReqId=lambda: 100)
        self.pos = [NS(contract=NS(symbol="USD", currency="JPY"), position=1000.0, avgCost=150.0)]
        self.hist_args = None

    def connect(self, host, port, clientId, readonly, timeout):
        if self.connect_error:
            raise self.connect_error
        self.connected, self.conn = True, (host, port, clientId, readonly)

    def isConnected(self): return self.connected
    def disconnect(self): self.connected = False
    def managedAccounts(self): return self.accounts
    def qualifyContracts(self, c): return [c]
    def sleep(self, s): pass

    def placeOrder(self, contract, order):
        self.placed.append((contract, order))
        return NS(orderStatus=NS(status=self.status, avgFillPrice=150.25))

    def positions(self): return self.pos

    def reqHistoricalData(self, contract, **kw):
        self.hist_args = (contract, kw)
        bars = [NS(date=datetime(2026, 11, 24, h, tzinfo=UTC), open=150, high=151, low=149, close=150.5, volume=7)
                for h in range(12)]
        return bars + [NS(date=datetime(2026, 11, 25, 0, tzinfo=UTC), open=1, high=1, low=1, close=1, volume=0)]


def make_api(ib):
    def order(kind):
        def build(action, qty, *price, **kw):
            return NS(kind=kind, action=action, qty=qty, price=price[0] if price else None, account="", **kw)
        return build
    return NS(IB=lambda: ib, Forex=lambda s: NS(symbol=s[:3], currency=s[3:]), MarketOrder=order("MKT"),
              LimitOrder=order("LMT"), StopOrder=order("STP"))


def session(ib=None, **kw):
    ib = ib or FakeIB()
    return IbkrSession(IbkrSettings(**kw), api=make_api(ib)), ib


def test_la_orden_sale_a_mercado_con_stop_y_objetivo_colgados():
    s, ib = session()
    f = IbkrBroker(s).place(Order("USD/JPY", "long", 1000.4, 149.5, 151.0, "sig1"), price=150.0)
    parent, tp, sl = (o for _, o in ib.placed)
    assert (parent.kind, parent.action, parent.qty, parent.transmit) == ("MKT", "BUY", 1000, False)
    assert (tp.kind, tp.action, tp.price, tp.parentId, tp.transmit) == ("LMT", "SELL", 151.0, 100, False)
    assert (sl.kind, sl.action, sl.price, sl.parentId, sl.transmit) == ("STP", "SELL", 149.5, 100, True)
    assert ib.placed[0][0].symbol == "USD" and ib.placed[0][0].currency == "JPY"
    assert ib.conn == ("127.0.0.1", 4002, 7, False)
    assert f.id == "100" and f.price == 150.25 and f.simulated is False and f.broker == "ibkr"


def test_corto_vende_al_entrar():
    s, ib = session()
    IbkrBroker(s).place(Order("USD/JPY", "short", 500, 151.0, 149.0, "x"))
    assert ib.placed[0][1].action == "SELL" and ib.placed[1][1].action == "BUY"


def test_orden_cancelada_por_ib_es_error():
    s, _ = session(FakeIB(status="Cancelled"))
    with pytest.raises(BrokerError, match="no aceptó"):
        IbkrBroker(s).place(Order("USD/JPY", "long", 10, 1, 2))


def test_cuenta_real_en_sesion_demo_se_niega():
    s, ib = session(FakeIB(accounts=("U9999999",)))
    with pytest.raises(BrokerError, match="NO es demo"):
        IbkrBroker(s).place(Order("USD/JPY", "long", 10, 1, 2))
    assert ib.placed == []


def test_sin_tws_abierto_explica_que_hacer():
    s, _ = session(FakeIB(connect_error=ConnectionRefusedError()))
    with pytest.raises(BrokerError, match="TWS/IB Gateway"):
        IbkrBroker(s).place(Order("USD/JPY", "long", 10, 1, 2))


def test_posiciones_y_cierre():
    s, ib = session()
    b = IbkrBroker(s)
    assert b.positions()[0]["id"] == "USDJPY"
    assert b.close("USDJPY")["closed"] and ib.placed[-1][1].action == "SELL" and ib.placed[-1][1].qty == 1000
    with pytest.raises(BrokerError):
        b.close("EURUSD")


def test_la_cuenta_real_exige_permiso_explicito():
    with pytest.raises(IbkrError, match="TRADING_ALLOW_LIVE"):
        IbkrSettings.from_env("live", {})
    assert IbkrSettings.from_env("live", {"TRADING_ALLOW_LIVE": "1"}).port == 4001
    assert IbkrSettings.from_env("practice", {"IBKR_PORT": "7497"}).port == 7497
    with pytest.raises(IbkrError):
        IbkrSettings.from_env("practice", {"IBKR_PORT": "abc"})


def test_velas_de_ibkr_descartan_la_barra_en_curso():
    s, ib = session()
    c = fetch_candles(s, "USD/JPY", "1h", 8)
    assert len(c) == 8 and c[0].t < c[-1].t and c[-1].c == 150.5
    assert ib.hist_args[1]["whatToShow"] == "MIDPOINT" and ib.hist_args[1]["barSizeSetting"] == "1 hour"


def test_datos_ibkr_sin_conexion_caen_a_simulado_y_avisan():
    s, _ = session(FakeIB(connect_error=ConnectionRefusedError()))
    cfg = TradingConfig.model_validate({"data": {"adapter": "ibkr"}})
    candles, src = load_candles(cfg, cfg.watch.instruments[0], ibkr_session=s)
    assert src.simulated and "IBKR" in src.note and candles


def test_datos_ibkr_reales():
    s, _ = session()
    cfg = TradingConfig.model_validate({"data": {"adapter": "ibkr", "candles": 60}})
    candles, src = load_candles(cfg, cfg.watch.instruments[0], ibkr_session=s)
    assert src.kind == "ibkr" and not src.simulated and len(candles) == 12


def test_make_broker_ibkr_sin_libreria_cae_a_simulado(monkeypatch):
    import raphael_trading.ibkr as m
    monkeypatch.setattr(m, "available", lambda: False)
    b, note = make_broker("ibkr", "practice", env={})
    assert isinstance(b, SimulatedBroker) and "ib_async" in note
    s, _ = session()
    assert isinstance(make_broker("ibkr", "practice", ibkr_session=s)[0], IbkrBroker)
