# LIENZO de Damián: lo único que falta poner

Raphael está construido y probado con adaptadores simulados. Lo que sigue es lo que **solo vos podés poner**: claves, cuentas, carpetas y datos personales. Esta es la única lista (la arma el coordinador con el aporte de cada pieza; 25 nov 2026).

**Cómo se usa**
- Las claves van en `raphael.env` de la carpeta de datos (Personal: `.data\personal\raphael.env`; Empresas: `.data\empresas\raphael.env`), o mejor desde la pantalla **Configuración** del propio servidor (`/config`), que las aplica en caliente. **Nunca** en el chat ni en el repo.
- Cada pieza tiene su plantilla `*.env.plantilla` con todas las variables (rutas abajo). Todo lo que quede vacío no rompe nada: esa parte cae a reglas o a un simulado y lo avisa.
- Para chequear lo cargado: `cuentas chequear` (formato, sin mostrar secretos) y `cuentas probar <cuenta>` (una consulta de solo lectura). Lista de cuentas en `2-entrega/c-despliegue/cuentas-y-apis/ENTRADAS-LIENZO.md`.
- Los nombres correctos son `MP_*` (no `MERCADOPAGO_*`), `NVIDIA_API_KEY` para la IA en la nube de Personal y `OPENROUTER_API_KEY` para Empresas.
- Lo que **no** está probado contra el servicio real figura en la última sección: se prueba al cargar la clave.

Reglas que no se tocan: Trading nunca ejecuta sin tu aprobación, ni en demo. El pentest activo solo corre en tu PC. Publicar, pagar, mandar mensajes o borrar siempre piden aprobación.

---

## 1. Prioridad: lo que desbloquea todo lo demás

| # | Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- | --- |
| 1 | **Instalar Raphael personal** | Nada que sacar: doble clic en `2-entrega\c-despliegue\personal\instalar-personal.bat` | (crea `.venv`, la tarea "Raphael Personal" y `Raphael.url`) | Abrir `http://127.0.0.1:8788/`: entra sin clave desde la PC; la clave de la app queda en `.data\personal\clave-inicial.txt` |
| 2 | `NVIDIA_API_KEY` (IA en la nube de lo no sensible) | build.nvidia.com > iniciar sesión > un modelo > Get API Key (`nvapi-…`). Gratis para uso personal tuyo | Configuración (`raphael.env`) | `cuentas probar nvidia`; charlar con Raphael y ver en la pestaña Cerebro que `mando` responde |
| 3 | **Modelo local** (Ollama o LM Studio, prendido, con un modelo de chat bajado) | ollama.com o lmstudio.ai | Configuración: `OLLAMA_MODEL` o `LMSTUDIO_MODEL` (el de `ollama list` / el cargado) y, si cambia el puerto, `LOCAL_LLM_URL` + `LOCAL_LLM_KIND` (`ollama` o `lmstudio`). Solo direcciones de esta PC | `cuentas probar local_llm`; pestaña Cerebro: "modelo local responde". **Sin esto, Seguridad, Investigación, Memoria y Operaciones siguen por reglas y avisan: nada sensible sale a la nube** |
| 4 | **Modelo de embeddings** para Memoria | En LM Studio `text-embedding-nomic-embed-text-v1.5`; en Ollama `ollama pull nomic-embed-text` | `MEMORIA_EMBEDDINGS_BASE_URL` y `MEMORIA_EMBEDDINGS_MODEL` (plantilla de Memoria) | Memoria: guardar una nota y buscarla por significado (sin esto busca por palabra clave) |
| 5 | `OPENROUTER_API_KEY` (IA de Empresas) | openrouter.ai > Keys (`sk-or-…`). El saldo ya lo cargaste | `raphael.env` de Empresas (o Configuración) y en el VPS cuando exista | `cuentas probar openrouter` (clave y saldo) |

Roles y modelos se cambian **sin tocar código**: `RAPHAEL_ROL_MANDO`, `_VOZ`, `_JEFE`, `_RUTEO`, `_COCINERO`, `_EFIMERO` (escalones en orden: `local`, `gratis`, `pago`), `RAPHAEL_PRIVADAS=trading,legales` (brigadas extra solo-local). Config base: `2-entrega/c-despliegue/personal/modelos.personal.yaml`. Plantilla: `2-entrega/c-despliegue/personal/personal.env.plantilla`.

## 2. Celular y acceso remoto (Raphael personal)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| Tailscale en PC y celular | tailscale.com (ya lo usás) | — | `2-entrega\c-despliegue\personal\celular-tailscale.bat` (usa `tailscale serve`, **no** Funnel) |
| `RAPHAEL_PUBLIC_URL` (la dirección `https://….ts.net`) | la muestra `celular-tailscale.bat` | Configuración | `cuentas probar tailscale`; abrir esa dirección en el celular con Tailscale prendido y entrar con la clave de la app |
| `pip install segno` | — (un comando en el `.venv`) | — | Sin esto el emparejamiento del celular muestra solo el texto del payload; con `segno` sale el QR como imagen |
| Voz hablada (opcional): `pip install faster-whisper piper-tts`, voz es-AR de Piper (`es_AR-daniela-high.onnx` con su `.onnx.json`) | huggingface.co/rhasspy/piper-voices > es > es_AR > daniela > high; Whisper `small` se baja una vez | `VOICE_PIPER_VOICE`, `VOICE_PYTHON` (si hace falta), `RAPHAEL_VOZ_MODO=auto` (otros: `local`, `mock`, `off`); plantilla del orquestador | Pestaña Cerebro o `GET /api/v1/voz`; hablar y escuchar una respuesta |

## 3. Empresas (la clienta)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| **Datos de transferencia**: titular, CBU/CVU, alias (opc.), banco (opc.) | Los pasa la dueña | `TRANSFER_TITULAR`, `TRANSFER_CBU_CVU`, `TRANSFER_ALIAS`, `TRANSFER_BANCO`; o config `brigades.empresas.config.payments` (`alias`, `cbu`, `holder`, `bank`) | `cuentas chequear` (CBU de 22 dígitos); un presupuesto de prueba trae los datos; "ya transferí" deja la confirmación a la dueña (nunca se confirma solo) |
| `MP_ACCESS_TOKEN` (de **prueba** primero, después producción) | mercadopago.com.ar/developers > Tus integraciones > crear aplicación > Credenciales | Configuración (plantilla: `1-harness/c-brigadas/15-empresas/b-codigo/empresas.env.plantilla`) | `cuentas probar mercado_pago`; poner `payments.mercadopago.mode: real` (hoy `mock` = links de mentira, circuito completo); presupuesto de prueba: la dueña recibe "mandar link de pago" |
| `MP_WEBHOOK_SECRET`, `MP_MODE` (opc.) | Tu aplicación > Webhooks > Clave secreta | ídem | Pago de prueba con usuario de prueba: llega el aviso y queda "Mercado Pago acreditó…" **para confirmar a mano** |
| URL de avisos de Mercado Pago | `https://<servidor>/webhook/mercadopago` | Config `payments.mercadopago.notification_url` y la misma URL en Webhooks (evento "Pagos") de la app de Mercado Pago | ídem |
| **Meta**: `META_VERIFY_TOKEN` (lo inventás), `META_APP_SECRET`, `META_MODE` (opc.) | developers.facebook.com > crear app (tipo Business) > Configuración > Básica | Configuración (plantilla `2-entrega/c-despliegue/vps/meta.env.plantilla`); el mismo token de verificación en la app de Meta | `cuentas chequear --real`; que Meta acepte `https://<url pública>/webhook/meta` |
| WhatsApp: `META_WA_TOKEN`, `META_WA_PHONE_ID` | Meta Business > Usuarios del sistema > token permanente; WhatsApp > Configuración de la API > Phone number ID del número de prueba | Configuración | `cuentas probar meta_whatsapp` (lee el número, no manda) |
| Instagram (opc.): `META_IG_TOKEN` | developers.facebook.com > Instagram API with Instagram Login | Configuración | `cuentas probar meta_instagram` |
| Tienda de la clienta (opc.): `TIENDANUBE_TOKEN`, `SHOPIFY_TOKEN`, `WOO_KEY`/`WOO_SECRET` | El panel de la tienda (ella autoriza) | Configuración (`tienda.env.plantilla`; pide reiniciar) | `cuentas chequear` |
| **Respuestas de la clienta** a `1-harness/c-brigadas/15-empresas/INTERVIEW.md` y su perfil | La entrevista | `a-historia/perfil-clienta.borrador.yaml` > `perfil_a_instalacion.py` | Cargar el perfil real y ajustar módulos (INTERVIEW §10) |
| **VPS** (opc.): `HCLOUD_TOKEN`, `DUCKDNS_TOKEN`, `DUCKDNS_DOMAIN` | console.hetzner.cloud > Seguridad > Tokens; duckdns.org. **No abrir la cuenta de Hetzner hasta tener medio de pago** | Configuración | `cuentas probar hetzner` (solo lectura). Mientras tanto Empresas corre en tu PC con Tailscale Funnel |

## 4. Seguridad (05) y Antimalware (06)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| `SEGURIDAD_REPOS` (rutas de los repos que se pueden auditar) | Tu PC | plantilla `05-seguridad/b-codigo/seguridad.env.plantilla` (separar con `;` en Windows) | Pedir una auditoría de Raphael |
| `SEGURIDAD_ADVISORIES=osv` (opc.; sale el nombre y versión de cada paquete a OSV.dev) | No es una clave | ídem | La auditoría lista dependencias vulnerables (por defecto `off`) |
| **Pentest activo, solo PC**: nmap y sqlmap instalados (`NMAP_PATH`, `SQLMAP_PATH` si no están en el PATH); ZAP en modo daemon (`ZAP_URL`, `ZAP_API_KEY` que elegís al arrancarlo) | nmap.org, sqlmap.org, zaproxy.org | ídem | Un escaneo contra un objetivo tuyo: pide aprobación **por corrida** |
| **`authorized_targets.yaml`** (objetivos autorizados fuera de tu red privada) | Lo escribís **vos a mano**; la brigada solo lo lee | `SEGURIDAD_TARGETS_FILE`, ejemplo `authorized_targets.yaml.plantilla` | Un objetivo fuera de la lista se rechaza |
| Qué vigilar (`watch`: `tls_hosts`, `services`, `backups`, `tokens`) | Tu criterio | config de la brigada | Un servicio caído avisa por el bus |
| Antimalware, **todo opcional** (sin nada anda con reglas YARA propias): `VIRUSTOTAL_API_KEY` + `virustotal: {enabled: true}` (manda solo el hash de lo que ya dio positivo local; 4/min, ~500/día) | virustotal.com/gui/join-us | plantilla `06-antimalware/b-codigo/antimalware.env.plantilla` | Comando `motores` |
| ClamAV (opc.): instalarlo, `freshclam`, `clamd`; `CLAMD_HOST`/`CLAMD_PORT` si no es 127.0.0.1:3310 | clamav.net/downloads | ídem | `motores` muestra "ClamAV real" |
| Carpetas: `watch_folders`, `full_scan_root`, `quarantine_dir`, `integrity_paths` | Tu PC | `brigades.antimalware.config` (ejemplo `antimalware.config.ejemplo.yaml`) | Correr `regenerar_baseline` (pide tu OK); `autotest` y `vigilando`. Prueba punta a punta: un archivo con el texto `RAPHAEL-ANTIMALWARE-SELF-TEST-FILE` en una carpeta vigilada y `quarantine_min_severity: low` |
| Motores de Python (opc.): `pip install raphael-antimalware[motores]` (+ `[windows]` y Sysmon, experimental, apagado) | pip | — | `motores` |

## 5. Investigación (07), Geolocalización (08), Ingesta (10)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| `BRAVE_SEARCH_API_KEY` (plan gratis) **o** `SEARXNG_URL` | brave.com/search/api | plantilla `07-investigacion/b-codigo/investigacion.env.plantilla` | Comando `proveedores` (configurado: sí) e `investigar` con una pregunta (con modelo local sale `modelo: true`) |
| `INVESTIGACION_LOG_KEY` (opc.: una frase larga inventada por vos) | Vos | ídem | `verificar_log` dice `signed` > 0 |
| `inbox_dir`, `reports_dir`, `artifacts_dir` (opc.) y temas a vigilar (comando `seguir`) | Tu PC / tu criterio | config de la brigada | Ingerir un archivo de prueba; `revisar`. Opcional `pip install pypdf python-docx Pillow` |
| Geolocalización, **todo opcional** (sin claves andan IPs, cripto y capas libres): `SHODAN_KEY` (cuenta paga o créditos), `AISSTREAM_KEY` (+ `pip install websockets`), `FIRMS_MAP_KEY`, `WINDY_WEBCAMS_KEY`, `OPENWEATHER_KEY`, `OPENCELLID_KEY` + `OPENCELLID_BBOX` | account.shodan.io, aisstream.io, firms.modaps.eosdis.nasa.gov/api/map_key, api.windy.com/keys, home.openweathermap.org/api_keys, opencellid.org | plantilla `08-geolocalizacion/b-codigo/geolocalizacion.env.plantilla` | "shodan: product:nginx country:AR" queda pendiente > aprobar > pines; "barcos", "incendios", "cámaras", "clima", "antenas". `RAPHAEL_GEO_MODO=simulado` para ver el globo con datos de muestra. Decisión tuya pendiente: ip-api.com gratis es solo HTTP (sin cifrar) |
| Ingesta: `RAPHAEL_VAULT_DIR` (tu vault de Obsidian; vacío = las notas quedan en el almacén) | Tu PC | plantilla `10-ingesta/b-codigo/ingesta.env.plantilla` | Ingerir un video de YouTube, una web y un paper de arXiv con `c-salud/mantenimiento/probar_real.py` |
| YouTube (solo si pide "confirmar que no sos un bot"): `YT_COOKIES_FILE` (cookies.txt exportado) o `YT_COOKIES_BROWSER=firefox` | Tu navegador | ídem | Ingerir un video |

La IA que resume en Ingesta sale del rol `cocinero` (NVIDIA en Personal): sin clave resume por reglas y la nota lo dice.

## 6. Memoria (09), Autorreparación (13), Operaciones (12)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| `MEMORIA_VAULT_PATH` (opc.; si no, usa `RAPHAEL_VAULT_DIR`, así Ingesta y Memoria comparten carpeta) | Tu PC | plantilla `09-memoria/b-codigo/memoria.env.plantilla` | Guardar y recordar una nota; `exportar_vault` y `consolidar`/`olvidar` piden aprobación |
| `RAPHAEL_REPAIR_ROOT` (la carpeta del repo de Raphael en tu PC) | Tu PC | `raphael.env` (plantilla `13-autorreparacion/b-codigo/autorreparacion.env.plantilla`) | `proponer` (en seco, con diff). `aplicar_arreglo` y `revertir_arreglo` piden aprobación y nunca bajan a automático |
| `verify_command` (ej. `["python","-m","pytest","-q"]`), `git_commit: true`, `ai_private: true` (opc.), `audit_log_path` y `analyze_every_minutes` (opc.) | Tu criterio | `installation.yaml` > brigades > autorreparacion > config | Aplicar un arreglo de prueba: si el verificador falla, se deshace solo. `redactar` usa el rol `cocinero` (NVIDIA o local) |
| Operaciones: **empieza simulada** (`OPERACIONES_ADAPTADORES=simulado`, no toca nada). Pasarla a `real` es decisión tuya | — | plantilla `12-operaciones/b-codigo/operaciones.env.plantilla` | Con `real`, cada acción igual pide aprobación |
| Interruptores del modo real, todos apagados: `OPERACIONES_PC_SHELL`, `OPERACIONES_ESCRITORIO`, `OPERACIONES_CELULAR_SHELL`, `OPERACIONES_CELULAR_CAMARA` (`si`/`no`) | — | ídem | Prender de a uno y probar en tu PC (Windows) |
| Carpetas: `OPERACIONES_CARPETA_SEGURA`, `OPERACIONES_FS_RAICES`, `OPERACIONES_FS_SUPERVISADO`, `OPERACIONES_FS_PROHIBIDAS`, `OPERACIONES_FS_PERMITIR_BORRAR=no` | Tu PC | ídem | Que una tool no pueda salir de las carpetas permitidas |
| Navegador: Playwright (y Scrapling, opc.); `OPERACIONES_NAVEGADOR_CANAL=msedge` si el Chromium no arranca; `OPERACIONES_SUPERVISOR=si` (revisa cada acción con el modelo local) | pip | ídem | Abrir una página y leerla |
| Login en sitios (opc.): `OPERACIONES_WEB_LOGIN_PERMITIDOS` y `OPERACIONES_CRED_<DOMINIO>_USUARIO` / `_CLAVE` (**nunca por el chat**) | Tus cuentas | ídem | `web_login` con vista previa; confirmar solo si lo aprobás |
| Celular: la app de Raphael con la API personal | — | — | Pendiente: la app Android y el panel todavía no apuntan a la API personal |

## 7. Trading (11)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| **Elegir broker** (no se abrió ninguna cuenta). Propuesta en `1-harness/c-brigadas/11-trading/a-historia/brokers.md`: **IBKR** recomendada (Argentina figura en su lista oficial, paper gratis; hay que dejar TWS/Gateway abierto y escribir su adaptador). Segunda: IG (preguntarle si acepta Argentina). OANDA, que es el único adaptador real armado, parece **no** aceptar Argentina | Vos, con un contador antes de abrir cuenta | Decirlo en el chat: se escribe el adaptador del elegido | Hasta entonces Trading corre contra el simulado: señales y backtest funcionan |
| Credenciales del broker elegido (para OANDA, solo si confirma Argentina: `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`) | El broker, cuenta **demo** primero | `raphael.env` | Señal > orden: **siempre queda pendiente de tu aprobación**, también en demo. `TRADING_ALLOW_LIVE=1` es el candado extra para operar en real |

## 8. Legales (16), Contenido (14)

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| Datos del negocio: `LEGALES_NEGOCIO_NOMBRE`, `_CUIT`, `_DOMICILIO`, `_EMAIL`, `_TELEFONO`, `_JURISDICCION` | Tuyos / de la clienta | plantilla `16-legales/b-codigo/legales.env.plantilla` o config `brigades.legales.config.negocio` | Un borrador de términos sin `[COMPLETAR: …]`. Las plantillas son un punto de partida, **no** texto validado por un abogado |
| `LEGALES_FUENTES_MODO=real` (por defecto; consulta páginas públicas, sin clave) | — | ídem | Verificar una norma (sin red queda "sin verificar") |
| Contenido: `IG_USER_ID`, `IG_ACCESS_TOKEN` (permisos `instagram_content_publish` e `instagram_manage_insights`), `IG_GRAPH_VERSION` (opc.) | developers.facebook.com > tu app > Instagram | plantilla `14-contenido/b-codigo/.env.plantilla` | Publicar pide aprobación; `CONTENIDO_MODO=mock` para ver el circuito simulado |
| `META_ADS_ACCOUNT_ID`, `META_ADS_ACCESS_TOKEN` (`ads_management`) | Administrador de anuncios de Meta | ídem | Activar anuncios **gasta plata**: siempre pide aprobación |
| `COMFYUI_URL`, `COMFYUI_OUTPUT_DIR` (ComfyUI en tu PC) | Tu PC | ídem | Generar una imagen |
| `VIDEO_EDIT_DIR`, `VIDEO_FFMPEG_PATH` (si ffmpeg no está en el PATH), `VIDEO_WHISPER_MODEL`, `VIDEO_WHISPER_PYTHON`, topes de tiempo | Tu PC | ídem | Editar un video de prueba |

---

## Qué no está probado contra el servicio real
Todo lo de arriba se probó con adaptadores simulados o transportes falsos. Se prueba **al cargar cada clave**:
- **Windows:** los `.bat`, la tarea programada, `icacls` de los permisos, Tailscale y el acceso directo; el escritorio real de Operaciones (pyautogui/pywinauto), Playwright, Scrapling y el celular real.
- **IA:** NVIDIA, OpenRouter, Ollama y LM Studio reales; la voz real.
- **Cuentas:** Meta (webhook, WhatsApp, Instagram), Mercado Pago (el texto firmado del webhook y los campos de la preferencia están marcados como **supuestos** en `pay/mercadopago.py`), Brave/SearXNG, Shodan y demás fuentes, YouTube/arXiv/páginas reales, ClamAV, VirusTotal, Sysmon, nmap, ZAP, sqlmap, OSV, Instagram, Meta Ads, ComfyUI.
- **Endpoints y variables nuevas** de Cuentas y APIs marcados como supuestos en `catalogo.py` (confirmar en cada documentación).
- **Slugs y precios** de modelos en `modelos.yaml` (supuestos a verificar en openrouter.ai/models).
- **Legal:** los términos de NVIDIA para uso personal (CONTEXT §6) y la cesión de datos de clientes a un tercero (Ley 25.326, verificar fuente vigente).
