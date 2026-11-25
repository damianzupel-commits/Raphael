# Operaciones · b-codigo
El código de la brigada para el harness v2 (paquete `raphael-operaciones`, `src/raphael_operaciones/`). Solo edición personal: nunca en el VPS.

## Qué hay
| Módulo | Qué hace |
|---|---|
| `manifest.yaml` (en `src/raphael_operaciones/`; copia en esta carpeta con `scripts/sync_manifest.py`) | 4 cocineros, 7 acciones y 39 tools, cada una con su nivel. Lo que lee dentro del sandbox o de la web es `automatico`; lo que actúa pide `aprobacion` y casi todo es `irreversible` (nunca baja solo a automático) |
| `config.py` | Config de la brigada > variable `OPERACIONES_*` > default seguro. Un valor inválido corta el montaje con un mensaje claro |
| `service.py` | `Operations`: un solo camino al mundo real (interruptor → guardarraíl → sandbox → supervisor → adaptador). Las tools y los cocineros llaman a los mismos métodos |
| `guardrails.py`, `fs.py`, `modes.py` | Patrones destructivos, sandbox de archivos (raíces por modo, prohibidas, borrado apagado) y modo supervisado/autónomo con defensa anti auto-escalada |
| `adapters/` | Cada uno con versión **real** y **simulada**: `shell`, `desktop` (pyautogui/pywinauto), `phone` (enlace WebSocket), `browser` (Playwright), `web` (urllib; Scrapling opcional), `credentials` |
| `webreader.py` | `web_get`: escalado de pisos, caché versionada, deny-list y guarda de red local |
| `spec.py` | Jefe y 3 efímeros (pc, celular, navegador), todos `private=True`: solo modelo local |
| `cooks/` | `pc`, `phone`, `browser-web`, `supervisor`; entienden órdenes explícitas por reglas (sin modelo) y solo de Damián |
| `setup.py`, `health.py`, `registry.py` | Registro de tools al montar, healthcheck y el servicio compartido |

## Probar
```bash
python -m pytest ../c-salud/pruebas      # 96 tests, sin red y con adaptadores simulados
ruff check .
```

## Pasar de simulado a real
Por defecto todo corre **simulado** (no toca nada). `operaciones.env.plantilla` lista cada interruptor; los pasos para Damián están en `3-mando/a-conocimiento/LIENZO-DAMIAN.md`. Aun en real, cada interruptor de riesgo (shell PC, escritorio, shell y cámara del celular, borrar) viene apagado y todo lo que actúa pide aprobación.

## Para el servidor (pieza 3)
El celular se conecta al servidor por WebSocket. El endpoint (y el emparejamiento por QR) son del servidor; la brigada solo espera esto:
```python
from raphael_operaciones.adapters.phone import link
await link.register(ws)            # al conectarse el celular (ws con send_text)
await link.handle_incoming(msg)    # por cada mensaje que manda el celular
await link.unregister(ws)          # al desconectarse
```

## Qué NO se portó, a propósito
`web_credential_save` (la contraseña pasaba por el modelo): las credenciales se cargan en variables `OPERACIONES_CRED_*`. El gancho de `fs_write_file` con `codeedit` (es de Autorreparación). El emparejamiento por QR (servidor).
