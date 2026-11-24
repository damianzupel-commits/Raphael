"""Tool `web_scrape` — extracción de contenido web robusta con Scrapling.

Scrapling (https://github.com/D4Vinci/Scrapling, BSD-3) es un framework de scraping
que **aguanta cambios de diseño** (su parser reubica los elementos cuando la página
cambia, con `adaptive=True`) y trae fetchers que bypassean anti-bot (Cloudflare, etc.).

Se agregó (2026-09-27) como tool del agente para traer datos de la web de forma
confiable: noticias/calendarios (trading), fuentes del war tracker, OSINT en Raphael.
ADITIVO. Import perezoso: si Scrapling no está instalado, la tool devuelve un error
claro sin romper el backend. No es para reconocimiento ofensivo de terceros.

Instalación (en la PC): `pip install scrapling` (y `scrapling install` para los
modos 'stealth'/'dynamic', que usan Playwright).
"""

from __future__ import annotations

from . import register_tool


@register_tool(
    name="web_scrape",
    description=(
        "Extrae contenido de una página web de forma ROBUSTA usando Scrapling (aguanta "
        "cambios de diseño del sitio). Modos: 'fast' (HTTP simple, default), 'stealth' "
        "(bypassea anti-bot tipo Cloudflare) y 'dynamic' (sitios con mucho JavaScript, vía "
        "navegador/Playwright). Si pasás un `selector` CSS, devuelve los elementos que "
        "matchean (con auto-reubicación adaptativa); si no, devuelve el texto plano de la "
        "página. Usalo para traer datos públicos (noticias, precios, calendarios, OSINT), "
        "NO para nada ofensivo contra terceros. Requiere 'pip install scrapling' en la PC "
        "(y 'scrapling install' para stealth/dynamic); si no está, te avisa con un error claro."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL a scrapear (http/https)."},
            "selector": {
                "type": "string",
                "description": (
                    "Selector CSS opcional (ej. '.quote .text::text', 'a::attr(href)', "
                    "'h2'). Si se pasa, se devuelven los matches (con adaptación a cambios "
                    "de diseño). Si se omite, se devuelve el texto completo de la página."
                ),
            },
            "mode": {
                "type": "string",
                "enum": ["fast", "stealth", "dynamic"],
                "description": (
                    "'fast' (default): request HTTP, rápido. 'stealth': bypass de anti-bot "
                    "(Cloudflare Turnstile, etc.). 'dynamic': navegador real para sitios con JS."
                ),
            },
            "max_chars": {
                "type": "integer",
                "description": "Tope de caracteres del texto devuelto (default 8000).",
            },
        },
        "required": ["url"],
    },
)
def web_scrape(url: str, selector: str | None = None, mode: str = "fast",
               max_chars: int = 8000) -> dict:
    try:
        from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher
    except ImportError:
        return {
            "error": (
                "Scrapling no está instalado. En la PC: `pip install scrapling` "
                "(y `scrapling install` para los modos stealth/dynamic)."
            )
        }

    # traer la página con el fetcher del modo pedido
    try:
        if mode == "stealth":
            page = StealthyFetcher.fetch(url)
        elif mode == "dynamic":
            page = DynamicFetcher.fetch(url)
        else:
            page = Fetcher.get(url)
    except Exception as exc:  # noqa: BLE001 -- red/anti-bot pueden fallar; error claro al agente
        return {"error": f"fetch falló ({mode}): {exc!r}"}

    status = getattr(page, "status", None)

    # con selector -> devolver los elementos que matchean (adaptativo)
    if selector:
        try:
            matches = page.css(selector, adaptive=True)
            items = []
            for m in list(matches)[:60]:
                if hasattr(m, "get_all_text"):
                    items.append(m.get_all_text().strip())
                elif hasattr(m, "get"):
                    items.append(str(m.get()).strip())
                else:
                    items.append(str(m).strip())
            return {"url": url, "status": status, "selector": selector,
                    "matches": len(items), "items": [i for i in items if i][:60]}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"el selector falló: {exc!r}"}

    # sin selector -> texto plano
    try:
        text = page.get_all_text() if hasattr(page, "get_all_text") else str(page)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"no pude extraer texto: {exc!r}"}
    text = text or ""
    return {
        "url": url, "status": status,
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "total_chars": len(text),
    }
