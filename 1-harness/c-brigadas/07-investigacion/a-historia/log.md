# Registro · 07-investigacion · Investigación

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 25 nov 2026 · Portado al harness v2 (hilo "pieza 07")
Resumen de cierre:
- La brigada `investigacion` 2.0.0 quedó montable: 4 cocineros (forense, scout, ideas, tendencias), jefe con 4 efímeros privados, 29 tools, 9 acciones con su nivel y 17 comandos de lectura. Suite de contrato en verde (personal y nube) y 68 tests.
- Se reescribió en vez de copiar línea a línea el código de JarvisRemote: se sacaron `win32crypt`, `llm_client`, `networkx`, `matplotlib` y `fpdf`; casos y grafo viven en el almacén del harness; el registro es hash-encadenado con firma HMAC opcional (antes Ed25519 + DPAPI).
- Decisiones de Damian aplicadas: modelos locales (sin modelo local: reglas y aviso, nada a la nube); claves solo por variable de entorno; adaptadores reales (Brave, SearXNG) y simulado (`mock`).
- No se portó: mapeo de columnas de CSV asistido por modelo (hoy reglas o mapeo explícito), OCR, informe PDF nativo, firma Ed25519.
- Pendiente para otras piezas: ver `para-el-coordinador.md` (modelos.yaml, gate.py, LIENZO). Sin probar contra Brave/SearXNG reales ni con un modelo local real.
