"""Pantalla de Configuración dentro del panel del harness (Tk): barra lateral con 9 secciones, todo se guarda con
`config_modelo.Configuracion`. No abre navegador ni otra ventana: es una vista más de «Raphael — Harness v2»."""

from __future__ import annotations

import json
import threading
import tkinter as tk
import urllib.request
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk

from config_modelo import (CAMPOS, NIVELES_AUTONOMIA, OPCIONES_APARIENCIA, SECCIONES, SIEMPRE_PIDE, Configuracion, es_local)
from raphael_core.models.config import ROLES
from widgets import ACTIVE, BG, CARD, CYAN, GREEN, INPUT, MUTED, ORANGE, PANEL, RED, SANS, TEXT, MONO, Pill, spaced

#: prefijos de variables por brigada (id de la carpeta sin número) para el editor de «toda su config»
PREFIJOS = {"seguridad": ("SEGURIDAD_", "NMAP_", "SQLMAP_", "ZAP_"), "antimalware": ("ANTIMALWARE_", "CLAMD_", "VIRUSTOTAL_"),
            "investigacion": ("INVESTIGACION_", "BRAVE_", "SEARXNG_"), "geolocalizacion-publica": ("RAPHAEL_GEO_", "SHODAN_", "AISSTREAM_",
                                                                                                 "FIRMS_", "WINDY_", "OPENWEATHER_", "OPENCELLID_"),
            "memoria-cerebro": ("MEMORIA_",), "ingesta": ("RAPHAEL_VAULT_", "YT_", "INGESTA_"), "trading": ("TRADING_", "IBKR_"),
            "operaciones": ("OPERACIONES_",), "autorreparacion": ("RAPHAEL_REPAIR_",), "contenido": ("CONTENIDO_", "IG_", "META_ADS_",
                                                                                                   "COMFYUI_", "VIDEO_"),
            "raphael-empresas": ("MP_", "META_", "TRANSFER_", "TIENDANUBE_", "SHOPIFY_", "WOO_"), "legales": ("LEGALES_",)}


def _probar(url: str, clave: str) -> str:
    """Una consulta de solo lectura (`/models`) para ver si la API responde. No manda ningún dato tuyo."""
    req = urllib.request.Request(url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {clave}"} if clave else {})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 - dirección elegida por la persona dueña
            return f"responde ({r.status})"
    except Exception as e:  # noqa: BLE001
        return f"no responde: {str(e)[:90]}"


class ConfigView(tk.Frame):
    def __init__(self, parent: tk.Misc, cfg: Configuracion, app, on_models: Callable[[], None] | None = None) -> None:
        super().__init__(parent, bg=BG)
        self.cfg, self.app, self.on_models = cfg, app, on_models
        side = tk.Frame(self, bg=PANEL, width=230)
        side.pack(side="left", fill="y", padx=(0, 14))
        side.pack_propagate(False)
        tk.Label(side, text=spaced("Configuración"), bg=PANEL, fg=MUTED, font=(SANS, 8, "bold")).pack(anchor="w", padx=14, pady=(14, 8))
        self.nav: dict[str, tk.Label] = {}
        for key, titulo, sub in SECCIONES:
            b = tk.Label(side, text=titulo, bg=PANEL, fg=TEXT, font=(SANS, 10, "bold"), anchor="w", cursor="hand2", padx=14, pady=7)
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=key: self.mostrar(k))
            self.nav[key] = b
        self.msg = tk.Label(side, text="", bg=PANEL, fg=MUTED, font=(SANS, 9), wraplength=200, justify="left", anchor="w")
        self.msg.pack(side="bottom", fill="x", padx=14, pady=12)
        self.area = tk.Frame(self, bg=PANEL)
        self.area.pack(side="left", fill="both", expand=True)
        self.actual = "ia"
        self.mostrar("ia")

    # --- utilidades -------------------------------------------------------------------------------------------------
    def decir(self, texto: str, ok: bool = True) -> None:
        self.msg.configure(text=texto, fg=GREEN if ok else RED)

    def _intentar(self, fn: Callable[[], object], ok: str = "Guardado.") -> bool:
        try:
            fn()
        except PermissionError as e:
            self.decir(str(e), False)
            return False
        except Exception as e:  # noqa: BLE001 - validación en español: se muestra tal cual
            self.decir(str(e), False)
            return False
        self.decir(ok)
        return True

    def _scroll(self) -> tk.Frame:
        for w in self.area.winfo_children():
            w.destroy()
        canvas = tk.Canvas(self.area, bg=PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(canvas.master, orient="vertical", command=canvas.yview, style="Dark.Vertical.TScrollbar")
        inner = tk.Frame(canvas, bg=PANEL)
        win = canvas.create_window(0, 0, anchor="nw", window=inner)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        pad = tk.Frame(inner, bg=PANEL)
        pad.pack(fill="both", expand=True, padx=20, pady=16)
        return pad

    def _titulo(self, p: tk.Frame, texto: str, sub: str = "") -> None:
        tk.Label(p, text=texto, bg=PANEL, fg=TEXT, font=(SANS, 14, "bold"), anchor="w").pack(fill="x")
        if sub:
            tk.Label(p, text=sub, bg=PANEL, fg=MUTED, font=(SANS, 9), anchor="w", wraplength=820, justify="left").pack(fill="x", pady=(2, 10))

    def _sub(self, p: tk.Frame, texto: str) -> None:
        tk.Label(p, text=spaced(texto), bg=PANEL, fg=MUTED, font=(SANS, 8, "bold"), anchor="w").pack(fill="x", pady=(16, 6))

    def _entry(self, p: tk.Misc, ancho: int = 40, secreto: bool = False) -> tk.Entry:
        return tk.Entry(p, width=ancho, bg=INPUT, fg=TEXT, insertbackground=TEXT, relief="flat", font=(MONO, 10),
                        show="•" if secreto else "", highlightthickness=1, highlightbackground="#1d2b42", highlightcolor=CYAN)

    def _boton(self, p: tk.Misc, texto: str, cmd: Callable[[], None], variante: str = "ghost", ancho: int = 130) -> Pill:
        return Pill(p, [texto], command=cmd, variant=variante, outer=PANEL, width=ancho, height=34, size=9)

    def mostrar(self, key: str) -> None:
        self.actual = key
        for k, b in self.nav.items():
            b.configure(bg=ACTIVE if k == key else PANEL, fg=CYAN if k == key else TEXT)
        getattr(self, f"_s_{key}")()

    # --- secciones con campos simples (claves, acceso, voz, carpetas, autonomía) -------------------------------------
    def _formulario(self, seccion: str, titulo: str, sub: str, extra: Callable[[tk.Frame], None] | None = None) -> None:
        p = self._scroll()
        self._titulo(p, titulo, sub)
        if extra:
            extra(p)
        cajas: dict[str, tk.Entry | ttk.Combobox] = {}
        valores = {f["nombre"]: f["valor"] for f in self.cfg.vista()}
        for c in (c for c in CAMPOS if c.seccion == seccion and c.nombre != "RAPHAEL_AUTONOMIA"):
            fila = tk.Frame(p, bg=PANEL)
            fila.pack(fill="x", pady=3)
            tk.Label(fila, text=c.etiqueta, bg=PANEL, fg=TEXT, font=(SANS, 9), width=36, anchor="w").pack(side="left")
            if c.tipo == "opcion":
                w: tk.Widget = ttk.Combobox(fila, values=("", *c.opciones), width=38, state="readonly")
                w.set(valores[c.nombre])
            else:
                w = self._entry(fila, 40, secreto=c.tipo == "secreto")
                w.insert(0, valores[c.nombre])
            w.pack(side="left", padx=6)
            cajas[c.nombre] = w
            if c.tipo == "secreto":
                tk.Button(fila, text="👁", bg=PANEL, fg=MUTED, relief="flat", cursor="hand2",
                          command=lambda e=w: e.configure(show="" if e.cget("show") else "•")).pack(side="left")
            if c.tipo == "carpeta":
                tk.Button(fila, text="…", bg=PANEL, fg=MUTED, relief="flat", cursor="hand2",
                          command=lambda e=w, n=c.nombre: self._elegir(e, n)).pack(side="left")
            if c.reinicia:
                tk.Label(fila, text="reinicia", bg=PANEL, fg=ORANGE, font=(SANS, 8)).pack(side="left", padx=4)
            if c.ayuda:
                tk.Label(p, text=c.ayuda, bg=PANEL, fg=MUTED, font=(SANS, 8), anchor="w").pack(fill="x", padx=(0, 0))
        botones = tk.Frame(p, bg=PANEL)
        botones.pack(fill="x", pady=(14, 0))

        def guardar() -> None:
            poner, quitar = {}, []
            for n, w in cajas.items():
                v = w.get().strip()
                if v != valores[n]:
                    (poner.__setitem__(n, v) if v else quitar.append(n))
            if not poner and not quitar:
                self.decir("No hay cambios.")
                return
            res: list[str] = []
            if self._intentar(lambda: res.extend(self.cfg.aplicar(poner, quitar)), "Guardado y aplicado en caliente."):
                if res:
                    self.decir("Guardado. Para que tome efecto reiniciá: " + ", ".join(res), True)
                if self.on_models:
                    self.on_models()
                self.mostrar(self.actual)

        self._boton(botones, "Guardar cambios", guardar, "primary", 150).pack(side="left")

    def _s_claves(self) -> None:
        self._formulario("claves", "Claves y cuentas", "Se guardan solo en tu raphael.env local (nunca en git ni en el chat) y se aplican en "
                         "caliente. Dejar vacío y guardar quita la clave. Las que dicen «reinicia» toman efecto al reabrir.")

    def _s_acceso(self) -> None:
        self._formulario("acceso", "Acceso y celular", "Dirección del celular (Tailscale) y modelo local. Las direcciones de modelos locales "
                         "tienen que ser de esta PC. Desde la PC entrás sin clave; lo irreversible y todo lo de afuera piden clave.")

    def _s_voz(self) -> None:
        self._formulario("voz", "Voz", "Escuchar (Whisper) y hablar (Piper). Sin esto Raphael anda igual por texto.")

    def _s_carpetas(self) -> None:
        self._formulario("carpetas", "Carpetas y datos", "Donde Raphael puede leer, escribir y vigilar. Varias rutas se separan con ;")

    def _elegir(self, caja: tk.Entry, nombre: str) -> None:
        ruta = filedialog.askopenfilename() if nombre.startswith(("VOICE_",)) else filedialog.askdirectory()
        if ruta:
            caja.delete(0, "end")
            caja.insert(0, ruta)

    # --- autonomía ------------------------------------------------------------------------------------------------
    def _s_autonomia(self) -> None:
        p = self._scroll()
        self._titulo(p, "Autonomía y aprobaciones", "Un nivel global para todo lo que se queda adentro de tu PC.")
        var = tk.StringVar(value=self.cfg.autonomia())
        texto = {"cauteloso": "Cauteloso: te consulta casi todo antes de hacerlo.",
                 "equilibrado": "Equilibrado: hace solo lo rutinario y reversible; consulta lo demás.",
                 "confiado": "Confiado: hace solo todo lo reversible y te avisa después."}
        for n in NIVELES_AUTONOMIA:
            tk.Radiobutton(p, text=texto[n], variable=var, value=n, bg=PANEL, fg=TEXT, selectcolor=INPUT, activebackground=PANEL,
                           activeforeground=CYAN, font=(SANS, 10), anchor="w",
                           command=lambda: self._intentar(lambda: (self.cfg.aplicar({"RAPHAEL_AUTONOMIA": var.get()}), None))
                           ).pack(fill="x", pady=3)
        self._sub(p, "Esto nunca se afloja (no es configurable)")
        for s in SIEMPRE_PIDE:
            tk.Label(p, text=f"🔒 {s}: siempre pide tu aprobación", bg=PANEL, fg=TEXT, font=(SANS, 10), anchor="w").pack(fill="x", pady=2)

    # --- Cerebro e IA ---------------------------------------------------------------------------------------------
    def _s_ia(self) -> None:
        p = self._scroll()
        self._titulo(p, "Cerebro e IA", "Roles, escalones y proveedores. Podés apuntar cada rol, cada brigada y cada cocinero a la API y el "
                     "modelo que quieras. Las brigadas solo-local aceptan únicamente proveedores de esta PC.")
        cfg = self.cfg.modelos()
        self._sub(p, "1 · Proveedores (cualquier API compatible con OpenAI)")
        lista = tk.Frame(p, bg=PANEL)
        lista.pack(fill="x")
        propios = self.cfg._usuario().get("providers", {})  # noqa: SLF001
        for nombre, sp in cfg.providers.items():
            fila = tk.Frame(lista, bg=PANEL)
            fila.pack(fill="x", pady=2)
            marca = "PC" if sp.is_local else "nube"
            tk.Label(fila, text=f"{nombre}", bg=PANEL, fg=TEXT, font=(SANS, 10, "bold"), width=18, anchor="w").pack(side="left")
            tk.Label(fila, text=f"{sp.model} · {sp.base_url} · {marca}", bg=PANEL, fg=MUTED, font=(SANS, 9), anchor="w").pack(side="left")
            res = tk.Label(fila, text="", bg=PANEL, fg=MUTED, font=(SANS, 9))
            tk.Button(fila, text="probar", bg=PANEL, fg=CYAN, relief="flat", cursor="hand2",
                      command=lambda s=sp, r=res: self._probar_proveedor(s, r)).pack(side="right")
            res.pack(side="right", padx=8)
            if nombre in propios:
                tk.Button(fila, text="quitar", bg=PANEL, fg=RED, relief="flat", cursor="hand2",
                          command=lambda n=nombre: self._quitar_proveedor(n)).pack(side="right")
        self._sub(p, "Agregar o cambiar un proveedor")
        f = {}
        for k, etiqueta, ancho in (("nombre", "Nombre (ej. groq)", 18), ("url", "Dirección (…/v1)", 44), ("modelo", "Modelo", 30),
                                   ("clave", "Variable de la clave (ej. GROQ_API_KEY)", 26), ("escalon", "Escalón (local, gratis, pago)", 12)):
            fila = tk.Frame(p, bg=PANEL)
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text=etiqueta, bg=PANEL, fg=TEXT, font=(SANS, 9), width=36, anchor="w").pack(side="left")
            f[k] = self._entry(fila, ancho)
            f[k].pack(side="left", padx=6)

        def agregar() -> None:
            if self._intentar(lambda: self.cfg.agregar_proveedor(f["nombre"].get().strip(), f["url"].get().strip(), f["modelo"].get(),
                                                                  f["clave"].get().strip(), escalon=f["escalon"].get().strip()),
                              "Proveedor guardado. Pegá su clave en «Claves y cuentas» o en Avanzado."):
                self._recargar()
        self._boton(p, "Guardar proveedor", agregar, "primary", 160).pack(anchor="w", pady=(8, 0))

        self._sub(p, "2 · Escalones de cada rol (en orden: local, gratis, pago)")
        cajas = {}
        for r in ROLES:
            fila = tk.Frame(p, bg=PANEL)
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text=r, bg=PANEL, fg=TEXT, font=(SANS, 10), width=14, anchor="w").pack(side="left")
            cajas[r] = self._entry(fila, 30)
            cajas[r].insert(0, ", ".join(cfg.roles.get(r, [])))
            cajas[r].pack(side="left", padx=6)
            tk.Button(fila, text="guardar", bg=PANEL, fg=CYAN, relief="flat", cursor="hand2",
                      command=lambda x=r: self._guardar_rol(x, cajas[x].get())).pack(side="left")

        self._sub(p, "3 · API y modelo de UNA brigada o cocinero (pisa al rol)")
        fila = tk.Frame(p, bg=PANEL)
        fila.pack(fill="x", pady=2)
        rol = ttk.Combobox(fila, values=ROLES, width=12, state="readonly")
        rol.set("cocinero")
        rol.pack(side="left")
        ids = sorted({b.id for b in getattr(self.app, "brigades", [])} | set(cfg.private))
        dest = ttk.Combobox(fila, values=ids, width=26)
        dest.pack(side="left", padx=6)
        provs = self._entry(fila, 30)
        provs.pack(side="left", padx=6)
        tk.Label(fila, text="proveedores en orden (vacío = volver al rol)", bg=PANEL, fg=MUTED, font=(SANS, 8)).pack(side="left")
        self._boton(p, "Aplicar a ese destino", lambda: self._poner_destino(rol.get(), dest.get().strip(), provs.get()), "primary", 190
                    ).pack(anchor="w", pady=(6, 0))

        self._sub(p, "Dónde apunta hoy cada cosa")
        t = tk.Text(p, height=min(14, 3 + len(ROLES) + len(cfg.overrides)), bg=INPUT, fg=TEXT, font=(MONO, 9), relief="flat", wrap="none")
        for fila in self.cfg.resumen_destinos():
            t.insert("end", f"{fila['clave']:<34} {', '.join(fila['escalones']) or '—':<18} {' → '.join(fila['proveedores']) or '—'}\n")
        t.configure(state="disabled")
        t.pack(fill="x")

        self._sub(p, "4 · Brigadas y ayudantes solo-local")
        priv = self._entry(p, 90)
        priv.insert(0, ", ".join(cfg.private))
        priv.pack(fill="x")
        self._boton(p, "Guardar lista solo-local", lambda: self._guardar_privadas(priv.get()), "ghost", 190).pack(anchor="w", pady=(6, 0))
        self._sub(p, "5 · Tope mensual del escalón pago (USD, 0 = no se usa)")
        tope = self._entry(p, 10)
        tope.insert(0, str(cfg.paid_cap_usd_month))
        tope.pack(anchor="w")
        self._boton(p, "Guardar tope", lambda: self._intentar(lambda: (self.cfg.tope_pago(float(tope.get().replace(",", "."))),
                                                                       self._avisar())), "ghost", 130).pack(anchor="w", pady=(6, 0))

    def _avisar(self) -> None:
        if self.on_models:
            self.on_models()

    def _recargar(self) -> None:
        self._avisar()
        self.mostrar(self.actual)

    def _probar_proveedor(self, sp, etiqueta: tk.Label) -> None:
        etiqueta.configure(text="probando…", fg=MUTED)
        clave = self.cfg.environ.get(sp.api_key_env, "") if sp.api_key_env else ""

        def trabajo() -> None:
            r = _probar(sp.base_url, clave)
            self.after(0, lambda: etiqueta.configure(text=r, fg=GREEN if r.startswith("responde") else RED))
        threading.Thread(target=trabajo, daemon=True).start()

    def _quitar_proveedor(self, n: str) -> None:
        if self._intentar(lambda: self.cfg.quitar_proveedor(n), "Proveedor quitado."):
            self._recargar()

    def _guardar_rol(self, rol: str, texto: str) -> None:
        if self._intentar(lambda: self.cfg.poner_rol(rol, [x.strip() for x in texto.split(",") if x.strip()])):
            self._avisar()

    def _poner_destino(self, rol: str, destino: str, provs: str) -> None:
        if not destino:
            self.decir("Elegí o escribí el id de la brigada o cocinero.", False)
            return
        if self._intentar(lambda: self.cfg.poner_destino(rol, destino, [x.strip() for x in provs.split(",") if x.strip()])):
            self._recargar()

    def _guardar_privadas(self, texto: str) -> None:
        nuevos = [x.strip() for x in texto.split(",") if x.strip()]
        sacadas = sorted(set(self.cfg.privadas()) - set(nuevos))
        conf = False
        if sacadas:
            conf = messagebox.askyesno("Sacar de solo-local", "Esto puede mandar a la nube datos de: " + ", ".join(sacadas) +
                                       ".\n\n¿Seguro que querés sacarlas?")
            if not conf:
                self.decir("No se cambió la lista.", False)
                return
        if self._intentar(lambda: self.cfg.poner_privadas(nuevos, confirmar_nube=conf)):
            self._avisar()

    # --- brigadas -------------------------------------------------------------------------------------------------
    def _s_brigadas(self) -> None:
        p = self._scroll()
        self._titulo(p, "Brigadas", "Prendé o apagá cada brigada y editá todas sus variables. Lo de afuera sigue pidiendo aprobación.")
        env = self.cfg.env()
        for b in getattr(self.app, "brigades", []):
            fila = tk.Frame(p, bg=PANEL)
            fila.pack(fill="x", pady=3)
            var = tk.BooleanVar(value=bool(b.mounted))
            tk.Checkbutton(fila, text=b.name, variable=var, bg=PANEL, fg=TEXT, selectcolor=INPUT, activebackground=PANEL, font=(SANS, 10, "bold"),
                           width=26, anchor="w", command=lambda i=b.id, v=var: self._montar(i, v.get())).pack(side="left")
            tk.Label(fila, text=b.state, bg=PANEL, fg=MUTED, font=(SANS, 9), width=14, anchor="w").pack(side="left")
            tk.Button(fila, text="variables…", bg=PANEL, fg=CYAN, relief="flat", cursor="hand2",
                      command=lambda i=b.id, n=b.name: self._variables_brigada(i, n)).pack(side="left", padx=6)
            if b.id in self.cfg.privadas():
                tk.Label(fila, text="solo-local", bg=PANEL, fg=ORANGE, font=(SANS, 8)).pack(side="left")
        if not getattr(self.app, "brigades", []):
            tk.Label(p, text="No hay brigadas encontradas.", bg=PANEL, fg=MUTED).pack(anchor="w")
        del env

    def _montar(self, bid: str, montar: bool) -> None:
        msg = self.app.mount(bid) if montar else self.app.unmount(bid)
        self.decir(msg, not msg.startswith("No se pudo"))
        if self.on_models:
            self.on_models()

    def _variables_brigada(self, bid: str, nombre: str) -> None:
        p = self._scroll()
        self._titulo(p, f"Variables de {nombre}", "Las que empiezan con " + ", ".join(PREFIJOS.get(bid, ("(sin prefijo conocido)",))) +
                     ". Podés agregar cualquiera: es el mismo raphael.env.")
        pref = PREFIJOS.get(bid, ())
        self._editor_variables(p, lambda n: n.startswith(pref) if pref else False, pref[0] if pref else "")
        self._boton(p, "← volver a Brigadas", lambda: self.mostrar("brigadas"), "ghost", 190).pack(anchor="w", pady=(16, 0))

    def _editor_variables(self, p: tk.Frame, filtro: Callable[[str], bool], plantilla: str = "") -> None:
        env = self.cfg.env()
        for n in sorted(k for k in env if filtro(k)):
            fila = tk.Frame(p, bg=PANEL)
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text=n, bg=PANEL, fg=TEXT, font=(MONO, 9), width=38, anchor="w").pack(side="left")
            secreto = self.cfg._es_secreta(n)  # noqa: SLF001
            e = self._entry(fila, 44, secreto=secreto)
            e.insert(0, env[n])
            e.pack(side="left", padx=6)
            if secreto:
                tk.Button(fila, text="👁", bg=PANEL, fg=MUTED, relief="flat", cursor="hand2",
                          command=lambda w=e: w.configure(show="" if w.cget("show") else "•")).pack(side="left")
            tk.Button(fila, text="guardar", bg=PANEL, fg=CYAN, relief="flat", cursor="hand2",
                      command=lambda k=n, w=e: self._poner_var(k, w.get())).pack(side="left", padx=4)
            tk.Button(fila, text="quitar", bg=PANEL, fg=RED, relief="flat", cursor="hand2",
                      command=lambda k=n: self._quitar_var(k)).pack(side="left")
        self._sub(p, "Agregar una variable")
        fila = tk.Frame(p, bg=PANEL)
        fila.pack(fill="x")
        nombre = self._entry(fila, 36)
        nombre.insert(0, plantilla)
        nombre.pack(side="left")
        valor = self._entry(fila, 44)
        valor.pack(side="left", padx=6)
        tk.Button(fila, text="agregar", bg=PANEL, fg=CYAN, relief="flat", cursor="hand2",
                  command=lambda: self._poner_var(nombre.get().strip(), valor.get())).pack(side="left")

    def _poner_var(self, n: str, v: str) -> None:
        if self._intentar(lambda: self.cfg.aplicar({n: v}), "Guardado y aplicado."):
            self._avisar()

    def _quitar_var(self, n: str) -> None:
        if self._intentar(lambda: self.cfg.aplicar(None, [n]), "Quitada."):
            self.mostrar(self.actual) if self.actual != "brigadas" else None
            self._avisar()

    # --- apariencia -----------------------------------------------------------------------------------------------
    def _s_apariencia(self) -> None:
        p = self._scroll()
        self._titulo(p, "Apariencia", "Tema, color, letra, idioma y cómo te habla Raphael. Se guardan ahora; el panel los toma al reabrirse.")
        a = self.cfg.apariencia()
        cajas: dict[str, tk.Widget] = {}
        etiquetas = {"tema": "Tema", "acento": "Color de acento (#rrggbb)", "letra": "Tamaño de letra (8 a 20)", "densidad": "Densidad",
                     "idioma": "Idioma", "nombre": "Nombre del asistente", "tono": "Tono al hablarte"}
        for k, etiqueta in etiquetas.items():
            fila = tk.Frame(p, bg=PANEL)
            fila.pack(fill="x", pady=3)
            tk.Label(fila, text=etiqueta, bg=PANEL, fg=TEXT, font=(SANS, 9), width=36, anchor="w").pack(side="left")
            if k in OPCIONES_APARIENCIA:
                w: tk.Widget = ttk.Combobox(fila, values=OPCIONES_APARIENCIA[k], width=20, state="readonly")
                w.set(a[k])
            else:
                w = self._entry(fila, 22)
                w.insert(0, str(a[k]))
            w.pack(side="left", padx=6)
            cajas[k] = w

        def guardar() -> None:
            datos = {k: (int(w.get()) if k == "letra" and w.get().isdigit() else w.get().strip()) for k, w in cajas.items()}
            self._intentar(lambda: self.cfg.poner_apariencia(**datos), "Guardado. Se aplica al reabrir el panel.")
        self._boton(p, "Guardar", guardar, "primary", 130).pack(anchor="w", pady=(12, 0))

    # --- avanzado -------------------------------------------------------------------------------------------------
    def _s_avanzado(self) -> None:
        p = self._scroll()
        self._titulo(p, "Avanzado", "Todas las variables en crudo, historial con deshacer, perfiles y exportar.")
        self._sub(p, "Historial de cambios (sin valores de claves)")
        caja = tk.Text(p, height=8, bg=INPUT, fg=TEXT, font=(MONO, 9), relief="flat", wrap="none")
        for e in self.cfg.historial(30):
            caja.insert("end", f"#{e['n']:<4} {e['cuando']}  {e['area']:<10} {e['que'][:90]}{'  (deshecho)' if e['deshecho'] else ''}\n")
        caja.configure(state="disabled")
        caja.pack(fill="x")
        fila = tk.Frame(p, bg=PANEL)
        fila.pack(fill="x", pady=(6, 0))
        self._boton(fila, "Deshacer el último", lambda: (self.decir(self.cfg.deshacer()), self._recargar()), "ghost", 170).pack(side="left")
        self._sub(p, "Perfiles (sin claves)")
        fila = tk.Frame(p, bg=PANEL)
        fila.pack(fill="x")
        nombre = ttk.Combobox(fila, values=self.cfg.perfiles(), width=24)
        nombre.pack(side="left")
        self._boton(fila, "Guardar perfil", lambda: self._intentar(lambda: self.cfg.guardar_perfil(nombre.get().strip()), "Perfil guardado."),
                    "ghost", 140).pack(side="left", padx=6)
        self._boton(fila, "Cargar perfil", lambda: self._intentar(lambda: self.cfg.cargar_perfil(nombre.get().strip()), "Perfil cargado.")
                    and self._recargar(), "ghost", 140).pack(side="left")
        self._sub(p, "Exportar / importar (nunca incluye claves)")
        fila = tk.Frame(p, bg=PANEL)
        fila.pack(fill="x")
        self._boton(fila, "Exportar…", self._exportar, "ghost", 130).pack(side="left")
        self._boton(fila, "Importar…", self._importar, "ghost", 130).pack(side="left", padx=6)
        self._sub(p, "Todas las variables (raphael.env)")
        self._editor_variables(p, lambda n: True)

    def _exportar(self) -> None:
        ruta = filedialog.asksaveasfilename(defaultextension=".json", initialfile="raphael-config.json")
        if ruta:
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump(self.cfg.exportar(), fh, ensure_ascii=False, indent=2)
            self.decir("Exportado sin claves.")

    def _importar(self) -> None:
        ruta = filedialog.askopenfilename(filetypes=[("Configuración", "*.json")])
        if ruta:
            with open(ruta, encoding="utf-8") as fh:
                datos = json.load(fh)
            if self._intentar(lambda: self.cfg.importar(datos), "Importado."):
                self._recargar()


__all__ = ["ConfigView", "es_local", "CARD"]
