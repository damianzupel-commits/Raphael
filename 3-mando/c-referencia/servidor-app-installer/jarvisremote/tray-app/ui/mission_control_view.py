"""Vista "Centro de Mando" — pestaña de la ventana principal que embebe el panel de
brigadas que SIRVE el backend (http://.../centro-de-mando) dentro de un QWebEngineView.

Misma tecnología que el grafo 3D (ui/graph_view.py). Carga la versión EN VIVO: al venir
del backend por http, el panel se conecta solo a /ws/mission-control y muestra la
actividad real de las brigadas (no la simulación). Si el backend no está arriba todavía,
muestra el error del navegador; `reload()` lo reintenta (se llama al abrir la sección).
"""

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

import config


class MissionControlView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # La key va en la URL para que el chat del feed pueda autenticar contra /api/chat.
        # Queda dentro del webview de la app (local); por fuera (navegador sin ?key=) el chat
        # queda deshabilitado, así no se expone control de Raphael sin credencial.
        self._url = f"{config.BASE_URL}/centro-de-mando?key={config.API_KEY}"
        self.web = QWebEngineView()
        self.web.load(QUrl(self._url))
        layout.addWidget(self.web)

    def reload(self) -> None:
        """Recarga el panel desde el backend (reconecta el WebSocket en vivo)."""
        self.web.load(QUrl(self._url))
