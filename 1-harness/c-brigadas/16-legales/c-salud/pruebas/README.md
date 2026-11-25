# Legales · pruebas
54 tests, todos sin red y sin claves (fuentes simuladas, modelo falso).
- `test_gate.py`: suite de contrato en `personal` y `cloud`, ningún import ajeno, toda acción declarada con su nivel, nada que firme/envíe.
- `test_documents.py`: plantillas, `[COMPLETAR]`, versiones, emisión con aprobación, consentimientos y bajas, borrado.
- `test_compliance.py`: checklist, verificación de fuentes (cae, cambia, vence, `off`), tick diario, config y salud.
- `test_risks.py`: reglas, veredicto, evento de otra brigada, segunda lectura con modelo, texto hostil como dato.
Correr: `python -m pytest` desde esta carpeta. Falta sumar la suite `legales` a `3-mando/b-herramientas/gate.py` (lo hace el coordinador).
