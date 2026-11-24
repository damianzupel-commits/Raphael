"""Ventana principal de Jarvis para PC (PySide6).

Reemplaza la vieja ventana de chat en Tkinter (chat_window.py). Diseño pedido
por el usuario: chat al centro (elemento principal), selector de modelo arriba
al centro, barra lateral izquierda con accesos directos a utilidades (generar
imagen/video, más adelante otras) y un toggle de voz continua en un extremo de
esa barra. Nada de configuración técnica cruda acá -- eso va a vivir en un
ícono de ajustes aparte (pendiente de definir con el usuario).

Además del chat, aloja dos pestañas más -- Codebase y Obsidian (ver
`ui/codebase_view.py` y `ui/obsidian_view.py`) -- que exponen del lado
visual las dos capacidades nativas del backend (`backend/app/codebase/` y
`backend/app/obsidian/`). El chat en sí se extrajo a `ui/chat_view.py` para
que quepa como una pestaña más sin cambiar su comportamiento.

Corre en su propio hilo con su propio QApplication, igual que chat_window.py
corría Tkinter en el suyo -- pystray sigue dueño del hilo principal en tray.py.
Solo puede existir un QApplication por proceso, así que abrir "chat" una
segunda vez no crea una instancia nueva: reusa la ventana ya viva.
"""

import threading

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
import process_manager
from ui.chat_view import ChatView, build_animated_background
from ui.orb import FloatingOrb
from ui.brigada_view import BrigadaView
from ui.brigada_trading_view import TradingBrigadaView
from ui.codebase_view import CodebaseView
from ui.investigation_view import InvestigationView
from ui.mission_control_view import MissionControlView
from ui.globo_view import GloboView
from ui.obsidian_view import ObsidianView
from ui.config_dialog import ConfigDialog
from ui.pair_dialog import PairDialog
from ui.theming import force_dark_title_bar

# Tema oscuro fijo, sin opción de cambiar a claro -- pedido explícito de
# Damian ("es lo que usa la mayoría de la gente"). Ver también
# _force_dark_title_bar() para que la barra de título nativa de Windows
# acompañe (si no, quedaba blanca arriba de un contenido oscuro).
# Tema "system dossier" (2026-09-23): paleta navy oscuro + acento ámbar (#f59e0b)
# + cian secundario (#5ec8ff), inspirada en Ryoku pero manteniendo la esfera de
# Raphael de fondo (build_animated_background) y la identidad de la marca. Es un
# reskin de SOLO color/superficies: mismos selectores que antes, así todas las
# pestañas (Chat, Codebase, Obsidian, Investigación, Brigada) lo heredan de una.
# Paleta:
#   base navy   #0b1424 / #0a1120     superficies #0e1a2e / #0a1526
#   bordes      #22406a (líneas #1c3453)   acento ámbar #f59e0b (hover #d9820c)
#   cian        #5ec8ff    texto #cdd8e6 / apagado #7f96b2
STYLESHEET = """
QMainWindow, QWidget#chatArea { background: #0b1424; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
/* sidebar y topBar transparentes: dejan ver el fondo animado (esfera de Raphael).
   La legibilidad la da el velo oscuro del propio fondo (_AnimatedBackground). */
QWidget#sidebar { background: transparent; }
QWidget#topBar { background: transparent; border-bottom: 1px solid #1c3453; }
QComboBox {
    background: #0e1a2e; color: #e8f0fb; border: 1px solid #22406a; border-radius: 8px;
    padding: 6px 14px; font-size: 13px; min-width: 220px;
}
QComboBox:hover { border-color: #f59e0b; }
QComboBox QAbstractItemView {
    background: #0e1a2e; color: #e8f0fb; selection-background-color: #f59e0b;
    selection-color: #0a1120; border: 1px solid #22406a;
}
QPushButton#sidebarButton {
    background: transparent; color: #7f96b2; border: none;
    border-radius: 10px; padding: 12px; font-size: 22px; text-align: center;
}
QPushButton#sidebarButton:hover { background: #12233a; color: #ffffff; }
QPushButton#sidebarButton:checked { background: #f59e0b; color: #0a1120; }
QPushButton#settingsButton {
    background: transparent; border: none; border-radius: 8px;
    padding: 6px 10px; font-size: 18px; color: #7f96b2;
}
QPushButton#settingsButton:hover { background: #0e1a2e; color: #ffffff; }
QLineEdit#messageInput {
    background: #0a1526; color: #e8f0fb; border: 1px solid #22406a; border-radius: 18px;
    padding: 10px 16px; font-size: 14px;
}
QLineEdit#messageInput:focus { border-color: #f59e0b; }
QPushButton#sendButton {
    background: #f59e0b; color: #0a1120; border: none; border-radius: 18px;
    padding: 10px 20px; font-size: 14px; font-weight: 700;
}
QPushButton#sendButton:hover { background: #d9820c; }
QLabel#bubbleUser {
    background: #f59e0b; color: #0a1120; border-radius: 14px; padding: 10px 14px;
    font-size: 14px; font-weight: 600;
}
QLabel#bubbleAssistant {
    background: #0e1a2e; color: #cdd8e6; border-radius: 14px; padding: 10px 14px;
    font-size: 14px; border: 1px solid #22406a;
}
QLabel#bubbleTyping {
    background: #0e1a2e; color: #7f96b2; border-radius: 14px; padding: 10px 14px;
    font-size: 14px; font-style: italic; border: 1px solid #22406a;
}
QLabel#bubbleSystem {
    color: #7f96b2; font-size: 12px; font-style: italic; padding: 4px 8px;
}
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: #7f96b2; padding: 10px 18px; font-size: 13px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #f59e0b; }
QTabBar::tab:hover { color: #e8f0fb; }
QWidget#codebaseView, QWidget#obsidianView { background: #0b1424; }
QLineEdit#codebasePathInput {
    background: #0a1526; color: #e8f0fb; border: 1px solid #22406a; border-radius: 8px;
    padding: 8px 12px; font-size: 13px;
}
QLineEdit#codebasePathInput:focus { border-color: #f59e0b; }
QLabel#codebaseStatus, QLabel#obsidianStatus { color: #7f96b2; font-size: 12px; }
QLabel#obsidianDetailMeta { color: #9fb4cd; font-size: 12px; }
QTreeWidget, QListWidget, QTextEdit {
    background: rgba(10, 21, 38, 0.72); color: #cdd8e6; border: 1px solid #22406a; border-radius: 8px;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #f59e0b; color: #0a1120;
}

/* --- Encabezado de sección (reemplaza barra de modelo + pestañas) --- */
QWidget#sectionHeader { background: rgba(11, 20, 36, 0.78); border-bottom: 1px solid #1c3453; }
QLabel#sectionTitle { color: #e8f0fb; font-size: 15px; font-weight: 600; }
QPushButton#sectionClose {
    background: transparent; color: #7f96b2; border: none; border-radius: 8px;
    padding: 6px 11px; font-size: 16px;
}
QPushButton#sectionClose:hover { background: #0e1a2e; color: #ffffff; }

/* --- Chat: la columna es transparente para dejar ver el fondo animado --- */
QWidget#chatColumn { background: transparent; }

/* --- Chat: encabezado con nombre + píldora de estado (Conectado/Pensando) --- */
QWidget#chatHeader { background: transparent; }
QLabel#chatHeaderName { color: #e8f0fb; font-size: 15px; font-weight: 600; }
QLabel#statusPill {
    font-size: 12px; padding: 3px 10px; border-radius: 10px; background: #0a1526;
}
QLabel#statusPill[state="connected"] { color: #3ad29f; }
QLabel#statusPill[state="thinking"] { color: #f59e0b; }

/* --- Chat: pantalla de bienvenida + pedidos recurrentes --- */
QWidget#welcomeCard, QWidget#recurringPanel { background: transparent; }
QLabel#welcomeAvatar { margin-bottom: 8px; }
QLabel#welcomeTitle { color: #e8f0fb; font-size: 22px; font-weight: 700; }
QLabel#welcomeSubtitle { color: #9fb4cd; font-size: 13px; }
QPushButton#recurringToggle {
    background: #0a1526; color: #e8f0fb; border: 1px solid #22406a; border-radius: 16px;
    padding: 8px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#recurringToggle:hover { background: #0e1a2e; border-color: #f59e0b; }
QPushButton#recurringToggle:checked { background: #0e1a2e; border-color: #f59e0b; color: #ffffff; }
QPushButton#recurringItem {
    background: rgba(10, 21, 38, 0.72); color: #cdd8e6; border: 1px solid #22406a; border-radius: 12px;
    padding: 12px 16px; font-size: 14px; text-align: left;
}
QPushButton#recurringItem:hover { background: #0e1a2e; color: #ffffff; border-color: #f59e0b; }
"""


class ModelSwitchBridge(QObject):
    model_switch_done = Signal(str)


class ModelSwitchThread(QThread):
    def __init__(self, model_id: str, bridge: ModelSwitchBridge):
        super().__init__()
        self._model_id = model_id
        self._bridge = bridge

    def run(self) -> None:
        process_manager.set_active_model(self._model_id)
        self._bridge.model_switch_done.emit(self._model_id)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Raphael")
        self.resize(900, 680)
        try:
            if config.RAPHAEL_ICON.exists():
                self.setWindowIcon(QIcon(str(config.RAPHAEL_ICON)))
        except Exception:
            pass

        self._model_bridge = ModelSwitchBridge()
        self._model_bridge.model_switch_done.connect(self._on_model_switched)

        self._settings_dialog: ConfigDialog | None = None
        self._pair_dialog: PairDialog | None = None
        self._model_thread: ModelSwitchThread | None = None
        # Referencia al orbe flotante (la setea _run_qt_app). Se oculta mientras esta
        # ventana de sección está abierta, para que no se superponga sobre el contenido.
        self.orb = None

        central = QWidget()
        central.setObjectName("chatArea")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # La navegación ahora es el ORBE: la barra superior (selector de modelo) y
        # la fila de pestañas se ocultan. En su lugar, un encabezado slim muestra la
        # sección actual, para que la ventana se sienta parte del sistema Raphael.
        self._top_bar = self._build_top_bar()
        self._top_bar.hide()  # se mantiene creada (referencias al selector) pero oculta
        root.addWidget(self._top_bar)
        root.addWidget(self._build_section_header())

        self.tabs = QTabWidget()
        self.chat_view = ChatView()
        self.codebase_view = CodebaseView()
        self.obsidian_view = ObsidianView()
        self.investigation_view = InvestigationView()
        self.brigada_view = BrigadaView()
        self.trading_view = TradingBrigadaView()
        self.mission_control_view = MissionControlView()
        self.globo_view = GloboView()
        self.tabs.addTab(self.chat_view, "💬  Chat")
        self.tabs.addTab(self.codebase_view, "🗂  Codebase")
        self.tabs.addTab(self.obsidian_view, "🧠  Obsidian")
        self.tabs.addTab(self.investigation_view, "🔎  Investigación")
        self.tabs.addTab(self.brigada_view, "🍳  Brigada")
        self.tabs.addTab(self.trading_view, "📈  Trading")
        self.tabs.addTab(self.mission_control_view, "🎯  Centro de Mando")
        self.tabs.addTab(self.globo_view, "🌐  Mapa de inteligencia")
        self.tabs.tabBar().hide()  # se navega por el orbe, no por pestañas
        root.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(central)
        self.setStyleSheet(STYLESHEET)
        force_dark_title_bar(self)

        # Fondo animado (imagen de Raphael) a nivel de TODA la ventana: se pone
        # como hijo del widget central y se manda al fondo (lower), así queda
        # detrás de la barra superior, las pestañas y el chat -- que se hacen
        # semi-transparentes en el QSS para dejarlo ver. Se sincroniza el tamaño
        # en resizeEvent.
        self._central = central
        self._bg = build_animated_background(central)
        if self._bg is not None:
            self._bg.setGeometry(central.rect())
            self._bg.lower()
            self._bg.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "_bg", None) is not None:
            self._bg.setGeometry(self._central.rect())

    # ------------------------------------------------------------- layout

    def _build_section_header(self) -> QWidget:
        """Encabezado slim de la ventana de secciones: "Raphael · <sección>" a la
        izquierda + una ✕ para volver al orbe. Reemplaza a la barra de pestañas y
        al selector de modelo, para mantener la estética del orbe."""
        bar = QWidget()
        bar.setObjectName("sectionHeader")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 10, 0)

        self.section_label = QLabel("Raphael")
        self.section_label.setObjectName("sectionTitle")
        layout.addWidget(self.section_label)
        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("sectionClose")
        close_btn.setToolTip("Volver al orbe")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)
        return bar

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.addStretch()

        self.model_selector = QComboBox()
        for model in config.AVAILABLE_MODELS:
            self.model_selector.addItem(model["label"], userData=model["id"])
        current = self._current_model_id()
        idx = self.model_selector.findData(current)
        if idx >= 0:
            self.model_selector.setCurrentIndex(idx)
        self.model_selector.currentIndexChanged.connect(self._on_model_selected)
        layout.addWidget(self.model_selector)

        layout.addStretch()

        pair_button = QPushButton("📱")
        pair_button.setObjectName("settingsButton")
        pair_button.setToolTip("Vincular celular (mostrar QR)")
        pair_button.setCursor(Qt.PointingHandCursor)
        pair_button.clicked.connect(self._on_open_pairing)
        layout.addWidget(pair_button)

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("settingsButton")
        settings_button.setToolTip("Configuración (permisos y conectores)")
        settings_button.setCursor(Qt.PointingHandCursor)
        settings_button.clicked.connect(self._on_open_settings)
        layout.addWidget(settings_button)
        layout.setContentsMargins(0, 0, 12, 0)
        return bar

    # ------------------------------------------------------------- ajustes

    def _on_open_settings(self) -> None:
        # Diálogo no-modal reusado -- así el usuario puede seguir chateando
        # mientras lo tiene abierto, y no se acumulan instancias si lo abre
        # varias veces desde el ícono.
        if self._settings_dialog is None:
            self._settings_dialog = ConfigDialog(self)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _on_open_pairing(self) -> None:
        # Diálogo "Vincular celular": muestra el QR para sincronizar el teléfono.
        if self._pair_dialog is None:
            self._pair_dialog = PairDialog(self)
        self._pair_dialog.show()
        self._pair_dialog.raise_()
        self._pair_dialog.activateWindow()

    # ------------------------------------------------------------- modelo

    def _current_model_id(self) -> str:
        try:
            text = config.ENV_PATH.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("LMSTUDIO_MODEL="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            pass
        return config.AVAILABLE_MODELS[0]["id"]

    def _on_model_selected(self, index: int) -> None:
        model_id = self.model_selector.itemData(index)
        if model_id == self._current_model_id():
            return
        self.model_selector.setEnabled(False)
        self.chat_view.add_system_message("Cambiando de modelo... puede tardar un momento.")
        self._model_thread = ModelSwitchThread(model_id, self._model_bridge)
        self._model_thread.start()

    def _on_model_switched(self, model_id: str) -> None:
        self.model_selector.setEnabled(True)
        label = next((m["label"] for m in config.AVAILABLE_MODELS if m["id"] == model_id), model_id)
        self.chat_view.add_system_message(f"Listo, ahora estoy usando el modelo: {label}.")

    # ------------------------------------------------------------- orbe

    def handle_orb_select(self, key: str) -> None:
        """Acción elegida desde el menú del orbe flotante (ver ui/orb.py). Corre en
        el hilo de Qt (viene de un click de botón), así que es seguro tocar widgets."""
        if key == "settings":
            # El diálogo de config es su propia ventana: no hace falta abrir la
            # ventana grande detrás (que es para las secciones de datos).
            self._on_open_settings()
            return
        if key == "voice":
            # Alterna la escucha por voz sin abrir la ventana (el chat es la barra
            # flotante). El botón real vive en la barra del chat.
            self.chat_view.sidebar.voice_button.toggle()
            return
        self.show_section(key)

    def show_section(self, key: str) -> None:
        """Muestra la ventana en la pestaña pedida (o Chat por default) y actualiza
        el encabezado con el nombre de la sección."""
        index = {"history": 0, "chat": 0, "codebase": 1, "obsidian": 2, "investigation": 3, "brigada": 4, "trading": 5, "mando": 6}.get(key, 0)
        # La barra de título nativa ya dice "Raphael"; el header solo nombra la sección
        # (antes decía "Raphael · X", duplicando la marca en dos barras).
        titles = {
            "history": "Historial",
            "chat": "Chat",
            "codebase": "Codebase",
            "obsidian": "Obsidian",
            "investigation": "Investigación",
            "brigada": "Brigada",
            "trading": "Trading",
            "mando": "Centro de Mando",
        }
        # Al abrir Historial/Chat, RECARGAR el transcript desde disco para reflejar
        # todo lo hablado por la barra flotante del orbe (si no, muestra una copia
        # vieja cargada al arrancar la app).
        if key in ("history", "chat"):
            self.chat_view.reload_history()
        if key == "mando":
            # Recargar el panel al abrirlo, para reconectar el WebSocket en vivo.
            self.mission_control_view.reload()
        self.section_label.setText(titles.get(key, ""))
        self.tabs.setCurrentIndex(index)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        # El orbe es el launcher: mientras la ventana está abierta se oculta para no
        # superponerse sobre el contenido (vuelve al cerrar, ver hideEvent).
        self._set_orb_visible(False)

    def closeEvent(self, event) -> None:
        # La interfaz vive en el orbe flotante: cerrar la ventana con la X NO cierra
        # la app, solo la OCULTA (se vuelve a abrir desde el orbe). El apagado real
        # es por el ícono de bandeja -> Salir.
        event.ignore()
        self.hide()

    def hideEvent(self, event) -> None:
        # Al ocultar la ventana (✕ del header o la X nativa), vuelve el orbe launcher.
        self._set_orb_visible(True)
        super().hideEvent(event)

    def _set_orb_visible(self, visible: bool) -> None:
        if self.orb is None:
            return
        if visible:
            self.orb.show_all()
        else:
            self.orb.hide_all()


_qt_thread: threading.Thread | None = None
_window: MainWindow | None = None
_orb: FloatingOrb | None = None
_lock = threading.Lock()


def open_chat_window(icon=None, item=None) -> None:
    """Punto de entrada desde pystray. Ahora la interfaz es el ORBE flotante: esto
    lo trae al frente (o arranca la app Qt si todavía no corre). La ventana grande
    NO se abre acá -- se abre eligiendo una sección desde el orbe."""
    global _qt_thread, _orb
    with _lock:
        if _qt_thread is not None and _qt_thread.is_alive():
            if _orb is not None:
                # QWidget no es thread-safe: encolamos el show()/raise_() en el
                # hilo de Qt con invokeMethod en vez de tocarlo desde pystray.
                from PySide6.QtCore import QMetaObject

                QMetaObject.invokeMethod(_orb, "show", Qt.QueuedConnection)
                QMetaObject.invokeMethod(_orb, "raise_", Qt.QueuedConnection)
            return
        _qt_thread = threading.Thread(target=_run_qt_app, daemon=True)
        _qt_thread.start()


def _run_qt_app() -> None:
    global _window, _orb
    app = QApplication.instance() or QApplication([])
    # Que cerrar la ventana (o el menú) no cierre la app: la app vive en el orbe
    # y en la bandeja; el apagado real es por el ícono de bandeja -> Salir.
    app.setQuitOnLastWindowClosed(False)
    _window = MainWindow()  # se crea OCULTA: la interfaz por default es el orbe
    _orb = FloatingOrb(_window.handle_orb_select)
    _window.orb = _orb  # para ocultarlo mientras una ventana de sección está abierta
    _orb.show()
    app.exec()
