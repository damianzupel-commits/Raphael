"""Navegador automatizado. Portado de `tools/browser.py` (Playwright) y de la parte de navegador de `web_login`.

Una sola página viva entre llamadas (se abre la primera vez que se usa), para poder hacer abrir → clic → leer en varios
turnos sin perder el estado. Playwright se importa perezosamente: sin él, el adaptador real avisa y el resto sigue.

`channel` vacío usa el Chromium de Playwright. En la PC de Damián el Chromium propio no arrancaba (Windows no activaba su
manifiesto, WinError 14001) y el Edge del sistema sí: por eso el paso del LIENZO sugiere `OPERACIONES_NAVEGADOR_CANAL=msedge`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from . import AdapterUnavailable

MAX_TEXT_CHARS = 8000
LOGIN_USER_SELECTORS = ["input[type=email]", "input[name*=user i]", "input[name*=email i]", "input[id*=user i]",
                        "input[id*=email i]", "input[autocomplete=username]"]
LOGIN_PASS_SELECTORS = ["input[type=password]", "input[name*=pass i]", "input[id*=pass i]",
                        "input[autocomplete=current-password]"]
LOGIN_SUBMIT_SELECTORS = ["button[type=submit]", "input[type=submit]", "button:has-text('Log in')",
                          "button:has-text('Sign in')", "button:has-text('Iniciar')", "button:has-text('Ingresar')"]


class BrowserDriver(Protocol):
    async def open(self, url: str) -> dict: ...
    async def click(self, selector: str) -> dict: ...
    async def type(self, selector: str, text: str, submit: bool) -> dict: ...
    async def select_option(self, selector: str, value: str) -> dict: ...
    async def get_text(self, selector: str) -> dict: ...
    async def screenshot(self, path: Path) -> dict: ...
    async def login(self, url: str, username: str, password: str, user_selector: str, pass_selector: str,
                    submit_selector: str, confirm: bool, preview: Path) -> dict: ...
    async def close(self) -> dict: ...


class MockBrowser:
    """Un navegador de mentira: páginas en memoria (`pages = {url: {"title", "text"}}`) y un registro de lo que se hizo."""

    def __init__(self, pages: dict[str, dict] | None = None) -> None:
        self.pages = dict(pages or {})
        self.url: str | None = None
        self.calls: list[tuple[str, dict]] = []
        self.typed: dict[str, str] = {}

    def _page(self) -> dict:
        if self.url is None:
            raise AdapterUnavailable("No hay ninguna página abierta: primero hay que abrir una URL.")
        return self.pages.get(self.url, {"title": self.url, "text": ""})

    async def open(self, url: str) -> dict:
        self.calls.append(("open", {"url": url}))
        self.url = url
        return {"url": url, "title": self._page().get("title", url), "simulated": True}

    async def click(self, selector: str) -> dict:
        self._page()
        self.calls.append(("click", {"selector": selector}))
        return {"clicked": selector, "url": self.url, "simulated": True}

    async def type(self, selector: str, text: str, submit: bool) -> dict:
        self._page()
        self.typed[selector] = text
        self.calls.append(("type", {"selector": selector, "typed_chars": len(text), "submit": submit}))
        return {"selector": selector, "submitted": submit, "simulated": True}

    async def select_option(self, selector: str, value: str) -> dict:
        self._page()
        self.calls.append(("select_option", {"selector": selector, "value": value}))
        return {"selector": selector, "selected": [value], "simulated": True}

    async def get_text(self, selector: str) -> dict:
        text = str(self._page().get("text", ""))
        self.calls.append(("get_text", {"selector": selector}))
        return {"text": text[:MAX_TEXT_CHARS], "truncated": len(text) > MAX_TEXT_CHARS, "simulated": True}

    async def screenshot(self, path: Path) -> dict:
        self._page()
        self.calls.append(("screenshot", {"path": str(path)}))
        return {"screenshot_path": str(path), "simulated": True}

    async def login(self, url: str, username: str, password: str, user_selector: str, pass_selector: str,
                    submit_selector: str, confirm: bool, preview: Path) -> dict:
        self.url = url
        self.calls.append(("login", {"url": url, "username": username, "confirm": confirm}))   # la clave no queda
        if not confirm:
            return {"logged_in": False, "dry_run": True, "url": url, "preview": str(preview), "simulated": True,
                    "message": "Dejé los campos cargados y no envié nada. Confirmá para iniciar sesión."}
        return {"logged_in": True, "url": url, "simulated": True}

    async def close(self) -> dict:
        self.calls.append(("close", {}))
        self.url = None
        return {"closed": True, "simulated": True}


class RealBrowser:
    """Playwright de verdad. Una página viva, lanzada la primera vez."""

    def __init__(self, headless: bool = True, channel: str = "") -> None:
        self.headless, self.channel = headless, channel
        self._pw: Any = None
        self._browser: Any = None
        self._page: Any = None

    async def _ensure_page(self) -> Any:
        if self._page is not None and not self._page.is_closed():
            return self._page
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise AdapterUnavailable("Falta Playwright. En la PC: pip install playwright (extra 'navegador' del paquete) "
                                     "y, si usás el Chromium propio, playwright install chromium.") from None
        try:
            if self._pw is None:
                self._pw = await async_playwright().start()
            if self._browser is None:
                kw: dict = {"headless": self.headless}
                if self.channel:
                    kw["channel"] = self.channel
                self._browser = await self._pw.chromium.launch(**kw)
            context = await self._browser.new_context()
            self._page = await context.new_page()
        except Exception as exc:  # noqa: BLE001
            raise AdapterUnavailable(f"No se pudo abrir el navegador: {exc}. Probá OPERACIONES_NAVEGADOR_CANAL=msedge "
                                     "(usa el Edge del sistema).") from exc
        return self._page

    async def open(self, url: str) -> dict:
        page = await self._ensure_page()
        await page.goto(url, wait_until="domcontentloaded")
        return {"url": page.url, "title": await page.title()}

    async def click(self, selector: str) -> dict:
        page = await self._ensure_page()
        await page.click(selector, timeout=5000)
        return {"clicked": selector, "url": page.url}

    async def type(self, selector: str, text: str, submit: bool) -> dict:
        page = await self._ensure_page()
        await page.fill(selector, text, timeout=5000)
        if submit:
            await page.press(selector, "Enter")
        return {"selector": selector, "submitted": submit}

    async def select_option(self, selector: str, value: str) -> dict:
        from playwright.async_api import Error as PlaywrightError
        page = await self._ensure_page()
        try:
            selected = await page.select_option(selector, value=value, timeout=5000)
        except PlaywrightError:   # si no coincide el value, se reintenta por el texto visible
            selected = await page.select_option(selector, label=value, timeout=5000)
        return {"selector": selector, "selected": selected}

    async def get_text(self, selector: str) -> dict:
        page = await self._ensure_page()
        text = await page.inner_text(selector, timeout=5000)
        return {"text": text[:MAX_TEXT_CHARS], "truncated": len(text) > MAX_TEXT_CHARS}

    async def screenshot(self, path: Path) -> dict:
        page = await self._ensure_page()
        path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(path))
        return {"screenshot_path": str(path)}

    async def _first(self, page: Any, selectors: list[str]) -> str | None:
        from playwright.async_api import Error as PlaywrightError
        for s in selectors:
            try:
                if await page.locator(s).first.count() > 0:
                    return s
            except PlaywrightError:
                continue
        return None

    async def login(self, url: str, username: str, password: str, user_selector: str, pass_selector: str,
                    submit_selector: str, confirm: bool, preview: Path) -> dict:
        page = await self._ensure_page()
        await page.goto(url, wait_until="domcontentloaded")
        us = user_selector or await self._first(page, LOGIN_USER_SELECTORS)
        ps = pass_selector or await self._first(page, LOGIN_PASS_SELECTORS)
        if not us or not ps:
            return {"logged_in": False, "url": page.url,
                    "error": "No encontré los campos de usuario y contraseña: pasá user_selector y pass_selector."}
        await page.fill(us, username, timeout=8000)
        await page.fill(ps, password, timeout=8000)
        sub = submit_selector or await self._first(page, LOGIN_SUBMIT_SELECTORS)
        if not confirm:
            shot = None
            try:
                preview.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(preview))
                shot = str(preview)
            except Exception:  # noqa: BLE001 - la vista previa es de cortesía
                pass
            return {"logged_in": False, "dry_run": True, "url": page.url, "preview": shot,
                    "message": "Dejé los campos cargados y no envié nada. Confirmá para iniciar sesión."}
        if sub:
            await page.click(sub, timeout=8000)
        else:
            await page.press(ps, "Enter")
        await page.wait_for_load_state("domcontentloaded")
        return {"logged_in": True, "url": page.url, "title": await page.title()}

    async def close(self) -> dict:
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()
        self._browser = self._page = self._pw = None
        return {"closed": True}
