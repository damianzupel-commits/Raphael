"""Raphael · Harness v2: app nativa con la distribución pedida por Damián (21 nov 2026).

    ┌ brigadas montadas (+ agregar) ─────────────┬ estado y tareas en vivo ┐
    ├ chat de la brigada elegida ┬ cocineros permanentes                  ┤
    │ (uno por brigada, en disco)├ ayudantes efímeros                     ┤
    │                            ├ herramientas de uso compartido         ┤
    └────────────────────────────┴────────────────────────────────────────┘

La esfera abre el ORQUESTADOR: todo junto (tareas, cocineros, efímeros y herramientas de todas las
brigadas). Elegir una brigada muestra solo lo suyo. "⚙ Núcleo" abre las herramientas del harness.
Esqueleto de la app de Raphael personal: queda como pendiente para la pieza 03 (servidor, app e instalador).
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from demo import EXAMPLE_DRAFT, EXAMPLE_MANIFEST, MODULES, ORCHESTRATOR, STAGES, PanelState  # noqa: E402
from widgets import (  # noqa: E402
    ACTIVE,
    BG,
    CARD,
    CARD_BORDER,
    CYAN,
    DIM,
    GREEN,
    INPUT,
    MONO,
    MUTED,
    ORANGE,
    PANEL,
    PILL_BORDER,
    RED,
    SANS,
    SYMBOL,
    TEXT,
    HBar,
    Link,
    Pill,
    RoundPanel,
    TabCard,
    orb,
    rounded,
    spaced,
)

from config_vista import ConfigView  # noqa: E402
from raphael_core import CONTRACT_VERSION  # noqa: E402

#: subvistas del Núcleo (herramientas del harness)
HARNESS_TOOLS = [("estado", "Estado"), ("pruebas", "Pruebas en vivo"), ("manifiesto", "Manifiesto"),
                 ("borradores", "Borradores"),
                 ("auditoria", "Auditoría"), ("tests", "Tests")]
#: ícono y color por brigada (id de la carpeta sin el número)
BRIGADE_LOOK = {
    "seguridad": ("◈", "#5aa9ff"), "antimalware": ("☣", "#3ddc97"), "investigacion": ("⌕", "#c79bff"),
    "geolocalizacion-publica": ("⌖", "#35e0ff"), "memoria-cerebro": ("✺", "#ff8fd0"), "ingesta": ("⇩", "#7fe9ff"),
    "trading": ("⇅", "#ffd166"), "operaciones": ("⚙", "#a7b4cc"), "autorreparacion": ("↻", "#3ddc97"),
    "contenido": ("▶", "#b98cff"), "raphael-empresas": ("▣", "#ff7922"), "legales": ("⚖", "#e8d28a"),
}
ORCH_LOOK = ("◉", CYAN)
SECTIONS = {
    "nucleo": ("⚙", CYAN, "Núcleo", "herramientas del harness"),
    "brigadas": ("＋", CYAN, "Agregar brigadas", "catálogo · montar"),
    "config": ("☰", CYAN, "Configuración", "claves, modelos por brigada, autonomía, apariencia"),
}
LEVEL_TAG = {"automatico": "ok", "aprobacion": "warn", "humano": "bad"}
TASK_TAG = {"en curso": "cyan", "en cola": "muted", "aprobación": "warn"}


class RaphaelApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.app = PanelState()
        self._jobs: queue.Queue = queue.Queue()
        self._busy = False   # True mientras el chat espera a un modelo (el tick no se cruza)
        self.scope = ORCHESTRATOR
        self.title("Raphael — Harness v2")
        self.configure(bg=BG)
        self.geometry("1280x860")
        self.minsize(1100, 700)
        self._style()

        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=24, pady=(18, 16))
        self._header(root)
        self._top_band(root)
        self._section(root)
        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="both", expand=True, pady=(14, 0))
        self.views: dict[str, tk.Frame] = {}
        for key, builder in [("main", self._view_main), ("nucleo", self._view_nucleo),
                             ("brigadas", self._view_brigades), ("brigada", self._view_brigade),
                             ("config", self._view_config)]:
            f = tk.Frame(self.body, bg=BG)
            f.place(relx=0, rely=0, relwidth=1, relheight=1)
            builder(f)
            self.views[key] = f
        self.select(ORCHESTRATOR)
        self.after(150, self._poll_jobs)
        self.after(60_000, self._tick)

    def _tick(self) -> None:
        """Cada minuto: tareas programadas de las brigadas y su healthcheck (que el runtime corre cada 5 min)."""
        if not self._busy:
            try:
                self.app.tick()
            except Exception:  # noqa: BLE001 - un tick que falla no tumba la ventana; queda en la auditoría
                pass
            self.refresh()
        self.after(60_000, self._tick)

    # --- estilo ttk (tablas y barras) ----------------------------------------------------------------------------------
    def _style(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Dark.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=28,
                    borderwidth=0, font=(SANS, 10))
        s.layout("Dark.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Dark.Treeview.Heading", background=PANEL, foreground=MUTED, borderwidth=0, relief="flat",
                    font=(SANS, 8, "bold"), padding=(4, 6))
        s.map("Dark.Treeview.Heading", background=[("active", PANEL)], foreground=[("active", CYAN)])
        s.map("Dark.Treeview", background=[("selected", ACTIVE)], foreground=[("selected", TEXT)])
        s.configure("Dark.Vertical.TScrollbar", troughcolor=PANEL, background="#233753", bordercolor=PANEL,
                    lightcolor="#233753", darkcolor="#233753", arrowcolor=MUTED, gripcount=0, arrowsize=12)
        s.map("Dark.Vertical.TScrollbar", background=[("active", "#2f4a6e")])

    # --- encabezado ----------------------------------------------------------------------------------------------------
    def _header(self, root: tk.Frame) -> None:
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x")
        left = tk.Frame(bar, bg=BG)
        left.pack(side="left")
        self._orb = orb(56, BG)
        orb_lbl = tk.Label(left, image=self._orb, bg=BG, cursor="hand2")
        orb_lbl.pack(side="left", padx=(0, 10))
        titles = tk.Frame(left, bg=BG)
        titles.pack(side="left")
        title = tk.Label(titles, text=spaced("Raphael · Harness v2"), bg=BG, fg=TEXT, font=(SANS, 15, "bold"),
                         cursor="hand2")
        title.pack(anchor="w")
        tk.Label(titles, text=spaced("tocá la esfera para el orquestador"), bg=BG, fg=MUTED,
                 font=(SANS, 8)).pack(anchor="w", pady=(2, 0))
        for w in (orb_lbl, title):
            w.bind("<Button-1>", lambda e: self.select(ORCHESTRATOR))
        title.bind("<Enter>", lambda e: title.configure(fg=CYAN))
        title.bind("<Leave>", lambda e: title.configure(fg=TEXT))

        right = tk.Frame(bar, bg=BG)
        right.pack(side="right")
        st = self.app.status()
        info = tk.Frame(right, bg=BG)
        info.pack(side="left", padx=(0, 16))
        tk.Label(info, text=spaced("Contrato del núcleo"), bg=BG, fg=MUTED, font=(SANS, 7)).pack(anchor="e")
        tk.Label(info, text=f"{st['contract']} · {st['installation']} ({st['edition']})", bg=BG, fg=CYAN,
                 font=(SANS, 9, "bold")).pack(anchor="e")
        self.pill_sample = Pill(right, ["Muestra:", "OFF"], command=self._toggle_sample, variant="info", width=130)
        self.pill_sample.pack(side="left", padx=4)
        self.pill_down = Pill(right, ["⚡ 0 piezas", "caídas"], variant="info", width=130, bold=False)
        self.pill_down.pack(side="left", padx=4)
        Pill(right, ["⚙ Núcleo"], command=lambda: self.show_view("nucleo"), variant="ghost", height=44,
             width=120).pack(side="left", padx=(4, 0))
        Pill(right, ["☰ Configuración"], command=lambda: self.show_view("config"), variant="ghost", height=44,
             width=160).pack(side="left", padx=(6, 0))

    def _toggle_sample(self) -> None:
        self.app.sample = not self.app.sample
        self.pill_sample.set(["Muestra:", "ON" if self.app.sample else "OFF"],
                             variant="warn" if self.app.sample else "info")
        if self.scope != ORCHESTRATOR and self.scope not in {b.id for b in self.app.mounted()}:
            self.scope = ORCHESTRATOR
        self._build_row()
        self.select(self.scope)

    # --- franja de arriba: brigadas montadas + estado y tareas ----------------------------------------------------------
    def _top_band(self, root: tk.Frame) -> None:
        band = tk.Frame(root, bg=BG)
        band.pack(fill="x", pady=(16, 0))
        band.columnconfigure(0, weight=1)
        left = tk.Frame(band, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.tab_canvas = tk.Canvas(left, height=TabCard.H, bg=BG, highlightthickness=0, xscrollincrement=40)
        self.tab_canvas.pack(fill="x")
        self.row = tk.Frame(self.tab_canvas, bg=BG)
        self.tab_canvas.create_window(0, 0, anchor="nw", window=self.row)
        self.hbar = HBar(left, self.tab_canvas)
        self.hbar.pack(fill="x", pady=(6, 0))
        self.tab_canvas.configure(xscrollcommand=self.hbar.set)
        self.row.bind("<Configure>", lambda e: self.tab_canvas.configure(scrollregion=(0, 0, e.width, e.height)))
        self._scope_bar(left)

        status = RoundPanel(band, fill=CARD, border=CARD_BORDER, radius=14, pad=14, width=380, height=124)
        status.grid(row=0, column=1, sticky="ns")
        top = tk.Frame(status.inner, bg=CARD)
        top.pack(fill="x")
        self.status_title = tk.Label(top, text=spaced("Estado y tareas"), bg=CARD, fg=MUTED, font=(SANS, 7, "bold"))
        self.status_title.pack(side="left")
        self.status_live = tk.Label(top, text="● en vivo", bg=CARD, fg=GREEN, font=(SANS, 8, "bold"))
        self.status_live.pack(side="right")
        self.status_counts = tk.Label(status.inner, text="", bg=CARD, fg=TEXT, font=(SANS, 10, "bold"), anchor="w")
        self.status_counts.pack(fill="x", pady=(6, 4))
        self.status_tasks = tk.Frame(status.inner, bg=CARD)
        self.status_tasks.pack(fill="both", expand=True)
        self._build_row()

    def _scope_bar(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=BG)
        bar.pack(fill="x", pady=(10, 0))
        self._scope_canvas = tk.Canvas(bar, width=40, height=40, bg=BG, highlightthickness=0)
        self._scope_canvas.pack(side="left")
        self._scope_box = rounded(40, 40, 10, ACTIVE, "#1d4a60", BG)
        self._scope_canvas.create_image(0, 0, anchor="nw", image=self._scope_box)
        self._scope_icon = self._scope_canvas.create_text(20, 20, text="", fill=CYAN, font=(SYMBOL, 14))
        texts = tk.Frame(bar, bg=BG)
        texts.pack(side="left", padx=12)
        self.scope_title = tk.Label(texts, text="", bg=BG, fg=TEXT, font=(SANS, 13, "bold"))
        self.scope_title.pack(anchor="w")
        self.scope_sub = tk.Label(texts, text="", bg=BG, fg=MUTED, font=(SANS, 7, "bold"))
        self.scope_sub.pack(anchor="w")

    def _build_row(self) -> None:
        for w in self.row.winfo_children():
            w.destroy()
        self.tab_cards: dict[str, TabCard] = {}
        # solo las brigadas montadas; al final, el botón para agregar más (sin brigadas, queda solo el botón)
        for b in self.app.mounted():
            icon, color = BRIGADE_LOOK.get(b.id, ("◆", MUTED))
            sub = " · ".join(c.replace("-", " ") for c in b.cooks[:2]) or "montada"
            card = TabCard(self.row, icon, color, b.name, sub, command=lambda k=b.id: self.select(k))
            card.pack(side="left", padx=(0, 8))
            self.tab_cards[b.id] = card
        add = TabCard(self.row, "＋", CYAN, "Agregar brigadas", "catálogo · montar",
                      command=lambda: self.show_view("brigadas"), add=True)
        add.pack(side="left")
        self.tab_cards["_add"] = add

        def wheel(e: tk.Event) -> None:
            step = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
            self.tab_canvas.xview_scroll(step, "units")

        for w in [self.tab_canvas, self.row, *self.tab_cards.values()]:
            for ev in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(ev, wheel, add="+")
        self.tab_canvas.xview_moveto(0)

    # --- barra de sección (solo en Núcleo, catálogo y detalle de brigada) ----------------------------------------------
    def _section(self, root: tk.Frame) -> None:
        self.section = tk.Frame(root, bg=BG)
        self._sec_icon_box = tk.Canvas(self.section, width=44, height=44, bg=BG, highlightthickness=0)
        self._sec_icon_box.pack(side="left")
        self._sec_box = rounded(44, 44, 10, ACTIVE, "#1d4a60", BG)
        self._sec_icon_box.create_image(0, 0, anchor="nw", image=self._sec_box)
        self._sec_icon = self._sec_icon_box.create_text(22, 22, text="", fill=CYAN, font=(SYMBOL, 15))
        texts = tk.Frame(self.section, bg=BG)
        texts.pack(side="left", padx=12)
        self.sec_title = tk.Label(texts, text="", bg=BG, fg=TEXT, font=(SANS, 13, "bold"))
        self.sec_title.pack(anchor="w")
        self.sec_sub = tk.Label(texts, text="", bg=BG, fg=MUTED, font=(SANS, 7, "bold"))
        self.sec_sub.pack(anchor="w")
        Link(self.section, "← volver", lambda: self.select(self.scope), BG).pack(side="right")

    # --- navegación ----------------------------------------------------------------------------------------------------
    def select(self, scope: str) -> None:
        """Orquestador (todas las brigadas) o una brigada montada: la vista principal de la app."""
        self.scope = scope
        for k, card in self.tab_cards.items():
            card.set_active(k == scope)
        self._scope_header()
        self.section.pack_forget()
        self.views["main"].tkraise()
        self.refresh()
        card = self.tab_cards.get(scope)
        if card is not None:
            self.update_idletasks()
            region = str(self.tab_canvas.cget("scrollregion")).split()
            total = max(1, int(float(region[2]))) if len(region) == 4 else max(1, self.tab_canvas.winfo_width())
            lo, hi = self.tab_canvas.xview()
            x0, x1 = card.winfo_x() / total, (card.winfo_x() + card.winfo_width()) / total
            if x0 < lo or x1 > hi:
                self.tab_canvas.xview_moveto(max(0.0, x0 - 0.02))

    def _scope_header(self) -> None:
        scope = self.scope
        if scope == ORCHESTRATOR:
            icon, color = ORCH_LOOK
            n = len(self.app.mounted())
            title, sub = "Orquestador", f"todas las brigadas · {n} montadas" if n else "todas las brigadas · ninguna montada"
        else:
            b = self.app.brigade(scope)
            icon, color = BRIGADE_LOOK.get(scope, ("◆", MUTED))
            title, sub = (b.name if b else scope), f"{len(b.cooks) if b else 0} cocineros · solo esta brigada"
        self._scope_canvas.itemconfigure(self._scope_icon, text=icon, fill=color)
        self.scope_title.configure(text=title)
        self.scope_sub.configure(text=spaced(sub))

    def show_view(self, key: str) -> None:
        """Núcleo o catálogo de brigadas: tapan la vista principal; "← volver" regresa."""
        for card in self.tab_cards.values():
            card.set_active(False)
        self.tab_cards["_add"].set_active(key == "brigadas")
        icon, color, title, sub = SECTIONS[key]
        self._set_section(icon, color, title, sub)
        self.views[key].tkraise()
        self.refresh()

    def show_detail(self, bid: str) -> None:
        b = self.app.brigade(bid)
        if b is None:
            return
        icon, color = BRIGADE_LOOK.get(b.id, ("◆", MUTED))
        self._set_section(icon, color, b.name, f"{b.state} · {len(b.cooks)} cocineros")
        self._fill_brigade(b)
        self.views["brigada"].tkraise()

    def _set_section(self, icon: str, color: str, title: str, sub: str) -> None:
        self._sec_icon_box.itemconfigure(self._sec_icon, text=icon, fill=color)
        self.sec_title.configure(text=title)
        self.sec_sub.configure(text=spaced(sub))
        if not self.section.winfo_ismapped():
            self.section.pack(fill="x", pady=(14, 0), before=self.body)

    def show_tool(self, key: str) -> None:
        for k, pill in self.tool_pills.items():
            pill.set(variant="seg_on" if k == key else "seg")
        self.tools[key].tkraise()

    # --- vista principal: chat a la izquierda, cocineros / efímeros / herramientas a la derecha --------------------------
    def _view_main(self, f: tk.Frame) -> None:
        f.columnconfigure(0, weight=2, uniform="cols")
        f.columnconfigure(1, weight=3, uniform="cols")
        f.rowconfigure(0, weight=1)

        chat = RoundPanel(f)
        chat.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        head = tk.Frame(chat.inner, bg=PANEL)
        head.pack(fill="x", pady=(0, 8))
        self.chat_title = tk.Label(head, text="", bg=PANEL, fg=MUTED, font=(SANS, 8, "bold"))
        self.chat_title.pack(side="left")
        self.chat_note = tk.Label(head, text="", bg=PANEL, fg=DIM, font=(SANS, 8))
        self.chat_note.pack(side="right")
        self.chat_canvas = tk.Canvas(chat.inner, bg=PANEL, highlightthickness=0)
        self.chat_canvas.pack(fill="both", expand=True)
        self.chat_canvas.bind("<Configure>", lambda e: self._render_chat())
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.chat_canvas.bind(ev, self._chat_wheel)
        bar = tk.Frame(chat.inner, bg=PANEL)
        bar.pack(fill="x", pady=(10, 0))
        self.chat_send = Pill(bar, ["Enviar"], command=self._send, variant="primary", outer=PANEL, height=46,
                              width=96, radius=12)
        self.chat_send.pack(side="right")
        box = RoundPanel(bar, fill=INPUT, border=CYAN, radius=12, pad=12, outer=PANEL, height=46)
        box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.chat_entry = tk.Entry(box.inner, bg=INPUT, fg=TEXT, insertbackground=CYAN, relief="flat", bd=0,
                                   highlightthickness=0, font=(SANS, 10), disabledbackground=INPUT,
                                   disabledforeground=DIM)
        self.chat_entry.pack(fill="both", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self._send())

        right = tk.Frame(f, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        for i, w in enumerate((3, 2, 3)):
            right.rowconfigure(i, weight=w, uniform="right")
        pc = self._panel(right, "Cocineros permanentes")
        pc.grid(row=0, column=0, sticky="nsew")
        self.cooks_tree = self._tree(pc.inner, [("c", "Cocinero", 200), ("b", "Brigada", 160), ("e", "Estado", 150)])
        self.cooks_tree.bind("<Double-1>", lambda e: self._revive_selected())
        self.cooks_empty = self._empty(pc.inner)
        pe = self._panel(right, "Ayudantes efímeros")
        pe.grid(row=1, column=0, sticky="nsew", pady=12)
        self.eph_tree = self._tree(pe.inner, [("e", "Efímero", 170), ("b", "Brigada", 150), ("t", "Tarea", 220),
                                              ("d", "Tiempo", 70)])
        self.eph_empty = self._empty(pe.inner)
        pt = self._panel(right, "Herramientas de uso compartido", ("doble clic: activar o desactivar", lambda: None))
        pt.grid(row=2, column=0, sticky="nsew")
        self.tools_tree = self._tree(pt.inner, [("n", "Herramienta", 190), ("w", "La usa", 160), ("l", "Nivel", 110),
                                                ("s", "Estado", 110)])
        self.tools_tree.bind("<Double-1>", self._toggle_tool)
        self.tools_empty = self._empty(pt.inner)

    def _empty(self, parent: tk.Misc) -> tk.Label:
        return tk.Label(parent, text="", bg=PANEL, fg=DIM, font=(SANS, 9), justify="center")

    @staticmethod
    def _show_empty(label: tk.Label, text: str | None) -> None:
        if text:
            label.configure(text=text)
            label.place(relx=0.5, rely=0.62, anchor="center")
        else:
            label.place_forget()

    def _toggle_tool(self, e: tk.Event) -> None:
        iid = self.tools_tree.focus()
        if iid:
            self.app.toggle_tool(iid)
            self.refresh()

    # --- chat ----------------------------------------------------------------------------------------------------------
    def _send(self) -> None:
        text = self.chat_entry.get()
        if not text.strip() or self.app.sample:
            return
        self.chat_entry.delete(0, "end")
        scope = self.scope
        self.chat_send.set(enabled=False)
        self._busy = True
        self.chat_note.configure(text="pensando…")

        def work() -> None:
            try:
                self.app.send(scope, text)
                self._jobs.put(("chat", (True, scope)))
            except Exception as exc:  # noqa: BLE001
                self._jobs.put(("chat", (False, str(exc))))

        threading.Thread(target=work, daemon=True).start()

    def _chat_wheel(self, e: tk.Event) -> None:
        step = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
        self.chat_canvas.yview_scroll(step * 2, "units")

    def _render_chat(self) -> None:
        c = self.chat_canvas
        c.delete("all")
        self._bubbles: list = []
        w = max(200, c.winfo_width())
        msgs = self.app.chat(self.scope)
        name = "Orquestador" if self.scope == ORCHESTRATOR else (self.app.brigade(self.scope).name
                                                                 if self.app.brigade(self.scope) else self.scope)
        if not msgs:
            c.create_text(w // 2, max(60, c.winfo_height() // 2 - 20), width=w - 80, justify="center", fill=DIM,
                          font=(SANS, 10), text=f"Escribile a {name}.\nEl chat se guarda en tu PC y no se borra al "
                                                 "cerrar la app.")
            c.configure(scrollregion=(0, 0, w, c.winfo_height()))
            return
        y, maxw = 8, int(w * 0.8)
        for m in msgs:
            role = m.get("role", "system")
            if role == "system":
                tid = c.create_text(w // 2, y, anchor="n", width=w - 70, justify="center", fill=MUTED, font=(SANS, 9),
                                    text=m["text"])
                y = c.bbox(tid)[3] + 14
                continue
            user = role == "user"
            tid = c.create_text(0, 0, anchor="nw", width=maxw - 28, font=(SANS, 10), fill=TEXT, text=m["text"])
            x0, y0, x1, y1 = c.bbox(tid)
            bw, bh = (x1 - x0) + 28, (y1 - y0) + 20
            bx = w - 6 - bw if user else 6
            img = rounded(bw, bh, 14, ACTIVE if user else CARD, "#1d4a60" if user else CARD_BORDER, PANEL)
            self._bubbles.append(img)
            c.create_image(bx, y, anchor="nw", image=img)
            c.coords(tid, bx + 14, y + 10)
            c.tag_raise(tid)
            meta = f"{m.get('who', '')} · {m.get('when', '')}"
            c.create_text(bx + bw - 4 if user else bx + 4, y + bh + 4, anchor="ne" if user else "nw", text=meta,
                          fill=DIM, font=(SANS, 8))
            y += bh + 26
        c.configure(scrollregion=(0, 0, w, y + 6))
        c.yview_moveto(1.0)

    # --- estado y tareas en vivo ---------------------------------------------------------------------------------------
    def _render_status(self) -> None:
        scope_name = "todas las brigadas" if self.scope == ORCHESTRATOR else \
            (self.app.brigade(self.scope).name if self.app.brigade(self.scope) else self.scope)
        self.status_live.configure(text=f"● {scope_name}" if self.scope != ORCHESTRATOR else "● en vivo")
        tasks = self.app.tasks(self.scope)
        running = sum(1 for t in tasks if t[2] == "en curso")
        pending = sum(1 for t in tasks if t[2] in ("aprobación", "te toca a vos"))
        n_b = len(self.app.mounted()) if self.scope == ORCHESTRATOR else 1
        b = self.app.brigade(self.scope)
        first = f"{n_b} brigada{'s' if n_b != 1 else ''}" if self.scope == ORCHESTRATOR else \
            f"{len(b.cooks) if b else 0} cocineros"
        self.status_counts.configure(text=f"{first}  ·  {running} en curso  ·  {pending} por aprobar",
                                     fg=TEXT if tasks or n_b else MUTED)
        for w in self.status_tasks.winfo_children():
            w.destroy()
        if not tasks:
            tk.Label(self.status_tasks, text="Sin tareas: no hay brigadas trabajando." if not self.app.mounted() else
                     "Sin tareas en este momento.", bg=CARD, fg=DIM, font=(SANS, 9), anchor="w").pack(fill="x")
            return
        order = {"aprobación": 0, "te toca a vos": 1, "en curso": 2, "en cola": 3}
        for t, _b, st, _cook in sorted(tasks, key=lambda x: order.get(x[2], 4))[:3]:
            row = tk.Frame(self.status_tasks, bg=CARD)
            row.pack(fill="x")
            color = {"en curso": CYAN, "aprobación": ORANGE, "te toca a vos": ORANGE}.get(st, MUTED)
            pid = int(t.split()[0][1:]) if t.startswith("#") and t.split()[0][1:].isdigit() else None
            # lo de la derecha se empaqueta primero: así el texto largo no lo tapa
            if pid is not None and not self.app.sample:
                Link(row, "rechazar", lambda p=pid: self._resolve(p, False), CARD).pack(side="right", padx=(8, 0))
                if st == "aprobación":
                    Link(row, "aprobar", lambda p=pid: self._resolve(p, True), CARD).pack(side="right", padx=(8, 0))
            else:
                tk.Label(row, text=st, bg=CARD, fg=color, font=(SANS, 8, "bold")).pack(side="right")
            tk.Label(row, text="●", bg=CARD, fg=color, font=(SYMBOL, 8)).pack(side="left")
            tk.Label(row, text=t if len(t) <= 40 else t[:39] + "…", bg=CARD, fg=TEXT, font=(SANS, 9),
                     anchor="w").pack(side="left", padx=(4, 0), fill="x", expand=True)

    # --- utilidades de vistas ------------------------------------------------------------------------------------------
    def _panel(self, parent: tk.Misc, title: str, action: tuple[str, Callable[[], None]] | None = None) -> RoundPanel:
        p = RoundPanel(parent)
        head = tk.Frame(p.inner, bg=PANEL)
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text=spaced(title), bg=PANEL, fg=MUTED, font=(SANS, 8, "bold")).pack(side="left")
        if action:
            Link(head, action[0], action[1], PANEL).pack(side="right")
        return p

    def _tree(self, parent: tk.Misc, cols: list[tuple[str, str, int]]) -> ttk.Treeview:
        wrap = tk.Frame(parent, bg=PANEL)
        wrap.pack(fill="both", expand=True)
        widest = max(c[2] for c in cols)
        tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", style="Dark.Treeview")
        for key, title, width in cols:
            tree.heading(key, text=spaced(title), anchor="w")
            tree.column(key, width=width, minwidth=40, anchor="w", stretch=width == widest)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")

        def autohide(lo: str, hi: str) -> None:
            if float(lo) <= 0.0 and float(hi) >= 1.0:
                sb.pack_forget()
            elif not sb.winfo_ismapped():
                sb.pack(side="right", fill="y", before=tree)
            sb.set(lo, hi)

        tree.configure(yscrollcommand=autohide)
        tree.pack(side="left", fill="both", expand=True)
        for tag, color in [("ok", GREEN), ("muted", MUTED), ("bad", RED), ("cyan", CYAN), ("warn", ORANGE)]:
            tree.tag_configure(tag, foreground=color)
        return tree

    @staticmethod
    def _text(parent: tk.Misc, mono: bool = False, editable: bool = False) -> tk.Text:
        t = tk.Text(parent, bg=INPUT, fg=TEXT, insertbackground=CYAN, relief="flat", bd=0, wrap="none" if mono else "word",
                    font=(MONO, 10) if mono else (SANS, 10), padx=12, pady=10, highlightthickness=1,
                    highlightbackground=PILL_BORDER, highlightcolor=CYAN, selectbackground=ACTIVE, undo=editable,
                    spacing1=2, spacing3=2)
        t.tag_configure("ok", foreground=GREEN, font=(SANS, 11, "bold"))
        t.tag_configure("bad", foreground=RED, font=(SANS, 11, "bold"))
        t.tag_configure("muted", foreground=MUTED)
        if not editable:
            t.configure(state="disabled", cursor="arrow")
        return t

    @staticmethod
    def _write(widget: tk.Text, parts: list[tuple[str, str | None]]) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for text, tag in parts:
            widget.insert("end", text, tag or ())
        widget.configure(state="disabled")

    # --- vista Núcleo (herramientas del harness) ----------------------------------------------------------------
    def _view_nucleo(self, f: tk.Frame) -> None:
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(0, 12))
        self.tool_pills: dict[str, Pill] = {}
        for key, label in HARNESS_TOOLS:
            pill = Pill(bar, [label], command=lambda k=key: self.show_tool(k), variant="seg", height=32, radius=9,
                        size=9)
            pill.pack(side="left", padx=(0, 6))
            self.tool_pills[key] = pill
        stack = tk.Frame(f, bg=BG)
        stack.pack(fill="both", expand=True)
        self.tools: dict[str, tk.Frame] = {}
        for key, builder in [("estado", self._view_status), ("pruebas", self._view_live),
                             ("manifiesto", self._view_manifest), ("borradores", self._view_drafts),
                             ("auditoria", self._view_audit),
                             ("tests", self._view_tests)]:
            sub = tk.Frame(stack, bg=BG)
            sub.place(relx=0, rely=0, relwidth=1, relheight=1)
            builder(sub)
            self.tools[key] = sub
        self.show_tool("estado")

    def _view_config(self, f: tk.Frame) -> None:
        """Configuración dentro de la misma ventana: no abre navegador ni otra página."""
        self.config_view = ConfigView(f, self.app.config, self.app, on_models=self._config_changed)
        self.config_view.pack(fill="both", expand=True)

    def _config_changed(self) -> None:
        aviso = self.app.reload_models()
        if aviso:
            self.config_view.decir(aviso, False)

    # --- vista Brigadas (catálogo) --------------------------------------------------------------------------------------
    def _view_brigades(self, f: tk.Frame) -> None:
        note = RoundPanel(f, fill=INPUT, border=PILL_BORDER, radius=12, height=60)
        note.pack(fill="x")
        root = self.app.project_root
        where = f"{root}\\brigadas y de" if root else "(no encontré la carpeta del proyecto)"
        tk.Label(note.inner, text=f"Se leen de {where} las brigadas de ejemplo del núcleo (#ej). Se pueden montar "
                                  "las que tienen manifest.yaml; elegí una y tocá Montar. Doble clic para ver qué le "
                                  "falta a cada una.", bg=INPUT, fg=MUTED,
                 font=(SANS, 9), anchor="w", justify="left", wraplength=1000).pack(fill="both", expand=True)
        p = self._panel(f, "Catálogo de brigadas")
        p.pack(fill="both", expand=True, pady=(12, 0))
        bar = tk.Frame(p.inner, bg=PANEL)
        bar.pack(fill="x", pady=(0, 8))
        Pill(bar, ["Montar"], command=lambda: self._mount_selected(True), variant="primary", outer=PANEL,
             width=120).pack(side="left")
        Pill(bar, ["Desmontar"], command=lambda: self._mount_selected(False), variant="ghost", outer=PANEL,
             width=120).pack(side="left", padx=8)
        self.catalog_msg = tk.Label(bar, text="", bg=PANEL, fg=MUTED, font=(SANS, 9), anchor="w", justify="left",
                                    wraplength=760)
        self.catalog_msg.pack(side="left", padx=8, fill="x", expand=True)
        self.catalog = self._tree(p.inner, [("n", "#", 50), ("name", "Brigada", 220), ("cooks", "Cocineros", 380),
                                            ("manifest", "Manifiesto", 150), ("state", "Estado", 150)])
        self._fill_catalog()
        self.catalog.bind("<Double-1>", lambda e: self.catalog.focus() and self.show_detail(self.catalog.focus()))

    def _fill_catalog(self) -> None:
        sel = self.catalog.focus()
        self.catalog.delete(*self.catalog.get_children())
        for b in self.app.brigades:
            cooks = ", ".join(b.cooks + (["jefe"] if b.chief else [])) or "—"
            self.catalog.insert("", "end", iid=b.id, values=(b.number, b.name, cooks,
                                                              "válido" if b.manifest_ok else
                                                              ("con errores" if b.manifest_path else "falta"),
                                                              b.state),
                                tags=("ok" if b.mounted else ("bad" if b.error else "muted"),))
        if sel and self.catalog.exists(sel):
            self.catalog.focus(sel)
            self.catalog.selection_set(sel)

    def _mount_selected(self, mount: bool) -> None:
        bid = self.catalog.focus()
        if not bid:
            self.catalog_msg.configure(text="Elegí una brigada de la lista.", fg=ORANGE)
            return
        self._mount(bid, mount, self.catalog_msg)

    def _mount(self, bid: str, mount: bool, label: tk.Label | None = None) -> None:
        msg = self.app.mount(bid) if mount else self.app.unmount(bid)
        if label is not None:
            label.configure(text=msg, fg=RED if msg.startswith("No se pudo") else GREEN)
        if not mount and self.scope == bid:
            self.scope = ORCHESTRATOR
        self._build_row()
        self._scope_header()
        self.refresh()
        b = self.app.brigade(bid)
        if b is not None and self.views["brigada"].winfo_ismapped():
            self._fill_brigade(b)

    def _revive_selected(self) -> None:
        sel = self.cooks_tree.focus()
        if not sel:
            return
        cook, brigade, state = self.cooks_tree.item(sel, "values")
        if "jefe" in cook and state.startswith("caído"):
            self.chat_note.configure(text=self.app.revive_chief(brigade))
            self.refresh()

    def _resolve(self, pid: int, approve: bool) -> None:
        try:
            msg = self.app.approve(pid) if approve else self.app.reject(pid)
        except Exception as exc:  # noqa: BLE001
            msg = f"No se pudo: {exc}"
        self.chat_note.configure(text=msg)
        self.refresh()

    # --- vista de una brigada -------------------------------------------------------------------------------------------
    def _view_brigade(self, f: tk.Frame) -> None:
        f.columnconfigure(0, weight=3)
        f.columnconfigure(1, weight=2)
        f.rowconfigure(1, weight=1)
        pd = self._panel(f, "Qué hace")
        pd.configure(height=110)
        pd.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.b_desc = tk.Label(pd.inner, text="", bg=PANEL, fg=TEXT, font=(SANS, 11), anchor="nw", justify="left",
                               wraplength=1050)
        self.b_desc.pack(fill="both", expand=True)
        pc = self._panel(f, "Cocineros")
        pc.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.b_cooks = self._tree(pc.inner, [("c", "Cocinero", 260), ("e", "Estado", 300)])
        ps = self._panel(f, "Camino para montarla")
        ps.grid(row=1, column=1, sticky="nsew")
        self.b_steps = tk.Frame(ps.inner, bg=PANEL)
        self.b_steps.pack(fill="both", expand=True)
        self._detail_bid = ""
        self.b_mount = Pill(ps.inner, ["Montar"], command=self._mount_detail, variant="primary", outer=PANEL, width=140)
        self.b_mount.pack(anchor="w", pady=(8, 0))
        self.b_mount.set(enabled=False)

    def _fill_brigade(self, b) -> None:
        self.b_desc.configure(text=b.description or "Sin descripción en su README.")
        self.b_cooks.delete(*self.b_cooks.get_children())
        for c in b.cooks:
            self.b_cooks.insert("", "end", values=(c, "montado" if b.mounted else
                                                   ("sin montar" if b.mountable else "esperando el manifiesto")),
                                tags=("ok" if b.mounted else "muted",))
        for w in self.b_steps.winfo_children():
            w.destroy()
        steps = [
            (b.manifest_path is not None, "Tiene manifest.yaml", "lo escribe su pieza en codigo\\"),
            (b.manifest_ok, "El manifiesto valida", "; ".join(b.manifest_errors) or "esquema de raphael-core"),
            (b.contract_ok, f"Pide un contrato compatible con {CONTRACT_VERSION}", "campo contract del manifiesto"),
            (b.mountable, "La encuentra el cargador", b.error or "manifest.yaml en una carpeta que lee el panel"),
            (b.mounted, "Montada en esta instalación", "brigades: en installation.yaml"),
        ]
        self._detail_bid = b.id
        self.b_mount.set(["Desmontar" if b.mounted else "Montar"], enabled=b.mountable)
        for ok, label, hint in steps:
            row = tk.Frame(self.b_steps, bg=PANEL)
            row.pack(fill="x", pady=4)
            tk.Label(row, text="●" if ok else "○", bg=PANEL, fg=GREEN if ok else DIM, font=(SYMBOL, 11)).pack(
                side="left", padx=(0, 10))
            col = tk.Frame(row, bg=PANEL)
            col.pack(side="left", fill="x")
            tk.Label(col, text=label, bg=PANEL, fg=TEXT if ok else MUTED, font=(SANS, 10, "bold")).pack(anchor="w")
            tk.Label(col, text=hint, bg=PANEL, fg=DIM, font=(SANS, 8)).pack(anchor="w")

    def _mount_detail(self) -> None:
        b = self.app.brigade(self._detail_bid)
        if b is not None:
            self._mount(b.id, not b.mounted)

    # --- vista Estado --------------------------------------------------------------------------------------------------
    def _view_status(self, f: tk.Frame) -> None:
        tiles = tk.Frame(f, bg=BG)
        tiles.pack(fill="x")
        self.tiles: dict[str, tk.Label] = {}
        for i, (key, label) in enumerate([("brigades", "Brigadas montadas"), ("subscribers", "Suscriptores del bus"),
                                          ("down", "Piezas caídas"), ("audit", "Registros de auditoría")]):
            p = RoundPanel(tiles, fill=CARD, border=CARD_BORDER, radius=12, height=88)
            p.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            tiles.columnconfigure(i, weight=1)
            tk.Label(p.inner, text=spaced(label), bg=CARD, fg=MUTED, font=(SANS, 7, "bold")).pack(anchor="w")
            v = tk.Label(p.inner, text="0", bg=CARD, fg=TEXT, font=(SANS, 22, "bold"))
            v.pack(anchor="w")
            self.tiles[key] = v

        mid = tk.Frame(f, bg=BG)
        mid.pack(fill="both", expand=True, pady=(12, 0))
        mid.columnconfigure(0, weight=2)
        mid.columnconfigure(1, weight=3)
        mid.rowconfigure(0, weight=1)
        pb = self._panel(mid, "Brigadas encontradas")
        pb.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.brigades_tree = self._tree(pb.inner, [("id", "Brigada", 190), ("estado", "Estado", 200)])
        pt = self._panel(mid, "Tandas del harness v2")
        pt.grid(row=0, column=1, sticky="nsew")
        stages = self._tree(pt.inner, [("t", "Tanda", 60), ("que", "Qué", 330), ("estado", "Estado", 110)])
        for t, que, estado in STAGES:
            stages.insert("", "end", values=(t, que, estado), tags=("ok" if estado == "hecha" else "muted",))

        pm = self._panel(f, "Módulos de raphael_core")
        pm.configure(height=200)
        pm.pack(fill="x", pady=(12, 0))
        mt = self._tree(pm.inner, [("m", "Módulo", 130), ("que", "Qué hace", 700)])
        for m, que in MODULES:
            mt.insert("", "end", values=(m, que))
        tk.Label(f, text=f"Python {self.app.status()['python']}", bg=BG, fg=DIM, font=(SANS, 8)).pack(anchor="w",
                                                                                                    pady=(8, 0))

    # --- vista Pruebas en vivo -----------------------------------------------------------------------------------------
    def _view_live(self, f: tk.Frame) -> None:
        left = RoundPanel(f, fill=CARD, border=CARD_BORDER, radius=14, width=270)
        left.pack(side="left", fill="y", padx=(0, 12))
        groups = [
            ("Bus de eventos", [("Publicar evento", self.app.ping), ("Suscriptor roto", self.app.broken_subscriber),
                                ("Ciclo de eventos", self.app.cycle)]),
            ("Aislamiento de fallos", [("Hacer fallar una pieza", self.app.fail), ("Revivir la pieza", self.app.revive)]),
            ("Auditoría", [("Auditar un dato con clave", self.app.secret)]),
        ]
        for gi, (label, buttons) in enumerate(groups):
            tk.Label(left.inner, text=spaced(label), bg=CARD, fg=MUTED, font=(SANS, 7, "bold")).pack(
                anchor="w", pady=(0 if gi == 0 else 16, 6))
            for text, fn in buttons:
                Pill(left.inner, [text], command=lambda fn=fn: self._do(fn), outer=CARD, width=236, radius=10,
                     bold=False).pack(anchor="w", pady=3)

        right = tk.Frame(f, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        msg = RoundPanel(right, fill=INPUT, border=CYAN, radius=12, height=64)
        msg.pack(fill="x")
        self.live_msg = tk.Label(msg.inner, text="Tocá un botón para ver el núcleo en acción.", bg=INPUT, fg=TEXT,
                                 font=(SANS, 11), anchor="w", justify="left", wraplength=700)
        self.live_msg.pack(fill="both", expand=True)
        feed = self._panel(right, "Historial del bus", ("limpiar", self._clear_history))
        feed.pack(fill="both", expand=True, pady=(12, 0))
        self.events_tree = self._tree(feed.inner, [("ev", "Evento", 180), ("datos", "Datos", 560)])

    def _clear_history(self) -> None:
        self.app.bus.history.clear()
        self.refresh()

    # --- vista Manifiesto ----------------------------------------------------------------------------------------------
    def _view_manifest(self, f: tk.Frame) -> None:
        f.columnconfigure(0, weight=3)
        f.columnconfigure(1, weight=2)
        f.rowconfigure(0, weight=1)
        pe = self._panel(f, "manifest.yaml", ("restaurar ejemplo", self._reset_manifest))
        pe.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.manifest_text = self._text(pe.inner, mono=True, editable=True)
        self.manifest_text.insert("1.0", EXAMPLE_MANIFEST)
        self.manifest_text.pack(fill="both", expand=True)
        bar = tk.Frame(pe.inner, bg=PANEL)
        bar.pack(fill="x", pady=(10, 0))
        Pill(bar, ["Validar"], command=self._validate, variant="primary", outer=PANEL, width=120).pack(side="right")
        tk.Label(bar, text="Pegá el manifiesto de una brigada y validalo contra el contrato 2.0.0.", bg=PANEL,
                 fg=MUTED, font=(SANS, 9)).pack(side="left")
        pr = self._panel(f, "Resultado")
        pr.grid(row=0, column=1, sticky="nsew")
        self.manifest_out = self._text(pr.inner)
        self.manifest_out.pack(fill="both", expand=True)
        self._write(self.manifest_out, [("Todavía no validaste nada.", "muted")])

    def _validate(self) -> None:
        ok, lines = self.app.validate_manifest(self.manifest_text.get("1.0", "end"))
        self._write(self.manifest_out, [("Válido" if ok else "No valida", "ok" if ok else "bad"),
                                        *[("\n\n" + ln if i == 0 else "\n" + ln, None) for i, ln in enumerate(lines)]])
        self.refresh()

    def _reset_manifest(self) -> None:
        self.manifest_text.delete("1.0", "end")
        self.manifest_text.insert("1.0", EXAMPLE_MANIFEST)

    # --- vista Borradores (H6) -----------------------------------------------------------------------------------------
    def _view_drafts(self, f: tk.Frame) -> None:
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        pe = self._panel(f, "Borrador (JSON)", ("restaurar ejemplo", self._reset_draft))
        pe.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.draft_text = self._text(pe.inner, mono=True, editable=True)
        self.draft_text.insert("1.0", EXAMPLE_DRAFT)
        self.draft_text.pack(fill="both", expand=True)
        bar = tk.Frame(pe.inner, bg=PANEL)
        bar.pack(fill="x", pady=(10, 0))
        Pill(bar, ["Crear borrador"], command=self._create_draft, variant="primary", outer=PANEL, width=150).pack(
            side="right")
        tk.Label(bar, text="Nace como borrador: no corre hasta que lo actives con su hash.", bg=PANEL, fg=MUTED,
                 font=(SANS, 9)).pack(side="left")
        right = tk.Frame(f, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        pl = self._panel(right, "Brigadas creadas")
        pl.pack(fill="x")
        self.drafts_tree = self._tree(pl.inner, [("id", "Id", 150), ("name", "Nombre", 180), ("state", "Estado", 110),
                                                 ("hash", "Hash", 120)])
        self.drafts_tree.configure(height=4)
        self.drafts_tree.bind("<<TreeviewSelect>>", lambda e: self._show_draft())
        acts = tk.Frame(pl.inner, bg=PANEL)
        acts.pack(fill="x", pady=(8, 0))
        Pill(acts, ["Activar"], command=self._activate_draft, variant="primary", outer=PANEL, width=110).pack(side="left")
        Pill(acts, ["Desactivar"], command=lambda: self._draft_do(self.app.draft_deactivate), variant="ghost",
             outer=PANEL, width=110).pack(side="left", padx=6)
        Pill(acts, ["Descartar"], command=lambda: self._draft_do(self.app.draft_discard), variant="ghost", outer=PANEL,
             width=110).pack(side="left")
        pr = self._panel(right, "Revisión (lo que aprobás)")
        pr.pack(fill="both", expand=True, pady=(12, 0))
        self.draft_out = self._text(pr.inner)
        self.draft_out.pack(fill="both", expand=True)
        self._write(self.draft_out, [("Creá un borrador o elegí uno de la lista para ver su revisión.", "muted")])
        self._fill_drafts()

    def _fill_drafts(self) -> None:
        sel = self.drafts_tree.focus()
        self.drafts_tree.delete(*self.drafts_tree.get_children())
        for d in self.app.draft_list():
            state = ("activa · montada" if d["mounted"] else "activa") if d["state"] == "activa" else \
                ("borrador (aprobación inválida)" if d["invalid_approval"] else "borrador")
            self.drafts_tree.insert("", "end", iid=d["id"], values=(d["id"], d["name"], state, d["hash"]),
                                    tags=("ok" if d["state"] == "activa" else "muted",))
        if sel and self.drafts_tree.exists(sel):
            self.drafts_tree.focus(sel)
            self.drafts_tree.selection_set(sel)

    def _show_draft(self) -> None:
        bid = self.drafts_tree.focus()
        if bid:
            self._write(self.draft_out, [(self.app.draft_review(bid), None)])

    def _create_draft(self) -> None:
        ok, text = self.app.draft_create(self.draft_text.get("1.0", "end"))
        self._write(self.draft_out, [("Borrador guardado (NO está activo)\n\n" if ok else "No se creó\n\n",
                                      "ok" if ok else "bad"), (text, None)])
        self._fill_drafts()
        self.refresh_audit_only()

    def _activate_draft(self) -> None:
        bid = self.drafts_tree.focus()
        if not bid:
            self._write(self.draft_out, [("Elegí un borrador de la lista.", "bad")])
            return
        h = next((d["hash"] for d in self.app.draft_list() if d["id"] == bid), "")
        # la aprobación es sobre el hash que la persona está viendo en la revisión
        msg = self.app.draft_activate(bid, h)
        self._write(self.draft_out, [(msg + "\n\n", "bad" if msg.startswith("No se") else "ok"),
                                     (self.app.draft_review(bid), None)])
        self._after_drafts()

    def _draft_do(self, fn: Callable[[str], str]) -> None:
        bid = self.drafts_tree.focus()
        if not bid:
            return
        self._write(self.draft_out, [(fn(bid), None)])
        self._after_drafts()

    def _after_drafts(self) -> None:
        self._fill_drafts()
        self._build_row()
        self._scope_header()
        self.refresh()

    def _reset_draft(self) -> None:
        self.draft_text.delete("1.0", "end")
        self.draft_text.insert("1.0", EXAMPLE_DRAFT)

    # --- vista Auditoría -----------------------------------------------------------------------------------------------
    def _view_audit(self, f: tk.Frame) -> None:
        p = self._panel(f, "Registro (lo más nuevo arriba)")
        p.pack(fill="both", expand=True)
        self.audit_tree = self._tree(p.inner, [("n", "#", 50), ("when", "Cuándo", 160), ("what", "Qué", 170),
                                               ("who", "Quién", 140), ("detail", "Detalle", 520)])

    # --- vista Tests ---------------------------------------------------------------------------------------------------
    def _view_tests(self, f: tk.Frame) -> None:
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(0, 12))
        self.tests_btn = Pill(bar, ["Correr los tests"], command=self._run_tests, variant="primary", width=170)
        self.tests_btn.pack(side="left")
        self.regr_btn = Pill(bar, ["Empresas sobre el v2"], command=self._run_regression, variant="ghost", width=200)
        self.regr_btn.pack(side="left", padx=(10, 0))
        self.tests_label = tk.Label(bar, text="", bg=BG, fg=MUTED, font=(SANS, 10, "bold"))
        self.tests_label.pack(side="left", padx=14)
        p = self._panel(f, "Salida de pytest")
        p.pack(fill="both", expand=True)
        self.tests_out = self._text(p.inner, mono=True)
        self.tests_out.pack(fill="both", expand=True)

    def _run_regression(self) -> None:
        self.regr_btn.set(enabled=False)
        self.tests_label.configure(text="Corriendo Empresas sobre el v2…", fg=MUTED)

        def work() -> None:
            self._jobs.put(("tests", self.app.run_regression()))

        threading.Thread(target=work, daemon=True).start()

    def _run_tests(self) -> None:
        self.tests_btn.set(enabled=False)
        self.tests_label.configure(text="Corriendo…", fg=MUTED)

        def work() -> None:
            self._jobs.put(("tests", self.app.run_tests()))

        threading.Thread(target=work, daemon=True).start()

    def _poll_jobs(self) -> None:
        try:
            while True:
                kind, (ok, out) = self._jobs.get_nowait()
                if kind == "chat":
                    self.chat_send.set(enabled=True)
                    self._busy = False
                    self.refresh()
                    continue
                if kind == "tests":
                    self.tests_btn.set(enabled=True)
                    self.regr_btn.set(enabled=True)
                    last = out.strip().splitlines()[-1] if out.strip() else ""
                    self.tests_label.configure(text=("● En verde · " if ok else "● Fallan · ") + last,
                                               fg=GREEN if ok else RED)
                    self._write(self.tests_out, [(out, None)])
                    self.refresh()
        except queue.Empty:
            pass
        self.after(150, self._poll_jobs)

    # --- acciones y refresco -------------------------------------------------------------------------------------------
    def _do(self, fn: Callable[[], str]) -> None:
        try:
            msg = fn()
        except Exception as exc:  # noqa: BLE001 - el panel nunca se cae por una prueba
            msg = f"Falló la prueba: {exc!r}"
        self.live_msg.configure(text=msg)
        self.refresh()

    def refresh_audit_only(self) -> None:
        self.audit_tree.delete(*self.audit_tree.get_children())
        for e in self.app.audit_rows():
            detail = {k: v for k, v in e.items() if k not in ("n", "when", "what", "who")}
            tag = "bad" if e["what"] in ("evento_fallido", "pieza_caida") else ""
            self.audit_tree.insert("", "end", values=(e["n"], e["when"].replace("T", " "), e["what"], e["who"],
                                                      ", ".join(f"{k}={v}" for k, v in detail.items())), tags=(tag,))
        self.tiles["audit"].configure(text=str(len(self.app.audit.entries())))

    def refresh(self) -> None:
        st = self.app.status()
        mounted = self.app.mounted()
        # principal
        name = "Orquestador" if self.scope == ORCHESTRATOR else (self.app.brigade(self.scope).name
                                                                 if self.app.brigade(self.scope) else self.scope)
        self.chat_title.configure(text=spaced(f"Chat · {name}"))
        self.chat_note.configure(text="modo muestra: no se guarda" if self.app.sample else
                                 f"modelo: {st.get('models', '—')}")
        self.chat_entry.configure(state="disabled" if self.app.sample else "normal")
        self.chat_send.set(enabled=not self.app.sample)
        self._render_chat()
        self._render_status()

        none = "No hay brigadas montadas.\nAgregalas con «Agregar brigadas»."
        self.cooks_tree.delete(*self.cooks_tree.get_children())
        for c, b, s in self.app.cooks(self.scope):
            bad = s.startswith(("caíd", "mala"))
            self.cooks_tree.insert("", "end", values=(f"●  {c.replace('-', ' ')}", b, s),
                                   tags=("bad" if bad else {"trabajando": "cyan", "en espera": "ok"}.get(s, "muted"),))
        self._show_empty(self.cooks_empty, None if self.cooks_tree.get_children() else none)
        self.eph_tree.delete(*self.eph_tree.get_children())
        for e, b, t, d in self.app.ephemerals(self.scope):
            self.eph_tree.insert("", "end", values=(f"⚡  {e}", b, t, d), tags=("warn",))
        self._show_empty(self.eph_empty, None if self.eph_tree.get_children() else
                         (none if not mounted else "Ningún efímero corriendo.\nNacen con cada tarea y mueren al terminar."))
        self.tools_tree.delete(*self.tools_tree.get_children())
        for n, who, lvl, on in self.app.tools(self.scope):
            self.tools_tree.insert("", "end", iid=n, values=(n, who, lvl, "activada" if on else "desactivada"),
                                   tags=(LEVEL_TAG.get(lvl, "") if on else "muted",))
        self._show_empty(self.tools_empty, None if self.tools_tree.get_children() else
                         (none if not mounted else "Las herramientas salen de los manifiestos de las brigadas."))

        # encabezado
        n_d = len(st["down"])
        self.pill_down.set([f"⚡ {n_d} pieza{'s' if n_d != 1 else ''}", f"caída{'s' if n_d != 1 else ''}"],
                           variant="danger" if n_d else "info")
        # núcleo
        self.tiles["brigades"].configure(text=str(len([b for b in self.app.brigades if b.mounted])))
        self.tiles["subscribers"].configure(text=str(len(st["subscribers"])), fg=CYAN)
        self.tiles["down"].configure(text=str(n_d), fg=RED if n_d else TEXT)
        self.brigades_tree.delete(*self.brigades_tree.get_children())
        for b in self.app.brigades:
            self.brigades_tree.insert("", "end", values=(b.name, b.state), tags=("ok" if b.mounted else "muted",))
        if not self.app.brigades:
            self.brigades_tree.insert("", "end", values=("(ninguna)", "no encontré la carpeta brigadas"),
                                      tags=("muted",))
        self.events_tree.delete(*self.events_tree.get_children())
        for ev, data in self.app.event_rows():
            self.events_tree.insert("", "end", values=(ev, data), tags=("cyan",))
        if hasattr(self, "catalog"):
            self._fill_catalog()
        self.refresh_audit_only()


HarnessPanel = RaphaelApp


def main() -> None:
    try:
        app = RaphaelApp()
    except Exception:  # noqa: BLE001 - con pythonw no hay consola: el error se muestra y queda en un archivo
        import traceback
        from tkinter import messagebox

        detail = traceback.format_exc()
        (HERE / "ultimo-error.txt").write_text(detail, encoding="utf-8")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Raphael — Harness v2", "El panel no pudo arrancar.\n\nEl detalle quedó en "
                             f"{HERE / 'ultimo-error.txt'}\n\n{detail[-600:]}")
        return
    app.mainloop()


if __name__ == "__main__":
    main()
