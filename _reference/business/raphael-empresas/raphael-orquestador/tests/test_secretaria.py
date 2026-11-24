"""El orquestador como secretario: qué hay para hoy, qué primero, el detalle y las opciones."""

from datetime import datetime

from raphael_harness import Accion, Brigada, Mensaje, Respuesta
from raphael_harness.testing import Reloj, armar
from raphael_orquestador import OrquestadorRaphael


class Encargos(Brigada):
    nombre = "encargos"
    version = "1"
    acciones = {}

    def __init__(self, lista):
        self.lista = lista

    def interes(self, msg, ctx):
        return 1.0 if "vestido" in msg.texto else 0.0

    def comando(self, nombre, datos, ctx):
        if nombre == "listar":
            return self.lista
        if nombre == "ver":
            return next(e for e in self.lista if e["num"] == datos["num"])
        return super().comando(nombre, datos, ctx)

    def atender(self, msg, ctx):
        return Respuesta("ok", [Accion("enviar_presupuesto", {"num": 3, "precio": 90000}, "Encargo #3 de Lola: vestido — sugerido $ 90.000")])


class Agenda(Brigada):
    nombre = "agenda"
    version = "1"

    def comando(self, nombre, datos, ctx):
        return [{"fecha": "2026-11-18", "hora": "16:00", "motivo": "medidas", "nombre": "Sofi", "contacto": "w:1"}]


class Atencion(Brigada):
    nombre = "atencion"
    version = "1"

    def interes(self, msg, ctx):
        return 0.1

    def atender(self, msg, ctx):
        return Respuesta("pasalo", [Accion("derivar_humano", {"texto": msg.texto}, "Reclamo de Marta: «llegó roto»")])


def e(num, cliente, entrega, estado="en_confeccion", urgente=False):
    return {"num": num, "cliente": cliente, "descripcion": "saco", "entrega": entrega, "estado": estado, "urgente": urgente, "contacto": f"w:{num}"}


def sistema(lista=None, **kw):
    reloj = Reloj(datetime(2026, 11, 18, 9, 0))
    h = armar(Encargos(lista or []), Agenda(), Atencion(), orquestador=OrquestadorRaphael(), reloj=reloj, **kw)
    return h, reloj


def test_dia_tranquilo():
    h, _ = sistema()
    h.brigadas.pop("agenda")
    r = h.hablar_con_duena("buen día")
    assert "Buen día, Ana" in r.texto and "nada pendiente" in r.texto


def test_resumen_numerado_y_ordenado_por_urgencia():
    h, _ = sistema([e(1, "Pía", "2026-11-30"), e(2, "Rita", "2026-11-18"), e(3, "Luz", "2026-11-10")])
    r = h.hablar_con_duena("Buen día, ¿qué tareas tenemos hoy?")
    assert [t["encargo"] for t in r.tareas if t["origen"] == "encargo"] == [3, 2]       # vencido antes que el de hoy; el de 12 días no entra
    assert r.texto.index("1)") < r.texto.index("2)") and "Encargo #3 de Luz" in r.texto.split("2)")[0]
    assert "se pasó la fecha de entrega hace 8 días" in r.tareas[0]["motivo"]


def test_recomienda_la_mas_urgente_y_explica_por_que():
    h, _ = sistema([e(1, "Pía", "2026-11-19"), e(2, "Rita", "2026-11-17")])
    h.hablar_con_duena("hola")
    r = h.hablar_con_duena("perfecto, ¿cuál me recomendás hacer primero?")
    assert "Te recomiendo la 1)" in r.texto and "Rita" in r.texto and "Porque se pasó la fecha" in r.texto
    assert "Después seguiría con la 2)" in r.texto


def test_siguiente_recorre_la_lista_y_avisa_el_final():
    h, _ = sistema([e(1, "Pía", "2026-11-19"), e(2, "Rita", "2026-11-17")])
    h.hablar_con_duena("hola")
    h.hablar_con_duena("¿cuál primero?")
    n_tareas = len(h.hablar_con_duena("tareas").tareas)
    h.hablar_con_duena("¿cuál primero?")
    textos = [h.hablar_con_duena("¿y después?").texto for _ in range(n_tareas)]
    assert "la 2)" in textos[0]
    assert "la última" in textos[-1]


def test_pendiente_humano_pasa_adelante_y_la_ficha_trae_contexto_y_opciones():
    h, reloj = sistema([e(1, "Pía", "2026-11-25")])
    h.recibir("whatsapp", "w:9", "me llegó roto, quiero hablar con alguien", "Marta")
    reloj.ahora = datetime(2026, 11, 18, 14, 0)                                  # lleva horas esperando
    r = h.hablar_con_duena("qué hay hoy")
    assert r.tareas[0]["tipo"] == "derivar_humano" and "pidió hablar con una persona" in r.tareas[0]["motivo"]
    f = h.hablar_con_duena("contame la 1")
    assert "Contexto:" in f.texto and "Qué podés hacer" in f.texto and "(lo que yo haría)" in f.texto
    assert f.ficha["pendiente"]["id"] == r.tareas[0]["pendiente"]
    assert any("me llegó roto" in m["texto"] for m in f.ficha["conversacion"])
    assert f.ficha["opciones"][0]["recomendada"] and len(f.ficha["opciones"]) == 3


def test_presupuesto_urgente_suma_prioridad_y_avisa():
    h, _ = sistema([e(3, "Lola", "2026-11-20", estado="presupuesto", urgente=True)])
    h.recibir("whatsapp", "w:3", "quiero un vestido", "Lola")
    t = h.hablar_con_duena("tareas").tareas
    pres = next(x for x in t if x["tipo"] == "enviar_presupuesto" and "urgente" in x["motivo"])
    f = h.hablar_con_duena(f"la {pres['id']}")
    assert "Aprobar el precio sugerido" in f.texto or "Ponerle precio" in f.texto


def test_turno_de_hoy_figura():
    h, _ = sistema()
    r = h.hablar_con_duena("resumen")
    assert any(t["tipo"] == "turno" and "16:00" in t["titulo"] for t in r.tareas)


def test_numero_inexistente_y_frase_que_no_entiende():
    h, _ = sistema([e(1, "Pía", "2026-11-18")])
    h.hablar_con_duena("hola")
    assert "No tengo una tarea 7" in h.hablar_con_duena("contame la 7").texto
    assert "No te entendí" in h.hablar_con_duena("asdf qwerty").texto


def test_sin_ia_no_inventa_resumen_y_con_ia_lo_usa():
    cfg = {"planes": {"basico": {"resumen": "x", "secretaria": "x"}}, "proveedores": {"x": {"base_url": "http://ia", "model": "m", "api_key_env": ""}}}
    llamadas = []

    def ia(url, cuerpo, headers):
        llamadas.append(cuerpo["messages"][0]["content"][:20])
        return {"choices": [{"message": {"content": "Marta recibió algo roto y quiere solución."}}], "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

    h, _ = sistema(config_modelos=cfg, transporte_ia=ia)
    h.recibir("whatsapp", "w:9", "me llegó roto, quiero hablar con alguien", "Marta")
    h.hablar_con_duena("hola")
    f = h.hablar_con_duena("contame la 1")
    assert "Marta recibió algo roto" in f.texto and llamadas
    libre = h.hablar_con_duena("che, ¿y si me tomo el viernes libre?")
    assert libre.texto and len(llamadas) >= 2


def test_un_orquestador_sin_secretario_responde_amable():
    from raphael_harness import Orquestador

    class Viejo(Orquestador):
        nombre = "viejo"
        version = "1"

        def elegir(self, msg, ctx, brigadas):
            return brigadas

    h = armar(orquestador=Viejo())
    assert "actualizá el orquestador" in h.hablar_con_duena("hola").texto
