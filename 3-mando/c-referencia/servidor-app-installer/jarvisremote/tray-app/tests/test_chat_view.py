"""Tests de la vista de chat (pestaña "Chat", ver ui/chat_view.py). No arranca
VoiceListener de verdad (cargar whisper/VAD es lento y no hace falta para
probar el wiring de la UI)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

import config
from ui.chat_view import ChatView, Sidebar


@pytest.fixture(autouse=True)
def _isolate_history(tmp_path, monkeypatch):
    # ChatView recarga/persiste el transcript desde config.HISTORY_PATH. Se apunta
    # a un archivo temporal por test para no leer/escribir el historial real y para
    # que cada test arranque sin historial (bienvenida visible) de forma determinista.
    monkeypatch.setattr(config, "HISTORY_PATH", tmp_path / "tray_chat_history.json")


def test_sidebar_has_no_image_or_video_utilities():
    # generate_image/generate_video se sacaron de la UI (no solo deshabilitadas
    # del lado del backend) por precaución de hardware -- ver Sidebar.TOOLS y
    # INFORME_COMPLETO.md, sección 4.5. No reactivar sin haber investigado la
    # causa del apagado primero.
    tooltips = [tooltip for _, tooltip, _ in Sidebar.TOOLS]
    assert "Generar imagen" not in tooltips
    assert "Generar video" not in tooltips


def test_sidebar_has_no_utility_buttons_only_voice(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    tool_buttons = [
        b for b in sidebar.findChildren(QPushButton) if b.objectName() == "sidebarButton" and not b.isCheckable()
    ]
    assert tool_buttons == []


def test_sidebar_tool_click_emits_its_prompt_prefix(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    received = []
    sidebar.tool_selected.connect(received.append)

    tool_buttons = [
        b for b in sidebar.findChildren(QPushButton) if b.objectName() == "sidebarButton" and not b.isCheckable()
    ]
    assert len(tool_buttons) == len(Sidebar.TOOLS)

    for button, (_, _, expected_prefix) in zip(tool_buttons, Sidebar.TOOLS):
        qtbot.mouseClick(button, Qt.LeftButton)
        assert received[-1] == expected_prefix


def test_sidebar_voice_button_is_checkable_and_toggles(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    received = []
    sidebar.voice_toggled.connect(received.append)

    assert sidebar.voice_button.isCheckable()
    qtbot.mouseClick(sidebar.voice_button, Qt.LeftButton)
    qtbot.mouseClick(sidebar.voice_button, Qt.LeftButton)
    assert received == [True, False]


def test_tool_selected_prefills_and_focuses_the_message_input(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    view._on_tool_selected("Genera una imagen de: ")

    assert view.message_input.text() == "Genera una imagen de: "
    assert view.message_input.cursorPosition() == len("Genera una imagen de: ")


def test_add_system_message_appends_a_bubble(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    before = view._messages_layout.count()
    view.add_system_message("hola")

    assert view._messages_layout.count() == before + 1


def test_on_reply_hides_typing_indicator_and_adds_bubble(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    view._show_typing_indicator()
    assert view._typing_bubble is not None

    view._on_reply("assistant", "respuesta")

    assert view._typing_bubble is None


def test_pantalla_arranca_con_bienvenida(qtbot):
    # La conversación arranca con la tarjeta de bienvenida (saludo + pedidos
    # recurrentes), no vacía ni con un mensaje de sistema suelto.
    view = ChatView()
    qtbot.addWidget(view)

    assert view._welcome is not None
    assert view._welcome.objectName() == "welcomeCard"


def test_bienvenida_se_saca_al_primer_mensaje(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    assert view._welcome is not None
    view._remove_welcome()
    assert view._welcome is None
    view._remove_welcome()  # idempotente: llamarla de nuevo no rompe
    assert view._welcome is None


def test_toggle_de_pedidos_recurrentes_muestra_el_panel(qtbot):
    view = ChatView()
    qtbot.addWidget(view)

    # Colapsado por defecto. Se usa isHidden() (estado explícito) en vez de
    # isVisible(), que sería False igual porque la vista no está mostrada en el test.
    assert view._recurring_panel is not None
    assert view._recurring_panel.isHidden() is True

    view._recurring_toggle.setChecked(True)
    assert view._recurring_panel.isHidden() is False

    view._recurring_toggle.setChecked(False)
    assert view._recurring_panel.isHidden() is True


def test_pedido_plantilla_incompleto_prellena_el_input_sin_enviar(qtbot):
    # Un pedido que termina en "…" es una plantilla: se escribe en el input para
    # completar, NO se envía (no debe agregar burbuja de usuario ni disparar red).
    view = ChatView()
    qtbot.addWidget(view)
    antes = view._messages_layout.count()

    view._on_recurring_selected("Buscá en mis notas sobre …")

    assert view.message_input.text().startswith("Buscá en mis notas sobre")
    assert "…" not in view.message_input.text()  # se saca el placeholder al prellenar
    assert view._messages_layout.count() == antes  # no se envió nada


def test_transcript_se_persiste_y_se_recarga_al_reabrir(qtbot):
    # Simula "cerrar y reabrir": una vista graba mensajes; una vista nueva
    # (misma HISTORY_PATH temporal) debe recargarlos y saltear la bienvenida.
    v1 = ChatView()
    qtbot.addWidget(v1)
    assert v1._welcome is not None  # arranca sin historial -> bienvenida

    v1._record_message("user", "hola raphael")
    v1._on_reply("assistant", "hola damian")
    assert config.HISTORY_PATH.exists()

    v2 = ChatView()
    qtbot.addWidget(v2)
    assert v2._welcome is None  # había historial -> NO bienvenida
    assert [m["text"] for m in v2._transcript] == ["hola raphael", "hola damian"]
