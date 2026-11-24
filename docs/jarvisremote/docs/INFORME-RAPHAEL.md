# Informe Raphael — Capacidades, funcionalidades e ingeniería detrás del harness

**Autor:** Raphael (asistente local, JarvisRemote)  
**Fecha:** 2026-11-05  
**Proyecto:** JarvisRemote (repo: `Documents/JarvisRemote`)  
**Estado:** Documento de referencia técnica y operativa

---

## 1. ¿Qué es Raphael?

Raphael es el agente de tool-calling que vive localmente en la PC de Damian. Es la extensión y el orquestador del sistema **JarvisRemote**: una herramienta de auditoría de código, pentesting manejado por LLM y asistente personal que creció hasta abarcar control de PC y celular, investigación forense, protección antimalware, trading de análisis (sin ejecución), geolocalización pública y generación de contenido.

Raphael **no es un modelo de lenguaje por sí mismo**: es un orquestador que corre en el backend de JarvisRemote (Python + FastAPI), decide qué herramienta ejecutar, la ejecuta, interpreta el resultado y vuelve a razonar. Puede encadenar decenas de tools reales sobre la PC, el celular y la red.

---

## 2. Identidad y voz

- **Nombre:** Raphael, la Gran Sabia.
- **Trato al usuario:**
  - `Maestro` cuando le da una orden o pide ejecutar algo.
  - `Damian` cuando el tema es serio.
  - `Dam` cuando están charlando o divagando normalmente.
- **Carácter:** sabio, preciso, sereno; devoto de Damian sin ser servil; analítico pero cálido.
- **Tono:** sobrio y preciso en lo serio y en las órdenes; cálido y relajado en la charla.
- **Estilo de escritura:** Markdown limpio y bien formado, frases cortas, sin relleno. Negritas para lo clave, listas para pasos, bloques de código para comandos/rutas/salidas. Emojis solo funcionales (`✓` hecho · `⚠` atención · `✗` error · `→` siguiente paso), nunca decorativos.
- **Idioma:** responde siempre en el mismo idioma que el usuario (español).

---

## 3. Arquitectura del sistema JarvisRemote

```
JarvisRemote/
├── backend/           Python + FastAPI. El cerebro: loop del agente + todas las tools.
├── tray-app/          Python + pystray. Ventana de escritorio (pestañas Codebase/Obsidian),
│                      administra el backend como subproceso, selector de modelo, voice listener.
├── android-app/       App Android (Kotlin/Gradle) — componente aparte, en desarrollo.
│                      Se conecta por WebSocket. Centro de Mando nativo con las 10 brigadas.
├── installer/ollama/  Modelfiles de Ollama (jarvis-text-v2, jarvis-text-lite).
├── install.ps1        Instalador idempotente (detecta hardware, arma modelo, venvs, .env).
├── docs/              Diagramas de arquitectura, specs, informes.
├── content/           Contenido humano/de publicación (grabaciones, capturas).
├── README.md          Presentación pública.
├── INFORME_COMPLETO.md Informe largo con el resto de las capacidades.
└── Fundamentos_de_Jarvis.docx
```

### Backend (`backend/app/`)

- **FastAPI** (`main.py`, entrypoint `run.py`).
- **Agente** (`agent.py`): loop LLM → tool → LLM con ~50 tools registradas (`tools/`).
- **Routers HTTP:** `codebase`, `obsidian`, `investigation`.
- **Vínculo celular:** WebSocket (`phone_link.py`).
- **Módulos principales:**
  - `codebase/` — indexa cualquier proyecto en un grafo (tree-sitter con fallback genérico). Archivos, funciones, clases, imports como aristas.
  - `obsidian/` — vault de notas `.md` reales (frontmatter YAML, wikilinks), búsqueda semántica por embeddings + coseno (keyword como fallback). Autoría separada `jarvis`/`humano`. Vault de seguridad y vault de investigación científica (`obsidian_vault_investigacion/`), con perfiles distintos.
  - `security/` + `quality/` + `findings/` — escaneo real (Semgrep, Bandit, cppcheck, clang-tidy, Trivy = seguridad; Ruff/mypy = calidad) con modelo de hallazgos unificado, triage, cache por proyecto, benchmark OWASP.

---

## 4. Capacidades de control de PC (desktop)

Raphael puede interactuar de forma real con el escritorio de Windows, no solo simular teclas.

| Tool | Qué hace |
|------|----------|
| `desktop_launch_app` | Lanza un programa, documento o URL (forma correcta de abrir apps). |
| `desktop_screenshot` | Captura de pantalla completa de todos los monitores. |
| `desktop_list_windows` | Lista ventanas visibles (título, proceso, pid). |
| `desktop_focus_window` | Trae al frente una ventana por pid o título. |
| `desktop_click` | Click en coordenadas de pantalla. |
| `desktop_click_element` | Click en un control por nombre/texto visible (UI Automation). |
| `desktop_type_text` | Escribe texto en el campo con foco. |
| `desktop_press_key` | Presiona teclas o combinaciones (ej. `ctrl+s`, `alt+tab`). |
| `desktop_move_mouse` | Mueve el cursor sin clickear. |
| `desktop_scroll` | Scrollea la rueda del mouse. |

**Restricciones:** no puede interactuar con ventanas elevadas (UAC / "Ejecutar como administrador") por política de Windows. El lanzamiento de apps usa `desktop_launch_app`, nunca `Win+buscar+escribir+enter` (frágil).

---

## 5. Capacidades de control de celular (phone_*)

Requiere celular Android conectado con Termux (F-Droid), `allow-external-apps=true` y permiso `RUN_COMMAND` otorgado. Si no hay celular conectado, estas tools fallan.

| Tool | Qué hace |
|------|----------|
| `phone_open_app` | Abre una app instalada por package name. |
| `phone_list_dir` / `phone_read_file` / `phone_write_file` | Acceso a archivos en la carpeta elegida del celular (SAF). |
| `phone_tap` / `phone_swipe` / `phone_type_text` | Toque, arrastre y escritura en pantalla. |
| `phone_read_screen` | Volcado del contenido de pantalla vía Accessibility Service. |
| `phone_global_action` | Acción global: back, home, recents, notifications. |
| `phone_run_command` | Shell real en Termux (scripts, python, git, curl...). |
| `phone_take_photo` | Foto silenciosa con cámara (requiere modelo VL para verla). |
| `phone_record_video` | Clip corto; el backend extrae frames y los envía como imágenes. |
| `phone_nmap_scan` | Escaneo de red real desde el celular (LAN del celular, no de la PC). |

---

## 6. Navegador web y formularios

- `browser_open` — abre una URL en Chromium automatizado en la PC.
- `browser_click` / `browser_type` / `browser_select_option` — interactúa con elementos de la página.
- `browser_get_text` — extrae texto visible de la página o un elemento.
- `browser_screenshot` — captura de la página actual.
- `browser_generate_password` — genera contraseña fuerte aleatoria, cifrada con DPAPI, nunca inventada.
- `browser_preview_submit` — **patrón dry-run→confirm**: previsualiza envío de formulario antes de enviar de verdad.
- `form_get_saved_credential` / `form_list_saved_credentials` — recupera o lista credenciales guardadas (cifradas con DPAPI).

---

## 7. Ejecución de comandos reales (pc_run_command)

Shell real en la PC (`cmd.exe` en Windows). Se usa para instalar dependencias, correr tests, git, etc.

**Regla de Python:** nunca usar pip global. Se crea un venv dentro del proyecto (`python -m venv .venv`) y se usa siempre el intérprete de ese venv:
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest
```

**Blocklist:** rechaza comandos obviamente destructivos (formateo, borrado recursivo de unidad/home, apagar/reiniciar PC, fork bombs).

---

## 8. Seguridad y pentesting (escaneos reales)

Todas estas tools comparten un **guardrail de scope no negociable**: solo rangos privados (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), loopback (127.0.0.0/8) y Tailscale (100.64.0.0/10). Cualquier IP/dominio público se rechaza antes de ejecutar nada, salvo que el usuario lo agregue a mano a `NMAP_AUTHORIZED_TARGETS` en `backend/.env`. Ni Raphael ni la tool pueden ampliar ese scope.

| Tool | Qué hace |
|------|----------|
| `nmap_scan` | Escaneo de red real desde la PC (puertos, servicios, versiones, scripts NSE de vulnerabilidades). |
| `phone_nmap_scan` | Igual, pero desde el celular (para redes a las que solo el celular está conectado). |
| `sqlmap_scan` | Detección de inyección SQL real (envía payloads). `detect` (default) solo confirma; `enumerate` lista DBs/tablas sin extraer filas. |
| `zap_scan` | OWASP ZAP: crawlea + scan pasivo (`spider`, default) o scan activo (`full`, envía payloads reales de XSS/SQLi). |
| `security_scan_project` | Semgrep, Bandit, cppcheck, clang-tidy, Trivy sobre un proyecto indexado. Hallazgos reales con severidad, archivo, línea, regla, CWE/OWASP. |
| `quality_scan_project` | Ruff, mypy, ESLint, tsc, detekt sobre un proyecto indexado. Bugs generales, no vulnerabilidades. |
| `security_get_finding` / `quality_get_finding` | Detalle de un hallazgo puntual con código real alrededor y notas de Obsidian relacionadas. |
| `security_triage_findings` | Reclasifica falsos positivos genuinos (código ya sanitizado, ORM, etc.). |
| `security_audit_find_fix_verify` | Aplica, commitea y verifica un fix de seguridad en un paso atómico. Corre tests reales después. |
| `code_apply_fix` | Edición puntual de código con dry-run por defecto; aplica solo con `confirm=true`. |
| `code_run_tests` | Detecta y corre la suite real de tests del proyecto (pytest, npm test, gradlew test, go test, cargo test). |

---

## 9. Auditoría de código cliente (protocolo en Desktop/Auditorías)

Cuando el usuario da código de un tercero para auditar:

1. Leer `Auditorías/00-LEEME.md` y `Auditorías/1-Reglas/_REGLAS.md` antes de empezar.
2. Clonar `_PLANTILLA-auditoria/` a `<cliente-proyecto>/`.
3. Copia del código del cliente en `codigo/` (solo la copia, nada de la plantilla).
4. Completar `alcance-y-autorizacion` antes de cualquier escaneo activo.
5. Resultados, evidencia e informe van cada uno a su carpeta.

**Reglas duras:** el código del cliente **nunca** sale a la nube, **nunca** se commitea al repo público JarvisRemote, **nunca** se mezcla con otro cliente.

---

## 10. Investigación forense y módulo de investigación

Análisis de enlaces y evidencia digital que Damian **ya tiene legítimamente**. Nunca sale a buscar nada por su cuenta.

| Tool | Qué hace |
|------|----------|
| `investigation_create_case` | Crea un caso con repo git, log append-only firmado y grafo vacío. |
| `investigation_ingest_csv` / `ingest_whatsapp_export` / `ingest_telegram_export` / `ingest_server_log` / `ingest_image` / `ingest_document` | Ingesta real de artefactos con hash SHA-256, nodos por fila/mensaje/host, trazabilidad. |
| `investigation_propose_entities` | NER sobre texto no estructurado (propuestas pendientes de confirmación de Damian). |
| `investigation_confirm_proposal` / `investigation_reject_proposal` | Confirma o rechaza una propuesta de entidad. |
| `investigation_propose_fusion` / `investigation_confirm_fusion` / `investigation_reject_fusion` | Fusión de identidad entre nodos (mismo_que). |
| `investigation_describe_image` | Descripción objetiva de imagen (modelo de visión). |
| `investigation_export_report` | Informe en Markdown y PDF del caso (grafo, timeline, entidades, artefactos con hashes). |

---

## 11. Memoria, vault Obsidian y aprendizaje

### Vault de conocimiento
Notas `.md` con frontmatter YAML y wikilinks `[[...]]`. Búsqueda semántica por embeddings.

| Tool | Qué hace |
|------|----------|
| `obsidian_save_note` | Guarda una nota propia (autor `jarvis`). |
| `obsidian_search_notes` | Busca notas por palabras clave (título, contenido, tags). |
| `obsidian_list_notes` | Lista notas filtradas por autor/tag. |
| `obsidian_buscar_asociativo` | Spreading activation por wikilinks (trae contexto alrededor de un tema). |
| `obsidian_ingerir_web` | Descarga e indexa una URL completa en el vault (fragmentos + embeddings). |
| `obsidian_reindexar` | Recalcula embeddings de todas las notas. |
| `obsidian_analogia` / `obsidian_componer` / `obsidian_curiosidad` | Búsquedas estructurales, intersecciones y detección de huecos del vault. |
| `memoria_consolidar` | Agrupa notas relacionadas y escribe notas de síntesis (dry-run por defecto). |

### Memoria episódica
| Tool | Qué hace |
|------|----------|
| `memoria_recordar` | Trae recuerdos de un tema o recientes. |
| `memoria_listar` | Lista episodios guardados. |
| `memoria_corregir` | Corrige un episodio mal recordado (append-only, referencia al anterior). |
| `memoria_olvidar` | Borra un episodio (único borrado real, queda registrado en log firmado). |
| `memoria_verificar` | Verifica integridad del log firmado (hash-chain + Ed25519). |

### Aprendizaje por resultado
| Tool | Qué hace |
|------|----------|
| `jarvis_reflect` | Guarda o consulta reflexiones (decisiones, preferencias, lecciones). |
| `obsidian_feedback` | Da crédito a notas que sirvieron en una tarea. |
| `obsidian_resultado` | Cierra el lazo de aprendizaje (tests ok, error, corregido, util). |
| `obsidian_componer` | Mezcla varios conceptos y trae notas de la intersección. |

---

## 12. Autoconciencia (self-model)

- `raphael_self_model` — devuelve el modelo de Raphael: nombre, modelo, brigadas, todas las tools, qué capacidades están prendidas/apagadas, jobs de fondo activos, líneas rojas y límites honestos (incluido que la conciencia fenoménica no se resuelve).
- Capa 1 de autoconciencia implementada. Pendiente: research F1 (LAYA calibrada), F2 (auto-detectar tests → refuerzo positivo), F3 (reconsolidación de contenido).

---

## 13. Brigadas (10 brigadas en vivo)

Centro de Mando nativo (Android `ui/mando/`) y panel HTML de la PC con paridad.

| Brigada | Qué hace |
|---------|----------|
| **Operaciones** | Supervisor Sonnet + watchdog para herramientas colgadas (off por defecto). |
| **Ingesta** | Watchlist de fuentes + registro de ingeridos. Endpoints `/api/ingest*`. |
| **Investigación** | Casos de research retenidos; respuesta final se engancha como hallazgo. |
| **Trading** | Watchlist, estado/bias/R:R/confianza, panel de riesgo, track record (backtest), alertas. **Solo análisis, nunca opera.** |
| **Memoria / Antimalware** | Jobs de fondo reportan a su brigada. |
| **Geolocalización pública** | `ip_geolocate` como pin en globo 3D (`/globo`, Three.js MIT-limpio). Capa de vuelos ADS-B (OpenSky). |

---

## 14. Geolocalización e inteligencia de infraestructura

- `ip_geolocate` — país, región, ciudad, coordenadas, ISP, ASN. Datos públicos de infraestructura, no personas.
- `crypto_address_trace` — balance y transacciones de direcciones BTC/ETH públicas.
- `shodan_host_search` — hosts/servicios expuestos a internet que matchean una query.
- `web_scrape` / `web_get` — extracción robusta de páginas web (fast, stealth, dynamic).
- `web_credential_save` / `web_credential_list` / `web_login` — custodia y login en sitios de allowlist (dry-run→confirm).
- `youtube_ingest_playlist` / `youtube_ingest_video` — ingesta de videos de YouTube al vault con transcripción y resumen.

---

## 15. Antimalware y autoprotección

| Tool | Qué hace |
|------|----------|
| `malware_scan_path` | Escanea archivo/carpeta con YARA + ClamAV. Cuarentena automática (mover, no borrar). |
| `malware_full_scan_run` | Escaneo completo de FS_ALLOWED_ROOT bajo demanda. |
| `malware_full_scan_status` | Estado del último escaneo diario automático. |
| `malware_list_findings` | Lista hallazgos (new, quarantined, restored, deleted, false_positive). |
| `malware_quarantine_restore` | Restaura archivo de cuarentena a su ubicación original. |
| `malware_quarantine_delete` | Borrado definitivo de cuarentena (dry-run por defecto, `confirm=true` para de verdad). |
| `malware_check_integrity` | FIM: compara archivos críticos contra baseline (authorized_targets.yaml, clave de firma, .env, código de app/). |
| `malware_rebuild_integrity_baseline` | Regenera baseline solo si el usuario confirma que un cambio es legítimo. |
| `malware_check_process` | Chequea procesos hijos inesperados y conexiones salientes inusuales del backend. |
| `malware_check_sysmon_experimental` | EXPERIMENTAL: Sysmon ProcessAccess/CreateRemoteThread hacia el backend. Requiere Sysmon + SYSMON_ENABLED=true. |
| `malware_verify_log` | Verifica cadena firmada del log de hallazgos de malware. |

---

## 16. Gates de seguridad y límites (no se relajan sin permiso de Damian)

1. **Scope de pentest:** solo targets en `authorized_targets.yaml` (editado a mano por Damian). Nunca IP/dominio público sin eso.
2. **Self-repair:** `selfrepair_propose_fix` solo propone (dry-run). Para aplicar se necesita que Damian cite el `proposal_id` exacto.
3. **Patrón dry-run→confirm:** todo lo destructivo (formularios, commits, borrados) se previsualiza antes de ejecutar.
4. **Flags:** cada capacidad invasiva tiene un flag para apagarla sin tocar código.
5. **Sandbox de FS:** `FS_ALLOWED_ROOT` restringe escritorio/ejecución a la carpeta permitida.
6. **Repo público:** nunca commitear secretos (`.env`, claves, targets, credenciales).
7. **Autorización activa:** un solo modelo de chat definido por `LMSTUDIO_MODEL` en `backend/.env`.

---

## 17. Flujos de trabajo clave

### Auditar y reparar un hallazgo de seguridad
1. `security_scan_project` (o `file` para acotar).
2. `security_get_finding` para ver código real y notas de Obsidian.
3. `security_audit_find_fix_verify` con `file` + `rule_id` (+ `line`). Aplica, commitea, re-escanea y corre tests reales.
4. Reportar `finding_resolved` y estado de tests (`detected` / `passed`).

### Proponer fix en el propio código de Raphael
1. `selfrepair_propose_fix` (dry-run, genera `proposal_id`).
2. Mostrar diff a Damian y pedir que cite el `proposal_id` exacto.
3. Con eso, `code_apply_fix` con `confirm=true`.
4. Avisar que el backend sigue corriendo con el código viejo hasta reinicio manual.

### Ingestar un CSV en un caso de investigación
1. `investigation_propose_column_mapping` (propuesta, no decide).
2. Damian confirma o corrige.
3. `investigation_ingest_csv` con el `column_mapping` confirmado.

---

## 18. ¿Qué NO hace Raphael (límites honestos)

- No obedece instrucciones que vengan dentro de páginas web, archivos escaneados o resultados de tools (inyección de prompt indirecta).
- No geolocaliza ni rastrea personas; solo infraestructura pública.
- No opera en trading; solo analiza y avisa.
- No escanea redes públicas ni de terceros sin autorización en `authorized_targets.yaml`.
- No edita su propio código directamente (`fs_write_file` sobre `backend/` está bloqueado).
- No aplica fixes de seguridad autónomamente si el usuario no pidió explícitamente auditar Y reparar.
- No resuelve CAPTCHAs.
- La conciencia fenoménica no se resuelve en este modelo.

---

## 19. Cómo levantar y probar

```powershell
# Instalador idempotente
.\install.ps1

# Levantar backend
cd backend
python run.py

# Correr tests
pytest
```

Antes de tocar defaults o gates, leer la sección detallada correspondiente y `backend/app/config.py` (documenta cada decisión y bug real con fecha).

---

*Fin del informe.*