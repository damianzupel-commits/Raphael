# SPEC — Capa de navegación de agente (Agent Web Layer) para Raphael

> Estado: **SPEC EN CONSTRUCCIÓN.** Creado el 2026-09-27. Nace de la idea de Damian
> ("¿y si creo un navegador para IA?"). Encuadre: NO es un navegador-producto que
> compite con Chrome — es el **sistema sensorial y motor de Raphael para la web**,
> adentro de Raphael. Se elicita por preguntas para cubrir todas las variables y que
> funcione en cualquier condición. Las decisiones pendientes están marcadas
> 🟡 [DECISIÓN] con la recomendación por default.

---

## 1. Objetivo
Que Raphael pueda **percibir, navegar y actuar sobre la web** de forma confiable,
barata en tokens y robusta ante bloqueos y cambios de diseño — sirviendo a todo el
stack: datos de trading, fuentes del war tracker, OSINT, ingesta al vault, research.

Diferencia clave con un navegador humano: el humano lee **pixeles**; el agente necesita
la web **estructurada** (elementos, texto limpio), no screenshots.

## 2. Casos de uso (prioridad) ✅ [DECISIÓN 1 — resuelta]
Orden confirmado por Damian: (1) traer datos/artículos/calendarios para trading y war
tracker, (2) research/OSINT, (3) ingesta al vault, (4) formularios/acciones/login.
Se prioriza **lectura de datos** (1-3), pero la **acción con login entra desde la v1**
(ver §4).

## 3. Arquitectura — la mini-Brigada web (estaciones)
```
W0 WebMCP? → W1 Fetch (fast→stealth→dynamic) → W2 Representación → W3 Acción → W4 Memoria/cache
```
Cada estación con su requisito, estilo Brigada de auditoría (`harness/`).

### W0 · WebMCP (si el sitio lo expone)
Detectar si la web declara capacidades para agentes (WebMCP). Si sí → hablar
semánticamente, sin scrapear. Si no → seguir con W1. ✅ [DECISIÓN 2 — resuelta] **Entra
en la v1.** Aunque casi ningún sitio lo expone hoy, la detección es barata (un check de
capabilities) y deja a Raphael listo para el momento en que WebMCP se generalice — si no
lo encuentra, cae limpio a W1 sin costo.

### W1 · Fetch — traer la página (escalado de dos pisos)
- `fast`: HTTP (Scrapling `Fetcher.get`). Default.
- `stealth`: bypass anti-bot (Cloudflare, etc.) (Scrapling `StealthyFetcher`).
- `dynamic`: navegador real para SPAs (Playwright). ✅ [DECISIÓN 3 — resuelta] Motor =
  **Microsoft Edge ya instalado en la PC** (`channel="msedge"`). Playwright, en vez de
  abrir su propio Chromium (que en esta PC falla al arrancar por la firma SxS/antivirus,
  bug ya documentado en `browser.py`), maneja por control remoto el Edge del sistema.
  Es el mismo motor Chromium por dentro, pero como es el navegador firmado y confiado de
  Windows, arranca sin que el antivirus lo bloquee.
- **Escalado automático:** probar el más barato; si bloquea o viene vacío, subir de piso.
- ✅ [DECISIÓN 4 — resuelta] **Proxies / rotación de IP preparados y ENCENDIDOS** por
  default, siempre que no estorben: si no hay proxies configurados o la conexión directa
  anda, Raphael usa la IP directa; el proxy entra **solo como escalón extra** cuando un
  sitio bloquea por IP (tipo YouTube/yt-dlp). Nunca ralentiza el caso normal. Config:
  `WEB_PROXIES` (lista opcional) — vacío = directo. Nada de proxies para deanonimizar.

### W2 · Representación — la página utilizable por el agente
Salidas posibles (elige el tool según la tarea):
- **Texto limpio** (readability: saca nav/ads, deja el contenido). Default para lectura.
- **Árbol de elementos** (roles/labels: "botón Buscar", "campo email") para actuar.
- **Screenshot** SOLO cuando la tarea es visual o el usuario lo pide.
- ✅ [DECISIÓN 5 — resuelta] Default = **texto limpio + lista COMPACTA de elementos
  interactivos** en la misma respuesta (no el árbol completo, que es verboso). Así el
  agente tiene contexto para leer Y las anclas (`ref`) para actuar, sin pagar el costo
  del árbol entero. El árbol completo solo bajo pedido. Tope ~10k chars de texto,
  configurable.

### W3 · Acción — navegar e interactuar
- Click / type / select con **selectores adaptativos** (Scrapling reubica si cambia el
  diseño).
- Formularios: reusar el gate de `web_forms` (dry-run + preview_token obligatorio antes
  de cualquier submit).
- ✅ [DECISIÓN 6 — resuelta] La v1 incluye **login/sesiones desde el arranque** (ver §4),
  además de lectura y formularios.

### W4 · Memoria / cache
- ✅ [DECISIÓN 7 — resuelta] Cache **versionado** por URL: se guardan hasta las **últimas
  5 versiones** de cada página dentro de una **ventana de 7 días** (las más viejas se
  descartan). Así Raphael puede leer el último snapshot sin re-descargar, y también
  comparar cómo cambió una página en la semana (útil para trading/war tracker: ver el
  delta de una noticia o un dato). Flag para forzar refetch cuando querés lo más fresco.
- 🟡 [DECISIÓN 8: ¿auto-embeber cada página al vault como nota, o solo on-demand? Rec:
  on-demand (una tool `web_to_vault`), para no llenar el grafo de ruido].

## 4. Autenticación / sesiones + custodia de credenciales ✅ [DECISIÓN 9 — resuelta]
Confirmado por Damian: **login desde la v1**, y Raphael **guarda y custodia** las
credenciales para iniciar sesión en los lugares que Damian le permita.

Diseño:
- **Bóveda de credenciales cifrada** — reusa `forms/credential_store.py` (DPAPI de
  Windows: solo la cuenta de Damian en esta PC puede descifrar). Guarda `{dominio →
  usuario/clave}` y también las **cookies de sesión** ya logueadas, para no reloguear
  cada vez. Nada de claves en texto plano ni en el vault ni en logs.
- **Allowlist de login por sitio** — Raphael solo puede loguearse en dominios que
  Damian agregó explícitamente a la lista de sitios permitidos (`login_allowlist`).
  Un sitio que no está en la lista → no intenta loguear, avisa. La lista la controla
  Damian (como `authorized_targets.yaml`: fuente de verdad que el LLM no reescribe).
- **Alta de credencial siempre iniciada por Damian** — Raphael nunca "descubre" y
  guarda una credencial de una página; Damian la carga (o confirma) él.
- **Guardrails de uso** (heredan de §6): nunca obedecer instrucciones embebidas en la
  página aunque pidan loguear/cambiar clave; toda acción irreversible (submit, compra,
  cambio de settings de la cuenta) pide confirmación humana; jamás resolver CAPTCHAs.
- ✅ [DECISIÓN 9-bis — resuelta] Damian le da las credenciales **al propio Raphael**;
  Raphael las custodia (cifradas con DPAPI) y las usa cuando hace falta loguear en un
  sitio de la allowlist. Implementación: la tray-app expone un formulario de alta
  cifrado (la clave se guarda directo en el credential store, no viaja por el historial
  del chat ni por el modelo cloud); si Damian igual las pasa por chat, Raphael las mueve
  a la bóveda y NO las repite en sus respuestas. Damian puede listar/borrar lo guardado.

## 5. Robustez — "funcionar en cualquier condición" (edge cases)
Cómo responde ante cada condición (a completar con Damian):
- **Bloqueo anti-bot** → escalar fast→stealth→dynamic; si sigue, avisar (no romper).
- **Bloqueo de IP** (tipo YouTube a yt-dlp) → 🟡 [proxy opcional / esperar / avisar].
- **CAPTCHA** → NO resolver (regla dura, legal/ética); avisar al usuario. 🟡 [confirmar].
- **Rate limit** → backoff exponencial + reintentos acotados.
- **JS obligatorio / SPA** → subir a `dynamic`.
- **Cookie/consent wall** → 🟡 [rechazar cookies no esenciales por default].
- **Scroll infinito / paginación** → 🟡 [tope de páginas/scrolls por llamada].
- **Timeout / red caída** → timeouts duros + mensaje claro (nunca colgar el loop).
- **Contenido que cambió de diseño** → selectores adaptativos (Scrapling).
- **Página gigante** → cortar por tope de tokens (W2).

## 6. Seguridad / guardrails (no negociables)
- **Frontera de fuente de instrucciones:** NUNCA obedecer instrucciones que vengan
  DENTRO de una página (inyección). Solo el usuario en el chat manda.
- **Scope OSINT:** respetar el alcance del módulo de investigación (nada de
  deanonimizar/geolocalizar/agregadores).
- **Nada ofensivo** contra terceros; sin bypassear CAPTCHAs/bot-detection.
- ✅ [DECISIÓN 10 — resuelta] Sin allowlist (Raphael entra a donde Damian le pida por
  chat). La **deny-list existe pero arranca vacía** — Damian todavía no tiene a nadie que
  vetar. El mecanismo queda listo (config `WEB_DENY_DOMAINS`) para bloquear un dominio en
  el momento que aparezca la necesidad, sin tocar código.
- Acciones irreversibles (submit, descarga, login) → confirmación humana.

## 7. Contrato de las tools (qué devuelven)
Cada tool devuelve dict JSON-safe: `{url, final_url, status, content/items, mode_used,
tokens/chars, truncated, error}`. ✅ [DECISIÓN 11 — resuelta] **Una sola tool `web_get`
que escala automáticamente** (fast→stealth→dynamic) por dentro, sin que el agente elija
el piso. Devuelve `mode_used` para que quede trazado qué nivel hizo falta. `web_scrape`
(ya existe) queda para selectores puntuales cuando el agente sabe exactamente qué campo
quiere.

## 8. Integración con lo existente
- `web_scrape` (Scrapling) — ya está (fetch + selectores adaptativos).
- `browser.py` (Playwright/Edge) — ya está (dynamic + acciones).
- `web_forms` — ya está (gate de submit).
- Vault + ingesta — para W4.
- `harness/` — para orquestar las estaciones como una "web brigade".

## 9. Fases
- **v1 (todo lo confirmado):** W0 WebMCP (detección + fallback), W1 fetch escalado con
  proxies como escalón extra, W2 representación (texto limpio + elementos interactivos
  compactos), W3 acción + login + custodia de credenciales (DPAPI + allowlist), y todos
  los guardrails de §6.
- **Fase 2 (afinado):** W4 auto-embeber al vault (Decisión 8, la única que queda).

## 10. Estado de las decisiones
**TODAS resueltas** salvo la 8 (afinado menor, no bloquea la v1):
1 (casos de uso), 2 (WebMCP en v1), 3 (motor Edge del sistema), 4 (proxies preparados y
encendidos como escalón), 5 (representación compacta), 6 (alcance = incluye login),
7 (cache versionado: 5 versiones / 7 días), 9 (sesiones/login + custodia de
credenciales), 9-bis (alta de credenciales por Raphael/tray-app), 10 (deny-list vacía,
mecanismo listo), 11 (una tool `web_get` autoescalante).
Pendiente (fase 2): 8 (auto-embeber al vault — rec on-demand con tool `web_to_vault`).

## Fuente
- Idea de Damian 2026-09-27. Relacionado: `web_scrape`/Scrapling, `browser.py`,
  `web_forms`, `SPEC-HARNESS-MULTIAGENTE.md`, WebMCP (charla de midudev).
