"""Banco de pedidos ETIQUETADOS para medir y calibrar el ruteo del orquestador (O-1).

Cada entrada: (pedido, brigada esperada). Son pedidos inventados, del estilo de los que Damian le hace a Raphael; ninguno
sale de su vault ni de sus conversaciones. Criterio de etiquetado (el mismo sesgo de seguridad del ruteo):

  - `investigacion`  pide salir a la WEB (investigar algo nuevo, noticias, papers) o trabajar la EVIDENCIA de un caso
                     (archivos, chats, CSV, imágenes, entidades, fusiones, informe del caso).
  - `cerebro`        pregunta por lo que YA está guardado (notas, memoria, vault), o es ambiguo / charla: ante la duda, la
                     opción de menor daño (solo lectura; no manda nada a la web ni crea nada).

Se usa en `tests/test_optimizaciones.py` (exactitud de las reglas y % resuelto sin LLM) y en `python -m validation.medir ruteo`
(lo mismo + el clasificador LLM real sobre lo que las reglas no resuelven). Sumar un pedido mal ruteado acá ES la forma de
arreglarlo: primero falla el test, después se ajusta la regla.
"""

from __future__ import annotations

BANCO: tuple[tuple[str, str], ...] = (
    # --- Cerebro: lo que ya está guardado -------------------------------------------------------------------------------
    ("¿Qué sé de ransomware?", "cerebro"),
    ("¿Qué tengo guardado sobre la rotación de claves del servidor?", "cerebro"),
    ("Buscá en mis notas lo que anoté de CRISPR", "cerebro"),
    ("¿Qué dice mi vault sobre el plan de migración a Linux?", "cerebro"),
    ("Recordame qué decidimos sobre el umbral de consolidación", "cerebro"),
    ("¿Cada cuántos días se rotan las claves del servidor Orión?", "cerebro"),
    ("¿Qué anoté la semana pasada sobre el watchdog?", "cerebro"),
    ("Conectá lo que sé de embeddings con lo que sé de spreading activation", "cerebro"),
    ("¿Tengo alguna nota sobre Tailscale?", "cerebro"),
    ("Resumime lo que guardé de la charla de midudev", "cerebro"),
    ("¿Qué conclusiones saqué del experimento JEV?", "cerebro"),
    ("Según mis notas, ¿quién es el responsable del script de rotación?", "cerebro"),
    ("¿Qué sabemos del modelo de delegación de las brigadas?", "cerebro"),
    ("Decime qué hay en la memoria sobre el proyecto Fénix", "cerebro"),
    ("¿Dónde dejé apuntado lo del cyber range?", "cerebro"),
    ("¿Qué aprendiste de la playlist de esta semana?", "cerebro"),
    ("Repasame mis apuntes de transformers", "cerebro"),
    ("¿Qué relación hay entre mis notas de hebbiano y las de olvido?", "cerebro"),
    ("¿Te acordás de lo que hablamos del gate firmado?", "cerebro"),
    ("¿Cuál era el puerto del orquestador?", "cerebro"),
    # --- Cerebro por menor daño: ambiguos, charla, sin señal ---------------------------------------------------------------
    ("hola", "cerebro"),
    ("¿Cómo venimos?", "cerebro"),
    ("Necesito ayuda con algo", "cerebro"),
    ("Explicame qué es un transformer", "cerebro"),
    ("¿Qué opinás de pasar todo a un modelo local?", "cerebro"),
    ("Dame ideas para ordenar la semana", "cerebro"),
    ("¿Qué es mejor, Semgrep o Bandit?", "cerebro"),
    ("gracias, quedó claro", "cerebro"),
    ("¿En qué caso conviene usar un índice hebbiano?", "cerebro"),          # "en qué caso" no es un caso forense
    ("Contame de Rust", "cerebro"),
    # --- Investigación: salir a la web ---------------------------------------------------------------------------------
    ("Investigá en la web qué es ActivityPub", "investigacion"),
    ("Buscá en internet las novedades de Rust", "investigacion"),
    ("¿Qué salió en arxiv esta semana sobre agentes?", "investigacion"),
    ("Investigá el estado del arte en memoria para LLMs", "investigacion"),
    ("Buscame noticias de hoy sobre NVIDIA", "investigacion"),
    ("Hacé un research de vLLM contra Ollama", "investigacion"),
    ("Fijate qué dice https://ejemplo.org/articulo sobre el tema", "investigacion"),
    ("Averiguá online cuánto sale una GPU de 24 GB", "investigacion"),
    ("Investigame las últimas versiones de FastAPI", "investigacion"),
    ("Que Scout busque información sobre Piper TTS", "investigacion"),
    ("Buscá en Google si hay CVEs nuevos de OpenSSH", "investigacion"),
    ("Googleá qué es el protocolo MCP", "investigacion"),
    ("¿Hay novedades de faster-whisper?", "investigacion"),
    ("Traeme lo último que se publicó sobre spreading activation", "investigacion"),
    ("Investigá qué alternativas hay a Brave Search", "investigacion"),
    # --- Investigación: evidencia de un caso ------------------------------------------------------------------------------
    ("Creá un caso nuevo para la estafa del alquiler", "investigacion"),
    ("Ingestá el CSV de transferencias en el caso 3", "investigacion"),
    ("Analizá el chat de WhatsApp que exporté", "investigacion"),
    ("Sacale los metadatos EXIF a foto_recibo.jpg", "investigacion"),
    ("¿Qué entidades aparecen en la evidencia del caso orion?", "investigacion"),
    ("Proponé fusiones entre las personas del caso", "investigacion"),
    ("Exportá el informe del caso en PDF", "investigacion"),
    ("Revisá el log del servidor access.log del caso 7", "investigacion"),
    ("Ingestá este export de Telegram al caso", "investigacion"),
    ("¿Qué propuestas quedaron pendientes en el caso de la estafa?", "investigacion"),
    ("Mapeá las columnas de movimientos.csv", "investigacion"),
    ("Hacé el análisis forense del documento contrato.docx", "investigacion"),
    ("Listame los artefactos del caso 2", "investigacion"),
    # --- pedidos que tocan las dos: gana la señal explícita de trabajo (web / caso) ------------------------------------
    ("Investigá en la web qué es Orión y comparalo con mis notas", "investigacion"),
    ("Buscá en internet sobre ransomware y fijate qué tengo guardado", "investigacion"),
    ("Con la evidencia del caso 3, ¿qué dicen mis notas del banco?", "investigacion"),
)
