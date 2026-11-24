"""Tests del core de curiosidad (app/obsidian/curiosity.py, Etapa C). `find_gaps` puro."""

from app.obsidian.curiosity import find_gaps


def test_detecta_notas_faltantes_ordenadas():
    notes = [
        {"id": "a", "title": "A", "links": ["Falta", "B"]},
        {"id": "b", "title": "B", "links": ["Falta"]},   # "Falta" citada por 2 -> hueco importante
        {"id": "c", "title": "C", "links": ["B"]},
    ]
    g = find_gaps(notes)
    faltan = {f["titulo"]: f["citada_por"] for f in g["faltantes"]}
    assert faltan == {"falta": 2}                 # "Falta" no existe como nota, la piden 2
    assert g["faltantes"][0]["titulo"] == "falta"  # ordenado por más pedido


def test_detecta_huerfanas():
    notes = [
        {"id": "a", "title": "A", "links": ["B"]},   # A enlaza a B; nadie enlaza a A -> A huérfana
        {"id": "b", "title": "B", "links": []},       # B recibe de A -> no huérfana
    ]
    g = find_gaps(notes)
    ids = {h["id"] for h in g["huerfanas"]}
    assert "a" in ids and "b" not in ids


def test_sin_huecos():
    notes = [
        {"id": "a", "title": "A", "links": ["B"]},
        {"id": "b", "title": "B", "links": ["A"]},
    ]
    g = find_gaps(notes)
    assert g["faltantes"] == [] and g["huerfanas"] == []
