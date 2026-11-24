"""De punta a punta con todas las piezas reales. Necesita los repos raphael-* lado a lado (o instalados)."""

from datetime import timedelta
from pathlib import Path

import pytest

from raphael_harness import Harness, cargar_perfil
from raphael_harness.cargador import descubrir
from raphael_harness.testing import Reloj

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = Path(__file__).resolve().parents[1] / "ejemplos" / "perfil-ropa-medida.yaml"
_, DISPONIBLES, _ = descubrir(RAIZ)
pytestmark = pytest.mark.skipif(len(DISPONIBLES) < 5, reason="faltan los repos de las brigadas al lado de raphael-harness")


def armar():
    r = Reloj()
    return Harness(cargar_perfil(PERFIL), rutas_dev=RAIZ, reloj=r, config_modelos={}), r


def test_carga_todas_las_piezas_del_perfil():
    h, _ = armar()
    assert set(h.brigadas) == {"atencion", "encargos", "cobros", "agenda", "avisos"}
    assert h.orquestador.nombre == "orquestador"
    assert h.avisos == []


def test_recorrido_completo_de_una_clienta():
    h, r = armar()
    W = ("whatsapp", "5493415550000")
    c = "whatsapp:5493415550000"
    assert "Atendemos" in h.recibir(*W, "Hola! qué horario tienen?")[0]

    # encargo con una pregunta en el medio que responde Atención
    h.recibir(*W, "quiero un vestido largo a medida para el casamiento de mi hermana", nombre="Cami")
    out = h.recibir(*W, "¿hacen envíos?")
    assert "todo el país" in out[0] and out[0].endswith("¿Para qué fecha lo necesitás? 📅")
    for m in ("el 20 de marzo", "de gasa verde", "no", "prefiero que me midan", "el jueves a las 17", "Camila Pérez"):
        out = h.recibir(*W, m)
    assert "#1" in out[0]

    # la dueña: presupuesto sugerido (150.000 + 20% largo) y turno de medidas pedido por Encargos -> Agenda
    tipos = {p["accion"]["tipo"]: p for p in h.pendientes()}
    assert set(tipos) == {"enviar_presupuesto", "confirmar_turno"}
    assert tipos["enviar_presupuesto"]["accion"]["datos"]["precio"] == 180000
    h.aprobar(tipos["confirmar_turno"]["id"])
    assert "jueves 19 de noviembre a las 17:00" in h.salientes(c)[-1]["texto"]
    h.aprobar(tipos["enviar_presupuesto"]["id"])
    assert "$ 90.000" in h.salientes(c)[-1]["texto"]          # seña 50%

    # pago: la clienta avisa, la dueña confirma, Avisos le escribe solo
    assert "confirme la transferencia" in h.recibir(*W, "listo, ya te transferí")[0]
    [pago] = h.pendientes()
    h.aprobar(pago["id"])
    assert "Recibimos tu seña" in h.salientes(c)[-1]["texto"]
    assert h.comando("encargos", "ver", {"num": 1})["estado"] == "confirmado"

    # recordatorio del turno y aviso de "listo"
    r.ahora -= timedelta(days=0)
    h.tick()
    assert any("Te recordamos" in s["texto"] for s in h.salientes(c))
    h.comando("encargos", "estado", {"num": 1, "estado": "listo"})
    assert "está listo" in h.salientes(c)[-1]["texto"]

    # reclamo: se deriva a una persona y nadie más responde
    out = h.recibir(*W, "me llegó mal el pedido")
    assert "Ana" in out[0] and len(out) == 1
    assert h.pendientes()[-1]["nivel"] == "humano"

    est = h.estado()
    assert est["uso"]["mensajes"] == 11 and "Camila" not in str(est)


def test_duda_sin_respuesta_y_saludo():
    h, _ = armar()
    assert "Taller Ejemplo" in h.recibir("instagram", "x", "hola")[0]
    assert "te lo confirma Ana" in h.recibir("instagram", "x", "¿hacen arreglos de ruedos?")[0]
