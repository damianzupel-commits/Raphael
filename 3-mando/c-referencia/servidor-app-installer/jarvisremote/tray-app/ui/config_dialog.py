"""Diálogo de Configuración amigable (2026-10-11, pedido de Damian "agrega todo").

Embebe el panel web /configuracion que SIRVE el backend, dentro de un QWebEngineView
(mismo patrón que ui/mission_control_view.py). Reemplaza al viejo diálogo de 5 toggles:
este panel cubre TODAS las opciones amigables (personalización, voz, modo de trabajo,
conocimiento, permisos) y las guarda al backend/.env vía POST /api/config.

La key va en la URL para que el panel pueda autenticar GET/POST /api/config. Queda dentro
del webview local de la app; por fuera (navegador sin ?key=) el panel carga en modo lectura
y no puede guardar, así no se expone escritura del .env sin credencial.
"""

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QVBoxLayout

import config

# Señal que el panel web pone en document.title al guardar OK (ver configuracion-raphael.html).
# Damian (2026-10-11): al guardar, el diálogo se cierra y se reabre solo con valores frescos.
_SAVED_SIGNAL = "RAPHAEL_CFG_SAVED"


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración · Raphael")
        self.resize(840, 740)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._url = f"{config.BASE_URL}/configuracion?key={config.API_KEY}"
        self.web = QWebEngineView()
        self.web.load(QUrl(self._url))
        # El panel no puede cerrar la ventana Qt desde su JS; usa el título como puente.
        self.web.titleChanged.connect(self._on_title_changed)
        layout.addWidget(self.web)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Recargar al abrir para traer los valores actuales del .env.
        self.web.load(QUrl(self._url))

    def _on_title_changed(self, title: str) -> None:
        # Al guardar OK el panel setea este título -> cerramos y reabrimos (showEvent recarga
        # los valores frescos). El reload pone el título original, así que no hay loop.
        if title == _SAVED_SIGNAL:
            self.close()
            QTimer.singleShot(250, self._reopen)

    def _reopen(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
