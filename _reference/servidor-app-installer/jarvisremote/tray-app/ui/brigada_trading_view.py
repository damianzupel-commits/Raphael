"""Vista de la pestaña "Trading" — la Brigada de Trading (modelo IFVG de Fede
Esses), calcada de la consola de la Brigada de Auditoría, en 3 paneles:

  ┌──────────────┬───────────────────────────┐
  │ Estaciones   │ Veredicto + señal         │
  │ T1..T7       ├───────────────────────────┤
  │ (requisitos) │ Chat de la estación       │
  └──────────────┴───────────────────────────┘

NO ejecuta órdenes ni mueve dinero: analiza y propone; el humano decide.
No es asesoramiento financiero. Consume `app/routers/trading.py`.
"""

import os
import time

import requests

try:
    import psutil
except Exception:  # noqa: BLE001
    psutil = None

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

# (id, título, subtítulo) en orden del pipeline de trading.
_STATIONS = [
    ("T1_datos", "T1 · Datos", "velas"),
    ("T2_estructura", "T2 · Estructura", "BOS/CHoCH"),
    ("T3_liquidez", "T3 · Liquidez", "sweep"),
    ("T4_zona", "T4 · Zona/Bias", "premium/discount"),
    ("T5_poi", "T5 · POI/IFVG", "zona de entrada"),
    ("T6_riesgo", "T6 · Riesgo/Gate", "SL/TP/RR"),
    ("T7_senal", "T7 · Señal", "veredicto"),
]
_TITLE = {sid: t for sid, t, _s in _STATIONS}
_STATUS_EMOJI = {
    "ok": "🟢", "fallo": "🔴", "abortada": "🔴",
    "salteada": "⚪", "no-corrio": "⚫", "corriendo": "🟡",
}
_ROL_LABEL = {"usuario": "🧑 Vos", "raphael": "🤖 Raphael", "sistema": "⚙ Sistema"}

# fuentes de datos: etiqueta -> (source, placeholder de instrumento)
_SOURCES = [
    ("Demo (velas sintéticas)", None, ""),
    ("Cripto · Binance (ccxt)", "ccxt", "BTC/USDT"),
    ("Acciones/índices (yfinance)", "yfinance", "QQQ"),
]


def _fmt_rate(bps: float):
    bps = max(0.0, bps)
    if bps < 1024:
        return f"{bps:.0f}", "B/s"
    if bps < 1024 * 1024:
        return f"{bps / 1024:.0f}", "KB/s"
    return f"{bps / (1024 * 1024):.1f}", "MB/s"


class _TradingBridge(QObject):
    run_done = Signal(dict)
    bt_done = Signal(dict)
    error = Signal(str)


class _RunThread(QThread):
    def __init__(self, url, payload, bridge, is_bt=False):
        super().__init__()
        self._url = url
        self._payload = payload
        self._bridge = bridge
        self._is_bt = is_bt

    def run(self):
        try:
            resp = requests.post(self._url, json=self._payload, headers=_AUTH_HEADER, timeout=180)
            resp.raise_for_status()
            (self._bridge.bt_done if self._is_bt else self._bridge.run_done).emit(resp.json())
        except requests.RequestException as exc:
            self._bridge.error.emit(f"La corrida falló: {exc}")


def _panel(title):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(6)
    header = QLabel(title)
    header.setStyleSheet("color: #f59e0b; font-weight: 700; font-size: 12px;")
    lay.addWidget(header)
    return w, lay


class TradingBrigadaView(QWidget):
    def __init__(self):
        super().__init__()
        self.bridge = _TradingBridge()
        self.bridge.run_done.connect(self._on_run_done)
        self.bridge.bt_done.connect(self._on_bt_done)
        self.bridge.error.connect(self._on_error)
        self._threads = []
        self._run_stations = {}
        self._last = {}
        self._selected = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- barra superior ---
        top = QHBoxLayout()
        title = QLabel("📈  Brigada de trading")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f3f4f6;")
        self.mode_box = QComboBox()
        self.mode_box.addItem("📊  Señal ahora")
        self.mode_box.addItem("🔁  Backtest")
        self.mode_box.currentIndexChanged.connect(self._on_mode)
        self.source_box = QComboBox()
        for label, _src, _ph in _SOURCES:
            self.source_box.addItem(label)
        self.source_box.currentIndexChanged.connect(self._on_source)
        self.instrument_edit = QLineEdit()
        self.instrument_edit.setPlaceholderText("instrumento (Demo no necesita)")
        self.run_btn = QPushButton("▶  Correr")
        self.run_btn.clicked.connect(self._run)
        top.addWidget(title)
        top.addWidget(self.mode_box)
        top.addWidget(self.source_box)
        top.addWidget(self.instrument_edit, 1)
        top.addWidget(self.run_btn)
        root.addLayout(top)

        # perillas de win rate (R:R mínimo y confianza mínima)
        params = QHBoxLayout()
        params.addWidget(QLabel("R:R mín"))
        self.minrr_edit = QLineEdit("2.0")
        self.minrr_edit.setFixedWidth(50)
        params.addWidget(self.minrr_edit)
        params.addWidget(QLabel("Confianza mín"))
        self.minconf_edit = QLineEdit("0.6")
        self.minconf_edit.setFixedWidth(50)
        params.addWidget(self.minconf_edit)
        hint = QLabel("subí estos para filtrar más y (ojalá) subir el win rate")
        hint.setStyleSheet("color: #6d86a3; font-size: 10px;")
        params.addWidget(hint)
        params.addStretch(1)
        root.addLayout(params)

        # aviso (no ejecuta)
        note = QLabel("Analiza y propone — no ejecuta órdenes ni mueve dinero. El click final es tuyo.")
        note.setStyleSheet("color: #6d86a3; font-size: 10px;")
        root.addWidget(note)

        # --- telemetría ---
        root.addWidget(self._build_telemetry())

        # --- 3 paneles ---
        main = QSplitter(Qt.Horizontal)
        left = self._build_stations()
        right = QSplitter(Qt.Vertical)
        right.addWidget(self._build_estados())
        right.addWidget(self._build_chat())
        right.setSizes([260, 360])
        main.addWidget(left)
        main.addWidget(right)
        main.setSizes([300, 660])
        root.addWidget(main, 1)

        self._tel_timer = QTimer(self)
        self._tel_timer.setInterval(2000)
        self._tel_timer.timeout.connect(self._update_telemetry)
        self._tel_timer.start()
        self._update_telemetry()

    # --- telemetría (idéntica a la Brigada de auditoría) ---
    def _build_telemetry(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addStretch(1)
        self._tel_cells = {}
        for key, label in (("cpu", "CPU"), ("ram", "RAM"), ("disk", "DISCO"), ("net", "RED")):
            cell = QLabel()
            cell.setTextFormat(Qt.RichText)
            cell.setStyleSheet(
                "QLabel { border: 1px solid #22406a; border-radius: 7px;"
                " padding: 4px 12px; background: rgba(10, 21, 38, 0.7); }")
            cell.setText(self._tel_html(label, "—", ""))
            self._tel_cells[key] = (cell, label)
            lay.addWidget(cell)
        self._net_prev = None
        self._net_prev_t = None
        return bar

    @staticmethod
    def _tel_html(label, value, unit, hot=False):
        color = "#f59e0b" if hot else "#e8f0fb"
        return (
            f"<span style='font-family:Consolas,monospace; font-size:8px;"
            f" letter-spacing:1px; color:#6d86a3;'>{label}</span><br>"
            f"<span style='font-family:Consolas,monospace; font-size:14px;"
            f" font-weight:700; color:{color};'>{value}"
            f"<span style='font-size:9px; color:#8aa0ba;'>{unit}</span></span>")

    def _update_telemetry(self):
        if psutil is None:
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            self._set_cell("cpu", f"{cpu:.0f}", "%", cpu >= 80)
        except Exception:  # noqa: BLE001
            pass
        try:
            ram = psutil.virtual_memory().percent
            self._set_cell("ram", f"{ram:.0f}", "%", ram >= 85)
        except Exception:  # noqa: BLE001
            pass
        try:
            path = "C:\\" if os.name == "nt" else "/"
            disk = psutil.disk_usage(path).percent
            self._set_cell("disk", f"{disk:.0f}", "%", disk >= 90)
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

    # --- paneles ---
    def _build_stations(self):
        w, lay = _panel("ESTACIONES DE LA BRIGADA  ·  requisitos")
        self.stations_list = QListWidget()
        self.stations_list.setStyleSheet(
            "QListWidget { background: rgba(10, 21, 38, 0.6); border: 1px solid #22406a; border-radius: 6px; color: #dbe6f3; }"
            "QListWidget::item { padding: 6px; }"
            "QListWidget::item:selected { background: #f59e0b; color: #0a1120; }")
        for sid, titulo, sub in _STATIONS:
            item = QListWidgetItem(f"⚫  {titulo}  ·  {sub}")
            item.setData(Qt.UserRole, sid)
            self.stations_list.addItem(item)
        self.stations_list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self.stations_list, 1)
        return w

    def _build_estados(self):
        w, lay = _panel("VEREDICTO Y SEÑAL")
        self.estados_lbl = QLabel("Sin correr todavía. Elegí fuente e instrumento y dale a Correr brigada.")
        self.estados_lbl.setWordWrap(True)
        self.estados_lbl.setTextFormat(Qt.RichText)
        self.estados_lbl.setStyleSheet("color: #a9bdd4; font-size: 12px;")
        self.estados_lbl.setAlignment(Qt.AlignTop)
        lay.addWidget(self.estados_lbl, 1)
        return w

    def _build_chat(self):
        w, lay = _panel("CHAT DE LA ESTACIÓN")
        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setPlaceholderText("Elegí una estación para ver qué hizo.")
        self.chat_view.setStyleSheet(
            "background: rgba(10, 21, 38, 0.66); color: #c4d3e5; border: 1px solid #22406a; border-radius: 6px;")
        lay.addWidget(self.chat_view, 1)
        return w

    # --- lógica ---
    def _on_source(self, idx):
        _label, _src, ph = _SOURCES[idx]
        self.instrument_edit.setText("")
        self.instrument_edit.setPlaceholderText(ph or "Demo no necesita instrumento")

    def _start(self, thread):
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        thread.start()

    def _on_mode(self, _idx):
        bt = self.mode_box.currentIndex() == 1
        self.run_btn.setText("▶  Backtest" if bt else "▶  Correr")

    def _floats(self):
        try:
            mrr = float(self.minrr_edit.text().strip() or "2.0")
        except ValueError:
            mrr = 2.0
        try:
            mcf = float(self.minconf_edit.text().strip() or "0.6")
        except ValueError:
            mcf = 0.6
        return mrr, mcf

    def _run(self):
        idx = self.source_box.currentIndex()
        _label, source, _ph = _SOURCES[idx]
        mrr, mcf = self._floats()
        payload = {"account": 10000, "risk_pct": 1.0, "min_rr": mrr, "min_conf": mcf}
        if source is None:
            payload["demo"] = True
            payload["instrument"] = "DEMO"
        else:
            inst = self.instrument_edit.text().strip()
            if not inst:
                self._on_error("Poné el instrumento (ej. BTC/USDT o QQQ), o elegí Demo.")
                return
            payload["source"] = source
            payload["instrument"] = inst
        is_bt = self.mode_box.currentIndex() == 1
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Corriendo…")
        if is_bt:
            self.estados_lbl.setText(f"Corriendo backtest (R:R≥{mrr}, conf≥{mcf})…")
            self._start(_RunThread(config.TRADING_BACKTEST_RUN_URL, payload, self.bridge, is_bt=True))
        else:
            for i in range(self.stations_list.count()):
                self._set_item(i, "corriendo", None)
            self.estados_lbl.setText("Corriendo la brigada de trading…")
            self._start(_RunThread(config.TRADING_BRIGADA_RUN_URL, payload, self.bridge, is_bt=False))

    def _set_item(self, index, estado, requisito):
        item = self.stations_list.item(index)
        if not item:
            return
        sid = item.data(Qt.UserRole)
        sub = next((s for i, t, s in _STATIONS if i == sid), "")
        emoji = _STATUS_EMOJI.get(estado, "⚫")
        mark = ""
        if requisito is not None:
            mark = "  ✔" if requisito.get("cumple") else "  ✗"
        item.setText(f"{emoji}  {_TITLE.get(sid, sid)}  ·  {sub}{mark}")

    def _render_chat(self, chat):
        if not chat:
            return "(esta estación todavía no habló — corré la brigada)"
        out = []
        for m in chat:
            rol = _ROL_LABEL.get(m.get("rol", ""), m.get("rol", ""))
            out.append(f"{rol}:\n{m.get('texto', '')}\n")
        return "\n".join(out)

    def _show_station(self, sid):
        self._selected = sid
        data = self._run_stations.get(sid)
        self.chat_view.setPlainText(self._render_chat(data.get("chat") if data else None))

    def _render_verdict(self):
        r = self._last
        if not r:
            return
        verdict = r.get("verdict") or "—"
        color = "#22c55e" if verdict == "OPERAR" else "#f59e0b"
        sig = r.get("signal")
        parts = [f"<span style='font-size:20px; font-weight:700; color:{color};'>VEREDICTO: {verdict}</span>"]
        summ = r.get("run_summary") or {}
        parts.append(f"<span style='color:#6d86a3;'>{summ.get('ok', 0)}/7 estaciones ok · {summ.get('total_seconds', 0)}s</span>")
        if sig:
            valid = "✔ válida" if sig.get("valid") else f"✗ {sig.get('reject_reason', '')}"
            parts.append(
                f"<br><b>Señal:</b> {str(sig.get('direction', '')).upper()} · entry {sig.get('entry')} · "
                f"SL {sig.get('sl')} · TP {sig.get('tp')} · R:R {sig.get('rr')} · conf {sig.get('confidence')} · {valid}")
            sz = sig.get("size") or {}
            if sz:
                parts.append(f"<span style='color:#8aa0ba;'>tamaño {sz.get('units')} u · riesgo ${sz.get('risk_cash')}</span>")
            if sig.get("tags"):
                parts.append(f"<span style='color:#6d86a3;'>tags: {', '.join(sig['tags'])}</span>")
        parts.append("<br><b>Requisitos:</b>")
        for req in r.get("requisitos", []):
            mark = "✔" if req.get("cumple") else "✗"
            c = "#22c55e" if req.get("cumple") else "#ef4444"
            parts.append(f"<span style='color:{c};'>{mark}</span> {req.get('nombre')}: "
                         f"<span style='color:#8aa0ba;'>{req.get('detalle')}</span>")
        self.estados_lbl.setText("<br>".join(parts))

    # --- slots ---
    def _on_row(self, row):
        if row < 0:
            return
        item = self.stations_list.item(row)
        if item:
            self._show_station(item.data(Qt.UserRole))

    def _reset_btn(self):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  Backtest" if self.mode_box.currentIndex() == 1 else "▶  Correr")

    def _on_bt_done(self, r):
        self._reset_btn()
        if not r or not r.get("trades"):
            self.estados_lbl.setText("Backtest: 0 trades (subí las velas o bajá las perillas).")
            return
        wr = r.get("win_rate", 0) * 100
        exp = r.get("expectancy_R", 0)
        col = "#22c55e" if exp > 0 else "#ef4444"
        cfg = r.get("config", {})
        parts = [
            f"<span style='font-size:18px; font-weight:700; color:#f3f4f6;'>🔁 Backtest — {r.get('modo','?')} ({r.get('velas','?')} velas)</span>",
            f"<span style='color:#6d86a3;'>R:R≥{cfg.get('min_rr')} · conf≥{cfg.get('min_conf')}</span>",
            f"<br><b>Trades:</b> {r.get('trades')} (ganados {r.get('wins')} / perdidos {r.get('losses')})",
            f"<b>Win rate:</b> <span style='color:{col};'>{wr:.1f}%</span>",
            f"<b>Expectativa:</b> <span style='color:{col};'>{exp:+.3f} R</span> por trade",
            f"<b>R total:</b> {r.get('total_R')} · <b>Máx DD:</b> {r.get('max_drawdown_R')} R",
        ]
        by = r.get("by_setup", {})
        if by:
            parts.append("<br><b>Por tipo de POI:</b>")
            for k, v in by.items():
                parts.append(f"· {k}: {v['n']} trades, win {v['win_rate']*100:.0f}%, {v['total_R']:+.1f} R")
        parts.append("<br><span style='color:#6d86a3; font-size:10px;'>Subí R:R o Confianza y volvé a correr para ver si mejora el win rate. Backtest ≠ resultado en vivo.</span>")
        self.estados_lbl.setText("<br>".join(parts))
        self.chat_view.setPlainText("(modo backtest — el chat por estación es del modo 'Señal ahora')")

    def _on_run_done(self, result):
        self._reset_btn()
        self._last = result or {}
        self._run_stations = {s["estacion"]: s for s in result.get("stations", [])}
        for i in range(self.stations_list.count()):
            sid = self.stations_list.item(i).data(Qt.UserRole)
            s = self._run_stations.get(sid, {})
            self._set_item(i, s.get("estado", "no-corrio"), s.get("requisito"))
        self._render_verdict()
        target = self._selected or "T7_senal"
        for i in range(self.stations_list.count()):
            if self.stations_list.item(i).data(Qt.UserRole) == target:
                self.stations_list.setCurrentRow(i)
                break
        self._show_station(target)

    def _on_error(self, msg):
        self._reset_btn()
        self.estados_lbl.setText(f"⚠  {msg}")
