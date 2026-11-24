"""Diálogo "Vincular celular" (Etapa 1, 2026-10-12, pedido de Damian).

Embebe la página /vincular que sirve el backend (mismo patrón que config_dialog.py /
mission_control_view.py): muestra un QR con la API key + las URLs locales de esta PC. El
usuario abre la app en el celular, escanea el QR y queda sincronizado — sin tipear IPs ni
tokens. La key va en la URL (?key=) para autenticar GET /api/pairing; queda dentro del
webview local de la app.
"""

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QVBoxLayout

import config


class PairDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vincular celular · Raphael")
        self.resize(460, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._url = f"{config.BASE_URL}/vincular?key={config.API_KEY}"
        self.web = QWebEngineView()
        self.web.load(QUrl(self._url))
        layout.addWidget(self.web)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Recargar al abrir para traer las URLs actuales (la IP de LAN pudo cambiar).
        self.web.load(QUrl(self._url))
