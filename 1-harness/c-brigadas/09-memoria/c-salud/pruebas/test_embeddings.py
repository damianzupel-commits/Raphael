"""Embeddings enchufables: el real (servidor local) y el simulado. Sin servidor, la brigada sigue y lo dice."""

from __future__ import annotations

import httpx
import pytest
from raphael_core.store import Store

from raphael_memoria.config import memoria_config
from raphael_memoria.embeddings import EmbeddingIndex, LocalEmbedder, MockEmbedder, NoEmbedder, build_embedder, cosine


def server(handler):
    return httpx.MockTransport(handler)


def ok_handler(request: httpx.Request) -> httpx.Response:
    body = request.read().decode()
    return httpx.Response(200, json={"data": [{"embedding": [1.0, 2.0, 3.0]}], "echo": body})


def test_cosine_basico():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([], [1]) == 0.0 and cosine([1, 2], [1]) == 0.0 and cosine([0, 0], [1, 1]) == 0.0


def test_el_simulado_es_determinista_y_las_palabras_compartidas_acercan():
    m = MockEmbedder()
    a, b, c = m.embed("rotación de claves del servidor"), m.embed("claves del servidor Orión"), m.embed("receta de ñoquis")
    assert a == m.embed("rotación de claves del servidor")
    assert cosine(a, b) > cosine(a, c) and m.embed("") is None and m.embed("de la el") is None


def test_el_real_le_pega_a_embeddings_con_el_modelo_y_devuelve_el_vector():
    seen = []

    def h(req):
        seen.append((str(req.url), req.read().decode(), req.headers.get("authorization")))
        return ok_handler(req)
    e = LocalEmbedder("http://localhost:1234/v1/", "nomic", transport=server(h))
    assert e.embed("hola") == [1.0, 2.0, 3.0] and e.last_error is None
    url, body, auth = seen[0]
    assert url == "http://localhost:1234/v1/embeddings" and '"model":"nomic"' in body.replace(" ", "") and auth is None


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500, text="boom"),
    lambda r: httpx.Response(200, json={"data": []}),
    lambda r: httpx.Response(200, text="no es json"),
    lambda r: (_ for _ in ()).throw(httpx.ConnectError("apagado")),
])
def test_si_el_servidor_falla_devuelve_none_y_avisa_sin_levantar(handler):
    e = LocalEmbedder("http://localhost:1234/v1", "m", transport=server(handler))
    assert e.embed("hola") is None and "no respondió" in e.last_error
    assert e.embed("  ") is None


def test_una_direccion_que_no_es_de_esta_pc_se_rechaza_sin_permiso_explicito():
    cfg = memoria_config({"embeddings": {"provider": "local", "base_url": "https://api.example.com/v1"}})
    e = build_embedder(cfg, {})
    assert isinstance(e, NoEmbedder) and "no es de esta PC" in e.last_error and e.embed("x") is None


def test_con_allow_remote_pide_la_clave_de_una_variable_y_sin_ella_no_sale():
    cfg = memoria_config({"embeddings": {"base_url": "https://api.example.com/v1", "allow_remote": True,
                                         "api_key_env": "MI_CLAVE"}})
    assert isinstance(build_embedder(cfg, {}), NoEmbedder)
    assert "MI_CLAVE" in build_embedder(cfg, {}).last_error
    e = build_embedder(cfg, {"MI_CLAVE": "secreta"})
    assert isinstance(e, LocalEmbedder) and e.api_key == "secreta"


def test_por_defecto_apunta_a_lm_studio_y_el_entorno_lo_cambia():
    e = build_embedder(memoria_config({}), {})
    assert e.base_url == "http://localhost:1234/v1" and e.model.startswith("text-embedding-nomic")
    e2 = build_embedder(memoria_config({}), {"MEMORIA_EMBEDDINGS_BASE_URL": "http://localhost:11434/v1",
                                            "MEMORIA_EMBEDDINGS_MODEL": "nomic-embed-text"})
    assert e2.base_url == "http://localhost:11434/v1" and e2.model == "nomic-embed-text"


def test_provider_off_y_mock():
    assert isinstance(build_embedder(memoria_config({"embeddings": {"provider": "off"}}), {}), NoEmbedder)
    assert isinstance(build_embedder(memoria_config({"embeddings": {"provider": "mock"}}), {}), MockEmbedder)


def test_el_indice_guarda_reusa_y_se_invalida_al_cambiar_de_modelo():
    space = Store().space("memoria")
    calls = []
    m = MockEmbedder()
    orig = m.embed
    m.embed = lambda t: (calls.append(t), orig(t))[1]
    idx = EmbeddingIndex(space, m)
    assert idx.update("a/uno", "rotación de claves") and idx.update("a/uno", "rotación de claves")
    assert len(calls) == 1                                    # mismo texto: no recalcula
    assert set(idx.load()) == {"a/uno"}
    m2 = MockEmbedder()
    m2.model = "otro-modelo"
    assert EmbeddingIndex(space, m2).load() == {}             # otro modelo: los vectores viejos no se comparan


def test_reindexar_cuenta_lo_saltado_y_limpia_notas_borradas():
    space = Store().space("memoria")
    idx = EmbeddingIndex(space, MockEmbedder())
    idx.reindex([("a/uno", "texto uno"), ("a/dos", "texto dos")])
    res = idx.reindex([("a/uno", "texto uno"), ("a/vacia", "")])      # una nota sin texto no tiene vector
    assert res == {"indexed": 1, "skipped": 1} and set(idx.load()) == {"a/uno"}
