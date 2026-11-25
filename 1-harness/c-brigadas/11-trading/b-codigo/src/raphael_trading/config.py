"""Config de la brigada (lo que va en `installation.yaml` bajo `brigades.trading.config`).

Las CLAVES no van acá: se leen de variables de entorno (ver `.env.plantilla`). Sin clave, cada adaptador real cae al
simulado y lo avisa: nunca inventa datos de mercado ni opera.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Instrument(_Base):
    name: str = "USD/JPY"
    timeframe: str = "1h"
    value_per_point: float | None = None   # USD por punto y por unidad; vacío = se calcula (XXX/JPY: 1/precio; otros: 1)
    sim_start: float = 150.0       # precio de arranque del simulado
    sim_scale: float = 0.15        # volatilidad del simulado


class Risk(_Base):
    account: float = Field(10000.0, gt=0)
    risk_pct: float = Field(1.0, gt=0, le=5)        # % de la cuenta por operación
    max_risk_pct: float = Field(2.0, gt=0, le=5)    # techo duro: aunque se edite la orden al aprobar
    min_rr: float = Field(2.0, gt=0)
    min_conf: float = Field(0.6, ge=0, le=1)
    max_orders_per_day: int = Field(3, ge=0)
    signal_ttl_minutes: int = Field(120, ge=1)      # una señal vieja ya no se ejecuta


class Data(_Base):
    adapter: str = Field("simulado", pattern="^(simulado|csv|oanda)$")
    csv_path: str = ""                               # para adapter=csv: columnas t,o,h,l,c[,v]
    candles: int = Field(300, ge=60, le=5000)
    sim_seed: int | None = None                      # semilla del simulado (vacío = una por instrumento)


class Broker(_Base):
    adapter: str = Field("simulado", pattern="^(simulado|oanda)$")
    environment: str = Field("practice", pattern="^(practice|live)$")   # real exige además TRADING_ALLOW_LIVE=1


class Watch(_Base):
    enabled: bool = False                            # vigilancia automática (tick). Apagada por defecto
    interval_minutes: int = Field(30, ge=5)
    instruments: list[Instrument] = Field(default_factory=lambda: [Instrument()])
    propose_automatically: bool = False              # si es true, cada señal válida deja un pendiente de aprobación


class TradingConfig(_Base):
    risk: Risk = Risk()
    data: Data = Data()
    broker: Broker = Broker()
    watch: Watch = Watch()


def trading_config(raw: dict | None) -> TradingConfig:
    return TradingConfig.model_validate(raw or {})
