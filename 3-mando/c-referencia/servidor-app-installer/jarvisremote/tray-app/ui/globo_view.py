"""Vista "Mapa de inteligencia" — pestaña que embebe el globo 3D que SIRVE el backend
(/globo) dentro de un QWebEngineView. Mismo patrón que mission_control_view.py. Muestra el
OSINT geolocalizado de Raphael (pines) + capa de vuelos en vivo. La key va en la URL para
autenticar /api/geo/points + /ws/geo."""

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

import config


class GloboView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._url = f"{config.BASE_URL}/globo?key={config.API_KEY}"
        self.web = QWebEngineView()
        self.web.load(QUrl(self._url))
        layout.addWidget(self.web)

    def reload(self) -> None:
        self.web.load(QUrl(self._url))
