"""Config de la brigada Contenido (va en `installation.brigades.contenido.config`). Todo es opcional: sin nada anda con valores
por defecto y avisa lo que falta. Las CLAVES nunca van acá: se leen del entorno (ver `entorno.py` y `.env.plantilla`).

    mode: auto | mock          # auto = real si están las claves; mock = todo simulado (resultados marcados "simulado")
    brand: {name: Taller Ejemplo, tone: voseo_emojis, audience: ..., topics: [...], hashtags: [...], avoid: [...]}
    video: {dir: "D:/Videos-Raphael"}
    instagram: {max_caption: 2200, max_hashtags: 30}
    campaigns: {currency: ARS, daily_budget_cap: 20000, objective: OUTCOME_AWARENESS}
    analytics: {insight_metrics: [reach, saved, shares]}
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TONES = ("voseo_emojis", "voseo_formal", "usted", "neutro")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Brand(_Base):
    name: str = Field("", max_length=120)
    tone: Literal["voseo_emojis", "voseo_formal", "usted", "neutro"] = "voseo_emojis"
    audience: str = Field("", max_length=300)
    topics: tuple[str, ...] = ()
    hashtags: tuple[str, ...] = ()        # los de siempre de la marca (sin #)
    avoid: tuple[str, ...] = ()           # palabras que la marca no usa


class VideoCfg(_Base):
    dir: str | None = None                # carpeta fija de trabajo; sin esto, VIDEO_EDIT_DIR o Documentos/Videos-Raphael


class InstagramCfg(_Base):
    max_caption: int = Field(2200, ge=1, le=2200)
    max_hashtags: int = Field(30, ge=0, le=30)


class CampaignsCfg(_Base):
    currency: str = Field("ARS", min_length=3, max_length=3)
    daily_budget_cap: float = Field(20000, gt=0)     # tope diario por borrador: más que esto ni se arma
    objective: str = "OUTCOME_AWARENESS"


class AnalyticsCfg(_Base):
    insight_metrics: tuple[str, ...] = ("reach", "saved", "shares")


class ContenidoConfig(_Base):
    mode: Literal["auto", "mock"] = "auto"
    brand: Brand = Brand()
    video: VideoCfg = VideoCfg()
    instagram: InstagramCfg = InstagramCfg()
    campaigns: CampaignsCfg = CampaignsCfg()
    analytics: AnalyticsCfg = AnalyticsCfg()


def contenido_config(raw: dict | None) -> ContenidoConfig:
    return ContenidoConfig.model_validate(raw or {})
