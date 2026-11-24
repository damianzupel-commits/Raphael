# 🔪 La Tabla — ideas crudas

> Acá cae toda idea recién pensada, sin procesar. No se cocina desde acá: se captura para que no se pierda. Cuando una idea se decide cocinar, pasa al riel (`COMANDAS.md`).

---

## ✅ RESUELTO: ingesta YouTube frenada por bloqueo de `youtube-transcript-api`
**Anotado: 2026-09-01 · Resuelto: 2026-09-01**

> RESUELTO el mismo día: se hizo el **camino 1** (yt-dlp). `fetch_transcript` ahora
> lista subtítulos con `yt_dlp.extract_info` (manuales antes que auto; es→en→pt),
> baja el `.vtt` con el propio cliente de yt-dlp y lo parsea a texto plano (helpers
> `_select_subtitle_track` / `_pick_vtt_url` / `_parse_vtt`). Se fue el fallback de
> traducción (ahora el PT entra directo, DeepSeek resume igual). Se agregó reintento
> con backoff (3s/6s/12s) + respiro de 1.5s entre videos para el **HTTP 429** (throttle
> transitorio, distinto del IpBlock). Tests reescritos: 26 pasan. Corrida real: bajó
> las que antes fallaban; quedó 1 sola (`6GcfKpfA2kM`) trabada por 429 residual del
> maratón de anoche — se destraba re-corriendo (idempotente) cuando afloje el throttle.
> Detalle técnico en el docstring de `fetch_transcript`.

**(Diagnóstico original, se deja de registro):**

La ingesta de la playlist funciona end-to-end (enumera, detecta nuevos, resume con
DeepSeek, escribe nota), PERO **todos los videos fallan con `IpBlocked`**. Probado
el 2026-09-01: falla igual desde la IP de casa Y desde el 4G del celu (hotspot). O
sea NO es "IP de casa recalentada": YouTube está bloqueando a la librería
`youtube-transcript-api` en sí, incluso desde IPs móviles (compartidas, también
marcadas). Le vienen apretando fuerte a esa lib últimamente.

Dos caminos de arreglo (mini-build de cabeza fresca, no un ajuste):
1. **[PREFERIDO] Bajar la transcripción con yt-dlp** en vez de `youtube-transcript-api`.
   yt-dlp imita mejor a un navegador y suele esquivar el bloqueo. El pipeline YA usa
   yt-dlp para enumerar (`--flat-playlist`), así que es cambiarle solo la pieza de
   transcripción (`--write-auto-sub`/`--write-sub` + parsear el .vtt). Gratis.
2. Meterle un **proxy** (la lib lo soporta, tipo Webshare residencial). Más efectivo
   pero hay que configurar y a veces pagar.

Estado: la lógica de vault/detección/resumen quedó probada y OK. Falta solo destrabar
la obtención de transcripción. Prioridad: hacer el camino 1 primero (gratis, probable
que resuelva). Se cruza con el arreglo de traducción pt→es ya aplicado.

---

## 📺 Canal de YouTube de "cyberseguridad responsable"
**Anotado: 2026-09-04**

Idea: canal propio de ciberseguridad ética/responsable. Encaja con la marca de
Damian (divulgación responsable, no exponer repos ajenos) y con material que casi
nadie tiene: el vault (~95 notas curadas), auditorías reales, y Raphael como
historia ("me armé mi propio agente de seguridad").

**Encuadre / freno (importante):** NO es prioridad y NO hace la primera venta. Es
un juego lento (meses para tracción) que compite por la energía de vender. Trampa
conocida: grabar se *siente* productivo y evita el riesgo de rechazo de vender. El
canal es un **activo de autoridad que ALIMENTA la agencia**, no un reemplazo — y se
pone mejor DESPUÉS de las primeras auditorías reales (el mejor contenido es "este
hallazgo real encontré", anonimizado y con permiso, no teoría).

**Versión liviana si quiere plantar semilla sin descarrilar:** nada de pipeline de
producción. **Repurpose** de lo que ya hace — un short por lección real (el falso
positivo del `flask lint`, "1 hallazgo ≠ 1 problema"). 15 min, no un segundo laburo.
Máquina ya montada: proyecto `co-host-stream`, nota "canal faceless" en el vault, y
Raphael como guionista. **Revisitar post primera venta.**

---

## 🛣️ Roadmap de mejoras de Raphael — doc dedicado
**Anotado: 2026-09-03**

Se escribió un doc de roadmap: **`docs/ROADMAP-MEJORAS-RAPHAEL.md`**. Surge de dos
análisis independientes que CONVERGIERON: la autoevaluación de Raphael sobre sí
mismo ("¿qué te mejorarías?") + el análisis del vault (~93 notas) por Claude.
Ordenado por impacto y quick-win vs Fase 1. Incluye: routing de tools por dominio
(costo), citar fuentes en el informe de auditoría (credibilidad, toca la venta),
config checker (cobertura), anclar el cerebro, retrieval (el de más impacto),
la brigada (grafo/DAG + git-worktrees + A2A), memoria de criterio automática,
proactividad/background, y spec-driven en el build de apps. **Todo post-venta.**

---

## ⭐ HITO ESTRELLA: Hermes (ataque) vs Raphael (defensa) — experimento red-vs-blue
**Anotado: 2026-09-02**

Experimento para PROBAR la tesis de Damian ("mi harness compite en cyber"): enfrentar
a **Hermes Agent** (NousResearch, harness OFENSIVO — pentest autónomo, ~269 tools de
Kali) contra **Raphael** (defensa), **con el MISMO cerebro (LLM)** en ambos, para
aislar el *harness* como única variable. Es el método científico de "competir": un
benchmark real, medible, no un "le gano" abstracto. Además, cuando salga, es un **demo
de marketing espectacular** ("puse mi defensor contra una IA ofensiva").

**⚠️ SEGURIDAD — no negociable, VA ANTES QUE NADA:** Hermes es un agente ofensivo
autónomo. Correrlo exige una **jaula herméticamente aislada** (VM air-gapped, sin salida
a internet, SOLO contra targets propios). Sin eso puede escaparse, pegarle a algo real
y ser un problema legal grave. Coherente con el gate `authorized_targets.yaml` y con la
nota de la comandera ("jaula aislada ANTES de tirar nada, cabeza fresca, no apurado").

**Aclaración de qué "defensa":** Raphael es sobre todo AUDITORÍA (estático). Dos variantes:
- **(a) Blue team en vivo:** Raphael detecta/responde el ataque en tiempo real → usa sus
  módulos `malware/` + `network/` + FIM + heurística conductual (NO los escáneres de auditoría).
- **(b) [preferida, juega a su fuerza] Auditoría-prevención:** Raphael audita el target
  ANTES, marca las vulns, y se mide si Hermes explota justo las que Raphael ya flagueó
  ("la auditoría lo hubiera prevenido").

**Prerequisitos (por eso es el BROCHE, no el primer paso):** primera venta hecha +
auditorías validadas (tests PyGoat/Juice Shop) + laboratorio aislado (Endurecimiento
Fase 1) + Hermes instalado y configurado con el mismo cerebro (ojo: Hermes está afinado
para modelos Nous; forzarlo a DeepSeek puede handicapearlo o requerir config). NO saltear
al principio — sería el clásico todo-o-nada. Se cruza con [[El Restaurante Virtual]] (para
visualizar el enfrentamiento) y con el Nivel 5 (orquestación).

---

## Orbe flotante de voz (Raphael estilo anime) — PRÓXIMO PLATO
**Anotado: 2026-09-01**

En modo voz, que en vez de la ventana normal aparezca SOLO la imagen de Raphael
**flotando en el escritorio** y que "vibre"/pulse a medida que habla — como el
Raphael del anime (Rimuru). Pedido de Damian el 2026-09-01, quedó como el próximo
build después de la memoria + imagen (que ya se hicieron).

Qué implica (build propio, no un ajuste):
- Ventana Qt **sin bordes, fondo transparente, siempre encima** (frameless +
  `WA_TranslucentBackground` + `WindowStaysOnTopHint`), arrastrable, chica.
- Muestra `assets/raphael.png` con una **animación de pulso** (escala/opacidad).
- La animación se ATA a la voz: pulsa mientras Raphael habla/escucha. El
  `voice_listener.py` ya emite eventos (wake/transcript/reply) — engancharse a esos
  para arrancar/parar el pulso. Idealmente amplitud según el audio (más fino).
- Se muestra al activar modo voz (🎙) y se esconde al apagarlo.
- Cruza con: el toggle de voz que ya vive en `ui/chat_view.py` / `voice_listener.py`.

---

## Pantalla de Raphael (tray): mejoras pendientes tras la v1
**Anotado: 2026-09-01**

La v1 de la pantalla de chat ya se hizo (bienvenida + panel "Pedidos recurrentes"
desplegable + estado Conectado/Pensando + renombre Jarvis→Raphael, tema oscuro).
Quedaron pendientes A PROPÓSITO, por riesgo o por falta de cimiento:

- **Botón "Crear imágenes":** NO agregado. Motivo real: `generate_image`/`generate_video`
  se sacaron de la UI porque la PC se apagó físicamente al usarlas (ComfyUI local, ver
  `ui/chat_view.py` Sidebar y INFORME_COMPLETO.md 4.5). Para sumarlo SEGURO hay que
  primero cablear una tool de imagen a un modelo **en la nube** (no el ComfyUI local),
  y recién ahí poner el botón. Damian lo pidió; primero el backend cloud, después el botón.
- **"Usar periféricos" (drones, robots, lentes inteligentes):** NO agregado. Hoy no
  existe integración con ese hardware, así que un botón sería un botón muerto. El propio
  Damian dudó si era coherente ahora ("no sé si sea coherente hacerlo ahora") — no lo es
  todavía. Queda como VISIÓN futura, se suma cuando exista al menos una integración real.
- **"Mostrar exactamente qué está haciendo" (estilo Claude, paso a paso):** la v1 tiene
  el estado básico (Conectado/Pensando). El visor de pasos/tools EN VIVO necesita que el
  backend EMITA sus pasos por streaming (SSE/WebSocket) y que la tray los consuma — es una
  feature de verdad, no un ajuste de UI. Se cruza con [[El Restaurante Virtual]] (mismo
  stream de eventos). Build aparte.

---

## El Restaurante Virtual (tablero visual en vivo)
**Anotado: 2026-08-24**

Una herramienta visual donde Damian ve su "restaurante" funcionando en tiempo real: los agentes/cocineros moviéndose entre estaciones, las comandas viajando por el pase, el runner llevando el plato, cómo se comunican entre sí (hub-and-spoke + pizarra). Un "kitchen sim" atado a la actividad REAL de los agentes de Raphael.

- **Qué es:** dashboard de observabilidad renderizado como una cocina visual (agentes = sprites en estaciones, comandas = tickets que fluyen, estados en vivo). Se alimenta del stream de eventos del backend FastAPI (WebSocket).
- **Por qué es un plato de postre, no de entrada:** requiere que la cocina de agentes exista primero (el sous-chef, los jefes de partida y el router son Fase 1, sin construir). Hoy visualizaría una cocina vacía.
- **Valor extra:** cuando Raphael sea real, este visual en vivo es una **carta de presentación para vender** — mostrarle a un cliente una cocina de IA de seguridad funcionando impresiona.
- **Depende de:** orquestación construida (Fase 1) + un canal de eventos en tiempo real.

**Flujo visual completo que Damian quiere ver (spec):**
1. La **comanda entera** que entró (la orden completa).
2. Cómo el **sous-chef la dividió** en sub-tareas (árbol de descomposición).
3. A qué **estación/agente** fue cada pedazo (el ruteo).
4. El **estado de cada parte, en vivo**:
   - 🔥 cocinándose (agente trabajando)
   - ✅ parte lista (el agente terminó su pedazo)
   - 👍 aprobada (pasó su gate de confirmación)
5. El **emplatado**: cómo las partes se juntan en el plato final.
6. **Servido**: sale al pase / se entrega.

En resumen: un tablero tipo árbol/kanban por comanda, mostrando descomposición + estado por agente + estados de aprobación (gates), todo actualizándose en tiempo real.

**Dónde vive (metáfora: cámaras de seguridad de la cocina):**
- **Las cámaras** = el backend FastAPI de Raphael emite un stream de eventos en vivo (WebSocket/SSE): qué agente cocina qué, estados, aprobaciones.
- **El monitor** = una página web (dashboard) servida por el mismo backend, como una superficie más (junto a tray-app y Android).
- **Se mira desde:** localhost en la PC + remoto por Tailscale en el celular (como chequear las cámaras de seguridad desde el teléfono, privado por la red de Tailscale).
- Reusa: backend FastAPI (ya existe) + Tailscale (ya diseñado en ORQUESTACION-REMOTA-DESIGN).

---

## Modo PLAN vs BUILD para Raphael (inspirado en Claude Code)
**Anotado: 2026-08-31**

Dos modos operativos atados a dónde está Damian (canaliza su cabeza que no para):
- **PLAN mode (fuera de casa / desde el celu):** las tools con efectos (fs_write, shell,
  desktop, pentest, etc.) quedan en **solo-proponer**. Raphael lee, piensa, busca, redacta
  y guarda notas — pero **NO ejecuta**. Seguro para operar desde el celu sin supervisión.
- **BUILD mode (en casa / PC):** ejecución habilitada, con Damian supervisando + las
  confirmaciones de siempre (dry-run→confirm, proposal_id, preview_token).

**Clave anti-"planear sin ejecutar" (la herida de Damian):** el puente entre modos es una
COLA. En plan mode, cada plan se captura como **comanda concreta y ejecutable** (no charla
vaga). En build mode, Raphael **ejecuta la cola** sin re-pensar. Planear ALIMENTA construir.

**Se apoya en infra que YA existe:** `app/operation_mode.py` (SUPERVISED/AUTONOMOUS) + el
sistema de gates. Falta: un flag de modo que ponga las tools de efecto en "propose-only" en
plan mode, y (opcional) auto-detección por origen del request (celu/Tailscale → plan; PC → build).
Es un build scopeado, de la fase de endurecimiento/orquestación. No es de 5 minutos.

---

## Hub de orquestación único (celu + PC) — Raphael + IAs gratis
**Anotado: 2026-08-30**

Idea: un **solo lugar** (interfaz única en celu y PC) desde donde usar Raphael + varios
modelos **gratis** (OpenRouter free / local), con un orquestador que rutee entre ellos
según la tarea. Se cruza con [[Restaurante Virtual]], [[Herdr]] y la brigada de agentes.

**Verdad estructural (importante, no olvidar):** "Claude Dispatch" **NO se puede meter
como nodo programático** del orquestador — es un sistema hosted de Anthropic (esta interfaz),
sin API para enchufarlo dentro del backend de Raphael. "Claude en el loop" = sesiones de
planificación/arquitectura/builds difíciles con Claude, NO un agente dentro del sistema.
Lo que SÍ se construye: interfaz única sobre **Raphael + modelos gratis**, con Raphael/DeepSeek
(u otro) como orquestador que rutea.

**Por qué NO ahora:** es un build de varias sesiones (Fase 1 de orquestación), no un apuro.
Requiere diseño dedicado. Cimiento ya puesto (2026-08-30): acceso remoto celu↔PC por Tailscale.

---

## 🐞 BUG: el selector de la tray pisa la config de DeepSeek
**Anotado: 2026-08-30**

El selector de modelo de la tray-app (Lite/Medio/Hard) sobrescribe `LMSTUDIO_MODEL`
en `.env` con uno de los `jarvis-text-*` locales, pero **no toca `LMSTUDIO_BASE_URL`**.
Resultado: si estás en DeepSeek (base_url=OpenRouter) y tocás el selector, queda
`base_url=OpenRouter + model=jarvis-text-v2` → **config rota** (OpenRouter no tiene
ese modelo). Pasó el 2026-08-30. Arreglo posible: que el selector sume una opción
"Cloud/DeepSeek" o que no pise la config manual / que setee base_url coherente con
el tier. Mientras tanto: **si usás DeepSeek, no toques el selector de la tray.**
Es un ítem de "mejorar el harness / pantalla de uso".

---

## DeepSeek: experimentos y mejoras (post cambio de cerebro)
**Anotado: 2026-08-26**

Ideas que surgieron apenas DeepSeek quedó funcionando, capturadas para no dispersarse:

- **Harness engineering / mejorar el harness:** revisar el loop del agente y las tools a la luz de los videos ingeridos ("Harness Engineering", "Jerarquía: Modelos, Harness y Orquestadores"). OJO: Jarvis YA es un harness; esto es *mejorar*, no crear uno nuevo.
- **Mejorar la "pantalla de uso"** (la interfaz/tray) — UI, no bloquea nada.
- **Usar DeepSeek como orquestador de otras IAs/agentes** — es la orquestación de la brigada (Fase 1), el plato grande. Se cruza con [[Herdr]] y con el Restaurante Virtual. Requiere decidir el modelo de orquestación antes de construir.

Todo esto es *agregar/mejorar*, no *endurecer*. Va después de la prioridad actual (primera venta) y del endurecimiento Fase 1.

---

## Herdr — multiplexor de terminal para orquestar agentes de código
**Anotado: 2026-08-25**

Herramienta open-source (TUI, multiplataforma) que corre varios agentes de código CLI (Claude Code, Codex, Kimi, OpenCode…) en paneles dentro de una misma terminal, con sesiones persistentes (servidor por detrás), plugins, y un skill para que un agente lea la salida de otro y se pasen tareas. Fuente: video de Fazt Code (transcripción en uploads).

- **Qué NO es:** no es el "restaurante virtual" (el dashboard visual de los agentes de Raphael). Herdr son paneles de terminal, no sprites en una cocina, y no conoce Raphael ni sus tools.
- **Dónde podría encajar (futuro):** en la *orquestación* — Claude orquesta, varios agentes trabajan y se pasan el laburo. O como entorno de desarrollo para Damian (trabajar en Raphael con varios asistentes a la vez).
- **Por qué NO ahora:** cada agente necesita su suscripción/config aparte; es un contenedor de CLIs externos, no integrado con Raphael; adoptarlo es meter un ingrediente nuevo grande (contra "endurecer, no agregar").
- **Depende de:** decidir el modelo de orquestación de la brigada (Fase 1) antes de elegir si Herdr es la herramienta o no.

---

## Definir qué corre en Windows vs Linux (arquitectura híbrida)
**Anotado: 2026-08-24**

Surgió la idea de "usar Linux como base para todo". Conclusión: NO migrar — la arquitectura correcta es híbrida, y ya lo es. Definir formalmente el reparto cuando se arme la orquestación:
- **Windows:** escritorio/uso diario de Damian + **el blanco defensivo y el producto que se vende** (Defender, ASR, AppLocker, WDAC, DPAPI, Sysmon son SOLO Windows; los clientes PyME usan Windows).
- **Linux:** el servidor-agente always-on, lo ofensivo/lab (Kali, nmap, sqlmap, Metasploit, ZAP), la contención en contenedor, y Tailscale SSH (que no funciona como servidor en Windows). Vive en WSL2 o un contenedor.
- Razón de no migrar: se perdería todo el stack defensivo Windows (el producto monetizable) y migrar bases descarrila el servicio. Es un tema de la fase de orquestación/contención, no de ahora.

---
