# Autorreparación · pruebas
106 tests, sin red y sin claves (el modelo es un transporte falso). Se corren con `python -m pytest -q` desde esta carpeta; `conftest.py` arma las rutas al harness. Es la suite `selfrepair` de la puerta.

| Archivo | Qué prueba |
| --- | --- |
| `test_gate.py` | Suite de contrato (personal sí, nube no), imports solo del núcleo, toda acción declarada con nivel, aplicar deja pendiente y no escribe, el orquestador no puede pedir escrituras, la confianza progresiva no baja `aplicar` a automático |
| `test_guardrail.py` | Líneas rojas: lista protegida/libre, `..`, symlinks, fuera de la raíz, mayúsculas y barras, y que vale también al aplicar |
| `test_fixer.py` | Reemplazo único, binario/no UTF-8, CRLF, escritura atómica, commit solo del archivo, verificación |
| `test_propose.py` | Propuestas en seco, sin raíz, `redactar` con y sin modelo (respuestas malas no guardan, `ai_private` no sale a la nube) |
| `test_apply.py` | Camino feliz, rechazo, doble aplicación, huella que no coincide, snippets colados, archivo que cambió, verificación que falla, revertir, git, auditoría |
| `test_introspect.py` | Los tres patrones, hallazgos sin duplicar, tick, reflexiones (nunca se borran), autoconocimiento |
| `test_health.py` | Config inválida no monta; falta de raíz/modelo/verificación son avisos, no salud mala |
