"""Lo que necesitan las partes de la brigada para trabajar, sin depender de si las llama un cocinero (con `Context`),
una tool (con el `SetupContext` del montaje) o un test: el espacio de datos, la config, el reloj, el modelo y la red.

La red y el entorno van inyectables: los tests corren con el adaptador simulado y sin claves reales.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from raphael_core.store import Space

from .config import InvestigacionConfig, investigacion_config

#: una función que hace un GET y devuelve (status, texto). Default: urllib. Los tests inyectan una simulada.
HttpGet = Callable[[str, dict[str, str], dict[str, str]], tuple[int, str]]
#: una función que llama al modelo: (parte, mensajes) -> texto o None
Ask = Callable[[str, list[dict]], "str | None"]


def _now() -> datetime:
    return datetime.now()  # noqa: DTZ005 - mismo reloj ingenuo que el harness (Runtime usa datetime.now)


@dataclass
class Env:
    space: Space
    config: InvestigacionConfig = field(default_factory=InvestigacionConfig)
    now: Callable[[], datetime] = _now
    ask: Ask | None = None                    # None = sin modelo: la brigada sigue con reglas y lo dice
    http_get: HttpGet | None = None           # None = urllib
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    publish: Callable[[str, dict], None] | None = None
    record: Callable[..., None] | None = None
    notes: list[str] = field(default_factory=list)

    def iso(self) -> str:
        return self.now().isoformat(timespec="seconds")

    def event(self, name: str, data: dict) -> None:
        if self.publish is not None:
            self.publish(name, data)

    def audit(self, what: str, **data: Any) -> None:
        if self.record is not None:
            self.record(what, **data)


def env_from_context(ctx: Any, **over: Any) -> Env:
    """Un `Env` desde el `Context` de un cocinero (o el `SetupContext` del montaje, que tiene menos cosas)."""
    now = getattr(ctx, "now", None)
    publish = getattr(ctx, "publish", None)
    record = getattr(ctx, "record", None)
    ask = None
    if hasattr(ctx, "ai"):
        def ask(part: str, messages: list[dict]) -> str | None:   # noqa: E306
            cfg = investigacion_config(ctx.config)
            return ctx.ai("cocinero", messages, private=cfg.is_private(part))
    kw: dict[str, Any] = {"space": ctx.shared, "config": investigacion_config(ctx.config), "ask": ask,
                          "publish": publish, "record": record}
    if callable(now):
        kw["now"] = now
    kw.update(over)
    return Env(**kw)
