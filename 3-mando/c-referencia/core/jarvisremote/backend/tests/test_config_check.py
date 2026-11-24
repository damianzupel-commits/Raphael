"""Tests de E4 (brigada): chequeo determinista de configuración.

No usan LLM ni red -- arman un proyecto de prueba en un tmp_path y verifican
que `scan_config` encuentra los riesgos de config y NO grita por lo que está bien.
"""

from __future__ import annotations

from app.security.config_check import scan_config


def _rules(findings):
    return {f.rule_id for f in findings}


def test_detecta_riesgos_de_config_django(tmp_path):
    (tmp_path / "settings.py").write_text(
        "DEBUG = True\n"
        "ALLOWED_HOSTS = ['*']\n"
        "SECRET_KEY = 'django-insecure-averylongsecretkey123'\n",
        encoding="utf-8",
    )
    findings = scan_config(tmp_path)
    rules = _rules(findings)
    assert "CFG001-debug-true" in rules
    assert "CFG002-allowed-hosts-wildcard" in rules
    assert "CFG003-hardcoded-secret-key" in rules
    # todos con archivo:línea reales
    debug = next(f for f in findings if f.rule_id == "CFG001-debug-true")
    assert debug.file == "settings.py"
    assert debug.line == 1
    assert debug.severity == "high"
    assert debug.triage_status == "real"  # no lo manda a triage


def test_detecta_riesgos_de_config_flask(tmp_path):
    (tmp_path / "app.py").write_text(
        "app.secret_key = 'F12Zr47superclave'\n"
        "app.config['SECRET_KEY'] = 'otraclave123'\n"
        "if __name__ == '__main__':\n"
        "    app.run(debug=True, host='0.0.0.0')\n",
        encoding="utf-8",
    )
    findings = scan_config(tmp_path)
    rules = _rules(findings)
    assert "CFG003-hardcoded-secret-key" in rules
    assert "CFG004-flask-run-debug" in rules


def test_no_grita_por_config_correcta(tmp_path):
    # Config bien hecha: nada hardcodeado, DEBUG desde entorno.
    (tmp_path / "settings.py").write_text(
        "import os\n"
        "DEBUG = os.environ.get('DEBUG') == '1'\n"
        "ALLOWED_HOSTS = os.environ.get('HOSTS', '').split(',')\n"
        "SECRET_KEY = os.environ['SECRET_KEY']\n",
        encoding="utf-8",
    )
    findings = scan_config(tmp_path)
    assert findings == []


def test_archivo_sensible_flaggeado(tmp_path):
    (tmp_path / ".env").write_text("SECRET=abc\n", encoding="utf-8")
    (tmp_path / "db.sqlite3").write_bytes(b"SQLite format 3\x00")
    findings = scan_config(tmp_path)
    rules = _rules(findings)
    assert "CFG010-env-file" in rules
    assert "CFG011-database" in rules


def test_gitignore_evita_falso_positivo(tmp_path):
    # Si el .db está gitignoreado, NO se reporta (no está commiteado).
    (tmp_path / ".gitignore").write_text("*.sqlite3\n.env\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=abc\n", encoding="utf-8")
    (tmp_path / "db.sqlite3").write_bytes(b"SQLite format 3\x00")
    findings = scan_config(tmp_path)
    rules = _rules(findings)
    assert "CFG011-database" not in rules
    assert "CFG010-env-file" not in rules


def test_salta_dependencias(tmp_path):
    # Un DEBUG=True dentro de node_modules/ NO cuenta (dependencia de terceros).
    dep = tmp_path / "node_modules" / "pkg"
    dep.mkdir(parents=True)
    (dep / "settings.py").write_text("DEBUG = True\n", encoding="utf-8")
    findings = scan_config(tmp_path)
    assert findings == []


def test_debug_false_no_matchea(tmp_path):
    (tmp_path / "settings.py").write_text("DEBUG = False\n", encoding="utf-8")
    findings = scan_config(tmp_path)
    assert findings == []


def test_dockerfile_db_no_es_base(tmp_path):
    # 'Dockerfile.db' matchea *.db pero NO es una base SQLite -> no se reporta.
    (tmp_path / "Dockerfile.db").write_text("FROM postgres\n", encoding="utf-8")
    assert "CFG011-database" not in _rules(scan_config(tmp_path))


def test_env_example_es_template(tmp_path):
    # '.env.example' es un template que se commitea a propósito -> no se reporta.
    (tmp_path / ".env.example").write_text("SECRET=changeme\n", encoding="utf-8")
    assert "CFG010-env-file" not in _rules(scan_config(tmp_path))


def test_sqlite_real_si_se_reporta(tmp_path):
    (tmp_path / "db.sqlite3").write_bytes(b"SQLite format 3\x00resto")
    assert "CFG011-database" in _rules(scan_config(tmp_path))
