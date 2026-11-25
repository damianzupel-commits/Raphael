"""Config del negocio: lo único que cambia de una clienta a otra (va en `installation.brigades.empresas.config`).

Reemplaza al `perfil.yaml` de Empresas 0.4 (sin `plan`, `brigadas`, `politicas` ni `limites`: eso es de la
instalación). El cargador del harness valida la forma con el `config_schema` del manifiesto; acá se valida el
contenido (rangos, pasos conocidos) y se arman los valores por defecto.

    business: {name: Taller Ejemplo, owner: Ana}
    info: {hours: ..., shipping: ..., payment_methods: [transferencia], location: ..., faq: [{question, answer, keywords}]}
    payments: {deposit_pct: 50, alias: taller.ejemplo, holder: Ana Pérez}
    orders: {required_steps: [...], urgent_if_days_under: 15, prices: [{item, base, days}], surcharges: [{word, kind, value}]}
    schedule: {reminder_days_before: 3, slots: ["jueves de 16 a 19"]}
    store: {source: {kind: feed, url: https://..., format: json}, refresh_minutes: 60, low_stock: 2}
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ORDER_STEPS = ["prenda", "ocasion", "fecha", "detalles", "referencias", "medidas", "nombre"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Business(_Base):
    name: str = Field("", max_length=120)
    owner: str = Field("", max_length=80)          # cómo se nombra a la dueña en los mensajes a clientes
    tone: Literal["voseo_emojis", "voseo_formal", "usted"] = "voseo_emojis"


class Faq(_Base):
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=1000)
    keywords: tuple[str, ...] = ()


class Info(_Base):
    """Lo único que el bot puede afirmar. Lo que no está acá, no lo dice."""

    hours: str = ""
    shipping: str = ""
    payment_methods: tuple[str, ...] = ()
    location: str = ""
    faq: tuple[Faq, ...] = ()


class MercadoPagoCfg(_Base):
    """Mercado Pago. Las claves NO van acá: `token_env` y `secret_env` nombran variables de entorno (`raphael.env`).
    `mode`: off (sin Mercado Pago) · mock (simulado, sin cuenta) · real (con el access token de la dueña)."""

    mode: Literal["off", "mock", "real"] = "off"
    token_env: str = Field("MP_ACCESS_TOKEN", pattern=r"^[A-Z][A-Z0-9_]{0,59}$")
    secret_env: str = Field("MP_WEBHOOK_SECRET", pattern=r"^[A-Z][A-Z0-9_]{0,59}$")
    notification_url: str = ""                               # https://<servidor>/webhook/mercadopago
    back_url: str = ""                                       # a dónde vuelve el cliente después de pagar
    expires_hours: int = Field(48, ge=1, le=24 * 30)

    @field_validator("notification_url", "back_url")
    @classmethod
    def _https(cls, v: str) -> str:
        if v and not v.startswith("https://"):
            raise ValueError("tiene que empezar con https://")
        return v


class Payments(_Base):
    """Cobros de la seña: transferencia (datos de la cuenta; confirma la dueña a mano) y/o Mercado Pago."""

    deposit_pct: float = Field(50, ge=0, le=100)
    alias: str = ""
    holder: str = ""
    cbu: str = Field("", pattern=r"^(\d{22})?$")              # CBU/CVU, 22 dígitos
    bank: str = Field("", max_length=80)
    mercadopago: MercadoPagoCfg = MercadoPagoCfg()


class Price(_Base):
    item: str = Field(min_length=1)
    base: float = Field(gt=0)
    days: int | None = Field(None, ge=0)


class Surcharge(_Base):
    word: str = Field(min_length=1)
    kind: Literal["pct", "amount"]
    value: float


class Orders(_Base):
    required_steps: tuple[str, ...] = tuple(ORDER_STEPS)
    urgent_if_days_under: int = Field(15, ge=0)
    prices: tuple[Price, ...] = ()
    surcharges: tuple[Surcharge, ...] = ()

    @field_validator("required_steps")
    @classmethod
    def _steps(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        bad = [s for s in v if s not in ORDER_STEPS]
        if bad:
            raise ValueError(f"pasos desconocidos: {bad}. Válidos: {ORDER_STEPS}")
        return v if "nombre" in v else (*v, "nombre")        # el nombre se pide siempre


class Schedule(_Base):
    reminder_days_before: int = Field(3, ge=0)
    slots: tuple[str, ...] = ()


class Source(_Base):
    """De dónde sale el catálogo. Los tokens NO van acá: `token_env` y `secret_env` nombran variables de entorno."""

    kind: Literal["none", "feed", "tiendanube", "shopify", "woocommerce"] = "none"
    url: str = ""                                            # feed: el JSON o CSV · woocommerce: https:// del sitio
    format: Literal["json", "csv"] = "json"
    fields: dict[str, str] = Field(default_factory=dict)     # feed: campo nuestro -> campo del feed
    store_id: str = ""                                       # tiendanube: número de tienda
    contact: str = ""                                        # tiendanube: mail o web para el User-Agent (lo exige la API)
    shop: str = ""                                           # shopify: tu-tienda.myshopify.com
    api_version: str = ""                                    # shopify: por ejemplo 2026-07
    token_env: str = Field("", pattern=r"^([A-Z][A-Z0-9_]{0,59})?$")
    secret_env: str = Field("", pattern=r"^([A-Z][A-Z0-9_]{0,59})?$")

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        if v and not v.startswith(("https://", "http://")):
            raise ValueError("la URL del catálogo tiene que empezar con https:// (o http:// en pruebas)")
        return v


class Store(_Base):
    source: Source = Source()
    public_url: str = ""                                     # la tienda web, para pasarle el link al cliente
    refresh_minutes: int = Field(60, ge=5, le=24 * 60)
    low_stock: int = Field(2, ge=0)
    max_products: int = Field(2000, ge=1, le=20000)

    @field_validator("public_url")
    @classmethod
    def _public(cls, v: str) -> str:
        if v and not v.startswith(("https://", "http://")):
            raise ValueError("el link de la tienda tiene que empezar con https://")
        return v


class BusinessConfig(_Base):
    business: Business = Business()
    info: Info = Info()
    payments: Payments = Payments()
    orders: Orders = Orders()
    schedule: Schedule = Schedule()
    store: Store = Store()


_CACHE: dict[str, BusinessConfig] = {}


def business_config(raw: dict | None) -> BusinessConfig:
    """La config validada (con caché por contenido: el contexto la devuelve como dict en cada llamada)."""
    key = repr(sorted((raw or {}).items()))
    cfg = _CACHE.get(key)
    if cfg is None:
        cfg = BusinessConfig.model_validate(raw or {})
        if len(_CACHE) > 32:
            _CACHE.clear()
        _CACHE[key] = cfg
    return cfg


def of(ctx: Any) -> BusinessConfig:
    return business_config(ctx.config)


def business_name(ctx: Any) -> str:
    return of(ctx).business.name or "el negocio"


def decider(ctx: Any) -> str:
    """Cómo se nombra, ante los clientes, a la persona que decide."""
    cfg = of(ctx)
    return cfg.business.owner or getattr(ctx.identity, "user", "") or cfg.business.name or "la persona a cargo"
