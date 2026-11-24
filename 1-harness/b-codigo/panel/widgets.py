"""Paleta y widgets del panel (estética del panel del orquestador de JarvisRemote).

Tkinter + Pillow: bordes redondeados con antialiasing, la esfera con brillo, píldoras, tarjetas y barras.
"""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageTk

# --- paleta (sacada del panel del orquestador) -------------------------------------------------------------------------
BG = "#0f1521"
PANEL = "#111a28"
PANEL_BORDER = "#24344e"
CARD = "#162234"
CARD_BORDER = "#283b59"
CARD_HOVER = "#3a5478"
ACTIVE = "#13384c"
INPUT = "#0a101a"
PILL = "#080d16"
PILL_BORDER = "#1d2b42"
DIM_BG = "#0b1019"
DIM_BORDER = "#151d2b"
CYAN = "#35e0ff"
CYAN_SOFT = "#7fe9ff"
TEXT = "#e8f0ff"
MUTED = "#7f8db0"
DIM = "#59606d"
ORANGE = "#ff7922"
RED = "#ff6b7a"
GREEN = "#3ddc97"
ON_CYAN = "#04121a"

WIN = sys.platform == "win32"
SANS = "Segoe UI" if WIN else "DejaVu Sans"
SYMBOL = "Segoe UI Symbol" if WIN else "DejaVu Sans"
MONO = "Cascadia Mono" if WIN else "DejaVu Sans Mono"


def spaced(text: str) -> str:
    """Mayúsculas con aire entre letras (el 'tracking' del panel original)."""
    return " ".join(text.upper()).replace("   ", " ")


# --- imágenes redondeadas con antialiasing ----------------------------------------------------------------------------
_cache: dict[tuple, ImageTk.PhotoImage] = {}


def rounded(w: int, h: int, r: int, fill: str, border: str | None, outer: str, bw: int = 1) -> ImageTk.PhotoImage:
    key = (w, h, r, fill, border, outer, bw)
    if key in _cache:
        return _cache[key]
    s = 3
    img = Image.new("RGBA", (w * s, h * s), outer)
    d = ImageDraw.Draw(img)
    if border:
        d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], r * s, fill=border)
        i = bw * s
        d.rounded_rectangle([i, i, w * s - 1 - i, h * s - 1 - i], max(1, r - bw) * s, fill=fill)
    else:
        d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], r * s, fill=fill)
    photo = ImageTk.PhotoImage(img.resize((max(1, w), max(1, h)), Image.LANCZOS))
    if len(_cache) > 400:
        _cache.clear()
    _cache[key] = photo
    return photo


def orb(size: int, outer: str) -> ImageTk.PhotoImage:
    """La esfera brillante del encabezado: halo cian difuso + núcleo con degradé."""
    s = 4
    n = size * s
    img = Image.new("RGBA", (n, n), outer)
    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    c = n // 2
    gr = int(n * 0.36)
    gd.ellipse([c - gr, c - gr, c + gr, c + gr], fill=(54, 218, 253, 150))
    glow = glow.filter(ImageFilter.GaussianBlur(n * 0.09))
    img.alpha_composite(glow)
    core = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    cd = ImageDraw.Draw(core)
    r = int(n * 0.24)
    inner, mid, edge = (238, 251, 253), (54, 218, 253), (31, 120, 253)
    steps = 40
    for k in range(steps, 0, -1):
        t = k / steps
        col = tuple(int(mid[j] + (edge[j] - mid[j]) * (t - 0.5) * 2) if t > 0.5 else
                    int(inner[j] + (mid[j] - inner[j]) * t * 2) for j in range(3))
        rr = r * t
        ox, oy = c - r * 0.18 * (1 - t), c - r * 0.22 * (1 - t)   # brillo corrido arriba a la izquierda
        cd.ellipse([ox - rr, oy - rr, ox + rr, oy + rr], fill=(*col, 255))
    img.alpha_composite(core)
    return ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))


# --- widgets ----------------------------------------------------------------------------------------------------------
class RoundPanel(tk.Canvas):
    """Panel redondeado con un Frame adentro (`.inner`)."""

    def __init__(self, parent: tk.Misc, fill: str = PANEL, border: str | None = PANEL_BORDER, radius: int = 14,
                 pad: int = 14, outer: str = BG, **kw) -> None:
        super().__init__(parent, bg=outer, highlightthickness=0, bd=0, **kw)
        self._fill, self._border, self._r, self._pad, self._outer = fill, border, radius, pad, outer
        self.inner = tk.Frame(self, bg=fill)
        self._img = self.create_image(0, 0, anchor="nw")
        self._win = self.create_window(pad, pad, anchor="nw", window=self.inner)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e: tk.Event) -> None:
        w, h = max(e.width, 2 * self._r + 2), max(e.height, 2 * self._r + 2)
        self._photo = rounded(w, h, self._r, self._fill, self._border, self._outer)
        self.itemconfigure(self._img, image=self._photo)
        self.itemconfigure(self._win, width=max(1, w - 2 * self._pad), height=max(1, h - 2 * self._pad))


class Pill(tk.Canvas):
    """Botón o indicador en forma de píldora. `lines` = 1 o 2 renglones (etiqueta y valor)."""

    VARIANTS = {
        "primary": (CYAN, CYAN, ON_CYAN, "#6be9ff", "#6be9ff"),
        "ghost": (INPUT, PILL_BORDER, TEXT, INPUT, CYAN),
        "info": (PILL, PILL_BORDER, TEXT, PILL, PILL_BORDER),
        "warn": (PILL, ORANGE, ORANGE, PILL, ORANGE),
        "danger": (PILL, RED, RED, PILL, RED),
        "seg": (CARD, CARD_BORDER, MUTED, CARD, CARD_HOVER),
        "seg_on": (ACTIVE, CYAN, TEXT, ACTIVE, CYAN),
    }

    def __init__(self, parent: tk.Misc, lines: list[str], command: Callable[[], None] | None = None,
                 variant: str = "ghost", outer: str = BG, height: int | None = None, width: int | None = None,
                 radius: int | None = None, bold: bool = True, size: int = 10) -> None:
        self._lines, self._cmd, self._variant, self._outer = lines, command, variant, outer
        self._fonts = (tkfont.Font(family=SANS, size=size - (1 if len(lines) > 1 else 0)),
                       tkfont.Font(family=SANS, size=size, weight="bold" if bold else "normal"))
        self._h = height or (44 if len(lines) > 1 else 36)
        self._fixed_w = width
        self._radius = radius
        self._hover = False
        self._enabled = True
        super().__init__(parent, height=self._h, bg=outer, highlightthickness=0, bd=0,
                         cursor="hand2" if command else "")
        self._draw()
        if command:
            self.bind("<Enter>", lambda e: self._set_hover(True))
            self.bind("<Leave>", lambda e: self._set_hover(False))
            self.bind("<ButtonRelease-1>", lambda e: self._enabled and self._cmd())

    def _width(self) -> int:
        if self._fixed_w:
            return self._fixed_w
        widths = [self._fonts[1 if (i == len(self._lines) - 1) else 0].measure(t) for i, t in enumerate(self._lines)]
        return max(widths) + 40

    def _set_hover(self, v: bool) -> None:
        self._hover = v
        self._draw()

    def set(self, lines: list[str] | None = None, variant: str | None = None, enabled: bool | None = None) -> None:
        self._lines = lines or self._lines
        self._variant = variant or self._variant
        if enabled is not None:
            self._enabled = enabled
            self.configure(cursor="hand2" if (enabled and self._cmd) else "")
        self._draw()

    def _draw(self) -> None:
        fill, border, fg, hfill, hborder = self.VARIANTS[self._variant]
        if self._hover and self._enabled:
            fill, border = hfill, hborder
        if not self._enabled:
            fill, border, fg = DIM_BG, DIM_BORDER, DIM
        w, h = self._width(), self._h
        self.configure(width=w)
        self.delete("all")
        self._photo = rounded(w, h, self._radius or h // 2, fill, border, self._outer)
        self.create_image(0, 0, anchor="nw", image=self._photo)
        if len(self._lines) == 1:
            self.create_text(w // 2, h // 2, text=self._lines[0], fill=fg, font=self._fonts[1])
        else:
            label_fg = fg if self._variant in ("warn", "danger") else MUTED if self._variant == "info" else fg
            self.create_text(w // 2, h // 2 - 8, text=self._lines[0], fill=label_fg, font=self._fonts[0])
            self.create_text(w // 2, h // 2 + 9, text=self._lines[1], fill=fg, font=self._fonts[1])


class TabCard(tk.Canvas):
    """Pestaña con forma de tarjeta: ícono, título y subtítulo en mayúsculas. `dim` = brigada sin montar."""

    H = 46

    def __init__(self, parent: tk.Misc, icon: str, icon_color: str, title: str, subtitle: str,
                 command: Callable[[], None] | None, outer: str = BG, dim: bool = False, add: bool = False) -> None:
        self.W = max(140, tkfont.Font(family=SANS, size=10, weight="bold").measure(title),
                     tkfont.Font(family=SANS, size=6, weight="bold").measure(spaced(subtitle))) + 58
        super().__init__(parent, width=self.W, height=self.H, bg=outer, highlightthickness=0, bd=0,
                         cursor="hand2" if command else "")
        self._icon, self._icon_color, self._title, self._sub = icon, icon_color, title, subtitle
        self._cmd, self._outer, self._dim, self._add = command, outer, dim, add
        self.active = False
        self._hover = False
        self._draw()
        if command:
            self.bind("<Enter>", lambda e: self._set_hover(True))
            self.bind("<Leave>", lambda e: self._set_hover(False))
            self.bind("<ButtonRelease-1>", lambda e: self._cmd())

    def _set_hover(self, v: bool) -> None:
        self._hover = v
        self._draw()

    def set_active(self, v: bool) -> None:
        self.active = v
        self._draw()

    def _draw(self) -> None:
        if self.active:
            fill, border, fg, sub, icol = ACTIVE, CYAN, TEXT, MUTED, self._icon_color
        elif self._add:
            fill, border, fg, sub, icol = INPUT, CYAN if self._hover else PILL_BORDER, \
                TEXT if self._hover else MUTED, DIM, CYAN
        elif self._dim:
            fill, border, fg, sub, icol = DIM_BG, CARD_BORDER if self._hover else DIM_BORDER, DIM, "#3f4652", \
                _mix(self._icon_color, DIM_BG, 0.45)
        else:
            fill, border, fg, sub, icol = CARD, CARD_HOVER if self._hover else CARD_BORDER, TEXT, MUTED, self._icon_color
        self.delete("all")
        self._photo = rounded(self.W, self.H, 10, fill, border, self._outer)
        self.create_image(0, 0, anchor="nw", image=self._photo)
        self.create_text(24, self.H // 2, text=self._icon, fill=icol, font=(SYMBOL, 13))
        self.create_text(44, 17, text=self._title, fill=fg, font=(SANS, 10, "bold"), anchor="w")
        self.create_text(44, 32, text=spaced(self._sub), fill=sub, font=(SANS, 6, "bold"), anchor="w")


def _mix(a: str, b: str, t: float) -> str:
    """Color entre `a` (t=1) y `b` (t=0)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(cb[k] + (ca[k] - cb[k]) * t):02x}" for k in range(3))


class HBar(tk.Canvas):
    """Barra de scroll horizontal fina y redondeada (como la del orquestador). Se arrastra y se esconde si no hace falta."""

    def __init__(self, parent: tk.Misc, target: tk.Canvas, outer: str = BG) -> None:
        super().__init__(parent, height=10, bg=outer, highlightthickness=0, bd=0)
        self._t, self._lo, self._hi, self._drag, self._hover = target, 0.0, 1.0, None, False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self._draw()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self._draw()))

    def set(self, lo: str, hi: str) -> None:
        self._lo, self._hi = float(lo), float(hi)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        if w < 20 or (self._lo <= 0.0 and self._hi >= 1.0):
            return
        self.create_line(6, 5, w - 6, 5, fill="#141d2b", width=6, capstyle="round")
        x0, x1 = 6 + (w - 12) * self._lo, 6 + (w - 12) * self._hi
        self.create_line(x0, 5, max(x0 + 1, x1), 5, fill="#2f4a6e" if self._hover else "#233753", width=6,
                         capstyle="round")

    def _press(self, e: tk.Event) -> None:
        w = max(1, self.winfo_width() - 12)
        pos = (e.x - 6) / w
        if not (self._lo <= pos <= self._hi):
            self._t.xview_moveto(max(0.0, pos - (self._hi - self._lo) / 2))
        self._drag = (e.x, self._lo)

    def _motion(self, e: tk.Event) -> None:
        if self._drag:
            x, lo = self._drag
            self._t.xview_moveto(max(0.0, lo + (e.x - x) / max(1, self.winfo_width() - 12)))


class Link(tk.Label):
    def __init__(self, parent: tk.Misc, text: str, command: Callable[[], None], bg: str) -> None:
        super().__init__(parent, text=text, bg=bg, fg=MUTED, font=(SANS, 8, "bold"), cursor="hand2")
        self.bind("<Enter>", lambda e: self.configure(fg=CYAN))
        self.bind("<Leave>", lambda e: self.configure(fg=MUTED))
        self.bind("<Button-1>", lambda e: command())
