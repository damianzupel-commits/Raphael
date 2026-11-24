"""Test de agent.get_display_history (historial mostrable para el espejado PC↔celular)."""

from app import agent


def test_filtra_solo_user_y_assistant_con_texto(monkeypatch):
    monkeypatch.setattr(agent, "_conversations", {
        "default": [
            {"role": "system", "content": "sys"},                     # se saltea
            {"role": "user", "content": "hola"},                       # va
            {"role": "assistant", "content": "qué tal"},               # va
            {"role": "assistant", "content": None, "tool_calls": [1]},  # puro tool call -> no
            {"role": "tool", "content": "resultado"},                  # se saltea
            {"role": "user", "content": [                              # multimodal -> junta texto
                {"type": "text", "text": "multi"}, {"type": "image_url"}]},
        ]
    })
    assert agent.get_display_history("default") == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "qué tal"},
        {"role": "user", "content": "multi"},
    ]


def test_vacio_si_no_existe(monkeypatch):
    monkeypatch.setattr(agent, "_conversations", {})
    assert agent.get_display_history("nope") == []


def test_respeta_limit(monkeypatch):
    monkeypatch.setattr(agent, "_conversations", {
        "c": [{"role": "user", "content": str(i)} for i in range(10)]
    })
    h = agent.get_display_history("c", limit=3)
    assert [m["content"] for m in h] == ["7", "8", "9"]
