# AGENTS.md — Reglas operativas para agentes (DeepSeek Harness, etc.)

> Este archivo lo leen los agentes de codificación (DeepSeek Harness / `dsh`,
> Claude Code, Codex, etc.) al abrir el proyecto. Son **reglas cortas y estándar**;
> el contexto profundo vive en los docs que se enlazan abajo. Si algo acá difiere
> del detalle en `CLAUDE.md`, gana `CLAUDE.md`.
>
> Creado 2026-10-13 para onboardear a **DeepSeek Harness** al proyecto. DSH lee
> `AGENTS.md` y `CLAUDE.md` caminando desde la raíz (marcada por `.git`) hacia abajo.

---

## Qué es esto (en una línea)

**JarvisRemote** — el agente se llama **Raphael**. Nació como auditoría de código /
pentesting manejado por LLM y creció a asistente personal (control de PC/celular,
forense, antimalware, trading, geolocalización pública/OSINT). **Backend Python/
FastAPI** + **tray-app** (PySide/pystray) + **app Android** (Kotlin/Compose).

## Antes de tocar NADA — leé esto primero, en este orden

1. **`ESTADO.md`** (raíz) — en qué se está trabajando ahora, qué quedó a medias,
   próximos pasos. Es lo más actual. **Empezá siempre por acá.**
2. **`CLAUDE.md`** (raíz) — contexto estructural completo: arquitectura, módulos,
   modelos en uso, convenciones, y los gates de seguridad ya decididos.
3. **`backend/app/config.py`** — la fuente más rica de decisiones y bugs reales,
   comentada línea por línea con fecha. **Leela antes de cambiar cualquier default.**
4. **`backend/README.md`** — setup detallado, limitaciones conocidas, notas de
   seguridad, instalación de nmap/ClamAV/etc.

## Reglas que NO se negocian

- **El repo remoto es PÚBLICO** (github.com/damianzupel-commits/JarvisRemote).
  **NUNCA commitees secretos**: `.env` / `.env.*` (salvo `.env.example`), claves,
  `backend/authorized_targets.yaml`, targets de pentest, credenciales, `*.pem/.key`,
  tokens. El `.gitignore` cubre lo obvio — **revisá igual antes de pushear.**
- **No commitees sin que Damian lo pida.** Dejá el trabajo listo y avisá; él decide
  cuándo commitear/pushear.
- **Gates de seguridad ya decididos — no los debilites sin permiso explícito de Damian:**
  - Pentest activo (nmap/sqlmap/ZAP/captura) valida el target contra
    `backend/authorized_targets.yaml`. **Ni las tools ni el LLM escriben ese archivo** —
    solo Damian a mano. Por default solo rangos privados/loopback/Tailscale.
  - Self-repair (`selfrepair/`): proponer fix en dry-run sin gate; **aplicarlo de
    verdad (`confirm=true`) requiere un `proposal_id` que Damian confirma a mano.**
  - Patrón **dry-run → confirm=true** para todo lo destructivo/irreversible
    (cuarentena de malware = mover no borrar; fixes de código; submit de formularios
    con preview obligatorio).
  - Flags para apagar cada capacidad invasiva (`DESKTOP_CONTROL_ENABLED`,
    `PC_SHELL_ENABLED`, `NMAP_ENABLED`, etc.). Por default prendidas a pedido de Damian.
  - Sandbox de FS: `FS_ALLOWED_ROOT` limita las tools de FS.
  - Cualquier capacidad que **gaste plata, use red o cambie comportamiento** va
    **apagada por default** detrás de un flag (`OPS_SUPERVISOR_ENABLED`,
    `PROACTIVE_LEARNING_ENABLED`, `TRADING_WATCH_LOOP_ENABLED`, etc.).
- **No confundir repos:** ESTE proyecto es `C:\Users\dam\Documents\JarvisRemote`.
  `cerebro-fenix/_Jarvis-Local` es un **prototipo VIEJO muerto** (no copiar de ahí).
  `Vault-Fenix` es un vault aparte del que vive en `backend/obsidian_vault/`.

## Modelo de chat/agente (ojo con el nombre)

- Hay **un solo modelo de chat por vez**, definido por **`LMSTUDIO_MODEL` en
  `backend/.env`**. ⚠️ La variable `LMSTUDIO_*` es histórica: **HOY apunta a Ollama
  (puerto 11434), no a LM Studio.** Embeddings van aparte en LM Studio real (:1234).
- Si cambiás de modelo, sincronizá `MODEL_CONTEXT_TOKENS` con el `num_ctx` real
  (hubo bugs reales de "context exceeded").

## Cómo levantar y testear

```powershell
.\install.ps1              # idempotente: detecta hardware, Ollama, modelo, venvs, .env
```
```bash
cd backend && pytest       # 134 tests en backend/tests/
cd ../tray-app && pytest   # la tray tiene los suyos
```
El backend arranca con `cd backend && python run.py` (FastAPI :8000).
Requiere **Windows** (DPAPI, taskkill, pywinauto, Termux link son Windows-específicos).

## Convenciones del repo

- **Commits en español**, estilo Conventional Commits: `feat:` / `fix:` / `chore:` /
  `docs:`. Mensajes descriptivos con el *porqué*; aclarar "bug real" cuando fue
  reproducido, no hipotético.
- **`git config core.autocrlf = input`** — line endings LF. Respetalo.
- **Comentarios extensos y con fecha**: `config.py` documenta cada decisión y bug.
  Es la memoria del proyecto — **leelo antes de cambiar defaults, no lo borres.**

## Layout

```
backend/     Python + FastAPI — el cerebro: loop del agente (agent.py) + ~39 tools (tools/)
tray-app/    PySide/pystray — ventana de escritorio, administra el backend, selector de modelo
android-app/ Kotlin/Compose — app del celular, se conecta por WebSocket
install.ps1  instalador idempotente
docs/        specs, arquitectura, paneles HTML de Raphael (docs/raphael/)
```

## Cómo trabajar acá (tono)

Filosofía recurrente del código: **acciones reales sobre la PC, no simuladas**;
**flags para apagar cada capacidad invasiva sin tocar código**; **"sin fricción"
por default** a pedido de Damian, pero **con gate donde el daño sería irreversible**.
Cuando toques un gate, un default o algo destructivo: leé el comentario con fecha
que lo justifica, y si no existe, pedí confirmación antes de cambiarlo.
