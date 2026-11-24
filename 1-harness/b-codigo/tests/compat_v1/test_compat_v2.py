"""Lo que la compatibilidad agrega sobre v1: modelos por escalón, aislamiento y brigadas v1 montadas en el v2."""

from raphael_harness import Brigada, Respuesta
from raphael_harness.testing import armar

from raphael_core import Level

OK = {"choices": [{"message": {"content": "listo"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class Rota(Brigada):
    nombre = "rota"
    version = "1.0.0"

    def interes(self, msg, ctx):
        return 1.0

    def atender(self, msg, ctx):
        raise RuntimeError("se rompió")


class Eco(Brigada):
    nombre = "eco"
    version = "1.0.0"

    def interes(self, msg, ctx):
        return 0.5

    def atender(self, msg, ctx):
        return Respuesta("eco: " + msg.texto)


def test_sin_config_usa_openrouter_con_data_collection_deny():
    llamadas = []

    def transporte(url, cuerpo, headers):
        llamadas.append((url, cuerpo["model"], headers.get("Authorization"), cuerpo.get("provider")))
        return OK

    h = armar(Eco(), config_modelos=None, env={"OPENROUTER_API_KEY": "or"}, transporte_ia=transporte)
    ctx = h._ctx("orquestador")
    assert ctx.hay_ia("secretaria") and ctx.ia("secretaria", [{"role": "user", "content": "hola"}]) == "listo"
    url, modelo, auth, prov = llamadas[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions" and auth == "Bearer or"
    assert prov == {"data_collection": "deny"}
    sin_clave = armar(Eco(), config_modelos=None, env={})
    assert not sin_clave._ctx("orquestador").hay_ia("secretaria")
    # NVIDIA gratis es solo para desarrollo: tener su clave no habilita IA en producción
    solo_nvidia = armar(Eco(), config_modelos=None, env={"NVIDIA_API_KEY": "nv"})
    assert not solo_nvidia._ctx("orquestador").hay_ia("secretaria")


def test_una_brigada_v1_rota_no_tumba_el_mensaje():
    h = armar(Rota(), Eco())
    assert h.recibir("prueba", "1", "hola") == ["eco: hola"]


def test_las_brigadas_v1_quedan_montadas_en_el_v2():
    h = armar(Eco())
    assert set(h.runtime.brigades) == {"eco"}
    assert h.runtime.policy.level("eco", "devolver_dinero") is Level.HUMAN        # antes piso, ahora de fábrica
    assert h.runtime.policy.spec("eco", "devolver_dinero").risky
