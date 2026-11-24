"""Ventana de configuración (permisos/conectores), separada de la ventana
principal de chat a pedido de Damian: la vista de chat tiene que quedar
"limpia, nada técnica", así que todo lo de prender/apagar capacidades
invasivas (control de PC, shell del celular, cámara, etc.) vive acá, detrás
de un ícono de ajustes aparte.

Los toggles leen/escriben directamente backend/.env (las mismas flags que ya
existen en backend/app/config.py) y reinician el backend al guardar, igual
que el selector de modelo de la ventana principal.
"""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

import config
import process_manager
from ui.theming import force_dark_title_bar

# Mismo tema oscuro fijo que la ventana principal (ver main_window.py) --
# pedido explícito de Damian, sin opción de volver a claro.
STYLESHEET = """
QDialog { background: #0b1424; }
QLabel#settingsTitle { font-size: 16px; font-weight: 600; color: #e8f0fb; }
QLabel#settingsHint { color: #7f96b2; font-size: 12px; }
QCheckBox { font-size: 14px; color: #e8f0fb; padding: 6px 0; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #22406a; background: #0a1526;
}
QCheckBox::indicator:checked { background: #f59e0b; border: 1px solid #f59e0b; }
QPushButton#saveButton {
    background: #f59e0b; color: #0a1120; border: none; border-radius: 10px;
    padding: 8px 18px; font-size: 13px; font-weight: 700;
}
QPushButton#saveButton:hover { background: #d9820c; }
QPushButton#saveButton:disabled { background: #23324a; color: #7f96b2; }
QPushButton#cancelButton {
    background: transparent; color: #9fb4cd; border: none;
    padding: 8px 18px; font-size: 13px;
}
QPushButton#cancelButton:hover { color: #e5e7eb; }
"""

# (clave en .env, etiqueta amigable, texto de ayuda, valor por default si la
# clave no está en el .env -- tiene que coincidir con el default real de
# backend/app/config.py::Settings, si no la UI miente sobre el estado actual).
TOGGLES = [
    ("DESKTOP_CONTROL_ENABLED", "Controlar esta PC", "Permite mover el mouse, escribir y manejar ventanas.", True),
    ("PHONE_SHELL_ENABLED", "Ejecutar comandos en el celular", "Acceso más invasivo del celular: corre comandos reales via Termux.", True),
    ("PHONE_CAMERA_ENABLED", "Usar la cámara del celular", "Permite sacar fotos y grabar video corto desde el celular.", True),
    ("FS_ALLOW_DELETE", "Permitir borrar archivos", "Si está apagado, Raphael puede leer/crear archivos pero no borrarlos.", False),
    ("BROWSER_HEADLESS", "Ocultar la ventana del navegador automatizado", "Si está prendido, el navegador que Raphael usa corre invisible.", False),
]


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if config.ENV_PATH.exists():
        for line in config.ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def _write_env(updates: dict[str, str]) -> None:
    lines = config.ENV_PATH.read_text(encoding="utf-8").splitlines() if config.ENV_PATH.exists() else []
    seen = set()
    new_lines = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else None
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")
    config.ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class _RestartThread(QThread):
    done = Signal()

    def run(self) -> None:
        process_manager.stop()
        process_manager.start()
        self.done.emit()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Raphael")
        self.setMinimumWidth(420)
        self.setStyleSheet(STYLESHEET)
        force_dark_title_bar(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Permisos y conectores")
        title.setObjectName("settingsTitle")
        layout.addWidget(title)

        hint = QLabel("Qué puede hacer Raphael en esta PC y en tu celular. Los cambios piden reiniciar el backend.")
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        current = _read_env()
        self._checkboxes: dict[str, QCheckBox] = {}
        for key, label_text, help_text, default_value in TOGGLES:
            box = QCheckBox(label_text)
            box.setToolTip(help_text)
            raw = current.get(key, "").strip().lower()
            is_true = (raw in ("1", "true", "yes", "on")) if raw else default_value
            box.setChecked(is_true)
            self._checkboxes[key] = box
            layout.addWidget(box)

        self._status_label = QLabel("")
        self._status_label.setObjectName("settingsHint")
        layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = QPushButton("Cerrar")
        cancel_button.setObjectName("cancelButton")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.clicked.connect(self.close)
        button_row.addWidget(cancel_button)

        self._save_button = QPushButton("Guardar y reiniciar")
        self._save_button.setObjectName("saveButton")
        self._save_button.setCursor(Qt.PointingHandCursor)
        self._save_button.clicked.connect(self._on_save)
        button_row.addWidget(self._save_button)

        layout.addLayout(button_row)

    def _on_save(self) -> None:
        updates = {key: ("true" if box.isChecked() else "false") for key, box in self._checkboxes.items()}
        _write_env(updates)

        self._save_button.setEnabled(False)
        self._status_label.setText("Guardando y reiniciando el backend...")
        self._restart_thread = _RestartThread()
        self._restart_thread.done.connect(self._on_restart_done)
        self._restart_thread.start()

    def _on_restart_done(self) -> None:
        self._save_button.setEnabled(True)
        self._status_label.setText("Listo, los cambios ya están aplicados.")
