# 🛣️ Roadmap de mejoras de Raphael

> Doc de diseño / roadmap. Creado el **2026-09-03**.
>
> **Por qué existe y por qué confiar en él:** este roadmap surge de DOS análisis
> independientes que **convergieron en la misma lista**:
> 1. La **autoevaluación de Raphael sobre sí mismo** (se le preguntó "¿qué te
>    mejorarías?" — respondió con sus límites reales, no una lista de marketing).
> 2. El **análisis del vault de Obsidian** (~93 notas de video curadas por Damian
>    sobre IA/agentes/seguridad) hecho por Claude.
>
> Que dos análisis independientes lleguen a lo mismo = señal fuerte de que estos
> SON los cuellos de botella reales, no opiniones sueltas.
>
> **Prioridad global:** todo esto es **post primera venta** (endurecimiento /
> Fase 1), salvo lo marcado como afecta-directo-a-la-venta (el informe de
> auditoría). No dispara 5 builds a la vez: se ataca por impacto, quick-wins primero.

---

## ⚡ Quick wins (baratos, cortan costo/bugs ya)

### QW-1. Routing de tools por dominio *(Raphael #2 · en ESTADO.md)*
- **Problema:** en CADA pedido se cargan ~103 tools + ~30k tokens de system
  prompt, sea cual sea la tarea. Distrae al modelo (peores decisiones) y cuesta
  plata por llamada (es el diagnóstico del gasto de $0.32 del primer día).
- **Fix:** exponer solo las tools relevantes a la tarea (auditoría ≠ control de
  escritorio ≠ investigación). Ya hay un clasificador de skills (`app/skills.py`);
  extenderlo para acotar el set de tools por dominio.
- **Impacto:** menos ruido = mejores decisiones + menos costo. Bounded, seguro.

### QW-2. Anclar el cerebro (config de modelo estable) *(Raphael #5 · bug en TABLA)*
- **Problema:** corre DeepSeek V4, pero el selector de la tray puede pisar la
  config y volver a `jarvis-text-v2` sin querer. "Todo lo que soy depende de qué
  modelo me corre" — y hoy es frágil.
- **Fix:** que el selector no pise la config manual (o sume una opción "Cloud/
  DeepSeek" coherente con el `base_url`). Que Raphael pueda verificar su propio
  modelo activo.
- **Impacto:** evita romper la config de golpe. Chico.

### QW-3. Informe de auditoría: citar la fuente de cada afirmación *(vault: Hermes 0.20 · afecta la VENTA)*
- **Problema:** la narrativa del informe puede inflar/inventar (el caso `flask
  lint` → "posible RCE" que no existía). "La IA redacta, vos verificás" es hoy
  100% manual.
- **Fix:** que cada frase del informe **linkee al hallazgo exacto (archivo:línea:
  regla)** del que salió, como Hermes ahora da fuentes verificables. Si el LLM
  tiene que anclar cada afirmación a un hallazgo real, no puede inventar.
- **Impacto:** ataca de raíz el riesgo de credibilidad. **Build chico, valor
  enorme, y toca directo tu producto vendible.** Candidato a hacer pronto.

### QW-4. Config checker en la auditoría *(lección del Test B, studybud)*
- **Problema:** los escáneres (Semgrep/Bandit) **no revisan la config del
  framework**. En studybud se les escaparon `DEBUG=True`, `ALLOWED_HOSTS`, y una
  `db.sqlite3` commiteada — riesgos reales. "1 hallazgo" ≠ "1 problema".
- **Fix:** un chequeo simple de config Django/Flask que marque `DEBUG=True`,
  `ALLOWED_HOSTS=['*']`, SECRET_KEY hardcodeada, `.env`/DB commiteados.
- **Impacto:** sube la COBERTURA (no solo la precisión). Hace tu herramienta
  mejor que "correr Semgrep".

### QW-5. Retrieval que avisa cuando corre en modo degradado *(detectado 2026-09-04, en vivo)*
- **Problema:** si LM Studio (embeddings, puerto 1234) está caído, `search_notes`
  **degrada silenciosamente a keyword** y sigue como si nada. El usuario cree que
  tiene ranking semántico cuando en realidad tiene el peor (palabra clave). Se vio
  en vivo al intentar reindexar el vault: el server no respondía y nadie avisaba.
- **Fix:** que la búsqueda (y el reindex) detecten que el endpoint de embeddings no
  responde y lo **marquen explícitamente** (log + flag en la respuesta: "modo
  degradado: keyword-only, LM Studio no responde"). Chico, no cambia la lógica de
  ranking, solo la hace honesta.
- **Impacto:** evita confiar en retrieval fantasma. Se cruza con F1-1 (retrieval es
  el cuello de botella; esto es su síntoma observable).

---

## 🏗️ Fase 1 (builds medianos/grandes, post-venta)

### F1-1. Retrieval del propio conocimiento *(Raphael #1 — el de MÁS impacto)*
- **Problema:** el vault (~93-240 notas) + el codebase indexado son riquísimos,
  pero *alcanzar* lo que se sabe es el cuello de botella. Búsquedas que vuelven
  recortadas (`results_omitted_by_size_limit`), refinamiento a ciegas. "Tengo la
  info pero no la encuentro bien cuando la necesito."
- **Fix:** mejorar la capa de retrieval — ranking semántico más fino +
  recuperación que traiga **exactamente** la nota/sección relevante sin inundar
  ni quedarse corto. Es el principio de "el índice es el contexto" (aplica al
  vault Y a auditar codebases gigantes).
- **Impacto:** destraba TODO lo demás. Raphael mismo lo puso #1, y coincide.
- **Fuente vault:** RAG / "el índice es el contexto".

### F1-2. Orquestación — la Brigada *(Raphael: grafos · vault: git-worktrees, A2A)*
- **Modelo:** un grafo (DAG) de agentes. Nodos = agentes, aristas = comunicación,
  un **Sous-Chef/orquestador** central que reparte y ejecuta en **orden
  topológico** (escanear → triagear → config → reportar).
- **Estaciones** (ver también el diseño de la brigada): Reconocimiento (escáneres,
  determinista, NO LLM) · Triage (1 hallazgo por vez, ya existe) · Config (nuevo,
  ver QW-4) · Redacción (ya existe) · Pase/Agregador (nuevo) · Catador/QA (nuevo).
- **Paralelismo — el mecanismo concreto:** **git worktrees** — cada agente en su
  copia aislada del repo, sin pisar archivos, con sus commits que se integran
  después. Es la respuesta técnica a "auditar un codebase gigante".
- **Comunicación:** **A2A (Agent-to-Agent)** como protocolo cuando la brigada
  crezca (bidireccional, con protección anti-bucle-infinito — de Hermes 0.20).
- **Regla de oro:** cada puesto se gana su lugar solo si tiene trabajo puntual Y
  contexto propio y chico. Mismo cerebro (DeepSeek) para todas alcanza — la
  especialización es por contexto/prompt, no por modelo (eso es optimización
  posterior).

### F1-3. Memoria de criterio automática *(Raphael #3)*
- **Problema:** las lecciones (`jarvis_reflect`) no persisten solas — dependen de
  guardarlas a mano, y se pierden. "El 'no repitas esto' vive disperso."
- **Fix:** mecanismo automático de extracción de lecciones al cierre de cada
  sesión, para no re-cometer errores ya resueltos.
- **Nota:** hoy (2026-09-03) ya se mejoró la persistencia del historial de chat;
  esto es el siguiente paso (memoria de *criterio*, no de conversación).

### F1-4. Proactividad + procesos en background *(Raphael #4 · vault: Hermes)*
- **Problema:** Raphael es reactivo y síncrono — espera a que le pidan, y los
  comandos bloquean (no puede dejar un servidor corriendo mientras hace otra cosa).
- **Fix:** procesos en background + algo de proactividad dentro de un scope
  autorizado (ej. el monitoreo de malware/FIM que ya tiene, pero que ALERTE solo).
  Lo convierte de "asistente que responde" a "operador que gestiona".
- **Se cruza con:** la idea de "vanguardia CoT / monitoreo de logs" de la Tabla.

### F1-6. Model routing por tiers (costo → habilita mejor calidad donde importa)
- **Principio:** asignar el modelo por ESTACIÓN (fijo por rol), no por un juez de
  dificultad dinámico. Tres tiers:
  - **Tier 0 (sin modelo, determinista):** Reconocimiento/escáneres.
  - **Tier 1 (chico/rápido, Flash):** Router/clasificador, Config checker. Corren mucho.
  - **Tier 2 (potente):** Redacción del informe, Orquestador, Catador/QA, y el
    Triage de high/critical (bajable a Tier 1 para medium si hay que ahorrar).
- **Matiz de calidad:** el routing en sí es sobre todo COSTO; sube calidad solo
  INDIRECTO — al ahorrar en lo liviano, deja affordear el modelo más fuerte en
  triage/redacción (los pasos donde el LLM razona = donde el modelo mueve la calidad).
  El escaneo es determinista: ahí la calidad la da la COBERTURA (config checker), no el modelo.
- **Plomería:** ya existe multi-modelo (`cloud_expert`=Gemini, embeddings=nomic).
  Extender a un mapa `{tier → modelo}` en config.

### F1-7. Suite de calibración / benchmark (set curado de repos)
- **Qué:** 10-20 repos reales DIVERSOS (Django, Flask, FastAPI, Node, distintos
  tamaños), NO cientos (rendimientos decrecientes + costo). Se corre después de cada
  fix para medir regresión/mejora: ¿bajó la tasa de falsos positivos?, ¿subió cobertura?
- **Doble valor:** suite de regresión del producto + forma OBJETIVA de medir
  "competir en la frontera" (se cruza con Cybench / el OWASP benchmark que ya corre).
  Un número, no un "creo que es bueno".
- **⚠️ Ética/legal:** auditar código público ajeno para CALIBRAR está bien (estático,
  no se ejecuta). PUBLICAR vulnerabilidades de proyectos ajenos NO — rige divulgación
  responsable (reporte privado al mantenedor, con tiempo). Calibrar, no exponer.

### F1-5. Spec-Driven Development en el build de apps *(vault: Attekita Dev)*
- **Qué:** cuando Raphael construye apps, seguir el flujo **Clarificar → Especificar
  → Tickets → Implementar**. El paso 1 ("Grill Me": interrogar para sacar
  requisitos antes de escribir nada) es el que más se saltea y el que más importa
  — "la calidad del output depende de la del input".
- **Se cruza con:** la idea de PLAN mode (Tabla). Es su versión formal.
- **Impacto:** código más determinista y confiable, menos improvisado.

---

## Orden sugerido de ataque

1. **QW-3 (citar fuentes en el informe)** — chico y toca la venta directo.
2. **QW-1 (tool routing)** — barato, da aire (costo + decisiones).
3. **QW-4 (config checker)** — sube cobertura de la auditoría.
4. **QW-2 (anclar cerebro)** — saca un bug molesto.
5. **F1-1 (retrieval)** — cuando le dediques una sesión seria; destraba todo.
6. **F1-2 (brigada)** — el build grande, con retrieval ya resuelto abajo.
7. El resto (memoria de criterio, proactividad, spec-driven) según haga falta.

> Recordatorio: **nada de esto va antes de la primera venta.** Es el plano para
> cuando toque construir, no una orden de arranque.
