import pytest

from raphael_geolocalizacion import validar


@pytest.mark.parametrize("lat,lon,esperado", [
    (-32.95, -60.64, (-32.95, -60.64)), ("10", "20", (10.0, 20.0)), (0, 0, None), (91, 0, None), (0, 181, None),
    (None, 3, None), ("x", "y", None), (-32.123456789, -60.0, (-32.12346, -60.0))])
def test_coordenadas(lat, lon, esperado):
    assert validar.coordenadas(lat, lon) == esperado


@pytest.mark.parametrize("texto", ["10.0.0.1", "192.168.1.5", "127.0.0.1", "169.254.1.1", "::1", "fe80::1", "0.0.0.0"])
def test_ips_privadas_no_se_geolocalizan(texto):
    objetivo, motivo = validar.objetivo_ip(texto)
    assert objetivo is None and "privada o reservada" in motivo


@pytest.mark.parametrize("texto,esperado", [("8.8.8.8", "8.8.8.8"), ("  8.8.8.8. ", "8.8.8.8"), ("Google.com", "google.com"),
                                            ("https://example.org/ruta", "example.org"),
                                            ("2001:4860:4860::8888", "2001:4860:4860::8888")])
def test_objetivos_validos(texto, esperado):
    assert validar.objetivo_ip(texto) == (esperado, "")


@pytest.mark.parametrize("texto", ["", "   ", "hola", "localhost", "999.1.1.1", "a b.com"])
def test_objetivos_invalidos(texto):
    assert validar.objetivo_ip(texto)[0] is None


def test_direcciones_cripto():
    eth = "0x" + "ab" * 20
    assert validar.direccion_cripto(eth) == (eth, "ethereum")
    assert validar.direccion_cripto("1BoatSLRHtKNngkdXEeobR76b53LETtpyT") == ("1BoatSLRHtKNngkdXEeobR76b53LETtpyT", "bitcoin")
    assert validar.direccion_cripto("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")[1] == "bitcoin"
    assert validar.direccion_cripto("0x123") == (None, None)


def test_limpiar_texto_de_terceros():
    sucio = "Noticia\x00\x1b[31m  con\n\nsaltos\t" + "x" * 500
    out = validar.limpiar(sucio, 50)
    assert "\x00" not in out and "\x1b" not in out and "\n" not in out and len(out) <= 50
