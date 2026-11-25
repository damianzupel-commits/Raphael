"""Forense: casos, ingesta, entidades, fusiones, retractar, registro encadenado, informe."""

import json

import pytest
from kit import make_env, make_inv

from raphael_investigacion.casefile import CaseError
from raphael_investigacion.service import safe_path

WA = ("[12/08/2026, 14:30] Ana Pérez: hola, mi mail es ana@ejemplo.com\n"
      "[12/08/2026, 14:35] Beto: pasame la IP 10.1.2.3\ncontinúa en otra línea\n"
      "[15/08/2026, 09:00] Ana Pérez: https://sitio.ejemplo.org/x\n")
APACHE = ('1.2.3.4 - - [12/Aug/2026:14:30:00 +0000] "GET /admin HTTP/1.1" 403 12\n'
          '1.2.3.4 - - [12/Aug/2026:14:31:00 +0000] "GET /login HTTP/1.1" 200 99\n')
SSH = ("Aug 12 14:30:00 srv sshd[1]: Failed password for root from 9.9.9.9 port 22 ssh2\n"
       "Aug 12 14:31:00 srv sshd[1]: Accepted password for admin from 9.9.9.9 port 22 ssh2\n")


def case(inv):
    return inv.cases.create("Caso Prueba", "x")["id"]


def test_crear_caso_id_estable_y_unico():
    inv = make_inv()
    assert inv.cases.create("Mi Caso ñandú")["id"] == "mi-caso-nandu"
    assert inv.cases.create("Mi Caso ñandú")["id"] == "mi-caso-nandu-2"
    with pytest.raises(CaseError):
        inv.cases.create("  ")


def test_whatsapp_ingesta_idempotente_y_multilinea():
    inv = make_inv()
    c = case(inv)
    r = inv.ingestor.ingest_bytes(c, "chat.txt", WA.encode())
    assert r["kind"] == "whatsapp" and r["nodes_new"] > 0
    ev = inv.cases.nodes(c, tipo="Evento")
    assert len(ev) == 3 and any("continúa en otra línea" in e["campos"]["descripcion"] for e in ev)
    again = inv.ingestor.ingest_bytes(c, "chat.txt", WA.encode())
    assert again["already"] and again["nodes_new"] == 0
    assert len(inv.cases.nodes(c, tipo="Evento")) == 3


def test_telegram_cuenta_por_id():
    inv = make_inv()
    c = case(inv)
    doc = {"id": 77, "messages": [{"type": "message", "date": "2026-08-12T10:00:00", "from": "Ana", "from_id": "user1",
                                   "text": ["hola ", {"text": "mundo"}]}, {"type": "service", "date": "x"}]}
    inv.ingestor.ingest_bytes(c, "result.json", json.dumps(doc).encode())
    assert [n["campos"]["handle"] for n in inv.cases.nodes(c, tipo="Cuenta")] == ["user1"]
    assert "hola mundo" in inv.cases.nodes(c, tipo="Evento")[0]["campos"]["descripcion"]


def test_json_que_no_es_telegram_se_rechaza():
    inv = make_inv()
    with pytest.raises(CaseError, match="Telegram"):
        inv.ingestor.ingest_bytes(case(inv), "x.json", b'{"a": 1}')


def test_logs_de_servidor():
    inv = make_inv()
    c = case(inv)
    assert inv.ingestor.ingest_bytes(c, "access.log", APACHE.encode())["kind"] == "log-web"
    r = inv.ingestor.ingest_bytes(c, "auth.log", SSH.encode())
    assert r["kind"] == "log-ssh" and any("año" in w for w in r["warnings"])
    assert {n["campos"]["ip_o_dominio"] for n in inv.cases.nodes(c, tipo="Host")} == {"1.2.3.4", "9.9.9.9"}


def test_csv_transacciones_eventos_y_sin_adivinar():
    inv = make_inv()
    c = case(inv)
    inv.ingestor.ingest_bytes(c, "mov.csv", b"fecha;monto;contraparte\n12/08/2026;1.500,50;Beto\n13/08/2026;abc;Ana\n")
    tx = inv.cases.nodes(c, tipo="Transacción")
    assert len(tx) == 1 and tx[0]["campos"]["monto"] == 1500.5
    with pytest.raises(CaseError, match="mapeo"):
        inv.ingestor.ingest_bytes(c, "raro.csv", b"a,b\n1,2\n")
    inv.ingestor.ingest_bytes(c, "raro2.csv", b"a,b\n12/08/2026,algo\n", mapping={"tipo": "Evento",
                              "columns": {"timestamp": "a", "descripcion": "b"}})
    assert len(inv.cases.nodes(c, tipo="Evento")) == 1


def test_texto_y_deteccion():
    inv = make_inv()
    c = case(inv)
    r = inv.ingestor.ingest_bytes(c, "nota.txt", b"contacto: ana@ejemplo.com, IP 8.8.8.8, 999.1.1.1")
    assert r["kind"] == "texto" and r["chars"] > 0
    with pytest.raises(CaseError, match="no sé qué es"):
        inv.ingestor.ingest_bytes(c, "x.xyz", b"data")


def test_extraccion_por_reglas_propone_y_no_confirma():
    inv = make_inv()
    c = case(inv)
    sha = inv.ingestor.ingest_bytes(c, "nota.txt", b"mail ana@ejemplo.com, IP 8.8.8.8, 999.1.1.1, https://x.ejemplo.org/p, "
                                    b"CUIT 30-71234567-1 y 20-12345678-6")["sha256"]
    r = inv.entities.extract(c, sha)
    tipos = sorted((p["node"]["tipo"], p["node"]["campos"].get("handle") or p["node"]["campos"].get("ip_o_dominio")) for p in r["created"])
    assert ("Cuenta", "ana@ejemplo.com") in tipos and ("Host", "8.8.8.8") in tipos and ("Host", "x.ejemplo.org") in tipos
    assert not any(t[1] == "999.1.1.1" for t in tipos)
    assert not inv.cases.nodes(c, tipo="Cuenta")                       # nada entró solo
    pid = r["created"][0]["id"]
    inv.entities.confirm(c, pid)
    assert len(inv.cases.nodes(c, tipo=r["created"][0]["node"]["tipo"])) >= 1
    with pytest.raises(CaseError, match="ya está"):
        inv.entities.confirm(c, pid)


def test_propuesta_exige_artefacto_y_descarta_invalidos():
    inv = make_inv()
    c = case(inv)
    with pytest.raises(CaseError):
        inv.entities.propose(c, "0" * 64, [])
    sha = inv.ingestor.ingest_bytes(c, "n.txt", b"hola")["sha256"]
    r = inv.entities.propose(c, sha, [{"tipo": "Archivo", "campos": {}}, {"tipo": "Persona", "campos": {"etiqueta": "x"}},
                                      {"tipo": "Persona", "campos": {"etiqueta": "Ana", "alias": [], "confianza": 0.4},
                                       "confianza_extraccion": 0.7, "texto_fuente": "Ana"}])
    assert len(r["created"]) == 1 and len(r["discarded"]) == 2
    assert "Archivo" in r["discarded"][0]["motivo"]


def test_fusion_no_combina_nodos_y_se_puede_retractar():
    inv = make_inv()
    c = case(inv)
    sha = inv.ingestor.ingest_bytes(c, "n.txt", b"x")["sha256"]
    ids = []
    for et in ("Ana Pérez", "ana perez"):
        r = inv.entities.propose(c, sha, [{"tipo": "Persona", "campos": {"etiqueta": et, "alias": [et], "confianza": 0.5}}])
        ids.append(inv.entities.confirm(c, r["created"][0]["id"])["node_id"])
    sug = inv.entities.suggest_fusions(c)
    assert len(sug) == 1 and sug[0]["status"] == "pendiente"
    f = inv.entities.confirm_fusion(c, sug[0]["id"])
    assert len(inv.cases.nodes(c, tipo="Persona")) == 2                # los dos siguen
    assert any(e["tipo"] == "mismo_que" for e in inv.cases.edges(c))
    inv.cases.retract(c, "arista", f["edge"], "eran homónimos")
    assert not any(e["tipo"] == "mismo_que" for e in inv.cases.edges(c))
    assert inv.cases.edges(c, retracted=True)
    with pytest.raises(CaseError, match="motivo"):
        inv.cases.retract(c, "nodo", ids[0], "")


def test_no_se_retracta_un_artefacto():
    inv = make_inv()
    c = case(inv)
    art = inv.cases.add_artifact(c, "a.txt", b"hola")
    with pytest.raises(CaseError, match="artefacto"):
        inv.cases.retract(c, "nodo", art["node"], "no me gusta")


def test_registro_detecta_manipulacion():
    inv = make_inv(environ={"INVESTIGACION_LOG_KEY": "k"})
    c = case(inv)
    inv.ingestor.ingest_bytes(c, "n.txt", b"hola")
    v = inv.cases.verify_log(c)
    assert v["ok"] and v["signed"] == v["entries"] >= 3
    key = f"{c}:00000002"
    e = inv.cases.s.get("log", key)
    e["payload"] = {"name": "otra cosa"}
    inv.cases.s.put("log", key, e)
    assert not inv.cases.verify_log(c)["ok"]


def test_firma_invalida_se_detecta():
    inv = make_inv(environ={"INVESTIGACION_LOG_KEY": "k"})
    c = case(inv)
    inv.cases.env.environ = {"INVESTIGACION_LOG_KEY": "otra"}
    assert "firma" in inv.cases.verify_log(c)["problem"]


def test_copia_y_verificacion_del_artefacto(tmp_path):
    inv = make_inv({"artifacts_dir": str(tmp_path)})
    c = case(inv)
    sha = inv.cases.add_artifact(c, "a.txt", b"hola")["sha256"]
    assert inv.cases.verify_artifact(c, sha)["ok"] is True
    (tmp_path / c / sha).write_bytes(b"alterado")
    assert inv.cases.verify_artifact(c, sha)["ok"] is False


def test_linea_de_tiempo_y_grafo():
    inv = make_inv()
    c = case(inv)
    inv.ingestor.ingest_bytes(c, "chat.txt", WA.encode())
    tl = inv.reports.timeline(c)
    assert [e["at"][:10] for e in tl["events"]] == ["2026-08-12", "2026-08-12", "2026-08-15"]
    assert tl["gaps"] and tl["gaps"][0]["hours"] > 24
    g = inv.reports.graph(c)
    assert g["components"] == 1 and g["top_degree"]


def test_informe_separa_confirmado_de_pendiente(tmp_path):
    inv = make_inv({"reports_dir": str(tmp_path)})
    c = case(inv)
    sha = inv.ingestor.ingest_bytes(c, "n.txt", b"mail ana@ejemplo.com")["sha256"]
    inv.entities.extract(c, sha)
    md = inv.reports.render(c)
    assert "Pendiente de confirmación (NO verificado)" in md and "ana@ejemplo.com" in md and sha in md
    assert "## Entidades confirmadas\n\n_Ninguna._" in md
    out = inv.reports.export(c, "html")
    assert out["path"].endswith(".html") and "<h1>" in open(out["path"], encoding="utf-8").read()
    inv3 = make_inv()
    assert "aviso" in inv3.reports.export(case(inv3), "md")
    with pytest.raises(CaseError):
        inv.reports.render(c, "pdf")


def test_extraer_con_modelo_valida_y_sin_modelo_avisa():
    ask = lambda part, msgs: json.dumps([{"tipo": "Persona", "campos": {"etiqueta": "Beto", "alias": [], "confianza": 0.5},  # noqa: E731
                                          "texto_fuente": "Beto", "confianza_extraccion": 0.8}, {"tipo": "Archivo"}])
    inv = make_inv(ask=ask)
    c = case(inv)
    sha = inv.ingestor.ingest_bytes(c, "n.txt", b"Beto dijo hola")["sha256"]
    r = inv.entities.extract_with_model(c, sha)
    assert len(r["created"]) == 1 and r["created"][0]["origen"] == "modelo" and len(r["discarded"]) == 1
    inv2 = make_inv(ask=lambda p, m: None)
    c2 = case(inv2)
    sha2 = inv2.ingestor.ingest_bytes(c2, "n.txt", b"hola")["sha256"]
    assert "no se manda a la nube" in inv2.entities.extract_with_model(c2, sha2)["aviso"]


def test_safe_path_bloquea_claves_y_fuera_de_la_carpeta(tmp_path):
    (tmp_path / "ok.txt").write_text("x")
    (tmp_path / ".env").write_text("K=1")
    assert safe_path(str(tmp_path / "ok.txt"), str(tmp_path))
    with pytest.raises(CaseError, match="credenciales"):
        safe_path(str(tmp_path / ".env"), str(tmp_path))
    with pytest.raises(CaseError, match="carpeta de evidencia"):
        safe_path("/etc/hostname", str(tmp_path))


def test_tool_ingerir_exige_inbox(tmp_path):
    (tmp_path / "a.txt").write_text("hola")
    inv = make_inv()
    t = inv.tools()
    c = t["caso_crear"](title="X")["id"]
    assert "inbox_dir" in t["ingerir_artefacto"](case=c, path=str(tmp_path / "a.txt"))["error"]
    inv2 = make_inv({"inbox_dir": str(tmp_path)})
    c2 = inv2.tools()["caso_crear"](title="X")["id"]
    assert inv2.tools()["ingerir_artefacto"](case=c2, path=str(tmp_path / "a.txt"))["kind"] == "texto"
    assert "error" in inv2.tools()["caso_resumen"](case="no-existe")


def test_eventos_publicados():
    ev: list = []
    inv = make_inv(events=ev)
    c = case(inv)
    inv.ingestor.ingest_bytes(c, "n.txt", b"hola")
    assert [n for n, _ in ev][:2] == ["caso.creado", "caso.actualizado"]


def test_env_defecto():
    assert make_env().config.is_private()
