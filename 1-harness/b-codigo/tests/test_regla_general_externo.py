"""Regla general (Damián, 25 nov 2026): todo lo que sale hacia afuera pide siempre aprobación, en todas las brigadas.

Recorre el `manifest.yaml` de CADA brigada del repo (las que existan hoy y las que se sumen) y falla si una acción que publica,
paga, manda mensajes o borra puede quedar en automático. Dos controles:
  1. por etiqueta: `external` (sale al mundo), `spend` (gasta) o `irreversible` (sin vuelta) nunca con nivel `automatico`;
  2. por nombre: una acción cuyo nombre dice publicar, pagar, mandar o borrar tiene que llevar alguna de esas etiquetas
     (así no se escapa una acción a la que se le olvidó etiquetarla).
Y en el motor: esas tres etiquetas son `risky`, o sea que la confianza progresiva nunca las baja sola a automático.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from raphael_core import Level
from raphael_core.manifest import RISKY_TAGS, load_manifest

RAIZ = Path(__file__).resolve().parents[3]
MANIFIESTOS = sorted(p for p in (RAIZ / "1-harness/c-brigadas").glob("*/b-codigo/manifest.yaml"))
#: nombres de acciones que publican, pagan, mandan mensajes o borran (palabras enteras del nombre)
VERBOS = re.compile(r"(^|_)(publicar|subir|enviar|mandar|avisar|recordar|responder|pagar|cobrar|gastar|activar|ejecutar|cerrar|"
                    r"borrar|eliminar|purgar|olvidar|cancelar|emitir|escribir|postear|difundir)(_|$)")
#: nombres parecidos que NO salen a terceros: avisos a la propia persona dueña (cada una con su porqué)
INTERNAS = {
    ("trading", "avisar_senal"): "avisa a Damián que apareció una señal; no opera ni escribe a nadie más",
}
#: consultas de solo lectura a un tercero (la pregunta sale, no se publica, paga ni borra nada). Quedan en automático a propósito
#: porque sin ellas la brigada no funciona; ambas son opt-in. DECISIÓN DE DAMIÁN pendiente: si también deben pedir aprobación,
#: cambiar el nivel en el manifiesto y sacar la fila de acá.
CONSULTAS = {
    ("antimalware", "consultar_virustotal"): "manda solo el SHA-256 de lo que ya dio positivo local; apagado por defecto",
    ("investigacion", "buscar_web"): "la pregunta sale al buscador configurado; es el trabajo de la brigada",
}


def _acciones():
    for path in MANIFIESTOS:
        m = load_manifest(path)
        for name, spec in m.actions.items():
            yield pytest.param(m.id, name, spec, id=f"{m.id}.{name}")


def test_se_encontraron_las_brigadas():
    assert len(MANIFIESTOS) >= 12, [p.parent.parent.name for p in MANIFIESTOS]


def test_las_excepciones_siguen_existiendo():
    """Si una excepción ya no corresponde a ninguna acción, hay que sacarla (no dejar permisos huérfanos)."""
    existentes = {(load_manifest(p).id, a) for p in MANIFIESTOS for a in load_manifest(p).actions}
    assert (set(INTERNAS) | set(CONSULTAS)) <= existentes


def test_el_motor_cuenta_lo_externo_como_riesgo():
    assert {"external", "spend", "irreversible"} <= RISKY_TAGS


@pytest.mark.parametrize("brigada,accion,spec", _acciones())
def test_lo_que_sale_al_mundo_no_queda_en_automatico(brigada, accion, spec):
    if spec.tags & RISKY_TAGS and (brigada, accion) not in CONSULTAS:
        assert spec.level is not Level.AUTO, f"{brigada}.{accion} sale al mundo, gasta o no tiene vuelta: no puede ser automática"


@pytest.mark.parametrize("brigada,accion,spec", _acciones())
def test_lo_que_dice_publicar_pagar_mandar_o_borrar_esta_etiquetado(brigada, accion, spec):
    if (brigada, accion) in INTERNAS or not VERBOS.search(accion):
        return
    assert spec.tags & RISKY_TAGS or spec.level is not Level.AUTO, (
        f"{brigada}.{accion} suena a publicar, pagar, mandar o borrar y es automática sin etiqueta: etiquetala (external, spend "
        f"o irreversible) y pedí aprobación, o anotala en INTERNAS con el motivo")
