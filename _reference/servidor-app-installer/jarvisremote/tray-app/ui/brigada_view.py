"""Vista de la pestaña "Brigada" — consola multiagente de auditoría, en 4 paneles:

  ┌──────────────┬───────────────────────────┐
  │ Configs      │ Estados de Raphael        │
  │ (modelo por  ├───────────────────────────┤
  │  estación)   │ Chat de la estación       │
  │ Chats de la  │ seleccionada              │
  │ brigada      │                           │
  └──────────────┴───────────────────────────┘

Izquierda-arriba: configs (modelo/API por estación con LLM). Izquierda-abajo:
la lista de las 7 estaciones (cada una es un "chat" que abrís). Derecha-arriba:
el estado de la corrida / la estación elegida. Derecha-abajo: el chat de esa
estación (su ida-y-vuelta). Consume `app/routers/brigada.py`.
"""

import os
import time

import requests

try:
    import psutil  # telemetría en vivo (CPU/RAM/disco/red). Ya viene en la venv.
except Exception:  # noqa: BLE001 -- si faltara, la franja muestra "—" sin romper la vista
    psutil = None

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config

_AUTH_HEADER = {"Authorization": f"Bearer {config.API_KEY}"}


def _fmt_rate(bps: float) -> tuple[str, str]:
    """Formatea una tasa en bytes/segundo a (valor, unidad) legible."""
    bps = max(0.0, bps)
    if bps < 1024:
        return f"{bps:.0f}", "B/s"
    if bps < 1024 * 1024:
        return f"{bps / 1024:.0f}", "KB/s"
    return f"{bps / (1024 * 1024):.1f}", "MB/s"

# (id, título, subtítulo, usa_llm) en orden de pipeline.
_STATIONS = [
    ("E1_reconocimiento", "E1 · Reconocimiento", "escáneres", False),
    ("E4_config", "E4 · Config checker", "config", False),
    ("E3_triage", "E3 · Triage", "falsos positivos", True),
    ("E2_contexto", "E2 · Contexto", "prod vs tests", False),
    ("E5_redaccion", "E5 · Redacción", "informe", True),
    ("E6_catador", "E6 · Catador / QA", "verificación", True),
    ("E7_pase", "E7 · Pase", "reporte + vault", False),
]
_TITLE = {sid: t for sid, t, _s, _l in _STATIONS}
_IS_LLM = {sid: l for sid, _t, _s, l in _STATIONS}
_STATUS_EMOJI = {
    "ok": "🟢", "fallo": "🔴", "abortada": "🔴",
    "salteada": "⚪", "no-corrio": "⚫", "corriendo": "🟡",
}
_ROL_LABEL = {"usuario": "🧑 Vos", "raphael": "🤖 Raphael", "sistema": "⚙ Sistema"}


class BrigadaBridge(QObject):
    config_ready = Signal(dict)
    run_done = Signal(dict)
    error = Signal(str)


class _ConfigFetchThread(QThread):
    _MAX_ATTEMPTS = 10

    def __init__(self, bridge, retry=False):
        super().__init__()
        self._bridge = bridge
        self._max = self._MAX_ATTEMPTS if retry else 1

    def run(self):
        for attempt in range(1, self._max + 1):
            try:
                resp = requests.get(config.BRIGADA_MODEL_CONFIG_URL, headers=_AUTH_HEADER, timeout=30)
                resp.raise_for_status()
                self._bridge.config_ready.emit(resp.json())
                return
            except requests.RequestException as exc:
                if attempt == self._max:
                    self._bridge.error.emit(f"No pude cargar la config: {exc}")
                    return
                self.msleep(1500)


class _SetModelThread(QThread):
    def __init__(self, payload, bridge):
        super().__init__()
        self._payload = payload
        self._bridge = bridge

    def run(self):
        try:
            resp = requests.post(config.BRIGADA_MODEL_CONFIG_URL, json=self._payload, headers=_AUTH_HEADER, timeout=30)
            resp.raise_for_status()
            self._bridge.config_ready.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.error.emit(f"No pude guardar el modelo: {exc}")


class _RunThread(QThread):
    def __init__(self, path, bridge):
        super().__init__()
        self._path = path
        self._bridge = bridge

    def run(self):
        try:
            resp = requests.post(config.BRIGADA_RUN_URL, json={"path": self._path}, headers=_AUTH_HEADER, timeout=1800)
            resp.raise_for_status()
            self._bridge.run_done.emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.error.emit(f"La corrida falló: {exc}")


def _panel(title):
    """Un QWidget con header + un layout vertical vacío listo para llenar."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(6)
    header = QLabel(title)
    header.setStyleSheet("color: #f59e0b; font-weight: 700; font-size: 12px;")
    lay.addWidget(header)
    return w, lay


class BrigadaView(QWidget):
    def __init__(self):
        super().__init__()
        self.bridge = BrigadaBridge()
        self.bridge.config_ready.connect(self._on_config)
        self.bridge.run_done.connect(self._on_run_done)
        self.bridge.error.connect(self._on_error)
        self._threads = []
        self._model_edits = {}     # id -> QLineEdit (solo LLM)
        self._run_stations = {}    # id -> {estado, segundos, chat, error}
        self._last_summary = {}
        self._selected = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- barra superior: correr ---
        top = QHBoxLayout()
        title = QLabel("🍳  Brigada de auditoría")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f3f4f6;")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"Proyecto ya escaneado, ej. C:\Users\dam\Downloads\audit-targets\pygoat")
        self.browse_btn = QPushButton("📁  Explorar…")
        self.browse_btn.setToolTip("Buscar la carpeta del proyecto a mano en el explorador de archivos")
        self.browse_btn.clicked.connect(self._browse)
        self.run_btn = QPushButton("▶  Correr auditoría")
        self.run_btn.clicked.connect(self._run)
        top.addWidget(title)
        top.addWidget(self.path_edit, 1)
        top.addWidget(self.browse_btn)
        top.addWidget(self.run_btn)
        root.addLayout(top)

        # --- franja de telemetría en vivo: estado de la PC (CPU/RAM/disco/red) ---
        root.addWidget(self._build_telemetry())

        # --- 4 paneles ---
        main = QSplitter(Qt.Horizontal)
        left = QSplitter(Qt.Vertical)
        right = QSplitter(Qt.Vertical)
        left.addWidget(self._build_configs())
        left.addWidget(self._build_stations())
        right.addWidget(self._build_estados())
        right.addWidget(self._build_chat())
        main.addWidget(left)
        main.addWidget(right)
        main.setSizes([320, 640])
        left.setSizes([230, 380])
        right.setSizes([150, 460])
        root.addWidget(main, 1)

        self._load_config(retry=True)

        # arranca el poll de telemetría (cada 2s). Primer update inmediato.
        self._tel_timer = QTimer(self)
        self._tel_timer.setInterval(2000)
        self._tel_timer.timeout.connect(self._update_telemetry)
        self._tel_timer.start()
        self._update_telemetry()

    # --- telemetría (estado de la PC, en vivo) ---
    def _build_telemetry(self):
        """Franja horizontal de estado de la PC: CPU, RAM, disco y red, en vivo.
        Inspirada en el 'live telemetry' del mockup. Datos reales de psutil; si
        psutil no está, muestra '—' sin romper nada."""
        bar = QWidget()
        bar.setObjectName("telBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addStretch(1)  # empuja las celdas a la derecha, como en el mockup
        self._tel_cells = {}
        for key, label in (("cpu", "CPU"), ("ram", "RAM"), ("disk", "DISCO"), ("net", "RED")):
            cell = QLabel()
            cell.setObjectName("telCell")
            cell.setTextFormat(Qt.RichText)
            cell.setStyleSheet(
                "QLabel#telCell { border: 1px solid #22406a; border-radius: 7px;"
                " padding: 4px 12px; background: rgba(10, 21, 38, 0.7); }"
            )
            cell.setText(self._tel_html(label, "—", ""))
            self._tel_cells[key] = (cell, label)
            lay.addWidget(cell)
        # baseline de red para calcular B/s entre polls
        self._net_prev = None
        self._net_prev_t = None
        return bar

    @staticmethod
    def _tel_html(label: str, value: str, unit: str, hot: bool = False) -> str:
        color = "#f59e0b" if hot else "#e8f0fb"
        return (
            f"<span style='font-family:Consolas,monospace; font-size:8px;"
            f" letter-spacing:1px; color:#6d86a3;'>{label}</span><br>"
            f"<span style='font-family:Consolas,monospace; font-size:14px;"
            f" font-weight:700; color:{color};'>{value}"
            f"<span style='font-size:9px; color:#8aa0ba;'>{unit}</span></span>"
        )

    def _update_telemetry(self):
        if psutil is None:
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            self._set_cell("cpu", f"{cpu:.0f}", "%", hot=cpu >= 80)
        except Exception:  # noqa: BLE001
            pass
        try:
            ram = psutil.virtual_memory().percent
            self._set_cell("ram", f"{ram:.0f}", "%", hot=ram >= 85)
        except Exception:  # noqa: BLE001
            pass
        try:
            path = "C:\\" if os.name == "nt" else "/"
            disk = psutil.disk_usage(path).percent
            self._set_cell("disk", f"{disk:.0f}", "%", hot=disk >= 90)
        except Exception:  # noqa: BLE001
            pass
        try:
            io = psutil.net_io_counters()
            now = time.monotonic()
            total = io.bytes_recv + io.bytes_sent
            if self._net_prev is not None and now > self._net_prev_t:
                bps = (total - self._net_prev) / (now - self._net_prev_t)
                self._set_cell("net", *_fmt_rate(bps))
            self._net_prev = total
            self._net_prev_t = now
        except Exception:  # noqa: BLE001
            pass

    def _set_cell(self, key, value, unit, hot=False):
        cell, label = self._tel_cells[key]
        cell.setText(self._tel_html(label, value, unit, hot))

    # --- construcción de paneles ---
    def _build_configs(self):
        w, lay = _panel("CONFIGS DE RAPHAEL  ·  modelo por estación")
        for sid, titulo, _sub, llm in _STATIONS:
            if not llm:
                continue
            row = QHBoxLayout()
            lbl = QLabel(titulo.split("·")[0].strip())
            lbl.setFixedWidth(40)
            lbl.setStyleSheet("color: #d1d5db; font-size: 11px;")
            edit = QLineEdit()
            edit.setPlaceholderText("global")
            edit.returnPressed.connect(lambda s=sid: self._save_model(s))
            save = QPushButton("✓")
            save.setFixedWidth(28)
            save.clicked.connect(lambda _c=False, s=sid: self._save_model(s))
            self._model_edits[sid] = edit
            row.addWidget(lbl)
            row.addWidget(edit, 1)
            row.addWidget(save)
            lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _build_stations(self):
        w, lay = _panel("LOS CHATS DE LA BRIGADA")
        self.stations_list = QListWidget()
        self.stations_list.setStyleSheet(
            "QListWidget { background: rgba(10, 21, 38, 0.6); border: 1px solid #22406a; border-radius: 6px; color: #dbe6f3; }"
            "QListWidget::item { padding: 6px; }"
            "QListWidget::item:selected { background: #f59e0b; color: #0a1120; }"
        )
        for sid, titulo, _sub, _llm in _STATIONS:
            item = QListWidgetItem(f"⚫  {titulo}")
            item.setData(Qt.UserRole, sid)
            self.stations_list.addItem(item)
        self.stations_list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self.stations_list, 1)
        return w

    def _build_estados(self):
        w, lay = _panel("ESTADOS DE RAPHAEL")
        self.estados_lbl = QLabel("Sin correr todavía. Poné una ruta y dale a Correr auditoría.")
        self.estados_lbl.setWordWrap(True)
        self.estados_lbl.setStyleSheet("color: #a9bdd4; font-size: 12px;")
        self.estados_lbl.setAlignment(Qt.AlignTop)
        lay.addWidget(self.estados_lbl, 1)
        return w

    def _build_chat(self):
        w, lay = _panel("CHAT DE LA ESTACIÓN")
        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setPlaceholderText("Elegí una estación de la lista para ver su conversación.")
        self.chat_view.setStyleSheet(
            "background: rgba(10, 21, 38, 0.66); color: #c4d3e5; border: 1px solid #22406a; border-radius: 6px;"
        )
        lay.addWidget(self.chat_view, 1)
        return w

    # --- red ---
    def _start(self, thread):
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.start()

    def _load_config(self, retry=False):
        self._start(_ConfigFetchThread(self.bridge, retry=retry))

    def _save_model(self, sid):
        model = self._model_edits[sid].text().strip()
        self._start(_SetModelThread({"station": sid, "model": model}, self.bridge))

    def _browse(self):
        """Abre el explorador de archivos de Windows para elegir la carpeta del
        proyecto a mano y la carga en el campo de ruta. Arranca en la ruta que ya
        esté escrita (o su carpeta contenedora) si existe."""
        current = self.path_edit.text().strip().strip('"')
        start = ""
        if current:
            start = current if os.path.isdir(current) else os.path.dirname(current)
        if not (start and os.path.isdir(start)):
            start = os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Elegí la carpeta del proyecto a auditar", start
        )
        if folder:
            self.path_edit.setText(os.path.normpath(folder))

    def _run(self):
        path = self.path_edit.text().strip().strip('"')
        if not path:
            self._on_error("Poné la ruta de un proyecto ya escaneado con security_scan_project.")
            return
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Corriendo…")
        for i in range(self.stations_list.count()):
            self._set_item_status(i, "corriendo")
        self.estados_lbl.setText("Corriendo la brigada… puede tardar unos minutos (triage + narrativa + catador).")
        self._start(_RunThread(path, self.bridge))

    # --- helpers UI ---
    def _set_item_status(self, index, estado):
        item = self.stations_list.item(index)
        if not item:
            return
        sid = item.data(Qt.UserRole)
        emoji = _STATUS_EMOJI.get(estado, "⚫")
        item.setText(f"{emoji}  {_TITLE.get(sid, sid)}")

    def _render_chat(self, chat):
        if not chat:
            return "(esta estación todavía no habló — corré una auditoría)"
        out = []
        for m in chat:
            rol = _ROL_LABEL.get(m.get("rol", ""), m.get("rol", ""))
            out.append(f"{rol}:\n{m.get('texto', '')}\n")
        return "\n".join(out)

    def _show_station(self, sid):
        self._selected = sid
        data = self._run_stations.get(sid)
        # chat
        self.chat_view.setPlainText(self._render_chat(data.get("chat") if data else None))
        # estados (overall + esta estación)
        rs = self._last_summary
        parts = []
        if rs:
            parts.append(f"Corrida: {rs.get('ok', 0)}/7 estaciones ok · {rs.get('total_seconds', 0)}s")
        if data:
            parts.append(f"{_TITLE.get(sid, sid)} — {data.get('estado', '?')}"
                         + (f" · {data.get('segundos')}s" if data.get('segundos') else ""))
            if data.get("error"):
                parts.append(f"error: {data['error']}")
        else:
            parts.append(f"{_TITLE.get(sid, sid)} — sin datos (todavía no corrió)")
        self.estados_lbl.setText("\n\n".join(parts))

    # --- slots ---
    def _on_row(self, row):
        if row < 0:
            return
        item = self.stations_list.item(row)
        if item:
            self._show_station(item.data(Qt.UserRole))

    def _on_config(self, snap):
        default_model = (snap.get("default") or {}).get("model", "")
        stations = snap.get("stations") or {}
        for sid, edit in self._model_edits.items():
            cfg = stations.get(sid)
            if cfg:
                edit.setText(cfg.get("model", ""))
            else:
                edit.setText("")
                edit.setPlaceholderText(f"global: {default_model}")

    def _on_run_done(self, result):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  Correr auditoría")
        self._last_summary = result.get("run_summary") or {}
        self._run_stations = {s["estacion"]: s for s in result.get("stations", [])}
        # actualizar los estados en la lista
        for i in range(self.stations_list.count()):
            sid = self.stations_list.item(i).data(Qt.UserRole)
            estado = self._run_stations.get(sid, {}).get("estado", "no-corrio")
            self._set_item_status(i, estado)
        # refrescar la estación seleccionada (o E7 por default para ver el reporte)
        target = self._selected or "E7_pase"
        for i in range(self.stations_list.count()):
            if self.stations_list.item(i).data(Qt.UserRole) == target:
                self.stations_list.setCurrentRow(i)
                break
        self._show_station(target)

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  Correr auditoría")
        self.estados_lbl.setText(f"⚠  {msg}")
