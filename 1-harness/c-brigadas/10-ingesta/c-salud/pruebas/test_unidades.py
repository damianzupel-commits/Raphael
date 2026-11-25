"""Las piezas sueltas y los adaptadores reales (con transportes falsos: la nube no tiene red de salida)."""

from __future__ import annotations

import sys
import types
from datetime import datetime

import pytest
from raphael_core import Health

from raphael_ingesta import health
from raphael_ingesta.adapters import make, mock
from raphael_ingesta.adapters import youtube as yt
from raphael_ingesta.adapters.arxiv import RealArxiv, arxiv_id_of, parse_atom
from raphael_ingesta.adapters.web import RealWeb, web_id
from raphael_ingesta.config import settings_of
from raphael_ingesta.model import Item, NoContent, SourceError
from raphael_ingesta.safeurl import validate_public_url
from raphael_ingesta.summary import by_rules, normalize_verdict, parse
from raphael_ingesta.text import html_to_text, one_line, parse_vtt
from raphael_ingesta.vault import FileVault, build_note, slug


def _dns(ip):
    return lambda host, port, **kw: [(2, 1, 6, "", (ip, port))]


# --- direcciones públicas ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "172.16.0.9", "::1", "0.0.0.0", "100.64.0.1"]
)
def test_rechaza_redes_privadas_y_locales(ip):
    with pytest.raises(SourceError, match="privada"):
        validate_public_url("https://sitio.example/x", resolve=_dns(ip))


@pytest.mark.parametrize(
    "url", ["ftp://a.com/x", "file:///etc/passwd", "javascript:alert(1)", "https://usuario:clave@a.com/", "https:///x", ""]
)
def test_rechaza_esquemas_raros_y_credenciales(url):
    with pytest.raises(SourceError):
        validate_public_url(url, resolve=_dns("93.184.216.34"))


def test_acepta_un_sitio_publico():
    assert validate_public_url("https://ejemplo.org/a?b=1", resolve=_dns("93.184.216.34")) == "https://ejemplo.org/a?b=1"


# --- texto ------------------------------------------------------------------------------------------------------------
def test_html_a_texto_saca_scripts_menus_y_toma_el_titulo():
    html = (
        "<html><head><title> Mi  guía </title><meta property='og:title' content='Guía OG'></head><body><nav>menú</nav>"
        "<script>alert(1)</script><h1>Hola</h1><p>Primer párrafo &amp; más.</p><div>Otro</div><footer>pie</footer></body></html>"
    )
    title, body, meta = html_to_text(html)
    assert title == "Mi guía" and meta["og:title"] == "Guía OG"
    assert body.splitlines() == ["Hola", "Primer párrafo & más.", "Otro"]


def test_vtt_a_texto_colapsa_lo_repetido():
    raw = (
        "WEBVTT\nKind: captions\nLanguage: es\n\n1\n00:00:00.000 --> 00:00:02.000\nHola <c>mundo</c>\n\n"
        "2\n00:00:01.000 --> 00:00:03.000\nHola mundo\nsegunda línea\n"
    )
    assert parse_vtt(raw) == "Hola mundo segunda línea"


def test_one_line_neutraliza_enlaces_y_controles():
    assert one_line("a [[b]]\n\x00c   d") == "a [ [b] ] c d"


# --- resumen ----------------------------------------------------------------------------------------------------------
ITEM = Item("youtube", "abc", "Título", "https://y/abc", "Una oración. Otra oración larga sobre agentes. " * 5)


def test_parse_tolera_fences_y_rechaza_lo_inutilizable():
    raw = '```json\n{"summary": "ok", "relevance": {"verdict": "util", "score": "9"}}\n```'
    s = parse(raw, ITEM)
    assert s.summary == "ok" and s.verdict == "útil" and s.score == 5 and s.title == "Título" and s.category == "general"
    assert parse("nada", ITEM) is None and parse('{"title": "x"}', ITEM) is None and parse("[1]", ITEM) is None


def test_veredictos():
    assert normalize_verdict("No-útil", 4) == "no útil" and normalize_verdict("raro", 1) == "no útil"
    assert normalize_verdict("raro", 3) == "dudoso" and normalize_verdict("raro", 5) == "útil"


def test_resumen_por_reglas_no_inventa():
    s = by_rules(ITEM)
    assert (
        s.by == "reglas"
        and s.verdict == ""
        and "agentes" in s.summary
        and by_rules(Item("web", "x", "T", "u")).summary.startswith("(sin texto")
    )


# --- vault ------------------------------------------------------------------------------------------------------------
def test_el_vault_nunca_sale_de_su_carpeta(tmp_path):
    v = FileVault(tmp_path / "vault")
    item = Item("web", "../../../etc/passwd", "t", "https://x")
    p = v.path_for(item, "../../../../tmp/malo")
    assert p.is_relative_to((tmp_path / "vault").resolve())
    assert slug("../../a b/ñandú") == "a-b-nandu"
    assert v.delete(str(tmp_path / "fuera.md")) is False


def test_la_nota_siempre_trae_origen_y_fecha():
    from raphael_ingesta.summary import Summary

    text = build_note(
        Item("arxiv", "2401.1", "T", "https://arxiv.org/abs/2401.1", authors=["A"]),
        Summary("T", summary="s"),
        datetime(2026, 11, 25, 9, 30),
    )
    assert "origen: https://arxiv.org/abs/2401.1" in text and "- Origen: https://arxiv.org/abs/2401.1" in text
    assert "fecha_ingesta: 2026-11-25T09:30:00" in text and "- Fecha de ingesta: 2026-11-25" in text


# --- adaptadores reales con transportes falsos -------------------------------------------------------------------------
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>http://arxiv.org/abs/2401.12345v2</id><published>2024-01-22T10:00:00Z</published><title>Un  título
 largo</title><summary> Abstract   con espacios. </summary><author><name>Ana</name></author>
<author><name>Beto</name></author></entry>
<entry><id>http://arxiv.org/abs/hep-th/9901001v1</id><title>Viejo</title><summary>x</summary></entry>
<entry><title>sin id</title></entry></feed>"""


def test_parse_atom():
    [a, b] = parse_atom(ATOM)
    assert a.source_id == "2401.12345" and a.item.title == "Un título largo" and a.item.text == "Abstract con espacios."
    assert (
        a.item.authors == ["Ana", "Beto"]
        and a.item.published == "2024-01-22"
        and a.item.url == "https://arxiv.org/abs/2401.12345"
    )
    assert b.source_id == "hep-th/9901001" and parse_atom("no es xml") == []


def test_ids_de_arxiv():
    assert arxiv_id_of("https://arxiv.org/pdf/2401.12345v3") == "2401.12345" and arxiv_id_of("arXiv:2401.12345") == "2401.12345"
    assert arxiv_id_of("2401.12345v2") == "2401.12345" and arxiv_id_of("hola") is None


def test_arxiv_real_arma_la_consulta_y_levanta_errores_claros():
    seen = []
    api = RealArxiv(get=lambda url: seen.append(url) or ATOM)
    assert len(api.search("cat:cs.AI", 500)) == 2 and "max_results=50" in seen[0] and "sortBy=submittedDate" in seen[0]
    assert api.fetch("2401.12345").title == "Un título largo" and "id_list=2401.12345" in seen[1]
    with pytest.raises(NoContent):
        RealArxiv(get=lambda url: "<feed xmlns='http://www.w3.org/2005/Atom'/>").fetch("2401.99999")


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code, self._body, self.headers, self.encoding = status, body, headers or {}, "utf-8"

    is_redirect = property(lambda self: self.status_code in (301, 302) and "location" in self.headers)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self):
        yield self._body


class FakeClient:
    def __init__(self, routes):
        self.routes, self.asked = routes, []

    def stream(self, method, url):
        self.asked.append(url)
        return self.routes[url]


PAGE = (
    "<html><head><title>Guía</title></head><body><p>" + "Texto de la página con contenido suficiente. " * 6 + "</p></body></html>"
).encode()


def test_web_real_sigue_redirecciones_validando_cada_salto():
    def validate(url):  # el segundo salto apunta adentro: se corta ahí
        if "interno" in url:
            raise SourceError("esa dirección apunta a una red privada o local")
        return url

    ok = FakeClient(
        {
            "https://a.org/1": FakeResponse(302, headers={"location": "/2"}),
            "https://a.org/2": FakeResponse(200, PAGE, {"content-type": "text/html; charset=utf-8"}),
        }
    )
    item = RealWeb(validate=validate, client=ok).fetch("https://a.org/1")
    assert item.url == "https://a.org/2" and item.title == "Guía" and item.source_id == web_id("https://a.org/1")
    evil = FakeClient({"https://a.org/1": FakeResponse(302, headers={"location": "http://interno.local/admin"})})
    with pytest.raises(SourceError, match="privada"):
        RealWeb(validate=validate, client=evil).fetch("https://a.org/1")
    assert evil.asked == ["https://a.org/1"]  # nunca le pidió nada al destino interno


def test_web_real_rechaza_binarios_vacios_y_errores_http():
    w = lambda r: RealWeb(validate=lambda u: u, client=FakeClient({"https://a.org/": r})).fetch("https://a.org/")  # noqa: E731
    with pytest.raises(NoContent, match="no es una página de texto"):
        w(FakeResponse(200, b"%PDF", {"content-type": "application/pdf"}))
    with pytest.raises(NoContent, match="casi no tiene texto"):
        w(FakeResponse(200, b"<html><body>hola</body></html>", {"content-type": "text/html"}))
    with pytest.raises(SourceError) as e:
        w(FakeResponse(503))
    assert e.value.retriable
    with pytest.raises(SourceError) as e:
        w(FakeResponse(404))
    assert not e.value.retriable


def test_youtube_ids_y_listas():
    assert yt.video_id_of("https://youtu.be/dQw4w9WgXcQ?t=3") == "dQw4w9WgXcQ" and yt.video_id_of("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert (
        yt.video_id_of("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1") == "dQw4w9WgXcQ" and yt.video_id_of("hola") is None
    )
    assert yt.is_list_url("https://www.youtube.com/playlist?list=PL1") and yt.is_list_url("https://www.youtube.com/@canal")
    assert not yt.is_list_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1") and not yt.is_list_url(
        "https://youtu.be/dQw4w9WgXcQ"
    )


def test_youtube_elige_la_mejor_pista():
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "man-en"}]},
        "automatic_captions": {
            "es": [{"ext": "json3", "url": "x"}, {"ext": "vtt", "url": "auto-es"}],
            "pt-BR": [{"ext": "vtt", "url": "auto-pt"}],
        },
    }
    assert yt.pick_track(info) == ("en", "man-en")  # manual antes que automática
    del info["subtitles"]
    assert yt.pick_track(info) == ("es", "auto-es")  # es antes que pt, y solo vtt
    assert yt.pick_track({"automatic_captions": {"fr": [{"ext": "vtt", "url": "u"}]}}) is None


class FakeYDL:
    script: list = []
    opened: list = []

    def __init__(self, opts):
        FakeYDL.opened.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        step = FakeYDL.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def urlopen(self, url):
        return types.SimpleNamespace(read=lambda: b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHola desde el video\n")


@pytest.fixture
def fake_ytdlp(monkeypatch):
    FakeYDL.script, FakeYDL.opened = [], []
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYDL))
    return FakeYDL


def test_youtube_real_reintenta_el_429_con_espera_creciente(fake_ytdlp):
    waits = []
    ok = {
        "title": "T",
        "channel": "C",
        "upload_date": "20261101",
        "duration": 125,
        "subtitles": {"es": [{"ext": "vtt", "url": "u"}]},
    }
    fake_ytdlp.script = [RuntimeError("HTTP Error 429: Too Many Requests"), RuntimeError("429"), ok]
    item = yt.RealYouTube(sleep=waits.append).fetch_video("dQw4w9WgXcQ")
    assert waits == [3.0, 6.0] and item.text == "Hola desde el video" and item.published == "2026-11-01"
    assert item.extra == {"duration": "2:05", "lang": "es"} and item.authors == ["C"]


def test_youtube_real_distingue_sin_subtitulos_de_error_tecnico(fake_ytdlp):
    fake_ytdlp.script = [{"title": "T", "subtitles": {}, "automatic_captions": {}}]
    with pytest.raises(NoContent):
        yt.RealYouTube(sleep=lambda s: None).fetch_video("dQw4w9WgXcQ")
    fake_ytdlp.script = [RuntimeError("Sign in to confirm you're not a bot")]
    with pytest.raises(SourceError, match="not a bot") as e:
        yt.RealYouTube(sleep=lambda s: None).fetch_video("dQw4w9WgXcQ")
    assert not isinstance(e.value, NoContent) and not e.value.retriable
    fake_ytdlp.script = [RuntimeError("429")] * 4
    with pytest.raises(SourceError) as e:
        yt.RealYouTube(sleep=lambda s: None).fetch_video("dQw4w9WgXcQ")
    assert e.value.retriable


def test_youtube_real_lista_y_cookies(fake_ytdlp, monkeypatch):
    monkeypatch.setenv("YT_COOKIES_FILE", "/ruta/cookies.txt")
    fake_ytdlp.script = [
        {"entries": [{"id": "dQw4w9WgXcQ", "title": "Uno", "duration": 61, "channel": "C"}, None, {"title": "sin id"}]}
    ]
    [e] = yt.RealYouTube().list_playlist("https://www.youtube.com/playlist?list=PL1")
    assert (e.source_id, e.title, e.duration, e.channel) == ("dQw4w9WgXcQ", "Uno", "1:01", "C")
    assert fake_ytdlp.opened[0]["cookiefile"] == "/ruta/cookies.txt" and fake_ytdlp.opened[0]["extract_flat"] is True


def test_youtube_real_sin_yt_dlp_lo_dice(monkeypatch):
    monkeypatch.setitem(sys.modules, "yt_dlp", None)  # como si no estuviera instalado
    with pytest.raises(SourceError, match="pip install yt-dlp"):
        yt.RealYouTube().list_playlist("https://www.youtube.com/playlist?list=PL1")


def test_la_fabrica_elige_real_o_simulado():
    assert isinstance(make("youtube", "simulado"), mock.MockYouTube) and isinstance(make("web", "real").__class__(), RealWeb)
    assert isinstance(make("arxiv", "real"), RealArxiv) and isinstance(make("youtube", "real"), yt.RealYouTube)


# --- configuración y salud ---------------------------------------------------------------------------------------------
def test_la_configuracion_lee_la_carpeta_del_vault_del_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("RAPHAEL_VAULT_DIR", str(tmp_path))
    assert settings_of({}).vault_dir == str(tmp_path) and settings_of({"vault_dir": "x"}).vault_dir == "x"
    assert settings_of({"modo": "simulado", "modos": {"web": "real"}}).mode_of("web") == "real"


def test_la_salud_solo_da_mal_por_lo_que_rompe(tmp_path, monkeypatch):
    monkeypatch.delenv("RAPHAEL_VAULT_DIR", raising=False)
    ctx = types.SimpleNamespace(config={"modo": "simulado"})
    assert health.check(ctx) == Health(True, "ok (sin RAPHAEL_VAULT_DIR: las notas quedan solo en el almacén de la brigada)")
    assert not health.check(types.SimpleNamespace(config={"modos": {"radio": "real"}})).ok
    assert not health.check(types.SimpleNamespace(config={"modo": "simulado", "por_pasada": 0})).ok
    with pytest.raises(ValueError, match="config de ingesta inválida"):
        health.validate(types.SimpleNamespace(config={"modos": {"web": "inventado"}}))
    assert health.check(types.SimpleNamespace(config={"modo": "real", "vault_dir": str(tmp_path)})).ok


def test_config_invalida_no_monta():
    from kit import BRIGADE_DIR
    from raphael_core import Loader, Runtime
    from raphael_core.installation import installation_from

    inst = installation_from(
        {
            "id": "t",
            "edition": "personal",
            "identity": {"user": "D"},
            "brigades": {"ingesta": {"active": True, "config": {"modo": "inventado"}}},
        }
    )
    rt = Runtime(inst)
    report = rt.run(Loader(rt, [BRIGADE_DIR], installed=False).apply())
    assert report["errors"] and "ingesta" not in rt.brigades
