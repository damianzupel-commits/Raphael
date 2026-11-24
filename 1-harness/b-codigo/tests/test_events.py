import asyncio

from raphael_core.events import EventBus, EventCycleError


def test_eventos_llegan_a_quien_los_escucha():
    """Portado de test_eventos_llegan_a_quien_los_escucha (Empresas)."""
    bus, vistos = EventBus(), []
    bus.subscribe("ping", lambda e, d: vistos.append((e, d)), owner="eco")
    bus.publish("ping", {"x": 1}, source="otra")
    assert vistos == [("ping", {"x": 1, "_from": "otra"})]


def test_un_suscriptor_roto_no_rompe_a_nadie():
    errores, vistos = [], []
    bus = EventBus(on_error=lambda o, e, x: errores.append((o, e, type(x).__name__)))

    def roto(e, d):
        raise ValueError("boom")

    bus.subscribe("ping", roto, owner="rota")
    bus.subscribe("ping", lambda e, d: vistos.append(d["x"]), owner="sana")
    bus.publish("ping", {"x": 1})            # no levanta
    assert vistos == [1] and errores == [("rota", "ping", "ValueError")]


def test_comodin_y_desuscribir_por_duenio():
    bus, vistos = EventBus(), []
    bus.subscribe("*", lambda e, d: vistos.append(e), owner="todo")
    bus.subscribe("a", lambda e, d: vistos.append("a2"), owner="todo")
    bus.subscribe("a", lambda e, d: vistos.append("otra"), owner="otra")
    bus.publish("a", {})
    assert vistos == ["a2", "otra", "a"]
    assert bus.unsubscribe("todo") == 2 and bus.owners() == {"otra"}
    vistos.clear()
    bus.publish("b", {})
    assert vistos == []


def test_ciclo_se_corta_y_se_reporta_sin_romper_al_que_publica():
    errores = []
    bus = EventBus(max_depth=4, on_error=lambda o, e, x: errores.append(type(x)))
    bus.subscribe("a", lambda e, d: bus.publish("b", {}), owner="x")
    bus.subscribe("b", lambda e, d: bus.publish("a", {}), owner="y")
    bus.publish("a", {})
    assert errores and errores[0] is EventCycleError


def test_historial_acotado():
    bus = EventBus(history=3)
    for i in range(10):
        bus.publish("n", {"i": i})
    assert [d["i"] for _, d in bus.history] == [7, 8, 9]


def test_manejadores_async_con_apublish_y_con_publish_en_un_loop():
    vistos = []

    async def lento(e, d):
        await asyncio.sleep(0)
        vistos.append(d["i"])

    async def main():
        bus = EventBus()
        bus.subscribe("n", lento, owner="a")
        await bus.apublish("n", {"i": 1})
        bus.publish("n", {"i": 2})          # se agenda
        assert vistos == [1]
        await bus.drain()
        assert vistos == [1, 2]

    asyncio.run(main())


def test_manejador_async_sin_loop_se_resuelve_en_el_acto():
    vistos = []

    async def h(e, d):
        vistos.append(d["i"])

    bus = EventBus()
    bus.subscribe("n", h, owner="a")
    bus.publish("n", {"i": 5})
    assert vistos == [5]


def test_falla_de_manejador_async_se_reporta():
    errores = []

    async def roto(e, d):
        raise RuntimeError("x")

    async def main():
        bus = EventBus(on_error=lambda o, e, x: errores.append(o))
        bus.subscribe("n", roto, owner="rota")
        bus.publish("n", {})
        await bus.drain()
        await bus.apublish("n", {})

    asyncio.run(main())
    assert errores == ["rota", "rota"]
