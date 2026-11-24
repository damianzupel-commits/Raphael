"""Orbe flotante de Raphael: la interfaz principal (pedido de Damian 2026-09-01,
sobre su boceto). En vez de una ventana grande, en el escritorio flota SOLO un
orbe con la imagen de Raphael; al tocar el centro se despliega un menú compacto
con las secciones (Chat, Codebase, Obsidian, Investigación) + Configuración + Voz.

La ventana completa (`MainWindow`) sigue existiendo pero queda OCULTA hasta que se
elige una sección desde el orbe -- así se reutilizan tal cual las vistas ya hechas
(codebase/obsidian/investigación/chat) sin reescribir nada, y el orbe es solo el
nuevo punto de entrada. El orbe es sin bordes, transparente, siempre encima y
arrastrable.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QGuiApplication,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ui.chat_view import ChatBridge, ChatRequestThread, _append_transcript
from voice_listener import VoiceListener

try:
    import tts  # para que el orbe lata al ritmo de la voz (tts.get_level())
except Exception:  # noqa: BLE001
    tts = None

ORB_SIZE = 104
_CLICK_MOVE_THRESHOLD = 6  # px: si al soltar te moviste menos que esto, fue un click (no un arrastre)


_MENU_QSS = """
QWidget#orbMenu { background: rgba(11, 20, 36, 238); border: 1px solid #22406a; border-radius: 12px; }
QPushButton#orbMenuItem {
    background: transparent; color: #e8f0fb; border: none; border-radius: 8px;
    padding: 9px 16px; font-size: 14px; text-align: left; min-width: 180px;
}
QPushButton#orbMenuItem:hover { background: #12233a; color: #ffffff; }
"""


class _OrbMenu(QWidget):
    """Panel compacto que se despliega al tocar el orbe. Cada ítem llama a
    `on_select(key)` y se cierra."""

    # "Chat" NO va acá: el chat vive siempre en la barra flotante debajo del orbe.
    # "Historial" SÍ: despliega la conversación COMPLETA en la ventana (incluye lo
    # que escribiste por la barra flotante -- comparten el mismo transcript).
    ITEMS = [
        ("🎯  Centro de Mando", "mando"),
        ("⚙  Configuración", "settings"),
    ]

    def __init__(self, on_select):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._on_select = on_select

        self.setObjectName("orbMenu")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        for label, key in self.ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("orbMenuItem")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            layout.addWidget(btn)
        self.setStyleSheet(_MENU_QSS)

    def _pick(self, key: str) -> None:
        self.hide()
        self._on_select(key)


_CHATBAR_QSS = """
QWidget#chatBar { background: transparent; }
QLineEdit#orbInput {
    background: rgba(10, 21, 38, 240); color: #e8f0fb; border: 1px solid #22406a;
    border-radius: 18px; padding: 9px 16px; font-size: 14px;
}
QLineEdit#orbInput:focus { border-color: #f59e0b; }
QPushButton#orbMic {
    background: rgba(10, 21, 38, 240); color: #cdd8e6; border: 1px solid #22406a;
    border-radius: 18px; min-width: 36px; min-height: 36px; font-size: 16px;
}
QPushButton#orbMic:hover { background: #0e1a2e; color: #ffffff; }
QPushButton#orbMic:checked { background: #f59e0b; color: #0a1120; border-color: #f59e0b; }
QScrollArea#orbReplyScroll {
    background: rgba(11, 20, 36, 242); border: 1px solid #22406a; border-radius: 12px;
}
QScrollArea#orbReplyScroll > QWidget > QWidget { background: transparent; }
QLabel#orbReply { background: transparent; color: #e8f0fb; padding: 10px 14px; font-size: 13px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 4px 2px 4px 0; }
QScrollBar::handle:vertical { background: #3b3d47; border-radius: 4px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: #4a4d59; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

_CHATBAR_WIDTH = 340


class FloatingChatBar(QWidget):
    """Barra de chat flotante debajo del orbe (pedido de Damian 2026-09-01): se
    escribe a Raphael sin abrir la ventana. Usa la MISMA conversación que la
    ventana (conversation_id None -> "default" en el backend), así comparten
    contexto/memoria. La respuesta se muestra en una burbuja debajo del input."""

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("chatBar")
        self.setMinimumSize(280, 64)
        self.resize(_CHATBAR_WIDTH, 68)
        self._sized_once = False  # para dar un alto cómodo en la 1ra respuesta

        self._bridge = ChatBridge()
        self._bridge.reply_ready.connect(self._on_reply)
        self._thread: ChatRequestThread | None = None
        self._voice: VoiceListener | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Fila: input de escritura + botón de micrófono al lado.
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setObjectName("orbInput")
        self._input.setPlaceholderText("Escribile a Raphael…")
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, stretch=1)

        self._mic = QPushButton("🎙")
        self._mic.setObjectName("orbMic")
        self._mic.setCheckable(True)
        self._mic.setCursor(Qt.PointingHandCursor)
        self._mic.setToolTip("Hablar por voz (prender/apagar)")
        self._mic.toggled.connect(self._on_mic_toggled)
        input_row.addWidget(self._mic)

        layout.addLayout(input_row)

        # La respuesta va DENTRO de un área con scroll: si es larga, aparece la
        # barra de deslizado en vez de desbordar la pantalla.
        self._reply = QLabel()
        self._reply.setObjectName("orbReply")
        self._reply.setWordWrap(True)
        self._reply.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._reply.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._reply_scroll = QScrollArea()
        self._reply_scroll.setObjectName("orbReplyScroll")
        self._reply_scroll.setWidgetResizable(True)
        self._reply_scroll.setWidget(self._reply)
        self._reply_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._reply_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._reply_scroll.hide()
        # stretch=1: la respuesta ocupa el alto que le des al redimensionar la barra.
        layout.addWidget(self._reply_scroll, stretch=1)

        # AGARRADERA visible (QSizeGrip) abajo a la derecha: redimensiona la ventana
        # de forma confiable. El resize por borde (startSystemResize / manual) no
        # andaba en ventanas frameless+translúcidas de Windows; este SÍ.
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip = QSizeGrip(self)
        grip.setObjectName("orbGrip")
        grip.setFixedSize(16, 16)
        grip_row.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        layout.addLayout(grip_row)

        self.setStyleSheet(_CHATBAR_QSS)

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        _append_transcript("user", text)  # queda en el historial completo compartido
        self._show_reply("Raphael está pensando…")
        self._thread = ChatRequestThread(text, None, self._bridge)
        self._thread.start()

    def _on_reply(self, author: str, text: str) -> None:
        # Vale tanto para respuestas escritas (siempre "assistant") como para la voz
        # (que además manda el "transcript" del usuario como author "user").
        _append_transcript("user" if author == "user" else "assistant", text)
        self._show_reply(text)

    # ---- voz ----

    def _on_mic_toggled(self, on: bool) -> None:
        if on:
            if self._voice is None:
                # require_wake_word=False: prender el botón YA es la señal de
                # "escuchame", no hace falta decir "hey Raphael".
                self._voice = VoiceListener(
                    on_event=self._on_voice_event, require_wake_word=False
                )
            self._voice.start()
            self._show_reply("Escuchando… hablá.")
        elif self._voice is not None:
            self._voice.stop()

    def _on_voice_event(self, kind: str, text: str) -> None:
        # VoiceListener llama esto desde su hilo de audio -> NO tocar widgets acá.
        # Se reemite por la señal Qt (thread-safe) para procesarlo en el hilo GUI.
        if kind == "wake":
            return
        author = "user" if kind == "transcript" else "assistant"
        self._bridge.reply_ready.emit(author, text)

    def _show_reply(self, text: str) -> None:
        self._reply.setText(text)
        self._reply_scroll.show()
        # La 1ra vez que hay respuesta le damos un alto cómodo; después respetamos
        # el tamaño que hayas puesto con la agarradera.
        if not self._sized_once:
            self.resize(max(self.width(), _CHATBAR_WIDTH), 240)
            self._sized_once = True
        # Arranca arriba, para leer la respuesta desde el principio.
        self._reply_scroll.verticalScrollBar().setValue(0)

    def closeEvent(self, event) -> None:
        if self._voice is not None:
            self._voice.stop()
        super().closeEvent(event)


class FloatingOrb(QWidget):
    """El orbe en sí. Click en el centro -> abre/cierra el menú. Arrastrar -> lo
    reposiciona en el escritorio. Debajo lleva una barra de chat flotante."""

    def __init__(self, on_select):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(ORB_SIZE, ORB_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Raphael -- tocá para abrir, arrastrá para mover")

        self._on_select = on_select
        self._press_global = None
        self._moved = False
        self._menu = _OrbMenu(self._on_select)
        self._chatbar = FloatingChatBar()

        # Animación del orbe (dibujado desde cero, estilo anime): un reloj `_t`
        # avanza y dispara el repintado. FPS ADAPTATIVO (fix lag de tecleo 2026-11-01):
        # ~30fps cuando Raphael habla (fluido) y ~15fps en reposo (ahorrativo). A 50fps
        # fijos, el orbe translúcido repintaba todo el tiempo y trababa el hilo de la
        # GUI -> las letras del chat aparecían con delay. La respiración es lenta, así
        # que 15fps en reposo se ve igual de bien y libera el hilo.
        self._t = 0.0
        # Nivel de voz suavizado (0..1): cuando Raphael habla, el orbe se expande
        # y se enciende al ritmo del audio (lo publica tts._level / get_level()).
        self._voice_level = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_anim)
        self._timer.start(66)  # arranca en modo reposo (~15fps); sube solo al hablar

        self._place_bottom_right()
        self._position_chatbar()
        self._chatbar.show()

    # ------------------------------------------------- orbe animado (anime)

    def _tick_anim(self) -> None:
        # Avanzar el reloj en tiempo REAL (según el intervalo actual del timer), no un
        # paso fijo: así la animación corre a la misma velocidad sin importar los FPS,
        # y bajar los FPS en reposo no la hace ver más lenta.
        self._t += max(0.001, self._timer.interval() / 1000.0)
        # Leer el nivel de voz y suavizarlo: ataque rápido (sube al toque cuando
        # habla) y caída más lenta (para que no titile entre sílabas).
        target = tts.get_level() if tts is not None else 0.0
        if target > self._voice_level:
            self._voice_level += (target - self._voice_level) * 0.6
        else:
            self._voice_level += (target - self._voice_level) * 0.2
        self.update()
        # FPS adaptativo: fluido mientras Raphael habla, ahorrativo en reposo, para no
        # trabar el hilo de la GUI (y que el tecleo aparezca al instante). Ver __init__.
        speaking = self._voice_level > 0.03 or target > 0.03
        desired = 33 if speaking else 66  # ~30fps hablando / ~15fps en reposo
        if self._timer.interval() != desired:
            self._timer.setInterval(desired)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        t = self._t
        c = ORB_SIZE / 2.0
        center = QPointF(c, c)
        R = c - 3

        # "Respiración" lenta (dos frecuencias combinadas -> nada mecánico).
        breath = 0.5 + 0.5 * math.sin(t * 0.9) * 0.7 + 0.5 * math.sin(t * 1.7 + 1.0) * 0.3

        # Nivel de voz (0..1): cuando Raphael habla, la esfera se expande y enciende.
        v = self._voice_level

        # --- 1) Halo exterior que respira (y se agranda con la voz) ---
        halo_r = R * (1.02 + 0.16 * breath + 0.28 * v)
        halo = QRadialGradient(center, halo_r)
        halo.setColorAt(0.0, QColor(255, 170, 70, 70))
        halo.setColorAt(0.45, QColor(255, 130, 50, 45))
        halo.setColorAt(1.0, QColor(255, 110, 40, 0))
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(center, halo_r, halo_r)

        # --- 2) Remolino de energía (gradiente cónico que gira = rayos del anime) ---
        painter.save()
        swirl_path_r = R * 0.94
        painter.setClipRect(QRectF(c - swirl_path_r, c - swirl_path_r, 2 * swirl_path_r, 2 * swirl_path_r))
        swirl = QConicalGradient(center, -t * 28.0)
        rays = 6
        for i in range(rays * 2 + 1):
            pos = i / (rays * 2)
            bright = i % 2 == 0
            swirl.setColorAt(pos, QColor(255, 200, 120, 90) if bright else QColor(255, 120, 40, 0))
        painter.setBrush(QBrush(swirl))
        painter.drawEllipse(center, swirl_path_r, swirl_path_r)
        painter.restore()

        # --- 3) Núcleo incandescente (esfera con gradiente radial; late con la voz) ---
        core_r = R * (0.72 + 0.05 * breath + 0.16 * v)
        core = QRadialGradient(QPointF(c - R * 0.08, c - R * 0.10), core_r * 1.15)  # highlight arriba-izq
        core.setColorAt(0.0, QColor(255, 252, 238, 255))
        core.setColorAt(0.30, QColor(255, 214, 140, 255))
        core.setColorAt(0.62, QColor(255, 140, 52, 235))
        core.setColorAt(1.0, QColor(150, 55, 12, 120))
        painter.setBrush(QBrush(core))
        painter.drawEllipse(center, core_r, core_r)

        # Punto caliente central que pulsa (el "alma" del orbe; se aviva con la voz).
        hot = 0.5 + 0.5 * math.sin(t * 2.3)
        hot_r = R * (0.16 + 0.06 * hot + 0.14 * v)
        hotg = QRadialGradient(center, hot_r)
        hotg.setColorAt(0.0, QColor(255, 255, 250, 255))
        hotg.setColorAt(1.0, QColor(255, 240, 200, 0))
        painter.setBrush(QBrush(hotg))
        painter.drawEllipse(center, hot_r, hot_r)

        # --- 4) Anillos orbitando (elipses inclinadas que giran a distinta velocidad) ---
        pen = QPen()
        pen.setWidthF(1.6)
        for i in range(3):
            painter.save()
            painter.translate(center)
            painter.rotate(t * (16 + i * 11) + i * 63)
            painter.scale(1.0, 0.34 + 0.06 * math.sin(t * 0.8 + i))  # aplasta -> anillo inclinado
            ring_r = R * (0.80 - i * 0.06)
            alpha = 120 - i * 25
            pen.setColor(QColor(255, 210, 140, alpha))
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), ring_r, ring_r)
            painter.restore()

        # --- 5) Partículas orbitando (con estela suave) ---
        painter.setPen(Qt.NoPen)
        for k in range(7):
            ang = t * (0.6 + k * 0.13) + k * (2 * math.pi / 7)
            rad = R * (0.55 + 0.28 * math.sin(t * 0.7 + k * 1.3))
            px = c + rad * math.cos(ang)
            py = c + rad * math.sin(ang) * 0.62  # órbita elíptica (perspectiva)
            psize = 1.4 + 1.4 * (0.5 + 0.5 * math.sin(t * 2.0 + k))
            pg = QRadialGradient(QPointF(px, py), psize * 2.2)
            pg.setColorAt(0.0, QColor(255, 245, 210, 235))
            pg.setColorAt(1.0, QColor(255, 200, 120, 0))
            painter.setBrush(QBrush(pg))
            painter.drawEllipse(QPointF(px, py), psize * 2.2, psize * 2.2)

        # --- 6) Anillo de borde tenue ---
        edge = QPen(QColor(255, 190, 110, 90 + int(60 * breath)))
        edge.setWidthF(1.4)
        painter.setPen(edge)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, R, R)
        painter.end()

    # ------------------------------------------------------------- posición

    def _place_bottom_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        margin = 40
        self.move(geo.right() - ORB_SIZE - margin, geo.bottom() - ORB_SIZE - margin)

    def _position_menu(self) -> None:
        """Ubica el menú a la izquierda-arriba del orbe (que suele estar abajo a la
        derecha), sin salirse de la pantalla."""
        self._menu.adjustSize()
        mw, mh = self._menu.width(), self._menu.height()
        x = self.x() - mw + ORB_SIZE  # alineado con el borde derecho del orbe
        y = self.y() - mh - 8  # arriba del orbe
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = max(geo.left() + 8, min(x, geo.right() - mw - 8))
            y = max(geo.top() + 8, y)
        self._menu.move(x, y)

    def _position_chatbar(self) -> None:
        """Centra la barra de chat justo debajo del orbe, sin salirse de pantalla.
        Usa el ancho ACTUAL de la barra (respeta el que hayas puesto redimensionando)."""
        bw = self._chatbar.width()
        x = self.x() + ORB_SIZE // 2 - bw // 2
        y = self.y() + ORB_SIZE + 8
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = max(geo.left() + 8, min(x, geo.right() - bw - 8))
        self._chatbar.move(x, y)

    def _toggle_menu(self) -> None:
        if self._menu.isVisible():
            self._menu.hide()
        else:
            self._position_menu()
            self._menu.show()
            self._menu.raise_()
            self._menu.activateWindow()

    # ------------------------------------------------- arrastre vs. click

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_win = self.pos()
            self._moved = False

    def mouseMoveEvent(self, event) -> None:
        if self._press_global is None:
            return
        delta = event.globalPosition().toPoint() - self._press_global
        if not self._moved and delta.manhattanLength() > _CLICK_MOVE_THRESHOLD:
            self._moved = True
        if self._moved:
            self.move(self._press_win + delta)
            self._position_chatbar()  # la barra de chat sigue al orbe
            if self._menu.isVisible():
                self._menu.hide()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        was_click = not self._moved
        self._press_global = None
        if was_click:
            self._toggle_menu()

    def shutdown(self) -> None:
        self._menu.close()
        self._chatbar.close()
        self.close()

    def hide_all(self) -> None:
        """Oculta el orbe y todo su séquito (menú + barra de chat). Se usa al abrir
        una ventana de sección, para que el launcher no quede encima del contenido."""
        self._menu.hide()
        self._chatbar.hide()
        self.hide()

    def show_all(self) -> None:
        """Vuelve a mostrar el orbe y su barra de chat (el menú queda cerrado)."""
        self.show()
        self.raise_()
        self._position_chatbar()
        self._chatbar.show()
        self._chatbar.raise_()
