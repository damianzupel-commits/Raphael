"""Vista de chat -- pestaña "Chat" de la ventana principal (ver
`ui/main_window.py`). Contiene todo lo que antes vivía directo en el cuerpo
de `MainWindow` (sidebar de utilidades + columna de mensajes + input + voz);
se extrajo a su propio widget para que `MainWindow` pueda alojarla como una
pestaña más junto a Codebase y Obsidian, sin cambiar ningún comportamiento.
"""

import json

import requests
from PySide6.QtCore import QObject, QPointF, Qt, QRectF, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import config
from ui.widgets import NoMinWidthLabel
from voice_listener import VoiceListener


# Pedidos recurrentes que se muestran en la pantalla de bienvenida (panel
# desplegable). Cada uno es (icono, etiqueta, prompt). Si el prompt termina en
# "…" es una plantilla incompleta: al tocarla se ESCRIBE en el input y se enfoca
# para que el usuario la complete. Si está completo, al tocarla se ENVÍA directo.
# Para agregar un pedido nuevo, sumá una tupla acá -- nada más.
RECURRING_REQUESTS: list[tuple[str, str, str]] = [
    ("🗂", "Listar archivos del escritorio", "Listame los archivos de mi escritorio"),
    ("🛡", "Auditar la seguridad de un proyecto", "Auditá la seguridad del proyecto en la carpeta …"),
    ("🧠", "Buscar en mis notas", "Buscá en mis notas sobre …"),
    ("📥", "Ingerir videos nuevos de la playlist", "Ingerí los videos nuevos de mi playlist de YouTube"),
    ("⚡", "Crear una app web rápida", "Creá una app web simple para …"),
]


class _WindowBackground(QWidget):
    """Fondo FIJO de la ventana: la imagen de Raphael cubriendo todo el panel,
    centrada y atenuada con un velo oscuro para que el texto quede legible. SIN
    movimiento -- cualquier deriva, por lenta que fuera, se percibía como temblor
    (pedido de Damian, 2026-09-01: dejarlo fijo). Transparente a los clicks para
    no bloquear el chat. Se escala una sola vez por resize."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._src = pixmap
        self._scaled = QPixmap()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0 or self._src.isNull():
            self._scaled = QPixmap()
            return
        # Cubre el panel manteniendo proporción (recorta lo que sobra).
        self._scaled = self._src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

    def paintEvent(self, event) -> None:
        if self._scaled.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()
        x = -(self._scaled.width() - w) / 2
        y = -(self._scaled.height() - h) / 2
        painter.drawPixmap(QPointF(x, y), self._scaled)
        # Velo oscuro por encima para mantener el chat legible sobre la imagen.
        painter.fillRect(self.rect(), QColor(14, 15, 20, 175))
        painter.end()


# --- Transcript compartido (historial VISIBLE) ---------------------------------
# La ventana de chat Y la barra flotante del orbe escriben en el MISMO archivo
# (config.HISTORY_PATH) para que el historial sea uno solo y completo. Se escribe
# en modo APPEND (leer -> agregar -> escribir), no rescribiendo desde una lista en
# memoria: así los mensajes de una superficie no pisan los de la otra.


def _append_transcript(author: str, text: str) -> None:
    try:
        path = config.HISTORY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = []
        if not isinstance(data, list):
            data = []
        data.append({"author": author, "text": text})
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass  # persistencia best-effort -- nunca romper el chat por el disco


def _load_transcript() -> list[dict]:
    try:
        if not config.HISTORY_PATH.exists():
            return []
        data = json.loads(config.HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [m for m in data if isinstance(m, dict) and m.get("text")]


def build_animated_background(parent=None) -> "_WindowBackground | None":
    """Crea el fondo FIJO de la ventana (imagen de Raphael) o None si no se puede
    cargar. Lo usa la ventana principal para poner el fondo a nivel de TODA la
    ventana (detrás de la barra superior, las pestañas y el chat). Se usa la imagen
    NÍTIDA: al ser fijo no hay temblor/shimmer, así que se ve clara."""
    try:
        src = config.RAPHAEL_IMAGE
        if not src.exists():
            return None
        pix = QPixmap(str(src))
        if pix.isNull():
            return None
    except Exception:
        return None
    return _WindowBackground(pix, parent)


class ChatBridge(QObject):
    """Recibe eventos desde hilos de trabajo (HTTP, voz) y los reemite como
    señales Qt -- así el hilo de la GUI es el único que toca los widgets."""

    reply_ready = Signal(str, str)  # (autor, texto)


class ChatRequestThread(QThread):
    def __init__(self, message: str, conversation_id: str, bridge: ChatBridge):
        super().__init__()
        self._message = message
        self._conversation_id = conversation_id
        self._bridge = bridge

    def run(self) -> None:
        try:
            resp = requests.post(
                config.CHAT_URL,
                json={
                    "message": self._message,
                    "conversation_id": self._conversation_id or config.SHARED_CONVERSATION_ID,
                    "client_id": config.CLIENT_ID,  # para que el backend no me reenvíe mi eco
                },
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                timeout=config.CHAT_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            reply = resp.json().get("reply", "(sin respuesta)")
        except requests.RequestException as exc:
            reply = f"No pude conectarme con Raphael: {exc}"
        self._bridge.reply_ready.emit("assistant", reply)


class Sidebar(QWidget):
    """Barra de accesos directos. `tools` es una lista de (icono, tooltip,
    prompt) -- agregar una utilidad nueva (ej. interpolación de frames) es
    agregar una tupla acá, nada más."""

    # Vacía a propósito: "Generar imagen"/"Generar video" se sacaron de la UI
    # (no solo deshabilitadas atrás) por precaución de hardware -- la PC se
    # apagó físicamente coincidiendo con generate_image/generate_video (ver
    # INFORME_COMPLETO.md, sección 4.5, y backend/app/tools/__init__.py,
    # donde esas dos tools están comentadas). No reactivar ninguna de las dos
    # puntas sin haber investigado la causa primero.
    TOOLS: list[tuple[str, str, str]] = []

    tool_selected = Signal(str)
    voice_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(64)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 16, 6, 16)
        layout.setSpacing(8)

        for icon, tooltip, prompt_prefix in self.TOOLS:
            btn = QPushButton(icon)
            btn.setObjectName("sidebarButton")
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, p=prompt_prefix: self.tool_selected.emit(p))
            layout.addWidget(btn)

        layout.addStretch()

        self.voice_button = QPushButton("🎙")
        self.voice_button.setObjectName("sidebarButton")
        self.voice_button.setToolTip("Activar/desactivar escucha continua (\"hey Jarvis\")")
        self.voice_button.setCheckable(True)
        self.voice_button.setCursor(Qt.PointingHandCursor)
        self.voice_button.toggled.connect(self.voice_toggled.emit)
        layout.addWidget(self.voice_button)


class ChatView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._bridge = ChatBridge()
        self._bridge.reply_ready.connect(self._on_reply)

        self._conversation_id: str | None = None
        self._voice_listener: VoiceListener | None = None
        self._typing_bubble: QWidget | None = None
        self._request_thread: ChatRequestThread | None = None
        self._welcome: QWidget | None = None
        self._recurring_panel: QWidget | None = None
        self._status_label: QLabel | None = None
        self._transcript: list[dict] = []  # historial VISIBLE persistido en disco

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.tool_selected.connect(self._on_tool_selected)
        self.sidebar.voice_toggled.connect(self._on_voice_toggled)
        layout.addWidget(self.sidebar)

        layout.addWidget(self._build_chat_column(), stretch=1)

        # Recarga el transcript de sesiones anteriores ("todo lo que hablamos").
        # Si no hay historial, arranca con la bienvenida (saludo + recurrentes).
        if not self._load_history():
            self._show_welcome()

        # Espejado en vivo con el celular (2026-10-06): WebSocket a /ws/chat. Lo que
        # se escribe desde el celular aparece acá al instante (y viceversa). QWebSocket
        # es nativo de Qt: sus señales llegan en el hilo de la GUI, así que puedo tocar
        # los widgets directo desde los slots, sin hilos extra.
        self._mirror_ws: QWebSocket | None = None
        self._start_mirror()

    # ------------------------------------------------------------- layout

    def _build_chat_column(self) -> QWidget:
        column = QWidget()
        column.setObjectName("chatColumn")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._build_header())

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.addStretch()
        self.scroll_area.setWidget(self._messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Escribile algo a Raphael…")
        self.message_input.returnPressed.connect(self._on_send_clicked)
        input_row.addWidget(self.message_input, stretch=1)

        send_button = QPushButton("Enviar")
        send_button.setObjectName("sendButton")
        send_button.setCursor(Qt.PointingHandCursor)
        send_button.clicked.connect(self._on_send_clicked)
        input_row.addWidget(send_button)

        layout.addLayout(input_row)
        return column

    def _build_header(self) -> QWidget:
        """Encabezado del chat: nombre a la izquierda + píldora de estado a la
        derecha (Conectado / Pensando…), estilo asistente moderno."""
        header = QWidget()
        header.setObjectName("chatHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(4, 0, 4, 0)

        name = QLabel("Raphael")
        name.setObjectName("chatHeaderName")
        row.addWidget(name)
        row.addStretch()

        self._status_label = QLabel("● Conectado")
        self._status_label.setObjectName("statusPill")
        self._status_label.setProperty("state", "connected")
        row.addWidget(self._status_label)
        return header

    def _set_status(self, state: str) -> None:
        """state: 'connected' | 'thinking'. Actualiza texto + color de la píldora."""
        if self._status_label is None:
            return
        labels = {"connected": "● Conectado", "thinking": "● Pensando…"}
        self._status_label.setText(labels.get(state, "● Conectado"))
        self._status_label.setProperty("state", state)
        # Re-aplicar el estilo tras cambiar la property (Qt no lo hace solo).
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    # ------------------------------------------------- pantalla de bienvenida

    def _show_welcome(self) -> None:
        """Inserta la tarjeta de bienvenida al tope de la conversación: saludo +
        panel desplegable de pedidos recurrentes. Se remueve al primer mensaje."""
        if self._welcome is not None:
            return
        card = QWidget()
        card.setObjectName("welcomeCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 24, 8, 8)
        v.setSpacing(6)

        title = QLabel("Hola, soy Raphael 👋")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        subtitle = QLabel("Tu asistente en esta PC. Escribime abajo lo que necesites,\ntocá 🎙 para hablarme, o elegí un pedido recurrente:")
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        v.addWidget(subtitle)

        # Botón que despliega / colapsa la lista de pedidos recurrentes.
        self._recurring_toggle = QPushButton("⚡  Pedidos recurrentes  ▾")
        self._recurring_toggle.setObjectName("recurringToggle")
        self._recurring_toggle.setCursor(Qt.PointingHandCursor)
        self._recurring_toggle.setCheckable(True)
        self._recurring_toggle.toggled.connect(self._on_recurring_toggled)
        v.addWidget(self._recurring_toggle, alignment=Qt.AlignHCenter)

        # Panel con los pedidos; oculto hasta que se toca el botón de arriba.
        panel = QWidget()
        panel.setObjectName("recurringPanel")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(0, 4, 0, 0)
        pv.setSpacing(6)
        for icon, label, prompt in RECURRING_REQUESTS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("recurringItem")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, p=prompt: self._on_recurring_selected(p))
            pv.addWidget(btn)
        panel.setVisible(False)
        self._recurring_panel = panel
        v.addWidget(panel)

        self._messages_layout.insertWidget(self._messages_layout.count() - 1, card)
        self._welcome = card

    def _on_recurring_toggled(self, expanded: bool) -> None:
        if self._recurring_panel is not None:
            self._recurring_panel.setVisible(expanded)
        self._recurring_toggle.setText(
            "⚡  Pedidos recurrentes  ▴" if expanded else "⚡  Pedidos recurrentes  ▾"
        )

    def _on_recurring_selected(self, prompt: str) -> None:
        """Plantilla incompleta (termina en '…') -> se escribe para completar.
        Pedido completo -> se envía directo."""
        if prompt.rstrip().endswith("…"):
            self.message_input.setText(prompt.rstrip("… ").rstrip() + " ")
            self.message_input.setFocus()
            self.message_input.setCursorPosition(len(self.message_input.text()))
        else:
            self._send_message(prompt)

    def _remove_welcome(self) -> None:
        if self._welcome is not None:
            self._messages_layout.removeWidget(self._welcome)
            self._welcome.deleteLater()
            self._welcome = None
            self._recurring_panel = None

    def _build_avatar(self, width: int) -> QLabel | None:
        """QLabel con la imagen de Raphael escalada a `width` px (proporción
        mantenida) y con **bordes redondeados suaves** (para que no quede el
        rectángulo duro del PNG), o None si no se puede cargar."""
        try:
            if not config.RAPHAEL_IMAGE.exists():
                return None
            pix = QPixmap(str(config.RAPHAEL_IMAGE))
            if pix.isNull():
                return None
        except Exception:
            return None
        pix = pix.scaledToWidth(width, Qt.SmoothTransformation)
        pix = self._round_pixmap(pix, radius=max(16, width // 10))
        label = QLabel()
        label.setObjectName("welcomeAvatar")
        label.setPixmap(pix)
        label.setAlignment(Qt.AlignCenter)
        return label

    @staticmethod
    def _round_pixmap(src: QPixmap, radius: int) -> QPixmap:
        """Devuelve una copia de `src` con las esquinas redondeadas y antialias,
        sobre fondo transparente -- suaviza el borde duro de la imagen."""
        rounded = QPixmap(src.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, src.width(), src.height()), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src)
        painter.end()
        return rounded

    # ---------------------------------------------- persistencia del historial

    def _record_message(self, author: str, text: str) -> None:
        """Agrega el mensaje al transcript compartido en disco (historial VISIBLE),
        que también usa la barra flotante del orbe -> un solo historial completo."""
        self._transcript.append({"author": author, "text": text})
        _append_transcript(author, text)

    def _load_history(self) -> bool:
        """Carga el transcript persistido (el mismo que escribe la barra flotante)
        y re-dibuja las burbujas. Devuelve True si había historial, False si no."""
        self._transcript = _load_transcript()
        if not self._transcript:
            return False
        for m in self._transcript:
            author = "user" if m.get("author") == "user" else "assistant"
            self._add_bubble(author, m.get("text", ""))
        return True

    def reload_history(self) -> None:
        """Vacía las burbujas actuales y RECARGA el historial completo desde disco.
        Se llama cada vez que se abre la ventana desde el orbe, para que refleje TODO
        lo hablado —incluido lo que escribiste por la barra flotante— y no una copia
        vieja cargada al arrancar la app."""
        # Sacar todas las burbujas/bienvenida (queda el stretch final, que es el
        # único item que NO es un widget).
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._welcome = None
        self._recurring_panel = None
        self._typing_bubble = None
        self._transcript = []
        if not self._load_history():
            self._show_welcome()
        # Bajar al último mensaje.
        self._scroll_to_bottom()

    # ------------------------------------------------------------- chat

    def _scroll_to_bottom(self) -> None:
        """Baja al fondo del chat DESPUÉS de que el layout recalculó la altura.
        Hacerlo en el mismo tick (justo tras insertar la burbuja) dejaba el scroll
        un poco más arriba del fondo real —el `maximum` todavía no incluía la burbuja
        recién agregada—, así que lo último quedaba cortado y no se podía leer (bug
        reportado 2026-10-18). `QTimer.singleShot(0)` lo difiere al próximo ciclo de
        eventos, cuando el `maximum` ya es el correcto."""
        def _do() -> None:
            bar = self.scroll_area.verticalScrollBar()
            bar.setValue(bar.maximum())
        QTimer.singleShot(0, _do)

    def _add_bubble(self, author: str, text: str, object_name: str | None = None) -> QWidget:
        # NoMinWidthLabel, no QLabel a secas -- el texto acá es de chat (del
        # usuario o de Jarvis) y puede traer una URL/path/hash larguísimo sin
        # espacios, que sin este fix estira la ventana principal (ver
        # ui/widgets.py para el bug real).
        label = NoMinWidthLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        row = QHBoxLayout()
        if author == "user":
            # El texto del usuario es literal: PlainText para no interpretar sus * o _.
            label.setTextFormat(Qt.PlainText)
            label.setObjectName(object_name or "bubbleUser")
            row.addStretch()
            row.addWidget(label, stretch=0)
        else:
            # Raphael escribe en Markdown: renderizarlo (negritas, listas, código, links)
            # en vez de mostrar los caracteres crudos -- fix "escribe feo / con caracteres /
            # difícil de leer" que notó Damian (2026-10-31).
            label.setTextFormat(Qt.MarkdownText)
            label.setOpenExternalLinks(True)
            label.setObjectName(object_name or "bubbleAssistant")
            row.addWidget(label, stretch=0)
            row.addStretch()

        wrapper = QWidget()
        wrapper.setLayout(row)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, wrapper)
        self._scroll_to_bottom()
        return wrapper

    def _show_typing_indicator(self) -> None:
        self._hide_typing_indicator()
        self._typing_bubble = self._add_bubble("assistant", "Raphael está pensando…", object_name="bubbleTyping")

    def _hide_typing_indicator(self) -> None:
        if self._typing_bubble is not None:
            self._messages_layout.removeWidget(self._typing_bubble)
            self._typing_bubble.deleteLater()
            self._typing_bubble = None

    def add_system_message(self, text: str) -> None:
        label = NoMinWidthLabel(text)
        label.setObjectName("bubbleSystem")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, label)
        self._scroll_to_bottom()

    def _add_system_message(self, text: str) -> None:
        self.add_system_message(text)

    def _on_send_clicked(self) -> None:
        text = self.message_input.text().strip()
        if not text:
            return
        self.message_input.clear()
        self._send_message(text)

    def _send_message(self, text: str) -> None:
        self._remove_welcome()
        self._add_bubble("user", text)
        self._record_message("user", text)
        self._set_status("thinking")
        self._show_typing_indicator()
        self._request_thread = ChatRequestThread(text, self._conversation_id, self._bridge)
        self._request_thread.start()

    def _on_tool_selected(self, prompt_prefix: str) -> None:
        self.message_input.setText(prompt_prefix)
        self.message_input.setFocus()
        self.message_input.setCursorPosition(len(prompt_prefix))

    def _on_reply(self, author: str, text: str) -> None:
        self._remove_welcome()
        self._hide_typing_indicator()
        self._set_status("connected")
        self._add_bubble(author, text)
        self._record_message(author, text)

    # ------------------------------------------------------------- voz

    def _on_voice_toggled(self, enabled: bool) -> None:
        if enabled:
            if self._voice_listener is None:
                # require_wake_word=False: prender este botón ya es la señal de
                # "escuchame" -- pedir además "hey Jarvis" sería redundante,
                # solo tiene sentido para una escucha pasiva en background (que
                # este botón no es).
                self._voice_listener = VoiceListener(
                    on_event=self._on_voice_event_threadsafe, require_wake_word=False
                )
            self._voice_listener.start()
            self.add_system_message("Escucha activada. Hablá directo, sin decir nada antes.")
        else:
            if self._voice_listener is not None:
                self._voice_listener.stop()
            self.add_system_message("Escucha desactivada.")

    def _on_voice_event_threadsafe(self, kind: str, text: str) -> None:
        # VoiceListener llama esto desde su propio hilo de audio -- nunca tocar
        # widgets acá directamente, todo pasa por la señal Qt (thread-safe).
        if kind == "wake":
            return
        labels = {"transcript": "user", "reply": "assistant", "error": "assistant"}
        self._bridge.reply_ready.emit(labels.get(kind, "assistant"), text)

    # ------------------------------------------------- espejado en vivo (celular)

    def _start_mirror(self) -> None:
        """Abre el WebSocket de espejado y conecta sus señales. Reintenta solo si se
        cae. Best-effort: si algo falla, el chat sigue andando igual (sin espejo)."""
        try:
            self._mirror_ws = QWebSocket()
            self._mirror_ws.connected.connect(self._on_mirror_connected)
            self._mirror_ws.textMessageReceived.connect(self._on_mirror_message)
            self._mirror_ws.disconnected.connect(self._on_mirror_disconnected)
            self._open_mirror()
        except Exception:  # noqa: BLE001 -- el espejo es un extra, nunca romper el chat
            self._mirror_ws = None

    def _open_mirror(self) -> None:
        if self._mirror_ws is None:
            return
        try:
            request = QNetworkRequest(QUrl(config.WS_CHAT_URL))
            request.setRawHeader(b"Authorization", f"Bearer {config.API_KEY}".encode("utf-8"))
            self._mirror_ws.open(request)
        except Exception:  # noqa: BLE001
            pass

    def _on_mirror_connected(self) -> None:
        # Suscribirse a la conversación compartida, diciendo quién soy (para que el
        # backend no me reenvíe mi propio eco).
        if self._mirror_ws is None:
            return
        self._mirror_ws.sendTextMessage(json.dumps({
            "conversation_id": config.SHARED_CONVERSATION_ID,
            "client_id": config.CLIENT_ID,
        }))

    def _on_mirror_disconnected(self) -> None:
        # Reintentar la conexión tras una pausa (ej. backend reiniciado).
        QTimer.singleShot(3000, self._open_mirror)

    def _on_mirror_message(self, text: str) -> None:
        """Llega un turno escrito desde OTRO dispositivo (el celular): lo muestro acá.
        El backend ya me saltea a mí por client_id, pero filtro por las dudas."""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return
        if data.get("type") != "turn" or data.get("origin") == config.CLIENT_ID:
            return
        for m in data.get("messages", []):
            content = (m.get("content") or "").strip()
            if not content:
                continue
            role = "user" if m.get("role") == "user" else "assistant"
            self._remove_welcome()
            self._add_bubble(role, content)
            self._record_message(role, content)

    def shutdown(self) -> None:
        if self._voice_listener is not None:
            self._voice_listener.stop()
        if self._mirror_ws is not None:
            try:
                # Evitar que el disconnected dispare un reintento mientras cerramos.
                self._mirror_ws.disconnected.disconnect(self._on_mirror_disconnected)
            except (RuntimeError, TypeError):
                pass
            self._mirror_ws.close()
