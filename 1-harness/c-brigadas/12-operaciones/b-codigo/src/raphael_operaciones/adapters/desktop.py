"""Escritorio de la PC (Windows): mouse, teclado, ventanas y capturas. Portado de `tools/desktop.py`.

Real = `pyautogui` (mouse, teclado, captura) + `pywinauto` y `pywin32` (ventanas y controles por UI Automation).
Se importan perezosamente: sin ellas, o fuera de Windows, el adaptador real avisa qué falta y el resto de la brigada sigue.

NO PROBADO en Windows desde la nube (acá no hay escritorio): lo primero que se prueba en la PC de Damián es el paso
"Escritorio" de `LIENZO-DAMIAN.md`.

Límite real de Windows (UIPI): una ventana elevada (UAC, "ejecutar como administrador") no se puede controlar desde un
proceso sin elevar. Se detecta donde se puede, pero `pyautogui` puede mandar clics "al vacío" sin error.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Protocol

from . import AdapterUnavailable

WINDOW_APPEAR_TIMEOUT = 5.0
WINDOW_APPEAR_POLL = 0.3
ELEVATION_MARKERS = ("access is denied", "-2147024891", "el acceso es denegado")
BUTTONS = ("left", "right", "middle")


class ElevatedWindowError(AdapterUnavailable):
    pass


class DesktopDriver(Protocol):
    def screenshot(self, path: Path) -> dict: ...
    def list_windows(self) -> dict: ...
    def focus_window(self, title: str | None, pid: int | None) -> dict: ...
    def click(self, x: int, y: int, button: str, double: bool) -> dict: ...
    def click_element(self, window_title: str, control_name: str) -> dict: ...
    def type_text(self, text: str) -> dict: ...
    def press_key(self, combo: str) -> dict: ...
    def move_mouse(self, x: int, y: int) -> dict: ...
    def scroll(self, amount: int, x: int | None, y: int | None) -> dict: ...
    def launch_app(self, path_or_name: str) -> dict: ...


def split_combo(combo: str) -> list[str]:
    keys = [k.strip().lower() for k in str(combo).split("+") if k.strip()]
    if not keys:
        raise ValueError("combo vacío")
    return keys


class MockDesktop:
    """Un escritorio de mentira: anota lo que se le pide y mantiene una lista de ventanas."""

    def __init__(self, windows: list[dict] | None = None) -> None:
        self.windows = windows if windows is not None else [{"title": "Bloc de notas", "pid": 4242, "process": "notepad.exe"}]
        self.calls: list[tuple[str, dict]] = []

    def _log(self, name: str, **kw: Any) -> dict:
        self.calls.append((name, kw))
        return {**kw, "simulated": True}

    def screenshot(self, path: Path) -> dict:
        return self._log("screenshot", screenshot_path=str(path), width=1920, height=1080)

    def list_windows(self) -> dict:
        self.calls.append(("list_windows", {}))
        return {"windows": list(self.windows), "simulated": True}

    def focus_window(self, title: str | None, pid: int | None) -> dict:
        if pid is None and title is None:
            raise ValueError("Hay que pasar 'title' o 'pid'.")
        match = next((w for w in self.windows if (pid is not None and w["pid"] == pid)
                      or (pid is None and title.lower() in w["title"].lower())), None)   # type: ignore[union-attr]
        if match is None:
            raise ValueError(f"No se encontró ninguna ventana para {pid if pid is not None else title!r}")
        return self._log("focus_window", focused=match["title"], pid=match["pid"], process=match["process"])

    def click(self, x: int, y: int, button: str, double: bool) -> dict:
        return self._log("click", x=x, y=y, button=button, double=double)

    def click_element(self, window_title: str, control_name: str) -> dict:
        return self._log("click_element", window=window_title, control=control_name)

    def type_text(self, text: str) -> dict:
        self.calls.append(("type_text", {"typed_chars": len(text)}))   # el texto no queda en el registro
        return {"typed_chars": len(text), "simulated": True}

    def press_key(self, combo: str) -> dict:
        return self._log("press_key", combo=combo, keys=split_combo(combo))

    def move_mouse(self, x: int, y: int) -> dict:
        return self._log("move_mouse", x=x, y=y)

    def scroll(self, amount: int, x: int | None, y: int | None) -> dict:
        return self._log("scroll", amount=amount, x=x, y=y)

    def launch_app(self, path_or_name: str) -> dict:
        pid = 5000 + len(self.calls)
        self.windows.append({"title": str(path_or_name), "pid": pid, "process": f"{path_or_name}.exe"})
        return self._log("launch_app", launched=path_or_name, method="simulado", focused=True, pid=pid)


class RealDesktop:
    """El escritorio de verdad (Windows). Las librerías se importan al usarlo."""

    def __init__(self) -> None:
        self._gui: Any = None

    # --- dependencias ----------------------------------------------------------------------------------------------
    def _need_windows(self) -> None:
        if sys.platform != "win32":
            raise AdapterUnavailable("El control del escritorio real es solo para Windows. Acá corre el simulado "
                                     "(OPERACIONES_ADAPTADORES=simulado).")

    def _pyautogui(self) -> Any:
        self._need_windows()
        if self._gui is None:
            try:
                import pyautogui
            except ImportError:
                raise AdapterUnavailable("Falta la librería pyautogui. En la PC: pip install pyautogui pywinauto pywin32 "
                                         "(extra 'escritorio' del paquete).") from None
            pyautogui.PAUSE = 0.05
            self._gui = pyautogui
        return self._gui

    def _uia(self) -> Any:
        self._need_windows()
        try:
            from pywinauto import Desktop
        except ImportError:
            raise AdapterUnavailable("Falta la librería pywinauto. En la PC: pip install pywinauto pywin32.") from None
        return Desktop(backend="uia")

    @staticmethod
    def _reraise_if_elevation(exc: Exception) -> None:
        if any(m in str(exc).lower() for m in ELEVATION_MARKERS):
            raise ElevatedWindowError("No se pudo interactuar con la ventana: probablemente está elevada (administrador "
                                      "o UAC) y Windows bloquea la entrada de un proceso sin elevar.") from exc

    # --- ventanas ----------------------------------------------------------------------------------------------------
    @staticmethod
    def _process_name(pid: int) -> str | None:
        try:
            import win32api
            import win32con
            import win32process
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                return win32process.GetModuleFileNameEx(handle, 0).rsplit("\\", 1)[-1]
            finally:
                win32api.CloseHandle(handle)
        except Exception:  # noqa: BLE001 - es solo un dato de más
            return None

    @staticmethod
    def _enum_windows() -> dict:
        import win32gui
        import win32process
        found: dict = {}

        def cb(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if title and win32gui.IsWindowVisible(hwnd):
                found[hwnd] = (title, win32process.GetWindowThreadProcessId(hwnd)[1])

        win32gui.EnumWindows(cb, None)
        return found

    def _wait_new_window(self, before: dict) -> tuple[int, str, int] | None:
        deadline = time.monotonic() + WINDOW_APPEAR_TIMEOUT
        while time.monotonic() < deadline:
            after = self._enum_windows()
            new = [h for h in after if h not in before]
            if new:
                return new[0], after[new[0]][0], after[new[0]][1]
            time.sleep(WINDOW_APPEAR_POLL)
        return None

    @staticmethod
    def _foreground(hwnd: int) -> bool:
        import pywintypes
        import win32con
        import win32gui
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except pywintypes.error:
            return False
        return win32gui.GetForegroundWindow() == hwnd

    def _find_window(self, title: str) -> Any:
        matches = [w for w in self._uia().windows() if title.lower() in (w.window_text() or "").lower()]
        if not matches:
            raise ValueError(f"No se encontró ninguna ventana con título que contenga '{title}'")
        return matches[0]

    def _find_window_by_pid(self, pid: int) -> Any:
        windows = [w for w in self._uia().windows() if w.process_id() == pid]
        if not windows:
            raise ValueError(f"No se encontró ninguna ventana top-level para el pid {pid}")
        for w in windows:
            try:
                if w.is_visible() and not w.is_minimized():
                    return w
            except Exception:  # noqa: BLE001
                continue
        return windows[0]

    # --- el protocolo -------------------------------------------------------------------------------------------------
    def screenshot(self, path: Path) -> dict:
        image = self._pyautogui().screenshot()
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path))
        return {"screenshot_path": str(path), "width": image.width, "height": image.height}

    def list_windows(self) -> dict:
        out = []
        for w in self._uia().windows():
            title = w.window_text() or ""
            if title:
                pid = w.process_id()
                out.append({"title": title, "pid": pid, "process": self._process_name(pid)})
        return {"windows": out}

    def focus_window(self, title: str | None, pid: int | None) -> dict:
        if pid is not None:
            window = self._find_window_by_pid(pid)
        elif title is not None:
            window = self._find_window(title)
        else:
            raise ValueError("Hay que pasar 'title' o 'pid'.")
        window.set_focus()
        rpid = window.process_id()
        return {"focused": window.window_text(), "pid": rpid, "process": self._process_name(rpid)}

    def click(self, x: int, y: int, button: str, double: bool) -> dict:
        if button not in BUTTONS:
            raise ValueError(f"botón inválido: {button!r}")
        gui = self._pyautogui()
        try:
            gui.doubleClick(x, y, button=button) if double else gui.click(x, y, button=button)
        except Exception as exc:  # noqa: BLE001
            self._reraise_if_elevation(exc)
            raise
        return {"x": x, "y": y, "button": button, "double": double}

    def click_element(self, window_title: str, control_name: str) -> dict:
        window = self._find_window(window_title)
        window.set_focus()
        matches = window.descendants(title=control_name)
        if not matches:
            raise ValueError(f"No se encontró ningún control con nombre '{control_name}' dentro de la ventana")
        matches[0].click_input()
        pid = window.process_id()
        return {"window": window.window_text(), "control": control_name, "pid": pid, "process": self._process_name(pid)}

    def type_text(self, text: str) -> dict:
        try:
            self._pyautogui().write(text)
        except Exception as exc:  # noqa: BLE001
            self._reraise_if_elevation(exc)
            raise
        return {"typed_chars": len(text)}

    def press_key(self, combo: str) -> dict:
        keys = split_combo(combo)
        gui = self._pyautogui()
        gui.press(keys[0]) if len(keys) == 1 else gui.hotkey(*keys)
        return {"combo": combo, "keys": keys}

    def move_mouse(self, x: int, y: int) -> dict:
        self._pyautogui().moveTo(x, y)
        return {"x": x, "y": y}

    def scroll(self, amount: int, x: int | None, y: int | None) -> dict:
        gui = self._pyautogui()
        gui.scroll(amount, x=x, y=y) if x is not None and y is not None else gui.scroll(amount)
        return {"amount": amount, "x": x, "y": y}

    def launch_app(self, path_or_name: str) -> dict:
        self._need_windows()
        before = self._enum_windows()
        try:
            os.startfile(path_or_name)   # type: ignore[attr-defined]  # solo existe en Windows
            method = "os.startfile"
        except OSError as exc:
            try:   # lista de argv (sin shell) para que el nombre no inyecte metacaracteres
                subprocess.Popen(["cmd", "/c", "start", "", path_or_name])
                method = "start (respaldo)"
            except Exception as fallback:  # noqa: BLE001
                raise AdapterUnavailable(f"No se pudo lanzar '{path_or_name}': os.startfile falló ({exc}) y el respaldo "
                                         f"con 'start' también ({fallback}).") from fallback
        found = self._wait_new_window(before)
        if found is None:
            return {"launched": path_or_name, "method": method, "focused": False,
                    "warning": f"Se lanzó pero no apareció ninguna ventana nueva en {WINDOW_APPEAR_TIMEOUT:g}s (puede "
                               "haber reusado una ventana abierta). No asumir que quedó enfocada."}
        hwnd, title, pid = found
        focused = self._foreground(hwnd)
        out = {"launched": path_or_name, "method": method, "focused": focused, "window_title": title, "pid": pid,
               "process": self._process_name(pid)}
        if not focused:
            out["warning"] = "Windows bloqueó traer la ventana al frente: puede no tener foco de teclado real."
        return out
