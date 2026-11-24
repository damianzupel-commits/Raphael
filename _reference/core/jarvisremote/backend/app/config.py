import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# Raíz del proyecto JarvisRemote (la carpeta que contiene backend/, content/,
# etc.). config.py vive en backend/app/, así que dos niveles arriba de `app`
# es la raíz del repo. Se usa como default acotado de FS_ALLOWED_ROOT (ver
# abajo): contiene el vault (backend/obsidian_vault/), los datos derivados
# (backend/app/data/... vía CODEBASE_INDEX_DIR/SECURITY_SCAN_DIR/etc.), los
# logs y las propuestas de self-repair -- todo lo que Jarvis legítimamente
# necesita escribir para funcionar, sin abrir el HOME entero.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _split_paths(value: str | None) -> list[str]:
    """Parsea una lista de rutas separadas por coma o punto y coma. Vacío ->
    lista vacía. Usado por FS_ALLOWED_ROOTS para configurar VARIAS raíces
    permitidas sin volver a abrir todo el HOME.

    A propósito NO se usa os.pathsep como separador: en este proyecto (Windows)
    os.pathsep es ';' -- ya cubierto explícitamente abajo -- pero las rutas de
    Windows usan ':' en la letra de unidad ('C:\\...'), así que separar por ':'
    partiría cada ruta al medio. Coma y punto y coma son inambiguos."""
    if not value:
        return []
    parts: list[str] = []
    for chunk in value.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    api_key: str = os.getenv("API_KEY") or secrets.token_urlsafe(32)
    _api_key_was_generated: bool = not os.getenv("API_KEY")

    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "local-model")
    # API key del proveedor LLM de chat/agente (llm_client.py). Default
    # "lm-studio": el servidor local (LM Studio/Ollama) no valida la key pero
    # el SDK de OpenAI exige mandar algo, así que este default deja el
    # comportamiento local idéntico al anterior. Se hace configurable por env
    # (LLM_API_KEY) para poder apuntar el cliente a proveedores cloud que sí
    # exigen una key real (OpenRouter/DeepSeek, etc.) sin tocar código.
    llm_api_key: str = os.getenv("LLM_API_KEY", "lm-studio")

    # Bug real 2026-08-10 (v6, sesión de creación del mod de Fabric): el cliente
    # OpenAI (app/llm_client.py) no tenía timeout explícito -- el SDK usaba su
    # default (600s), que una generación real lenta (cold start del modelo +
    # ~2800 tokens a ~4.4 tok/s) superó, disparando un reintento automático que
    # obligó a reprocesar el prompt completo (~21.6K tokens) desde cero.
    # Generoso a propósito: mejor esperar de más que cortar una generación real
    # en curso y forzar un reprocesamiento carísimo.
    llm_request_timeout_seconds: float = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "1800"))

    # Reintentos con backoff exponencial para fallas TRANSITORIAS de red al
    # llamar al LLM desde el loop del agente (agregado 2026-08-19, ver
    # app/agent.py::_create_chat_completion / _is_transient_llm_error).
    # Complementa -- no contradice -- el max_retries=0 del SDK en
    # llm_client.py: ahí se desactivan los reintentos AUTOMÁTICOS del SDK (que
    # reprocesaban el prompt entero ante un timeout de una generación local
    # legítimamente lenta, bug v6); acá se agrega un reintento EXPLÍCITO,
    # logueado y acotado a errores de CONEXIÓN, pensado sobre todo para el
    # modelo cloud (gpt-oss:120b-cloud), donde una caída de red transitoria SÍ
    # se recupera reintentando. max_attempts=3 => hasta 3 intentos totales.
    llm_retry_max_attempts: int = int(os.getenv("LLM_RETRY_MAX_ATTEMPTS", "3"))
    llm_retry_base_delay_seconds: float = float(os.getenv("LLM_RETRY_BASE_DELAY_SECONDS", "1.0"))
    llm_retry_max_delay_seconds: float = float(os.getenv("LLM_RETRY_MAX_DELAY_SECONDS", "30.0"))
    # Reintentar también ante APITimeoutError. Default False a propósito: un
    # timeout contra el modelo LOCAL suele ser una generación real lenta (no un
    # fallo de red) y reintentarla reprocesa el prompt entero desde cero (bug
    # real v6). Prender solo si se usa el modelo cloud y se entiende el
    # trade-off.
    llm_retry_on_timeout: bool = _bool(os.getenv("LLM_RETRY_ON_TIMEOUT"), False)

    # Server + modelo de embeddings para memoria semántica del vault (ver
    # app/obsidian/embeddings.py). A propósito NO reusa LMSTUDIO_BASE_URL:
    # en esta máquina esa variable en realidad apunta a Ollama (puerto 11434,
    # el LLM de chat real -- el nombre "lmstudio" quedó de una migración
    # anterior, ver LMSTUDIO_BASE_URL de más arriba), que no tiene un modelo
    # de embeddings cargado. El LM Studio real (la app, puerto 1234 por
    # default) corre aparte y sí lo tiene -- confirmado real en esta PC el
    # 2026-07-30 (`curl localhost:1234/v1/embeddings` responde, Ollama
    # devuelve 404 "model not found" para el mismo pedido).
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:1234/v1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5")

    # Sandbox de filesystem de las tools fs_* (app/tools/filesystem.py) y del
    # cwd del shell real (pc_command.py / opencode.py, que reusan el mismo
    # _resolve). TODA lectura/escritura/ejecución tiene que caer dentro de
    # alguna de las raíces permitidas o falla con PermissionError.
    #
    # DEFAULT CAMBIADO 2026-08-19: antes era el HOME entero (Path.home(),
    # C:\Users\dam) -- demasiado amplio, dejaba a Jarvis tocar CUALQUIER cosa
    # del usuario (documentos, otras carpetas, etc.). Ahora el default es la
    # RAÍZ DEL PROYECTO (_PROJECT_ROOT), que ya contiene todo lo que Jarvis
    # necesita para funcionar: el vault, los datos derivados, logs y
    # propuestas de self-repair (ver comentario de _PROJECT_ROOT).
    #
    # CÓMO AMPLIARLO si algo legítimo quedó afuera (ej. auditar/editar un repo
    # que vive en otra carpeta del disco): NO volver a poner el HOME entero.
    # En vez de eso, agregar esa(s) carpeta(s) puntuales a FS_ALLOWED_ROOTS
    # (lista separada por comas), que se SUMA a FS_ALLOWED_ROOT. Ej.:
    #   FS_ALLOWED_ROOTS=C:\Users\dam\otro-repo,D:\proyectos\cliente
    # Nota: el indexado de codebase (codebase_*) es de SOLO LECTURA y NO está
    # sandboxeado (ver app/tools/codebase.py), y el ciclo de fixes
    # (code_apply_fix -> app/codeedit/fixer.py) valida contra la raíz del repo
    # que se le pasa, no contra FS_ALLOWED_ROOT -- así que auditar y aplicar
    # fixes a un repo externo sigue funcionando aunque no esté en el sandbox.
    fs_allowed_root: str = os.getenv("FS_ALLOWED_ROOT", str(_PROJECT_ROOT))
    fs_allowed_roots_extra: list[str] = _split_paths(os.getenv("FS_ALLOWED_ROOTS"))
    fs_allow_delete: bool = _bool(os.getenv("FS_ALLOW_DELETE"), False)

    # LISTA NEGRA de carpetas (agregado 2026-08-30): rutas PROHIBIDAS aunque caigan
    # dentro de una raíz permitida -- incluso en modo SUPERVISADO con el HOME entero
    # abierto. Se chequea DESPUÉS de la allowlist en filesystem._resolve, así una
    # carpeta denegada gana SIEMPRE. Pensado para proteger material PERSONAL de Damian
    # (ej. Vault-Fenix con sus análisis psicológicos) que ninguna tool fs_* debe poder
    # leer, sin tener que achicar el sandbox entero. Configurable con FS_DENIED_PATHS
    # en el .env (separado por comas).
    # 2026-11-11: el almacén de brigadas creadas (borradores + aprobaciones firmadas +
    # claves del gate de activación, Etapa 2) se deniega SIEMPRE por default, además de
    # lo que ponga el .env: ninguna tool fs_* (ni un jefe manipulado) debe poder
    # escribir ahí. Es defensa en profundidad del gate borrador->activa.
    fs_denied_paths: list[str] = _split_paths(os.getenv("FS_DENIED_PATHS")) + [
        os.getenv("BRIGADAS_CREADAS_DIR")
        or str(Path(__file__).resolve().parent.parent / "data" / "brigades_creadas")
    ]

    # Raíz AMPLIA del modo SUPERVISADO (attended), agregado 2026-08-19 junto con
    # app/operation_mode.py. Cuando hay un humano usando Jarvis en vivo, el
    # sandbox se abre a esta raíz -- por default el HOME entero, que es la
    # potencia que Damian tenía ANTES de achicar FS_ALLOWED_ROOT al proyecto.
    # La idea del sistema de dos modos: con Damian presente para frenar una
    # macana no se pierde capacidad; el radio de daño solo se acota cuando
    # Jarvis corre SOLO (modo AUTÓNOMO, que usa fs_allowed_roots, el sandbox
    # chico). Configurable con FS_SUPERVISED_ROOT si Damian quiere otra raíz
    # amplia en vez del HOME. Ver Settings.fs_supervised_roots y
    # operation_mode.effective_fs_roots.
    fs_supervised_root: str = os.getenv("FS_SUPERVISED_ROOT", str(Path.home()))

    @property
    def fs_allowed_roots(self) -> list[str]:
        """Raíces del sandbox ACOTADO (modo AUTÓNOMO): la principal
        (fs_allowed_root, por default el proyecto) más las extra
        (FS_ALLOWED_ROOTS), deduplicadas preservando el orden. La principal va
        primero: las rutas relativas se resuelven contra ella (ver
        filesystem._resolve). En modo SUPERVISADO se usa fs_supervised_roots."""
        return self._dedup_roots([self.fs_allowed_root, *self.fs_allowed_roots_extra])

    @property
    def fs_supervised_roots(self) -> list[str]:
        """Raíces del sandbox AMPLIO (modo SUPERVISADO): el root amplio
        (fs_supervised_root, por default el HOME) PRIMERO -- así las rutas
        relativas se resuelven contra el HOME, restaurando el comportamiento
        potente de siempre -- seguido de las raíces del sandbox acotado, para
        garantizar que SUPERVISADO nunca tenga MENOS acceso que AUTÓNOMO
        (supervisado ⊇ autónomo). Deduplicado preservando el orden."""
        return self._dedup_roots([self.fs_supervised_root, *self.fs_allowed_roots])

    @staticmethod
    def _dedup_roots(roots: list[str]) -> list[str]:
        """Filtra vacíos y deduplica preservando el orden."""
        seen: set[str] = set()
        unique: list[str] = []
        for root in roots:
            if root and root not in seen:
                seen.add(root)
                unique.append(root)
        return unique

    browser_headless: bool = _bool(os.getenv("BROWSER_HEADLESS"), False)

    # Control de escritorio (mouse/teclado/ventanas de cualquier app, ver
    # app/tools/desktop.py) es tan invasivo como el Accessibility Service del
    # celular. Prendido por default porque el usuario pidió explícitamente la
    # versión sin fricción, pero queda como flag real para poder apagarlo.
    desktop_control_enabled: bool = _bool(os.getenv("DESKTOP_CONTROL_ENABLED"), True)

    # Ejecución de comandos de shell reales en la PC (ver app/tools/pc_command.py::
    # pc_run_command) -- análogo directo de PHONE_SHELL_ENABLED pero del lado de la
    # PC: código/comandos arbitrarios (pip install, pytest, npm, git, etc.), no solo
    # tools puntuales. Mismo criterio que DESKTOP_CONTROL_ENABLED/PHONE_SHELL_ENABLED
    # (usuario ya pidió explícitamente la versión sin fricción, prendido por default),
    # pero queda como flag real para poder apagarlo sin tocar código.
    pc_shell_enabled: bool = _bool(os.getenv("PC_SHELL_ENABLED"), True)

    max_agent_iterations: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))

    # Tope de iteraciones extendido, SOLO para tareas que resultan ser creación de
    # código multi-archivo -- ver app/agent.py::run_agent, se activa recién cuando
    # el turno actual ya usó fs_write_file al menos una vez (no es un default
    # general: una auditoría o un chat normal nunca llega a necesitarlo). Bug real
    # 2026-08-10: crear un mod de Fabric desde cero (build.gradle, fabric.mod.json,
    # varias clases Java, tags, lang, modelos) agotó las 30 iteraciones por defecto
    # antes de terminar de armar el wrapper de Gradle o intentar compilar.
    max_agent_iterations_code_task: int = int(os.getenv("MAX_AGENT_ITERATIONS_CODE_TASK", "50"))

    # Tope de mensajes que se guardan por conversación en memoria (ver
    # app/agent.py::_trim_history). Sin esto, `_conversations` crece para
    # siempre mientras el proceso esté vivo y termina superando el contexto
    # del modelo (pasó de verdad: "Context size has been exceeded" de LM
    # Studio, todo /api/chat empezó a tirar 500). El corte es simple —por
    # cantidad de mensajes, no por tokens reales— y siempre cae en el próximo
    # mensaje 'user' para no partir un tool_call de su respuesta.
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))

    # Tope de tamaño (caracteres del JSON serializado, proxy barato de tokens ya que
    # no tenemos el tokenizer real del modelo cargado) para el contenido de UN SOLO
    # mensaje 'tool' antes de mandarlo al modelo (ver app/agent.py::_cap_tool_result).
    # Bug real encontrado 2026-08-03: security_scan_project sobre un proyecto con
    # cientos de hallazgos (ej. pygoat, 312 hallazgos) devuelve ~47KB de JSON en un
    # solo tool result -- sumado al system prompt (~9.7KB) y al schema de las ~50
    # tools registradas (~40KB), eso ya eran ~98KB (~28k tokens estimados) contra un
    # n_ctx real de 16384 tokens en Ollama para jarvis-text-v2 (confirmado con
    # `ollama show jarvis-text-v2`, ver server.log de Ollama: n_ctx = 16384, la
    # PRIMERA llamada del turno -- solo system+tools+mensaje del usuario, sin ningún
    # tool result todavía -- ya consumía 12546 tokens, dejando ~3800 de margen real).
    # Con el prompt así de sobrepasado, el context-shift de llama.cpp/Ollama
    # descarta el prompt viejo (deja solo n_keep=4 tokens del principio, ver log:
    # "n_keep = 4") para hacer lugar al tool result gigante -- así se pierde el
    # system prompt Y el pedido original del usuario, y el modelo, sin ese marco,
    # respondía con una introducción genérica ("Hola, soy Jarvis...") en vez de
    # seguir razonando sobre hallazgos que ya no podía "ver". _trim_history ya poda
    # por CANTIDAD de mensajes, pero no protege contra que UN SOLO mensaje sea
    # gigante -- este tope aparte cubre ese caso.
    max_tool_result_chars: int = int(os.getenv("MAX_TOOL_RESULT_CHARS", "6000"))

    # Presupuesto REAL de contexto del modelo, en tokens (ver app/agent.py::
    # _history_char_budget). Bug real encontrado 2026-08-09: con 51 tools ya
    # registradas, el system prompt (~9.7KB) + el schema de tools (~42KB) solos ya
    # representan ~13-16k tokens estimados -- contra un num_ctx de 16384, eso deja
    # margen CASI NULO para el historial de la conversación, y `_trim_history`
    # (que poda por CANTIDAD de mensajes) + `_cap_tool_result` (que acota UN SOLO
    # mensaje) no alcanzan a evitarlo: varios tool results medianos, cada uno bajo
    # su propio tope individual, igual suman más de lo que queda de contexto.
    # Un pedido real (security_scan_project sobre pygoat) llegó a 16372/16384
    # tokens de prompt, tardó varios MINUTOS solo en el prompt-processing (el
    # throughput se degrada con el contexto en este hardware, GPU de 12GB
    # compartida con CPU) y nunca llegó a generar respuesta. Subimos num_ctx a
    # 32768 en el Modelfile de Ollama (había VRAM/RAM de sobra, 24GB+ libres tras
    # liberar el pedido colgado) para dar aire real, pero el límite de acá es la
    # protección de fondo -- tiene que quedar sincronizado con el num_ctx real del
    # modelo cargado (no hay forma de leerlo del backend en runtime sin pegarle a
    # la API de Ollama aparte, así que es config manual).
    model_context_tokens: int = int(os.getenv("MODEL_CONTEXT_TOKENS", "131072"))

    # Tokens que se reservan SIN TOCAR para que el modelo pueda generar una
    # respuesta real después de "leer" todo el prompt -- si el presupuesto de
    # historial no descuenta esto, un prompt que llena el contexto hasta el
    # límite exacto no deja lugar para la respuesta (llama.cpp/Ollama hace
    # context-shift y tira el system prompt, ver nota de MAX_TOOL_RESULT_CHARS).
    reserved_response_tokens: int = int(os.getenv("RESERVED_RESPONSE_TOKENS", "8192"))

    # No tenemos el tokenizer real del modelo cargado en el backend -- estimar
    # tokens contando caracteres y dividiendo por esto. 3.2 es conservador
    # (subestima cuántos caracteres entran por token) a propósito: JSON de tool
    # results/schemas es denso en símbolos/comillas, más cerca de 3-3.5 chars/token
    # que las ~4 típicas de prosa en inglés -- mejor quedarse corto en el
    # presupuesto que volver a exceder el contexto real.
    chars_per_token_estimate: float = float(os.getenv("CHARS_PER_TOKEN_ESTIMATE", "3.2"))

    phone_tool_timeout: float = float(os.getenv("PHONE_TOOL_TIMEOUT", "30"))

    # Ejecución de comandos de shell reales en el celular vía Termux
    # (ver app/tools/phone.py::phone_run_command). Es el nivel más invasivo
    # posible del lado del celular: código arbitrario, no solo interacción con
    # la UI. Prendido por default (mismo criterio que DESKTOP_CONTROL_ENABLED:
    # el usuario ya pidió explícitamente la versión sin fricción), pero queda
    # como flag real para poder apagarlo sin tocar código.
    phone_shell_enabled: bool = _bool(os.getenv("PHONE_SHELL_ENABLED"), True)

    # Uso de la cámara del celular (ver app/tools/phone.py::phone_take_photo). Captura
    # silenciosa (sin abrir la app de Cámara), en la misma categoría de invasividad que
    # el resto de las tools de celular. Prendido por default (mismo criterio que
    # DESKTOP_CONTROL_ENABLED/PHONE_SHELL_ENABLED), pero queda como flag real para
    # poder apagarlo sin tocar código.
    phone_camera_enabled: bool = _bool(os.getenv("PHONE_CAMERA_ENABLED"), True)

    # Extracción de frames de video (ver app/video_frames.py y app/tools/phone.py::
    # phone_record_video) — no depende de PHONE_CAMERA_ENABLED por separado, la tool
    # de video usa la misma cámara y el mismo flag que la foto.
    video_frame_interval_seconds: float = float(os.getenv("VIDEO_FRAME_INTERVAL_SECONDS", "1.5"))
    video_max_frames: int = int(os.getenv("VIDEO_MAX_FRAMES", "8"))

    # TLS para servir wss:// en vez de wss:// (la conexión hoy viaja en texto
    # plano — ver sección de seguridad de README.md). Preparado pero apagado
    # por default a propósito: activarlo cambia la URL que espera la app del
    # celular (https:// en vez de http://) y requiere que Android confíe en el
    # certificado self-signed (ver `certs/README.md`) — un corte que hay que
    # coordinar con el usuario presente, no activar solo. Generar el cert con
    # `certs/generate_cert.sh` (o el comando equivalente documentado ahí).
    tls_enabled: bool = _bool(os.getenv("TLS_ENABLED"), False)
    tls_cert_path: str = os.getenv("TLS_CERT_PATH", str(Path(__file__).resolve().parent.parent / "certs" / "cert.pem"))
    tls_key_path: str = os.getenv("TLS_KEY_PATH", str(Path(__file__).resolve().parent.parent / "certs" / "key.pem"))

    # Archivo donde `jarvis_reflect` persiste reflexiones/decisiones abstraídas
    # (ver app/tools/reflect.py) — un JSONL append-only, no pasa por el sandbox
    # de FS_ALLOWED_ROOT porque es estado interno del backend, no un archivo
    # del usuario.
    reflections_path: str = os.getenv(
        "REFLECTIONS_PATH", str(Path(__file__).resolve().parent.parent / "reflections.jsonl")
    )

    # generate_video (ver app/tools/video_gen.py): dónde vive la instalación
    # portable de ComfyUI y en qué URL escucha su API HTTP. Default apunta a la
    # instalación de este equipo -- en otra máquina hay que ajustar COMFYUI_DIR
    # en el .env.
    comfyui_dir: str = os.getenv("COMFYUI_DIR", r"E:\ComfyUI\ComfyUI_windows_portable")
    comfyui_base_url: str = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
    comfyui_startup_timeout: float = float(os.getenv("COMFYUI_STARTUP_TIMEOUT", "240"))
    # El Python embebido de la instalación portable (python_embeded/) trae un build
    # de PyTorch+ROCm que crashea (access violation real, reproducido con
    # torch.cuda.is_available()) en esta GPU no soportada oficialmente (gfx1031).
    # El venv separado `env_rocm/` (creado a mano durante el setup original) tiene
    # una versión de torch/ROCm que sí detecta la GPU sin crashear -- ese es el que
    # hay que usar para levantar el server. Configurable por si en otra instalación
    # el nombre/ubicación del venv que sí funciona es distinto.
    comfyui_python_path: str = os.getenv(
        "COMFYUI_PYTHON_PATH", r"E:\ComfyUI\ComfyUI_windows_portable\env_rocm\Scripts\python.exe"
    )

    # API nativa de Ollama (no la OpenAI-compatible de LMSTUDIO_BASE_URL) --
    # generate_video/generate_image la usan para descargar/recargar el modelo de
    # texto de la VRAM antes/después de generar, ya que compiten por la misma GPU.
    ollama_native_base_url: str = os.getenv("OLLAMA_NATIVE_BASE_URL", "http://127.0.0.1:11434")

    # generate_image (Flux.1 Schnell, un solo KSampler de 4 pasos) es más liviano que
    # generate_video, pero se deja igual un margen generoso por la misma variabilidad
    # de RAM/swapping observada en esta máquina.
    comfyui_generation_timeout_image: float = float(os.getenv("COMFYUI_GENERATION_TIMEOUT_IMAGE", "600"))

    # Cache en disco de índices de codebase (ver app/codebase/store.py) -- nunca
    # escribe dentro del proyecto que se indexa, un JSON por proyecto acá.
    codebase_index_dir: str = os.getenv(
        "CODEBASE_INDEX_DIR", str(Path(__file__).resolve().parent.parent / "data" / "codebase_index")
    )

    # Vault de notas estilo Obsidian (ver app/obsidian/vault.py) -- reemplazo
    # más rico de jarvis_reflect para notas con autor (jarvis/humano), tags y
    # wikilinks. Son archivos .md reales con frontmatter YAML, abribles con
    # Obsidian de verdad si el usuario quiere.
    obsidian_vault_path: str = os.getenv(
        "OBSIDIAN_VAULT_PATH", str(Path(__file__).resolve().parent.parent / "obsidian_vault")
    )

    # Índice de embeddings del vault (ver app/obsidian/embeddings.py) -- un
    # único JSON {note_id: vector}, nunca dentro del vault (que se abre con
    # Obsidian de verdad y parte de él se publica en git, ver .gitignore).
    # Mismo criterio que CODEBASE_INDEX_DIR/SECURITY_SCAN_DIR: cache derivado,
    # se puede borrar y reconstruir con `vault.reindex_all()`.
    obsidian_embeddings_path: str = os.getenv(
        "OBSIDIAN_EMBEDDINGS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "obsidian_embeddings.json")
    )

    # Cache en disco del último escaneo de seguridad por proyecto (ver
    # app/security/store.py) -- mismo criterio que CODEBASE_INDEX_DIR, nunca
    # escribe dentro del proyecto escaneado.
    security_scan_dir: str = os.getenv(
        "SECURITY_SCAN_DIR", str(Path(__file__).resolve().parent.parent / "data" / "security_scans")
    )

    # Cache en disco del último escaneo de CALIDAD (bugs generales, no
    # seguridad) por proyecto (ver app/quality/store.py) -- mismo criterio que
    # SECURITY_SCAN_DIR, carpeta separada para no mezclar los dos tipos de
    # hallazgo en el mismo cache.
    quality_scan_dir: str = os.getenv(
        "QUALITY_SCAN_DIR", str(Path(__file__).resolve().parent.parent / "data" / "quality_scans")
    )

    # Cache en disco de la ÚLTIMA corrida de tests reales por proyecto (ver
    # app/testing/store.py) -- mismo criterio que SECURITY_SCAN_DIR. Es lo que
    # lee `audit_report.generate_report` para marcar explícitamente si hubo (o
    # no) una corrida de tests real en verde después de los fixes aplicados,
    # en vez de asumir "compiló" == "funciona" (gap real 2026-08-10, ver
    # sesión de meta-observación: el pipeline nunca tenía un paso de
    # verificación funcional entre corregir y re-auditar).
    test_run_dir: str = os.getenv(
        "TEST_RUN_DIR", str(Path(__file__).resolve().parent.parent / "data" / "test_runs")
    )

    # Persistencia del historial de chat (agregado 2026-09-01, pedido de Damian:
    # "que mantenga la sesión de todo lo que hablamos por más que cierre"). El
    # historial vive en memoria (`agent._conversations`) y se perdía al reiniciar
    # el backend -- y cerrar la tray apaga el backend, así que se borraba todo. Se
    # persiste a este JSON después de cada turno y se recarga al arrancar. Vive
    # bajo backend/data/ que está gitignoreado (repo público: el chat NO se
    # commitea). Se puede apagar con CHAT_PERSIST_ENABLED=false.
    conversations_path: str = os.getenv(
        "CONVERSATIONS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "conversations.json")
    )
    chat_persist_enabled: bool = _bool(os.getenv("CHAT_PERSIST_ENABLED"), True)

    # Etapa D -- auto-rediseño seguro (2026-10-06, decisión de Damian). LÍNEAS ROJAS:
    # archivos que la auto-modificación NUNCA puede tocar, NI con confirmación -- tocarlos
    # debilitaría la seguridad. Fragmentos de ruta separados por coma; `selfrepair.guardrail`
    # rechaza cualquier fix cuyo archivo matchee uno. Por default: scope de pentest, el gate
    # de confirmación en sí, la auth, los secretos y la config (que tiene los flags de gates).
    self_protected_paths: str = os.getenv(
        "SELF_PROTECTED_PATHS",
        "authorized_targets.yaml,app/selfrepair/gate.py,app/auth.py,.env,app/config.py",
    )
    # Interruptor maestro del autorediseño (2026-10-06: wireado de verdad en
    # app/tools/selfrepair.py::selfrepair_propose_fix). Si está OFF, Raphael NO puede
    # ni proponer cambios a su propio código. Si está ON, PUEDE proponer -- pero aplicar
    # de verdad SIEMPRE sigue necesitando la confirmación manual de Damian por proposal_id
    # (code_apply_fix confirm=true) + las líneas rojas (self_protected_paths) que nunca se
    # tocan. "Encendido" nunca significa "aplica solo". Damian lo quiere siempre ON.
    self_redesign_enabled: bool = _bool(os.getenv("SELF_REDESIGN_ENABLED"), False)

    # Router de dificultad del chat (2026-10-06, pedido de Damian). Si está ON, el
    # chat clasifica cada mensaje (harness/difficulty_router.py) y escala a Claude
    # (tier 3 Sonnet / tier 4 Opus) solo cuando la tarea lo amerita; lo simple sigue
    # en free. Default OFF a pedido ("construilo pero ahora no lo usaremos"): es el
    # interruptor para prenderlo cuando quiera. En modo prueba no aplica (todo free).
    difficulty_router_enabled: bool = _bool(os.getenv("DIFFICULTY_ROUTER_ENABLED"), False)

    # Supervisor de la brigada Operaciones (2026-10-12, pedido de Damian). Si está ON, antes de
    # ejecutar una tool de ACCIÓN (PC/celular = brigada "ops"), un modelo tier-3 (Sonnet) revisa
    # el llamado y puede FRENARLO si es claramente erróneo/peligroso ("frenar malos llamados").
    # Default OFF: es un guardrail SUAVE y opcional, aparte de los gates duros; fail-open (si el
    # supervisor falla o tarda, NO bloquea, nunca rompe un turno). Ver app/ops_supervisor.py.
    ops_supervisor_enabled: bool = _bool(os.getenv("OPS_SUPERVISOR_ENABLED"), False)

    # Watchdog de la brigada Operaciones (2026-10-12, pedido de Damian: "destrabar los
    # colgados"). Si está ON, una tool de ACCIÓN (PC/celular = brigada "ops") que tarde más de
    # OPS_WATCHDOG_TIMEOUT_SECONDS se corta y devuelve error, para DESTRABAR el turno en vez de
    # quedar colgado para siempre (ej. una UI/shell que no vuelve). Default OFF para no cambiar
    # el comportamiento actual. Nota: los timeouts LLM (1800s) son otra cosa y no se tocan; esto
    # es solo para la ejecución de tools de acción, que no deberían tardar minutos. Ver agent.py.
    ops_watchdog_enabled: bool = _bool(os.getenv("OPS_WATCHDOG_ENABLED"), False)
    ops_watchdog_timeout_seconds: int = int(os.getenv("OPS_WATCHDOG_TIMEOUT_SECONDS", "300"))

    # Watchlist de Trading en background (2026-10-13): si está ON, refresca los símbolos cada
    # TRADING_WATCH_INTERVAL_MINUTES y alerta al pasar a "señal activa" (panel + espejo de chat).
    # Default OFF: gasta red (fetch de velas) y LLM (estación T8). SOLO análisis, nunca opera.
    trading_watch_loop_enabled: bool = _bool(os.getenv("TRADING_WATCH_LOOP_ENABLED"), False)
    trading_watch_interval_minutes: int = int(os.getenv("TRADING_WATCH_INTERVAL_MINUTES", "30"))

    # Aprendizaje proactivo (2026-10-13, ítem 5 del plan): si está ON, cada tanto Raphael
    # AMPLÍA por iniciativa propia un caso de investigación abierto (le suma un hallazgo) o
    # LLENA un hueco del vault (crea una nota sobre una nota citada que no existe). Default OFF:
    # gasta LLM/red. Respeta la compuerta de privacidad (lo personal nunca sale al tier 2).
    proactive_learning_enabled: bool = _bool(os.getenv("PROACTIVE_LEARNING_ENABLED"), False)
    proactive_interval_hours: float = float(os.getenv("PROACTIVE_INTERVAL_HOURS", "6"))

    # Keys de las fuentes del globo que las necesitan (batch amarillo, 2026-10-13). Vacío = esa
    # capa queda apagada (no rompe nada). Se cargan desde el panel de Configuración → .env.
    # Datos públicos de infraestructura/eventos/cámaras PUBLICADAS — nada de cámaras privadas.
    firms_map_key: str = os.getenv("FIRMS_MAP_KEY", "")        # incendios activos (NASA FIRMS)
    windy_webcams_key: str = os.getenv("WINDY_WEBCAMS_KEY", "")  # cámaras públicas (Windy Webcams)
    openweather_key: str = os.getenv("OPENWEATHER_KEY", "")     # clima (OpenWeather)
    opencellid_key: str = os.getenv("OPENCELLID_KEY", "")       # torres de celular (OpenCelliD)
    aisstream_key: str = os.getenv("AISSTREAM_KEY", "")         # barcos / AIS (AISStream, WebSocket)
    shodan_key: str = os.getenv("SHODAN_KEY", "")               # hosts expuestos (Shodan) — OSINT de infra pública
    # Query por defecto de la capa Shodan del globo (editable). Infra pública; nada de personas.
    shodan_query: str = os.getenv("SHODAN_QUERY", "product:nginx")
    # OpenCelliD es por ÁREA (no hay vista global): bbox "latSur,lonOeste,latNorte,lonEste".
    opencellid_bbox: str = os.getenv("OPENCELLID_BBOX", "-35.0,-59.0,-34.3,-58.2")

    # Personalización amigable (2026-10-11, pedido de Damian "agrega todo"). Expuesto
    # al usuario por el panel web /configuracion (app/user_config.py). assistant_name /
    # user_name / assistant_tone se inyectan en el system prompt del agente para que
    # Raphael sepa cómo se llama, cómo llamarte y en qué tono hablarte. ui_theme es la
    # paleta del panel/orbe. Son texto libre / opciones, no gates: cambiarlos no habilita
    # ninguna capacidad nueva. "Raphael" es el default del rebrand Jarvis->Raphael.
    assistant_name: str = os.getenv("ASSISTANT_NAME", "Raphael")
    user_name: str = os.getenv("USER_NAME", "")
    assistant_tone: str = os.getenv("ASSISTANT_TONE", "relajado")
    ui_theme: str = os.getenv("UI_THEME", "cian")

    # Store de propuestas de auto-reparación (ver app/selfrepair/, agregado
    # 2026-08-11 -- Opción C del diseño de auto-reparación: Jarvis puede
    # PROPONER (dry-run, sin gate) un fix a su propio código, pero aplicarlo
    # de verdad (confirm=true) requiere un proposal_id concreto que Damian
    # confirme a mano -- ver el guardrail de self-target en agent.py). Cada
    # propuesta queda acá hasta que se aplica o se descarta.
    selfrepair_dir: str = os.getenv(
        "SELFREPAIR_DIR", str(Path(__file__).resolve().parent.parent / "data" / "selfrepair")
    )

    # nmap_scan (ver app/tools/network_scan.py + app/network/) -- reconocimiento
    # de RED real (puertos, servicios, versiones, vulnerabilidades NSE), a
    # diferencia de TODO el resto del pipeline (Semgrep/Bandit/cppcheck/
    # clang-tidy/Trivy/Ruff/mypy/ESLint/tsc), que es SAST/SCA puro y solo lee
    # código/manifiestos en disco, nunca toca una red real. Prendida por
    # default porque el guardrail de scope (app/network/guardrail.py) ya la
    # hace segura por diseño -- por default SOLO puede escanear rangos
    # privados/reservados y Tailscale, nunca una IP pública, sin importar este
    # flag. Poner en false desactiva la tool nmap_scan por completo sin tocar
    # código, por si el usuario prefiere no exponerla ni siquiera con el
    # guardrail de scope activo.
    nmap_enabled: bool = _bool(os.getenv("NMAP_ENABLED"), True)

    # Whitelist explícita de IPs/rangos PÚBLICOS (o cualquier otro por fuera del
    # scope privado/loopback/Tailscale) autorizados para nmap_scan -- coma-
    # separado, cada entrada una IP suelta o un CIDR (ej.
    # "203.0.113.10,203.0.113.0/24"). VACÍO por default a propósito: el USUARIO
    # tiene que llenar esto a mano, en su propio backend/.env, con
    # infraestructura que sea suya o para la que tenga autorización explícita
    # de escanear -- ni nmap_scan ni el LLM pueden agregarse un target nuevo
    # acá por ningún argumento de la tool call (ver app/network/guardrail.py).
    # Escanear una IP/dominio público sin autorización explícita del dueño
    # puede ser ilegal (leyes de acceso no autorizado / computer fraud en la
    # mayoría de países).
    nmap_authorized_targets: str = os.getenv("NMAP_AUTHORIZED_TARGETS", "")

    # Fuente ÚNICA y compartida de autorización para TODAS las tools de
    # pentesting activo (nmap_scan ya migrado; sqlmap/tshark/metasploit/zap/
    # nessus la reusan según se van agregando, ver app/network/guardrail.py) --
    # decisión de Damian 2026-08-13: un solo archivo en vez de una whitelist
    # separada por tool, para no tener 6 listas que se puedan desincronizar.
    # Mismo criterio no negociable que NMAP_AUTHORIZED_TARGETS: el USUARIO
    # edita este archivo a mano, ninguna tool ni el LLM puede escribirlo. Un
    # target en la lista NO necesita estar corriendo/alcanzable en este
    # momento para estar "autorizado" -- los labs (PyGoat/NodeGoat/etc.) se
    # levantan bajo demanda, así que la autorización es independiente de que
    # el target esté vivo ahora mismo (eso lo valida cada tool al ejecutar,
    # nunca el gate). NMAP_AUTHORIZED_TARGETS de arriba se sigue leyendo
    # además de este archivo, por retrocompatibilidad -- no se rompe una
    # config que ya tenías andando.
    authorized_targets_path: str = os.getenv(
        "AUTHORIZED_TARGETS_PATH", str(Path(__file__).resolve().parent.parent / "authorized_targets.yaml")
    )

    # sqlmap_scan (ver app/tools/pentest_sqlmap.py + app/pentest/) -- primera
    # tool de pentesting ACTIVO del proyecto (a diferencia de nmap_scan, que
    # es reconocimiento pasivo: puertos/servicios, nunca envía payloads de
    # ataque). Gateada por el mismo guardrail no negociable de
    # authorized_targets.yaml, aplicado sobre el HOST de la URL antes de
    # correr nada. sqlmap es pura Python (sin UAC/admin, a diferencia de
    # nmap/Npcap) -- instalación manual: 'git clone --depth 1
    # https://github.com/sqlmapproject/sqlmap.git' y apuntar SQLMAP_PATH al
    # sqlmap.py resultante.
    sqlmap_enabled: bool = _bool(os.getenv("SQLMAP_ENABLED"), True)
    sqlmap_path: str = os.getenv("SQLMAP_PATH", str(Path.home() / "sqlmap-dev" / "sqlmap.py"))
    # REST API de SQLMap (sqlmapapi.py) -- SOLO localhost, nunca expuesta a
    # la red; Jarvis la arranca sola (lazy, si no está corriendo ya) cuando
    # hace falta. Credenciales HTTP Basic generadas una vez y persistidas
    # (ver app/pentest/sqlmap_client.py::_load_or_create_credentials) --
    # no hace falta configurarlas a mano.
    sqlmap_api_host: str = os.getenv("SQLMAP_API_HOST", "127.0.0.1")
    sqlmap_api_port: int = int(os.getenv("SQLMAP_API_PORT", "8775"))
    sqlmap_api_credentials_path: str = os.getenv(
        "SQLMAP_API_CREDENTIALS_PATH", str(Path(__file__).resolve().parent.parent / "sqlmap_api_credentials.json")
    )

    # packet_capture_scan / packet_capture_analyze (ver app/pentest/
    # packet_capture.py, "Wireshark" en la spec de Damian) -- implementado con
    # `scapy` (pip, sin binario externo) en vez de shellear a tshark.exe,
    # decisión documentada en el docstring del módulo. La mitad "analizar un
    # .pcap ya existente" no necesita Npcap ni nada más; la mitad "capturar en
    # vivo" sí (mismo click de UAC que nmap, ver https://npcap.com/#download).
    # Gateada distinto del resto: no hay un "target" remoto único, hay una
    # interfaz LOCAL -- exige host_filter no vacío, cada host pasa por el
    # mismo authorized_targets.yaml compartido (nunca captura sin acotar).
    packet_capture_enabled: bool = _bool(os.getenv("PACKET_CAPTURE_ENABLED"), True)
    pcap_output_dir: str = os.getenv(
        "PCAP_OUTPUT_DIR", str(Path(__file__).resolve().parent.parent.parent / "content" / "captures")
    )

    # zap_scan (ver app/tools/pentest_zap.py + app/pentest/zap_client.py,
    # checkpoint 5 -- OWASP ZAP en vez de Burp Suite Pro, decisión de Damian
    # 2026-08-13: ZAP es gratis y tiene REST API completa, Burp Pro necesita
    # licencia paga que no tiene). Gateado por el mismo guardrail no
    # negociable de authorized_targets.yaml, sobre el HOST de la URL, igual
    # que sqlmap_scan. ZAP se distribuye "Crossplatform" (zip, sin
    # instalador/UAC -- necesita Java 11+, ya presente en esta máquina) --
    # instalación manual: descargar el zip "Crossplatform" desde
    # https://github.com/zaproxy/zaproxy/releases/latest y apuntar ZAP_PATH
    # al zap-X.Y.Z.jar resultante.
    zap_enabled: bool = _bool(os.getenv("ZAP_ENABLED"), True)
    zap_path: str = os.getenv("ZAP_PATH", str(Path.home() / "zap-2.17.0" / "zap-2.17.0.jar"))
    # Daemon REST API de ZAP -- SOLO localhost, arrancado lazy por Jarvis
    # (mismo criterio que sqlmapapi.py). API key generada una vez y
    # persistida (ver app/pentest/zap_client.py::_load_or_create_api_key).
    zap_api_host: str = os.getenv("ZAP_API_HOST", "127.0.0.1")
    zap_api_port: int = int(os.getenv("ZAP_API_PORT", "8090"))
    zap_api_key_path: str = os.getenv(
        "ZAP_API_KEY_PATH", str(Path(__file__).resolve().parent.parent / "zap_api_key.json")
    )

    # opencode_run_task (ver app/tools/opencode.py, agregado 2026-08-11) --
    # delega tareas pesadas de escritura/edición de código a la CLI de
    # OpenCode (github.com/sst/opencode, MIT), apuntada al mismo Ollama local
    # que ya sirve jarvis-text-v2 (ver provider "jarvis-ollama" en
    # ~/.config/opencode/opencode.json) en vez de al propio loop de agente de
    # Jarvis. Mismo binario para todas las instalaciones por default (instalado
    # vía `curl -fsSL https://opencode.ai/install | bash`, que en Windows deja
    # el .exe en %USERPROFILE%\.opencode\bin) -- configurable por si en otra
    # máquina quedó en otro lado.
    opencode_bin_path: str = os.getenv(
        "OPENCODE_BIN_PATH", str(Path.home() / ".opencode" / "bin" / "opencode.exe")
    )
    opencode_default_model: str = os.getenv("OPENCODE_DEFAULT_MODEL", "jarvis-ollama/jarvis-text-v2")

    # cloud_expert_code/cloud_expert_marketing (ver app/tools/cloud_expert.py,
    # agregado 2026-08-12) -- delegan a Gemini Flash (API gratuita de Google
    # AI Studio, ~15 req/min y 1M tokens/día en el free tier, sin tarjeta) un
    # primer borrador de código o de texto de marketing. Reusa el SDK de
    # OpenAI (mismo patrón que llm_client.py) apuntado al endpoint
    # OpenAI-compatible real de Gemini (generativelanguage.googleapis.com/
    # v1beta/openai/), en vez de escribir un cliente REST propio -- Google
    # publica esta compatibilidad justamente para no tener que reimplementar
    # el cliente por proveedor. Vacío por default a propósito: sin
    # GOOGLE_AI_API_KEY seteada en backend/.env, ambas tools fallan con un
    # error claro en vez de intentar una llamada que va a rechazar la API.
    google_ai_api_key: str = os.getenv("GOOGLE_AI_API_KEY", "")
    google_ai_base_url: str = os.getenv(
        "GOOGLE_AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    google_ai_model: str = os.getenv("GOOGLE_AI_MODEL", "gemini-2.5-flash")

    # Perfil de investigación científica (ver app/obsidian/profile.py +
    # app/agent.py, agregado 2026-08-12) -- vault y directorio de trabajo
    # SEPARADOS del vault/codebase de seguridad de JarvisRemote, para que
    # Damian pueda usar a Jarvis como asistente de su propia investigación
    # de biotecnología sin mezclar esas notas con las de auditoría de
    # código. Mismo backend/modelo que el perfil default -- no es una
    # segunda instancia corriendo en paralelo (12GB de VRAM no da para dos
    # modelos grandes a la vez), es un cambio de contexto dentro de la
    # misma conversación/proceso.
    research_vault_path: str = os.getenv(
        "RESEARCH_VAULT_PATH", str(Path(__file__).resolve().parent.parent / "obsidian_vault_investigacion")
    )
    research_embeddings_path: str = os.getenv(
        "RESEARCH_EMBEDDINGS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "research_embeddings.json")
    )
    research_working_dir: str = os.getenv(
        "RESEARCH_WORKING_DIR", str(Path.home() / "Documents" / "Investigacion")
    )

    # Módulo de investigación (análisis de enlaces y evidencia digital, ver
    # app/investigation/ -- spec de Damian, 2026-08-12). Tres directorios
    # separados a propósito, mismo criterio que el resto del proyecto
    # (nunca mezclar cache/datos derivados con el vault/repo real):
    # - investigation_cases_dir: un subdirectorio por caso, CADA UNO su
    #   propio repo git (versiona grafo/log/metadata -- nunca los binarios).
    # - investigation_artifact_store_dir: almacén único, compartido entre
    #   TODOS los casos, de solo lectura, indexado por sha256 -- NUNCA
    #   versionado con git (decisión explícita de Damian: los binarios
    #   originales no van a git).
    # - investigation_keys_dir: clave de firma Ed25519 del log append-only
    #   (ver app/investigation/keys.py), protegida con DPAPI -- vive fuera
    #   de cualquier directorio versionado o exportable por accidente.
    investigation_cases_dir: str = os.getenv(
        "INVESTIGATION_CASES_DIR", str(Path(__file__).resolve().parent.parent / "investigation_cases")
    )
    investigation_artifact_store_dir: str = os.getenv(
        "INVESTIGATION_ARTIFACT_STORE_DIR",
        str(Path(__file__).resolve().parent.parent / "data" / "investigation_artifacts"),
    )
    investigation_keys_dir: str = os.getenv(
        "INVESTIGATION_KEYS_DIR", str(Path(__file__).resolve().parent.parent / "data" / "investigation_keys")
    )

    # Variante del SYSTEM_PROMPT (ablación, 2026-09-28, ver
    # docs/ABLACION-system-prompt.md). "full" = el prompt completo de siempre
    # (default, comportamiento idéntico al anterior). "slim" = la versión
    # adelgazada (tarea+guardrails+criterio, filtrada con la regla de las 3R,
    # conservando cada gate). Es para A/B medido: NO cambia nada hasta que se
    # setea a "slim". OJO: el prompt óptimo depende del modelo -- un modelo
    # fuerte (cloud) aguanta 'slim', uno local chico (8B) puede necesitar 'full'.
    system_prompt_variant: str = os.getenv("SYSTEM_PROMPT_VARIANT", "full")

    # ------------------------------------------------------------------
    # Ruteo de modelos por tarea. Con la única key de OpenRouter se accede a todos por
    # slug. Esquema de 5 tiers (Damian 2026-10-06, ver app/harness/routing.py):
    #   0 = sin modelo (determinista) · 1 = local (jobs programados) · 2 = free/operativo ·
    #   3 = Sonnet 5.5 (pesado) · 4 = especial (el más potente, hoy Opus). El planner de
    #   abajo es el tier "especial" en la práctica: usa su propia config (Opus) a demanda.
    # ------------------------------------------------------------------
    # Modelo "planificador": el loop principal (Sonnet) le delega planificación
    # dura a Opus vía la tool `planear_con_opus`. Opus planea, Sonnet ejecuta.
    planner_enabled: bool = _bool(os.getenv("PLANNER_ENABLED"), True)
    planner_model: str = os.getenv("PLANNER_MODEL", "anthropic/claude-opus-5.5")
    # Endpoint/key del planificador: por default reusa el del chat (OpenRouter),
    # ya que Opus vive en la misma cuenta. Se puede separar si algún día hace falta.
    planner_base_url: str = os.getenv("PLANNER_BASE_URL", "") or os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    planner_api_key: str = os.getenv("PLANNER_API_KEY", "") or (os.getenv("LLM_API_KEY", "lm-studio"))
    # "Esfuerzo" de razonamiento del planificador (extended thinking de Claude):
    # más presupuesto = mejor plan, más costo/latencia. Se manda como
    # reasoning_effort si el proveedor lo soporta; si no, se ignora sin romper.
    planner_reasoning_effort: str = os.getenv("PLANNER_REASONING_EFFORT", "high")

    # Persistencia del registro de modelo por estación (2026-09-29, pedido de
    # Damian). Los overrides que se setean desde la consola de la tray se guardan
    # a disco (SIN api keys) y se recargan al arrancar, para que el ruteo
    # sobreviva un reinicio del backend. Las keys se heredan del default global
    # cuando el base_url coincide (mismo proveedor), nunca se escriben en claro.
    model_registry_path: str = os.getenv(
        "MODEL_REGISTRY_PATH", str(Path(__file__).resolve().parent.parent / "data" / "model_registry.json")
    )

    # Endpoint LOCAL (Ollama) para el tier 1 (modelos baratos/locales tipo
    # jarvis-text-*). El base_url GLOBAL hoy apunta a OpenRouter (cloud), así que
    # los modelos locales necesitan su propio endpoint. El clasificador de
    # endpoints (model_registry.endpoint_for_model) manda los slugs con "/"
    # (anthropic/..., deepseek/...) a OpenRouter y los nombres locales acá.
    local_model_base_url: str = os.getenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
    local_model_api_key: str = os.getenv("LOCAL_MODEL_API_KEY", "ollama")

    # Variante de los prompt_fragments de skills (misma ablación, 2026-09-28).
    # "full" = fragmentos completos de siempre (default). "slim" = usa la versión
    # adelgazada del fragmento cuando el skill tiene una definida (si no, cae al
    # full). A/B medido, mismo criterio de modelo que system_prompt_variant.
    skills_prompt_variant: str = os.getenv("SKILLS_PROMPT_VARIANT", "full")

    # ------------------------------------------------------------------
    # Memoria episódica (ver docs/SPEC-memoria-episodica.md, 2026-09-28 +
    # app/memory/). Continuidad autobiográfica de Raphael: qué vivió, qué
    # decidió Damian, qué salió bien/mal. Distinta del vault (memoria
    # semántica). Captura automática al cierre de turno, store firmado
    # (reusa la clave Ed25519 de investigation_keys_dir), espejo en el grafo.
    # ------------------------------------------------------------------
    # Apagador global (toda capacidad invasiva tiene el suyo). Prendida por
    # default -- es el punto de la feature (que Raphael recuerde sin que
    # Damian tenga que pedirlo). La captura por default es BARATA (heurística,
    # sin LLM); el destilado con LLM es opt-in (episodic_memory_distill_llm).
    episodic_memory_enabled: bool = _bool(os.getenv("EPISODIC_MEMORY_ENABLED"), True)

    # Directorio del store episódico (JSON de episodios + log firmado + crudo).
    # Fuera del repo versionado, como el resto de los datos derivados.
    episodic_memory_dir: str = os.getenv(
        "EPISODIC_MEMORY_DIR", str(Path(__file__).resolve().parent.parent / "data" / "episodic_memory")
    )

    # Destilado con LLM (Decisión 3 del spec: split técnico=cloud / personal=
    # local). Off por default en Fase 1: sin esto, el episodio se arma con una
    # heurística barata (sin costo ni latencia de LLM). Prenderlo activa el
    # resumen por modelo -- los episodios `personal` SIEMPRE se destilan local
    # aunque el cerebro esté en cloud (nunca salen a la nube).
    episodic_memory_distill_llm: bool = _bool(os.getenv("EPISODIC_MEMORY_DISTILL_LLM"), False)

    # Ventana del recall automático (Decisión 6: últimas 24 h). Configurable.
    recall_window_hours: int = int(os.getenv("RECALL_WINDOW_HOURS", "24"))

    # Zona horaria de Damian para los timestamps mostrados (Rosario/Argentina,
    # UTC-3). Se guarda absoluto/ISO por dentro; esto es solo para mostrar.
    memory_display_tz: str = os.getenv("MEMORY_DISPLAY_TZ", "America/Argentina/Cordoba")

    # Módulo de protección contra malware (ver app/malware/ -- spec de
    # Damian, 2026-08-16). Motor: YARA (reglas de firmas + heurística propia)
    # + ClamAV (clamd, firmas masivas) + capa conductual (watchdog/psutil)
    # desde el arranque, ninguno como fase 2. Reusa el MISMO artifact_store
    # de app/investigation/ (INVESTIGATION_ARTIFACT_STORE_DIR de arriba, no
    # una copia separada) y el mismo mecanismo de firma Ed25519
    # (investigation/keys.py, mismo INVESTIGATION_KEYS_DIR) para su propio
    # log append-only -- decisión de diseño C de la ronda de preguntas: un
    # hallazgo de malware queda igual de trazable/verificable que un caso de
    # investigación, sin forzarlo dentro del modelo de "caso" (que es sobre
    # personas/timelines, un dominio distinto).
    malware_log_path: str = os.getenv(
        "MALWARE_LOG_PATH", str(Path(__file__).resolve().parent.parent / "data" / "malware_log.jsonl")
    )

    # Carpeta donde se mueven los archivos sospechosos en cuarentena (fuera de
    # cualquier ruta ejecutable/de inicio automático) -- reversible por
    # default (mover, no borrar, decisión de la pregunta 3: cuarentena por
    # default, eliminación definitiva solo con confirm=true explícito, mismo
    # patrón dry-run->confirm=true que code_apply_fix).
    malware_quarantine_dir: str = os.getenv(
        "MALWARE_QUARANTINE_DIR", str(Path(__file__).resolve().parent.parent / "data" / "malware_quarantine")
    )

    # Reglas YARA -- directorio con archivos .yar/.yara, cargados todos al
    # compilar. Viene con un set inicial propio (ver
    # app/malware/rules/starter.yar) mas lo que Damian agregue a mano (ej.
    # reglas descargadas de github.com/Yara-Rules/rules o similares).
    malware_yara_rules_dir: str = os.getenv(
        "MALWARE_YARA_RULES_DIR", str(Path(__file__).resolve().parent.parent / "app" / "malware" / "rules")
    )

    # FIM (File Integrity Monitoring, auto-protección parte A) -- manifiesto
    # baseline (hash SHA-256 por archivo vigilado) y lista de archivos/carpetas
    # críticos de la propia instalación de Jarvis. Coma-separado, rutas
    # absolutas o relativas a backend/. Default: el gate de pentesting
    # (authorized_targets.yaml), las claves de firma del módulo de
    # investigación (que ahora también firman el log de malware), el .env con
    # credenciales en texto plano, y el código fuente de app/ entero (para
    # detectar una modificación no versionada -- ej. inyectada por un proceso
    # malicioso -- antes del próximo `git status`).
    malware_integrity_baseline_path: str = os.getenv(
        "MALWARE_INTEGRITY_BASELINE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "malware_integrity_baseline.json")
    )
    malware_integrity_watch_paths: str = os.getenv(
        "MALWARE_INTEGRITY_WATCH_PATHS",
        ",".join([
            str(Path(__file__).resolve().parent.parent / "authorized_targets.yaml"),
            str(Path(__file__).resolve().parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent / "data" / "investigation_keys"),
            str(Path(__file__).resolve().parent.parent / "app"),
        ]),
    )

    # Vigilancia del proceso propio (auto-protección parte B, ver
    # app/malware/process_monitor.py) -- procesos hijos inesperados del PID
    # del backend y conexiones salientes fuera de lo esperado (LM Studio/
    # Ollama local, ClamAV local, VirusTotal, Tailscale). Prendida por
    # default (mismo criterio que el resto de las tools "sin fricción" del
    # proyecto), con flag real para apagarla.
    malware_process_monitor_enabled: bool = _bool(os.getenv("MALWARE_PROCESS_MONITOR_ENABLED"), True)

    # ClamAV real vía el daemon `clamd` -- requiere instalación manual (ver
    # backend/README.md, sección malware) + el servicio `clamd` corriendo en
    # esta IP/puerto. Sin eso, malware_scan_path sigue funcionando con YARA +
    # heurística conductual, solo se salta ClamAV con un aviso explícito (no
    # falla el escaneo entero por una pieza optativa no instalada).
    clamd_host: str = os.getenv("CLAMD_HOST", "127.0.0.1")
    clamd_port: int = int(os.getenv("CLAMD_PORT", "3310"))
    clamav_enabled: bool = _bool(os.getenv("CLAMAV_ENABLED"), True)

    # VirusTotal -- SOLO confirmación selectiva de hashes ya marcados
    # sospechosos localmente (decisión de la pregunta 5), nunca sube contenido
    # de archivos. Vacío por default: sin VIRUSTOTAL_API_KEY, esa capa se
    # salta con un aviso explícito (mismo criterio que GOOGLE_AI_API_KEY).
    # Sacar una key gratis en https://www.virustotal.com/gui/join-us.
    virustotal_api_key: str = os.getenv("VIRUSTOTAL_API_KEY", "")
    virustotal_cache_path: str = os.getenv(
        "VIRUSTOTAL_CACHE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "virustotal_cache.json")
    )
    # Límite real del tier gratis: 4 req/min. Se deja margen (15s entre
    # consultas = 4/min exacto) para no comerse baneos temporales por ráfagas.
    virustotal_min_seconds_between_requests: float = float(os.getenv("VIRUSTOTAL_MIN_SECONDS_BETWEEN_REQUESTS", "15"))

    # Sysmon (Sysinternals/Microsoft, driver YA firmado -- no es un driver
    # propio) -- capa EXPERIMENTAL de auto-protección parte C (detección tipo
    # EDR real: acceso a memoria del propio proceso, hijos remotos, etc.).
    # Instalación manual (ver backend/README.md). Apagada por default a
    # propósito: a diferencia del resto de este módulo (A+B, sólidos), C se
    # documentó explícitamente como experimental -- Damian eligió sumarla
    # igual sabiendo que la señal puede ser ruidosa/no confiable, así que
    # arranca en false hasta que la instale y la prenda a mano.
    sysmon_enabled: bool = _bool(os.getenv("SYSMON_ENABLED"), False)
    sysmon_event_log_channel: str = os.getenv("SYSMON_EVENT_LOG_CHANNEL", "Microsoft-Windows-Sysmon/Operational")

    # Escaneo completo del árbol bajo FS_ALLOWED_ROOT, corrido una vez cada 24h
    # (decisión de la pregunta 2: escaneo diario, no semanal) por un loop en
    # background arrancado en el startup del backend (ver app/main.py) --
    # ninguna configuración de Task Scheduler de Windows necesaria aparte.
    # Ojo: NO es "todo el disco C:\" literal (Windows/Program Files incluidos
    # sería enormemente más lento y en su mayoría archivos del sistema que
    # Windows Defender ya cubre) -- es el árbol completo de FS_ALLOWED_ROOT
    # (la carpeta de usuario), que es lo que en la práctica contiene los
    # archivos que el propio Damian descarga/crea/recibe. Configurable si
    # de verdad se quiere escanear otra raíz.
    malware_full_scan_enabled: bool = _bool(os.getenv("MALWARE_FULL_SCAN_ENABLED"), True)
    malware_full_scan_interval_hours: float = float(os.getenv("MALWARE_FULL_SCAN_INTERVAL_HOURS", "24"))

    # Vigilante de la playlist de YouTube (2026-10-05): tarea en background que cada
    # cierto rato revisa la playlist "Info para Jarvis" y INGIERE automáticamente los
    # videos nuevos. Reusa el pipeline idempotente (dedup por video ID), así que si no
    # hay videos nuevos el chequeo es barato (solo yt-dlp, sin llamar al LLM). Corre en
    # background, NO por el endpoint HTTP del chat -> no sufre el timeout de la tray.
    # ⚠️ Cuando SÍ hay videos nuevos, cada uno consume el LLM activo (lento en local,
    # con costo en Sonnet/OpenRouter). Apagable sin tocar código.
    playlist_watch_enabled: bool = _bool(os.getenv("PLAYLIST_WATCH_ENABLED"), True)
    # Default 3 min (pedido de Damian 2026-10-05): revisa seguido para que un video
    # recién guardado se ingiera casi al toque. Barato cuando no hay novedad (solo
    # yt-dlp, sin LLM). El loop duerme DESPUÉS de terminar, así que si una pasada con
    # videos nuevos tarda más de 3 min, no se encima: el próximo chequeo es 3 min
    # después de terminar, no 3 min después de arrancar.
    playlist_watch_interval_minutes: float = float(os.getenv("PLAYLIST_WATCH_INTERVAL_MINUTES", "3"))
    # Tope de videos NUEVOS a procesar por pasada (para que un backlog grande no haga
    # una corrida maratónica; lo que sobra entra en el próximo ciclo). 0 = sin tope.
    playlist_watch_max_per_run: int = int(os.getenv("PLAYLIST_WATCH_MAX_PER_RUN", "8"))
    # URL de la playlist a vigilar. Vacío = la playlist default del módulo de ingesta.
    playlist_watch_url: str = os.getenv("PLAYLIST_WATCH_URL", "")

    # Consolidación de memoria -- el "sueño" (2026-10-05, Fase 3 de la estructura
    # cerebro-símil, ver app/obsidian/consolidation.py). Job en background que agrupa
    # notas recientes relacionadas y escribe notas de SÍNTESIS (aditivas, nunca borra).
    # ⚠️ Default APAGADO: escribe en el vault con el LLM, se prende a conciencia. La
    # tool manual (memoria_consolidar) corre en dry-run por default para ver antes.
    consolidation_enabled: bool = _bool(os.getenv("CONSOLIDATION_ENABLED"), False)
    consolidation_interval_hours: float = float(os.getenv("CONSOLIDATION_INTERVAL_HOURS", "24"))
    consolidation_lookback_days: int = int(os.getenv("CONSOLIDATION_LOOKBACK_DAYS", "7"))
    consolidation_max_clusters_per_run: int = int(os.getenv("CONSOLIDATION_MAX_CLUSTERS_PER_RUN", "3"))
    # 2026-11-12 (Ronda 2 de Cerebro): 0.6 era muy flojo. Con nomic-embed-text-v1.5 un distractor sin relación puntúa
    # 0.74-0.77 contra las notas correctas (que puntúan ~0.91 entre sí) y se agrupaba, mezclando temas. Ahora el umbral
    # absoluto es 0.85 Y hay una brecha relativa (CONSOLIDATION_SIMILARITY_GAP): un par tiene que estar a lo sumo 0.08
    # por debajo de la mejor similitud de cualquiera de sus notas. Si cambia el modelo de embeddings, RECALIBRAR.
    consolidation_similarity_threshold: float = float(os.getenv("CONSOLIDATION_SIMILARITY_THRESHOLD", "0.85"))
    consolidation_similarity_gap: float = float(os.getenv("CONSOLIDATION_SIMILARITY_GAP", "0.08"))

    # Tier 2 (operativo/barato, 2026-10-06): modelos FREE de OpenRouter, rotativos
    # ("empleado descartable": si uno se cae o lo rate-limitean, la cascada salta al
    # siguiente). Lista separada por comas, env-configurable para cambiarlos sin tocar
    # código cuando OpenRouter rote su catálogo free. Son tool-capable (manejo de
    # navegador / búsqueda de archivos). ⚠️ SOLO tareas NO sensibles: los free pueden
    # rutear data a terceros, así que nada del vault personal (Fénix) va por el tier 2.
    tier2_free_models: str = os.getenv(
        "TIER2_FREE_MODELS",
        "meta-llama/llama-3.3-70b-instruct:free,openai/gpt-oss-120b:free,nvidia/nemotron-3-super-120b-a12b:free",
    )
    # Endpoint del tier 2 (2026-10-07, idea de Damian): por default vacío = OpenRouter
    # (los slugs free van ahí). Si se setea, el tier 2 apunta a ESE gateway OpenAI-compatible
    # -- pensado para **OmniRoute** (gateway local open-source que rota 90+ proveedores free
    # con fallback por cuota + compresión de prompts). OmniRoute corre en
    # `http://localhost:20128/v1`; poné ahí TIER2_BASE_URL y en TIER2_FREE_MODELS los
    # nombres de ruta/modelo que definas en su dashboard. Sigue aplicando la compuerta de
    # privacidad: lo personal NUNCA sale por el tier 2.
    tier2_base_url: str = os.getenv("TIER2_BASE_URL", "")
    tier2_api_key: str = os.getenv("TIER2_API_KEY", "not-needed")

    # Override de endpoint/key/modelo POR TIER (2026-10-11, pedido de Damian: "poner api
    # para cada tier excepto los deterministas"). Hasta ahora el endpoint/key de cada tier
    # se DERIVABA del nombre del modelo (model_registry.endpoint_for_model): slugs con "/"
    # -> nube global (LLM_API_KEY), nombres locales -> Ollama. Con esto, cada tier (1 local,
    # 3 Sonnet, 4 Opus; el 2 ya tiene TIER2_*) puede tener su PROPIA API: útil para, por ej.,
    # apuntar el tier 4 directo a Anthropic y el 3 a OpenRouter. Todo VACÍO por default =
    # idéntico al comportamiento anterior (se cae a la derivación por nombre / nube global).
    # Lo consume model_registry.client_and_model_for_tier / endpoint_for_model(tier=...).
    # El tier 0 (determinista) no tiene modelo, por eso no aparece acá.
    tier1_model: str = os.getenv("TIER1_MODEL", "")
    tier1_base_url: str = os.getenv("TIER1_BASE_URL", "")
    tier1_api_key: str = os.getenv("TIER1_API_KEY", "")
    tier3_model: str = os.getenv("TIER3_MODEL", "")
    tier3_base_url: str = os.getenv("TIER3_BASE_URL", "")
    tier3_api_key: str = os.getenv("TIER3_API_KEY", "")
    tier4_model: str = os.getenv("TIER4_MODEL", "")
    tier4_base_url: str = os.getenv("TIER4_BASE_URL", "")
    tier4_api_key: str = os.getenv("TIER4_API_KEY", "")

    # Compuerta de PRIVACIDAD (Etapa C, 2026-10-06): carpetas del vault consideradas
    # SENSIBLES (material personal / Fénix). Su contenido NUNCA se rutea al tier 2 (free,
    # que puede mandar data a terceros): va al `OBSIDIAN_SENSITIVE_TIER` (default 1 =
    # local, gratis y privado; se puede poner 3 = Sonnet si se quiere competencia).
    obsidian_sensitive_dirs: str = os.getenv(
        "OBSIDIAN_SENSITIVE_DIRS", "02-Fénix,01-Bitácora,04-Revisiones,05-Archivo,07-Conciencia,03-Biotecnología"
    )
    obsidian_sensitive_tier: int = int(os.getenv("OBSIDIAN_SENSITIVE_TIER", "1"))

    # Curiosidad (Etapa C): job en background que detecta huecos del vault (links
    # colgados, notas huérfanas, lo nuevo sin conectar) y los SURGE (solo-avisar por
    # default). Default APAGADO; se prende a conciencia. Tier 0 para detectar (sin modelo).
    curiosity_enabled: bool = _bool(os.getenv("CURIOSITY_ENABLED"), False)
    curiosity_interval_hours: float = float(os.getenv("CURIOSITY_INTERVAL_HOURS", "12"))

    # Hook automático del lazo de aprendizaje (Etapa B): al cerrar un turno que FALLÓ
    # (excepción), marca aversivamente -con piso- las notas que estaban en juego (el
    # último rastro de activación). El refuerzo POSITIVO queda explícito (tool
    # obsidian_resultado) para no reforzar todo por inercia. Conservador; apagable.
    feedback_auto_enabled: bool = _bool(os.getenv("FEEDBACK_AUTO_ENABLED"), True)

    # Carpetas de primer nivel del vault que el lector IGNORA además de las de sistema
    # (las que empiezan con "." o "_"). Lista separada por comas. Vacío = no excluir
    # nada extra. Para dejar afuera material personal de una carpeta puntual sin sacarlo
    # del vault (2026-10-05, al unificar la lectura de TODO Vault-Fenix).
    obsidian_excluded_dirs: str = os.getenv("OBSIDIAN_EXCLUDED_DIRS", "")
    # vacío = usa el HOME del usuario (Path.home()). Ojo: a partir del
    # 2026-08-19 esto NO reusa fs_allowed_root (que se achicó del HOME a la
    # raíz del proyecto) -- el barrido antimalware necesita cubrir toda la
    # carpeta del usuario (Descargas/Documentos/etc.), no solo el proyecto.
    # Ver app/malware/fullscan.py::run_full_scan.
    malware_full_scan_root: str = os.getenv("MALWARE_FULL_SCAN_ROOT", "")

    # Carpetas de riesgo típico para el escaneo "on-access" (YARA+ClamAV sobre
    # cada archivo nuevo apenas aparece, vía watchdog) -- coma-separado.
    # Default: Descargas/Escritorio/Temp del usuario actual.
    malware_watch_folders: str = os.getenv(
        "MALWARE_WATCH_FOLDERS",
        ",".join([
            str(Path.home() / "Downloads"),
            str(Path.home() / "Desktop"),
            os.getenv("TEMP", str(Path.home() / "AppData" / "Local" / "Temp")),
        ]),
    )

    # Credenciales generadas por Jarvis al completar formularios/registros web
    # (ver app/tools/web_forms.py + app/forms/credential_store.py) -- cifradas
    # con DPAPI, mismo mecanismo que investigation_keys_dir de arriba (ver ese
    # módulo para el razonamiento completo). Decisión de la ronda de
    # preguntas de "formularios web" 2026-08-16: Damian pidió guardarlas en
    # un archivo (no solo mostrarlas una vez en el chat) -- texto plano fue
    # descartado a propósito, mismo antipatrón ya señalado sobre .env.
    form_credentials_path: str = os.getenv(
        "FORM_CREDENTIALS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "form_credentials.dpapi")
    )

    # Capturas de pantalla del dry-run de browser_preview_submit (ver
    # app/tools/web_forms.py) -- previsualización real de qué se va a enviar
    # ANTES de tocar el botón de submit, pedido explícito de Damian (sin
    # excepción, ni para formularios simples de un par de campos).
    form_preview_dir: str = os.getenv(
        "FORM_PREVIEW_DIR", str(Path(__file__).resolve().parent.parent / "data" / "form_previews")
    )

    # TTL (segundos) del "preview token" de un solo uso que ata el dry-run de
    # browser_preview_submit al submit real (ver app/tools/web_forms.py,
    # 2026-08-17). El gate de consentimiento del envío de formularios dejó de
    # depender SOLO del prompt del modelo: ahora el código exige que confirm=true
    # traiga un token emitido por un dry-run reciente para ESE mismo
    # submit_selector+página, no reusado y no vencido -- mismo espíritu que el
    # proposal_id de selfrepair. TTL corto a propósito: la confirmación de Damian
    # llega en el mismo intercambio de chat; si pasan minutos, es más seguro
    # obligar a un dry-run nuevo (la página pudo cambiar debajo).
    form_preview_token_ttl_seconds: int = int(os.getenv("FORM_PREVIEW_TOKEN_TTL_SECONDS", "300"))

    # ------------------------------------------------------------------
    # Capa de navegación de agente (ver docs/SPEC-capa-navegacion-de-agente.md,
    # 2026-09-27). La tool `web_get` (app/tools/web_get.py) es el "sistema
    # sensorial y motor" de Raphael para la web: fetch escalado, representación
    # compacta, cache versionado, login con custodia de credenciales.
    # ------------------------------------------------------------------

    # Motor del piso 'dynamic' (SPAs con mucho JS): Edge YA instalado del
    # sistema (`channel="msedge"`), NO el Chromium bundleado de Playwright.
    # Decisión 3 del spec: en esta PC el Chromium propio de Playwright falla al
    # arrancar por la firma SxS/antivirus (bug ya documentado en browser.py);
    # Edge es el mismo motor Chromium pero firmado y confiado por Windows.
    web_dynamic_channel: str = os.getenv("WEB_DYNAMIC_CHANNEL", "msedge")

    # Proxies / rotación de IP (Decisión 4). PREPARADO y ENCENDIDO, pero solo
    # entra como ESCALÓN EXTRA cuando un sitio bloquea por IP -- si está vacío
    # (default) o la conexión directa anda, se usa la IP directa. Nunca frena
    # el caso normal. Lista coma/;-separada de URLs de proxy (http://host:port).
    web_proxies: list[str] = _split_paths(os.getenv("WEB_PROXIES"))

    # Deny-list de dominios (Decisión 10). Arranca VACÍA -- Damian todavía no
    # tiene a nadie que vetar. El mecanismo queda listo: agregar un dominio acá
    # (coma-separado) lo bloquea de entrada sin tocar código. NO hay allowlist:
    # Raphael entra a donde Damian le pida por chat.
    web_deny_domains: list[str] = _split_paths(os.getenv("WEB_DENY_DOMAINS"))

    # Allowlist de LOGIN por dominio (Decisión 9). Raphael solo intenta
    # loguearse en dominios que Damian agregó explícitamente acá -- fuente de
    # verdad que el LLM NO reescribe (mismo espíritu que authorized_targets.yaml
    # del pentest). Un sitio fuera de la lista => no loguea, avisa.
    web_login_allowlist: list[str] = _split_paths(os.getenv("WEB_LOGIN_ALLOWLIST"))

    # Credenciales web que Raphael custodia (Decisión 9/9-bis) -- cifradas con
    # DPAPI, MISMO store que las de formularios (app/forms/credential_store.py),
    # pero en archivo aparte para separar "credenciales que Damian confió para
    # loguear" de "contraseñas que Jarvis generó al registrarse en un form".
    web_credentials_path: str = os.getenv(
        "WEB_CREDENTIALS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "web_credentials.dpapi")
    )

    # Cache versionado de páginas (Decisión 7): hasta N versiones por URL dentro
    # de una ventana de D días. Sirve para no re-descargar Y para comparar cómo
    # cambió una página en la semana (deltas de noticias/datos para trading y
    # war tracker). Forzar refetch con el flag `fresh=true` de web_get.
    web_cache_dir: str = os.getenv(
        "WEB_CACHE_DIR", str(Path(__file__).resolve().parent.parent / "data" / "web_cache")
    )
    web_cache_max_versions: int = int(os.getenv("WEB_CACHE_MAX_VERSIONS", "5"))
    web_cache_window_days: int = int(os.getenv("WEB_CACHE_WINDOW_DAYS", "7"))

    # Grabación de pantalla real (ffmpeg, ver app/recording.py) -- se activa
    # sola alrededor de cualquier tool de la familia auditoría/fix/test (ver
    # app/tools/__init__.py::_RECORDABLE_TOOL_NAMES) para documentar el
    # trabajo de Jarvis de punta a punta con contenido real, pedido explícito
    # de Damian 2026-08-13. Tan sensible en privacidad como
    # DESKTOP_CONTROL_ENABLED (graba TODO el escritorio, no solo la ventana
    # relevante -- cualquier otra cosa visible en pantalla en ese momento
    # queda en el video) -- prendida por default porque ESE es el punto de la
    # feature (capturar sin que Damian tenga que acordarse de arrancarla a
    # mano cada vez), pero con un apagador real y efectivo por si en algún
    # momento hay algo en pantalla que no debería quedar grabado.
    screen_recording_enabled: bool = _bool(os.getenv("SCREEN_RECORDING_ENABLED"), True)

    # Carpeta de salida de las grabaciones -- a propósito en la RAÍZ del repo
    # (content/recordings/, hermana de backend/, no adentro de backend/):
    # esto es contenido humano/de publicación (mismo criterio que
    # Fundamentos_de_Jarvis.docx, que también vive en la raíz), no un dato
    # operativo del backend como investigation_cases_dir o selfrepair_dir.
    recording_output_dir: str = os.getenv(
        "RECORDING_OUTPUT_DIR", str(Path(__file__).resolve().parent.parent.parent / "content" / "recordings")
    )


settings = Settings()

if settings._api_key_was_generated:
    print(
        "[jarvis-backend] No API_KEY set in .env — generated one for this run:\n"
        f"  {settings.api_key}\n"
        "  Set API_KEY in backend/.env to keep it stable across restarts."
    )
