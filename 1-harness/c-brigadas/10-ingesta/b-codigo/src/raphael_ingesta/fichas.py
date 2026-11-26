"""Fichas de las fuentes públicas aprobadas por Damián (2026-11-26): qué es cada una, cómo se la trata y qué hay que citar.

Cada ficha sale de leer las condiciones oficiales de la fuente. Lo que la página no decía NO se afirma acá: queda como
`nota`. Todo lo que se trae se guarda como título, resumen y metadatos con enlace al original y crédito: nunca el texto
completo de un artículo ni un PDF. Quedaron AFUERA por sus términos: Al Jazeera, BBC, FMI y SIPRI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ficha:
    id: str
    nombre: str
    alias: tuple[str, ...]  # cómo la nombra la persona en un mensaje
    tipo: str  # rss | json
    consulta: str  # qué se trae si la persona no dice otra cosa (se ajusta en la config: `fuentes_consultas`)
    credito: str  # línea de crédito que lleva cada nota
    pausa: float  # segundos mínimos entre pedidos a esta fuente
    claves: tuple[str, ...] = ()  # variables de entorno OBLIGATORIAS (si faltan, no se llama a la red)
    nota: str = ""  # lo que hay que saber de sus condiciones
    listo: bool = True  # False = todavía no hay adaptador


FICHAS: dict[str, Ficha] = {
    f.id: f
    for f in (
        Ficha(
            "openalex",
            "OpenAlex",
            ("openalex",),
            "json",
            "armed conflict economics",
            "Datos: OpenAlex (CC0).",
            0.2,
            nota="CC0. Sin clave para lo básico (10 pedidos/s); clave gratis opcional en OPENALEX_API_KEY.",
        ),
        Ficha(
            "arxiv",
            "arXiv",
            ("arxiv",),
            "json",
            "",
            "Metadatos: arXiv (CC0). Texto completo en arxiv.org.",
            3.0,
            nota="Ya la cubre el cocinero de arXiv (1 pedido cada 3 s, una sola conexión).",
            listo=False,
        ),
        Ficha(
            "crossref",
            "Crossref",
            ("crossref",),
            "json",
            "armed conflict economics",
            "Metadatos: Crossref.",
            0.4,
            nota="Sin clave; se identifica con INGESTA_CONTACTO_EMAIL (grupo 'polite'). La licencia de los metadatos no figura "
            "en las páginas que se leyeron.",
        ),
        Ficha(
            "gdelt",
            "GDELT",
            ("gdelt",),
            "json",
            "war OR conflict OR sanctions",
            "Fuente: GDELT Project (https://www.gdeltproject.org).",
            5.0,
            nota="Uso libre, incluso comercial, citando a GDELT con un enlace. Límites de pedidos: no figuran; 5 s es prudencia "
            "nuestra. Solo título, dominio y enlace: nada del artículo.",
        ),
        Ficha(
            "fed",
            "Reserva Federal",
            ("reserva federal", "la fed"),
            "rss",
            "press_all.xml",
            "Fuente: Board of Governors of the Federal Reserve System (federalreserve.gov).",
            2.0,
            nota="RSS en federalreserve.gov/feeds/. Términos de reutilización de los feeds: no figuran.",
        ),
        Ficha(
            "fred",
            "FRED",
            ("fred",),
            "json",
            "FEDFUNDS",
            "Datos: FRED®, Federal Reserve Bank of St. Louis. Este producto usa la API de FRED® pero no está avalado ni "
            "certificado por la Reserva Federal de St. Louis.",
            1.0,
            ("FRED_API_KEY",),
            nota="Clave obligatoria. Las series con 'Copyright' en sus notas son solo para uso personal. "
            "Límite de pedidos: no figura.",
        ),
        Ficha(
            "bancomundial",
            "Banco Mundial",
            ("banco mundial", "world bank"),
            "json",
            "WLD/NY.GDP.MKTP.CD",
            "The World Bank: Indicadores de desarrollo (CC BY 4.0), https://data.worldbank.org.",
            1.0,
            nota="CC BY 4.0 con atribución; no insinuar aval del Banco. "
            "Algunas series pueden tener términos propios (ver metadatos).",
        ),
        Ficha(
            "reliefweb",
            "ReliefWeb",
            ("reliefweb",),
            "json",
            "conflict",
            "Fuente: ReliefWeb (OCHA), contenido CC BY 4.0 salvo que se indique otra cosa; el material puede ser de sus fuentes "
            "originales.",
            1.0,
            ("RELIEFWEB_APPNAME",),
            nota="Hace falta un appname pedido por formulario. Cuota: no figura.",
        ),
        Ficha(
            "ucdp",
            "UCDP",
            ("ucdp",),
            "json",
            "gedevents",
            "Datos: Uppsala Conflict Data Program (UCDP).",
            1.0,
            ("UCDP_TOKEN",),
            nota="Token gratis pedido por mail; 5.000 pedidos por día (los errores cuentan). Licencia: no figura; citar a UCDP.",
        ),
        Ficha(
            "mit",
            "MIT News",
            ("mit news", "mit"),
            "rss",
            "research",
            "Fuente: MIT News (news.mit.edu).",
            2.0,
            nota="RSS en news.mit.edu/rss/<sección>. Términos de reutilización del feed: no figuran.",
        ),
        Ficha(
            "harvard",
            "Harvard Gazette",
            ("harvard",),
            "rss",
            "feed/",
            "Fuente: The Harvard Gazette (news.harvard.edu/gazette).",
            2.0,
            nota="RSS en news.harvard.edu/gazette/. Términos de reutilización: no figuran.",
        ),
        Ficha(
            "oecd",
            "OECD",
            ("oecd", "ocde"),
            "json",
            "",
            "Datos: OECD (citar con la cita del dataset).",
            1.0,
            nota="Se puede copiar y usar citando a la OECD. Falta el adaptador (SDMX).",
            listo=False,
        ),
    )
}


def ficha_de(ref: str) -> tuple[Ficha, str]:
    """('openalex:guerra y economía') -> (ficha, 'guerra y economía'). Levanta ValueError si la fuente no existe."""
    fid, _, q = (ref or "").partition(":")
    fid = fid.strip().lower()
    if fid not in FICHAS:
        raise ValueError(f"fuente desconocida «{fid}» (válidas: {', '.join(FICHAS)})")
    return FICHAS[fid], q.strip()
