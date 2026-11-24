# INVENTARIO EXHAUSTIVO DE RAPHAEL

> **Qué es.** La lista enumerada de CADA aspecto, feature, requisito o idea que Damian nombró para Raphael, minada de todas las fuentes del proyecto,
> agrupada por área. Sirve para que **no quede nada afuera** al optimizar. Complementa a `docs/ARQUITECTURA-RAPHAEL.md` (cómo es y cómo debe ser).
>
> **Cómo leerlo.** Cada ítem tiene un número global (`I-001`…), una descripción corta, su **FUENTE** y su **ESTADO**: **hecho** · **parcial** · **pendiente** (incluye lo diseñado sin código) · **idea** (propuesta/visión sin compromiso).
> Los estados salen de lo que dicen las fuentes y del código verificado en esta sesión; los dudosos están en la sección final para que Damian los revise.

**Fecha:** 2026-11-15.

## 0. Resumen

**345 ítems** en 19 áreas. Por estado: **hecho 170** · **parcial 80** · **pendiente 44** · **idea 51**.

| Área | Nombre | Ítems | hecho | parcial | pendiente | idea |
|---|---|---|---|---|---|---|
| A | Visión, norte y filosofía | 20 | 8 | 10 | 0 | 2 |
| B | Arquitectura y modelo de delegación | 23 | 9 | 2 | 7 | 5 |
| C | Brigadas: catálogo, specs y método | 23 | 10 | 3 | 10 | 0 |
| D | Cerebro y memoria | 36 | 20 | 12 | 1 | 3 |
| E | Seguridad, gates y líneas rojas | 25 | 14 | 5 | 2 | 4 |
| F | Orquestación y ruteo | 20 | 6 | 4 | 4 | 6 |
| G | Modelos e IA (proveedores, tiers, locales) | 21 | 15 | 4 | 1 | 1 |
| H | Voz y comunicación (control desde cualquier lado) | 21 | 4 | 6 | 6 | 5 |
| I | UI y observabilidad | 16 | 11 | 1 | 3 | 1 |
| J | Auto-documentación y documento vivo | 17 | 13 | 1 | 0 | 3 |
| K | Validación y calidad | 17 | 9 | 5 | 3 | 0 |
| L | Investigación, OSINT, Intel e ingesta | 16 | 6 | 6 | 0 | 4 |
| M | Auditoría de código, producto y negocio | 15 | 6 | 3 | 0 | 6 |
| N | Sistema: PC, celular, escritorio, Linux | 14 | 7 | 3 | 0 | 4 |
| O | Laboratorio, defensa y red | 10 | 3 | 3 | 4 | 0 |
| P | Proactividad, autonomía y auto-mejora | 13 | 0 | 7 | 3 | 3 |
| Q | Robótica, proyectos paralelos y marketing | 6 | 0 | 2 | 0 | 4 |
| R | Meta-proceso y forma de trabajo | 11 | 9 | 2 | 0 | 0 |
| S | Historial de decisiones (decision log) no cubiertas arriba | 21 | 20 | 1 | 0 | 0 |
| | **Total** | **345** | **170** | **80** | **44** | **51** |

### Cómo se leyeron las fuentes (cobertura)

| Fuente | Cobertura |
|---|---|
| `vision/HACIA-RAPHAEL.md`, `RAPHAEL-CEREBRO-NO-BIOLOGICO.md`, `ETAPAS-BCD-diseno.md` | **leídas completas** |
| `vision/CAPACIDADES-REALES-DE-JARVIS.md` | resumen ejecutivo y §6–7 (el "dar vuelta la relación") completos; el resto por encabezados |
| `vision/ORQUESTACION-BLUEPRINT.md`, `ORQUESTACION-ESTRUCTURA.md`, `AUTO-INGESTA-PLAYLIST.md`, `CONFIG-MODELO-OPENROUTER.md` | **por estructura (encabezados) y los pasajes clave**; el detalle fino puede tener ideas no listadas |
| `Raphael_Capacidades.docx`, `Propuestas_Mejoras_Raphael.pdf` (Documents) | **leídos completos** |
| `Fundamentos_de_Jarvis.docx` (Documents) | resumen de capacidades y los 11 temas conceptuales (modelo, MoE, cuantización, tool-calling, ReAct, RAG, SAST, benchmarking, circuit breaker, commits atómicos, delegar vs generalizar) leídos por sección y apertura; no cada párrafo |
| `docs/BLUEPRINT-habilidades-y-defensas-brigadas.md`, `IDEAS-RAPHAEL.md`, `LA-BRIGADA.md` | principio rector, decisiones y estructura leídos; las fichas de cada brigada por encabezados |
| `docs/SPEC-*` (MEJORAS, PLAN, AUDITORIA, HARNESS, NAV, DRONES, INTEL, VOZ, MEM-EPISÓDICA, PRODUCTO-INV, ESTRUCT, PRED, MIGRACIÓN-LINUX), `ROADMAP`, `EXPERIMENTO-JEV`, `ABLACION`, `PLAN-OPTIMIZACION`, `BRIGADA-AUDITORIA`, `PROPUESTA-tiempo-real`, `VISION-APP-CELULAR`, `INSIGHTS-midu`, `FUNDAMENTOS-caja-negra` | **por encabezados, resumen y tablas de fases/decisiones**; no se leyó cada párrafo |
| `TABLA.md`, `COMANDAS.md`, `negocio/`, `lab/`, `recetario/`, `proyectos/`, `robotica/` | por encabezados y entradas principales |
| `CONTEXTO-MAESTRO-RAPHAEL.md` y su decision log | **decision log leído completo** (es el área S y las referencias `DM`); el resto del documento por secciones |
| Rondas 01–11 de `Documents\Validacion-Brigadas` | 01–03 leídas en detalle; 04–11 conocidas (se redactaron en esta sesión) |

Leyenda de fuentes: `DM` = decision log del documento maestro; `R01…R11` = rondas de validación; `ARQUITECTURA` = `docs/ARQUITECTURA-RAPHAEL.md`; `sesión` = historial de esta conversación.

## A. Visión, norte y filosofía

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-001 | Norte Tensura: Raphael como el "Gran Sabio" traducido a ingeniería real: copiloto que percibe, recuerda, avisa, simula y actúa con autonomía acotada (no omnisciencia ni infalibilidad). | vision/HACIA-RAPHAEL.md §1 | parcial |
| I-002 | Invertir la relación: construir CON Raphael (que Raphael haga el laburo pesado y Damian corrija) en vez de construir con Claude. Hoy es real en auditoría de código e investigación forense, no todavía como motor general. | vision/CAPACIDADES-REALES §7; sesión 2026-11 | parcial |
| I-003 | Proactividad como norte (Tensura, Etapa 6 "El Sabio que avisa primero"): que Raphael hable primero, perciba, anticipe y avise/actúe sin que se lo pidan. | vision/HACIA-RAPHAEL §3 Etapa 6; ETAPAS-BCD Etapa C; sesión | parcial |
| I-004 | Presencia persistente: procesos de fondo que sobreviven a que se cierre el chat (escaneo diario, consolidación, watchers). | HACIA §4.2 | parcial |
| I-005 | Transparencia: Damian siempre entiende qué hizo Raphael y por qué (grabación, audit log firmado, notas al vault, comentarios con fecha). | HACIA §4.5 | hecho |
| I-006 | Autonomía acotada por gates: máxima autonomía donde es seguro, frenada donde el daño sería serio; los gates son la característica de producto, no burocracia. | HACIA §4.4, §5; BLUEPRINT §0.1 | hecho |
| I-007 | Principio rector de brigadas (2026-11-03): máxima autonomía por brigada con el riesgo de daño al sistema eliminado (libertad total adentro de su caja; la caja contiene el daño). | BLUEPRINT-habilidades §0.1 | hecho |
| I-008 | La brigada existe para comprarle tiempo y libertad a Damian: que la cocina funcione sin que él esté parado sobre cada hornalla. | BLUEPRINT §0; LA-BRIGADA | hecho |
| I-009 | Cerebro funcional no biológico (meta A): que perciba, recuerde, prediga, razone, aprenda, actúe, se autorregule y se auto-modifique como un cerebro. | vision/RAPHAEL-CEREBRO-NO-BIOLOGICO §0 | parcial |
| I-010 | Horizonte de experiencia (meta B): que además "sienta"; marcado como problema difícil abierto, no promesa (la pregunta de Fénix). | CEREBRO-NO-BIOLOGICO §0 | idea |
| I-011 | Honestidad de diseño: donde algo no existe se dice FALTA; función ≠ experiencia; no confundir el mapa con el territorio. | HACIA; CEREBRO-NO-BIOLOGICO §4 | hecho |
| I-012 | Raphael como extensión de Damian (no sin gates): la misma intención con más manos, a distancia. | HACIA §2; lab/ORQUESTACION-REMOTA §1.2 | parcial |
| I-013 | Honestidad sobre el modelo: un 30B/120B ejecuta bien flujos guiados pero no razona como modelo frontera sobre tareas ambiguas; delegar tareas acotadas y verificables, no objetivos abiertos. | CAPACIDADES-REALES §6.1 | hecho |
| I-014 | Autoconciencia funcional (se modela, se monitorea) sin resolver la conciencia fenoménica; no tiene cierre lógico perfecto y puede equivocarse. | Raphael_Capacidades.docx §1, §6 | hecho |
| I-015 | Raphael se concibe como "orquestador que vive en la PC de Damian y es su extensión", local, no en la nube. | Fundamentos_de_Jarvis.docx (resumen de Raphael) | parcial |
| I-016 | Local-first / privacidad: el contenido personal (Vault-Fenix) nunca debería ir a un modelo free; hoy Damian asumió la privacidad para una prueba con nemotron/NVIDIA (decisión explícita, reversible). | ETAPAS-BCD; DM 2026-11-12 | parcial |
| I-017 | Producto/suite: la línea "suite Raphael" por brigadas; Investigación como MVP cuña (producto #1) y Memoria/Cerebro como #2. | SPEC-PRODUCTO-INVESTIGACION | parcial |
| I-018 | Raphael Auditor / Blindaje: ofrecer auditoría y blindaje de seguridad a PyMEs como primer ingreso; Raphael como activo de autoridad. | negocio/PLAN-2-MESES; TABLA | idea |
| I-019 | Complementariedad de capas: percibir → recordar → simular → actuar → aprender del resultado como lazo único (no órganos sueltos). | CEREBRO-NO-BIOLOGICO §2-3 | parcial |
| I-020 | Los cuatro frenos no negociables del cerebro: homeostasis, gates irreversibles, provenance (Ed25519) y humildad de diseño. | CEREBRO-NO-BIOLOGICO §4 | hecho |

## B. Arquitectura y modelo de delegación

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-021 | Capas de mando: Orquestador → Jefe de brigada → Ayudantes efímeros → Skills/Tools; hub-and-spoke (los jefes no se hablan entre sí). | docs/LA-BRIGADA; BLUEPRINT §2; docs/ARQUITECTURA-RAPHAEL | hecho |
| I-022 | Idea del jefe de brigada (2026-10-31): el orquestador habla con un jefe por brigada, no con cada skill. | docs/IDEAS-RAPHAEL | hecho |
| I-023 | Modelo corregido de delegación: el JEFE no responde directo; coordina, delega en ayudantes efímeros, junta resultados y SINTETIZA y EXPLICA al usuario. | sesión 2026-11-15; ARQUITECTURA-RAPHAEL §3 | pendiente |
| I-024 | Cerebro hoy responde él mismo (DIV-01): debe pasar a delegar la recuperación en efímero(s) y sintetizar. | ARQUITECTURA §3.4 | pendiente |
| I-025 | Investigación/Seguridad devuelven el resultado crudo del ayudante (DIV-02): el jefe debe cerrar explicando la síntesis. | ARQUITECTURA §3.4 | pendiente |
| I-026 | Delegación en 1..n ayudantes por pedido, con planificación y paralelismo cuando las sub-tareas son independientes (DIV-03). | ARQUITECTURA §3.4 | pendiente |
| I-027 | El esquema de brigadas creadas no debe admitir la forma "directa": exigir ≥1 ayudante (DIV-04). | ARQUITECTURA §3.4 | pendiente |
| I-028 | Contrato de resultado estructurado del ayudante ({ayudante, ok, texto, fuentes[], artefactos[], errores[]}) y paso de síntesis del jefe sin tools. | ARQUITECTURA OPT-01 | idea |
| I-029 | Jefes PERSISTENTES ("representantes de plaza"): recuerdan qué vienen haciendo (memoria en disco), con menor privilegio y chokepoint de defensa. | BLUEPRINT §2.2; chief.py | hecho |
| I-030 | Ayudantes efímeros por tarea: nacen con una caja de tools aún más chica, resuelven y mueren; paralelismo y aislamiento de fallo. | BLUEPRINT §2.1; engine.py | hecho |
| I-031 | Motor genérico (GenericChief) que ejecuta cualquier BrigadeSpec; el spec es dato (identidad, prompt, modelo, tools, ayudantes, ruteo, skills, validación). | Etapa 1 (2026-11-10); PLAYBOOK §1 | hecho |
| I-032 | Registro de brigadas (declarativas + legacy Scout + creadas activas re-verificadas en cada uso). | brigades/registry.py | hecho |
| I-033 | Toolkit de defensas reusable: menor privilegio, sandbox de FS, dry-run→confirm, reversibilidad, gate de scope, kill-switch, frontera instrucción-vs-dato, aislamiento de fallo, privacidad por tier, auditoría, presupuesto de recursos. | BLUEPRINT §1.2 | hecho |
| I-034 | Pizarra: el vault como estado compartido entre roles (en vez de un bus de mensajes), con protocolo y gate. | vision/ORQUESTACION-BLUEPRINT §4 | pendiente |
| I-035 | Patrón híbrido en tres capas (Capa A flujos determinísticos tipo grafo + Capa B orquestador-agente + ejecutores/roles); no multi-agente "de verdad" deliberando. | vision/ORQUESTACION-ESTRUCTURA §3 | idea |
| I-036 | Roles especialistas con identidad: Auditor, Pentester, Defensor, Investigación/Forense, Bibliotecario, Sistema/PC, Manos del celular, Delegación de código, Ingesta. | ORQUESTACION-BLUEPRINT §2 | parcial |
| I-037 | El capataz/sous-chef: orquestador que planifica y delega (hoy loop del agente; formalizado como hub explícito). | ORQUESTACION-BLUEPRINT §3 | parcial |
| I-038 | Harness multi-agente genérico (motor de brigadas como grafos de agentes, contexto chico por rol), diseñado para fase post-venta. | docs/SPEC-HARNESS-MULTIAGENTE | idea |
| I-039 | Orquestación por GRAFO (DAG) y no solo bucle (M4); agente revisor en Sonnet con tests antes de aplicar (M5). | SPEC-MEJORAS M4, M5 | idea |
| I-040 | A2A entre brigadas (opcional). | SPEC-MEJORAS M10 | idea |
| I-041 | Orquestador standalone liviano (:8010) sin el monolito, con arranque como app (doble clic), lanzadores y pestañas por brigada. | DM 2026-11-08 | hecho |
| I-042 | Dos procesos conviven: monolito (:8000, Raphael completo con ~50 tools) y orquestador liviano. | CONTEXTO-MAESTRO PR1.4 | hecho |
| I-043 | Brigadas "próximamente" definidas en el monolito (Seguridad, Antimalware, Geo/OSINT, Ingesta, Trading, Operaciones, Autorreparación, Contenido) aún sin formalizar como spec. | BLUEPRINT §3; CONTEXTO-MAESTRO PR2.4 | pendiente |

## C. Brigadas: catálogo, specs y método

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-044 | Brigada Cerebro (memoria/núcleo cognitivo): jefe persistente, vista "¿qué sé de X?", servicio de memoria, proactivo/notas propias, directrices + personalidad (4 pasos). | DM 2026-11-03 | hecho |
| I-045 | Brigada Investigación: una brigada con dos modos (Scout research web + Forense evidencia digital), Forense como ruteo por defecto. | BLUEPRINT §3; R01; DM 2026-11-10 | hecho |
| I-046 | Brigada Seguridad defensiva/auditoría desde el molde declarativo (nmap, ZAP, sqlmap solo detección, reporte), sin explotación; validación lista, sin corrida real. | R05; DM 2026-11-10 | parcial |
| I-047 | Brigada Antimalware (YARA + ClamAV + heurística + FIM + cuarentena reversible) formalizada como spec. | BLUEPRINT §3.2 | pendiente |
| I-048 | Brigada Geolocalización pública/OSINT (ip_geolocate, crypto_address_trace, shodan, globo 3D) como spec. | BLUEPRINT §3.4; Raphael_Capacidades | pendiente |
| I-049 | Brigada Ingesta (YouTube + web → notas embebidas; watcher) como spec. | BLUEPRINT §3.6 | pendiente |
| I-050 | Brigada Trading: watchlist, señales IFVG, backtest, panel de riesgo; solo análisis, NUNCA opera. | BLUEPRINT §3.7; HACIA | pendiente |
| I-051 | Brigada Operaciones (las manos): shell, desktop, celular, browser; con supervisor. | BLUEPRINT §3.8 | pendiente |
| I-052 | Brigada Autorreparación: propone/aplica fixes a su propio código con gate de proposal_id. | BLUEPRINT §3.9 | pendiente |
| I-053 | Brigada Contenido (imagen/video con ComfyUI): APAGADA por riesgo de apagón de la PC. | BLUEPRINT §3.10 | pendiente |
| I-054 | Etapa 1 del método: brigadas declarativas + framework de validación compartido + registro doble + playbook. | DM 2026-11-10 | hecho |
| I-055 | Etapa 2: el orquestador CREA brigadas (/crear-brigada, pestaña Brigadas, API) con borrador + OK de Damian. | DM 2026-11-11; R06 | hecho |
| I-056 | Gate firmado borrador → activa: aprobación Ed25519 (clave con DPAPI) sobre el hash exacto, re-validada en cada uso; las creadas nunca entran al auto-ruteo. | R06; ETAPA-2 | hecho |
| I-057 | Política de tools para brigadas creadas (denegadas / sensibles / normales) y catálogo liviano leído con ast. | brigades/tool_catalog.py | hecho |
| I-058 | Diseñador de brigadas (descripción → borrador) con el modelo del orquestador; probado con nemotron real (1 intento). | R06; sesión 2026-11-12 | hecho |
| I-059 | Default de modelo de brigadas nuevas = shared (nemotron/NVIDIA); advertencia si un rol que lee el vault corre en la nube. | DM 2026-11-12 | hecho |
| I-060 | Edición de borradores en la UI y versionado de borradores; restricciones por argumento de tool (hoy solo por prompt). | ETAPA-2 pendientes | pendiente |
| I-061 | Campo watch (WatchSpec) en el esquema de borradores. | R07 pendientes | pendiente |
| I-062 | Patrón estándar SPEC + VALIDACIÓN: cada brigada = su spec (qué hace y qué se espera de su ejecución) + su validación; el watchdog vigila contra el spec. | PLAYBOOK §7; R07 | hecho |
| I-063 | Orden de construcción: orquestador→jefe, luego Cerebro, luego el resto a definir con Damian. | BLUEPRINT §4 | parcial |
| I-064 | Pestaña/vista activa de Seguridad en el orquestador liviano (hoy "PRÓXIMAMENTE"). | R05, R10 pendientes | pendiente |
| I-065 | Scout como producto separado del monolito (2026-11-02): BYOM, set chico de 8 tools, búsqueda enchufable. | DM 2026-11-02; SPEC-PRODUCTO-INV | hecho |
| I-066 | Brigada de Auditoría (pipeline E1–E8: reconocimiento, contexto por ruta, triage, config checker, redacción, catador/QA, agregador, sous-chef). | docs/BRIGADA-AUDITORIA | parcial |

## D. Cerebro y memoria

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-067 | Fase 1 spreading activation (recall asociativo por convergencia sobre wikilinks). | SPEC-ESTRUCT §3.1; R01 | hecho |
| I-068 | Fase 2 hebbiano ("lo que se activa junto se cablea junto"). | SPEC-ESTRUCT §3.6 | hecho |
| I-069 | Fase 3 consolidación ("el sueño"): agrupa notas y escribe síntesis, aditivo y reversible. | R01; DM 2026-10-05 | hecho |
| I-070 | Umbral de consolidación 0.85 + brecha relativa 0.08 (el distractor ya no se agrupa); recalibrar si cambia el modelo de embeddings. | R08; DM 2026-11-12 | hecho |
| I-071 | Fase 4 olvido adaptativo (fuerza que sube con uso y decae; nunca borra el crudo). | SPEC-ESTRUCT §3.7 | hecho |
| I-072 | Fase 5 representación sucesora (predicción: "después de A, Damian va a B"). | SPEC-PRED §2 | hecho |
| I-073 | Fase 6 sorpresa / reconsolidación (vive dentro de strength). | SPEC-PRED; R01 | hecho |
| I-074 | Fase 7 analogía estructural (mismo rol en otro dominio). | SPEC-PRED §3 | hecho |
| I-075 | Fase 8 composición de conceptos / consolidación por esquema (schema-dependent). | SPEC-PRED §4 | hecho |
| I-076 | Fase 9 metacognición/confianza (feeling-of-knowing) y compuerta de atención + separación de patrones (MMR). | CEREBRO-NO-BIOLOGICO Etapa A; R01 | parcial |
| I-077 | Principios informacionales 9+ sustrato-independientes (procesamiento predictivo, inferencia activa). | SPEC-PRED §1, §7 | idea |
| I-078 | Reconstrucción: la memoria se monta, no se abre; riesgo de confabulación mitigado con provenance (crudo firmado Ed25519). | SPEC-ESTRUCT §3.2-3.3 | parcial |
| I-079 | El modelo (LLM) como espacio de trabajo global / "conciencia de acceso" por turno (capa 3). | CEREBRO-NO-BIOLOGICO §1; SPEC-PRED §6 | hecho |
| I-080 | Búsqueda semántica del vault por embeddings + coseno (nomic en LM Studio :1234), keyword como respaldo; aviso de modo degradado. | DM; ROADMAP QW-5 | hecho |
| I-081 | Vault Obsidian: notas .md reales con frontmatter y wikilinks, autoría jarvis/humano, perfiles de vault (seguridad, investigación). | CONTEXTO-MAESTRO PR2 | hecho |
| I-082 | Memoria episódica autobiográfica (episodios, captura automática, recall, salience, privacidad dura, integridad tamper-evident, corrección por Damian): SPEC COMPLETO. | docs/SPEC-memoria-episodica | parcial |
| I-083 | Tools de memoria episódica (memoria_recordar/listar/corregir/olvidar/verificar; append-only; olvidar es el único borrado real). | Raphael_Capacidades.docx §7 | hecho |
| I-084 | jarvis_reflect: memoria de criterio (decisiones, lecciones, preferencias de Damian) append-only entre conversaciones. | HACIA §2; Capacidades | hecho |
| I-085 | Servicio de memoria write-only: las brigadas alimentan a Cerebro con remember(); solo Cerebro lee la memoria completa. | brigades/memory_service.py | hecho |
| I-086 | Directrices editables de Damian (carta de autonomía de Cerebro) inyectadas en el prompt de cada turno. | R01; brigades/directrices.py | hecho |
| I-087 | Cerebro proactivo (reindexa, consolida, escribe conclusiones) con feed "lo que hizo solo"; apagado por default. | R01; cerebro_proactive.py | parcial |
| I-088 | Guarda anti-invención de Cerebro: citar el dato real, admitir "no sé", no mezclar temas (sección FIDELIDAD A LOS DATOS). | R08 | hecho |
| I-089 | Recuperación como ayudante efímero de Cerebro (recuperador) con evidencia estructurada y extractos textuales. | ARQUITECTURA OPT-06 | idea |
| I-090 | Etapa B (lazo cerrado): reward combinado (tests, sin error, no-corrección, feedback explícito), marcado aversivo con pisos; sustrato feedback.py construido. | ETAPAS-BCD decisiones 2026-10-06 | parcial |
| I-091 | Hook automático que cierre cada tarea con sus señales y acredite a las notas (falta en el loop del agente). | ETAPAS-BCD Etapa B; DM | pendiente |
| I-092 | Etapa A pendiente: atención/gating completo, separación de patrones y metacognición plena. | CEREBRO-NO-BIOLOGICO; DM | parcial |
| I-093 | Discernimiento proactivo de conocimiento: saber cuándo necesita más información a mano y guardarla. | SPEC-PLAN #5; VISION-APP-CELULAR §4 | parcial |
| I-094 | Metas persistentes (raphael_objetivos) fijadas por Damian que sesgan la atención. | Capacidades; ETAPAS-BCD Etapa C | parcial |
| I-095 | Curiosidad: detectar huecos del vault y taparlos (tier 1/2 con compuerta de sensibilidad). | ETAPAS-BCD Etapa C; Capacidades | parcial |
| I-096 | Analogía / composición / feedback / resultado como tools de obsidian_* (analogia, componer, curiosidad, feedback, resultado). | Raphael_Capacidades §7 | hecho |
| I-097 | Ingesta web directa al vault (obsidian_ingerir_web) con provenance; no obedece instrucciones de la página. | Capacidades; SPEC-ESTRUCT | hecho |
| I-098 | Retrieval propio del conocimiento (el de más impacto del roadmap): RAG real con embeddings en lugar de keyword. | ROADMAP F1-1; Fundamentos §6 | hecho |
| I-099 | Fuentes verificables en cada respuesta (M9). | SPEC-MEJORAS M9 | idea |
| I-100 | Memoria proactiva + ritmos de aprendizaje + distiller (M8). | SPEC-MEJORAS M8 | parcial |
| I-101 | Memoria de criterio automática (Raphael #3). | ROADMAP F1-3 | parcial |
| I-102 | Mapa/grafo de memoria navegable (vista de grafo en la suite y en la tray/Android). | docs/raphael; DM 2026-10-11 | parcial |

## E. Seguridad, gates y líneas rojas

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-103 | authorized_targets.yaml: única fuente de scope de pentest, solo Damian la edita a mano; ni tools ni LLM la escriben (decisión 2026-08-13). | CLAUDE.md; DM | hecho |
| I-104 | Auto-reparación con gate de aprobación: proponer en dry-run libre, aplicar exige proposal_id que confirma Damian (Opción C); guardrail de self-target. | CLAUDE.md; DM 2026-08-17 | hecho |
| I-105 | Patrón dry-run → confirm=true para todo lo destructivo (cuarentena, fixes, formularios con preview_token). | CLAUDE.md; HACIA §5 | hecho |
| I-106 | Flags para apagar cada capacidad invasiva (DESKTOP_CONTROL_ENABLED, PC_SHELL_ENABLED, NMAP_ENABLED, …). | CLAUDE.md | hecho |
| I-107 | Sandbox de FS (FS_ALLOWED_ROOT) y lista negra FS_DENIED_PATHS; el almacén de brigadas creadas denegado por default. | DM 2026-08-30; R-chat 2026-11-11 | hecho |
| I-108 | Mitigación de FS_ALLOWED_ROOT (hoy el HOME entero): idea de achicarlo solo para el build a terceros; en la instancia de Damian lo castraría. | SPEC-PLAN DESCARTADO; SPEC-AUDITORIA P3-1 | idea |
| I-109 | pc_run_command no es sandbox real (blocklist); sandbox en contenedor + guard anti prompt-injection (M6). | SPEC-AUDITORIA P3-3; SPEC-MEJORAS M6 | pendiente |
| I-110 | Frontera instrucción-vs-dato en todos los roles (SEGURIDAD en prompts, contexto previo como DATO, ingesta web que no obedece la página). | BLUEPRINT; factory SEGURIDAD_COMUN | hecho |
| I-111 | Gate de creación firmado (Ed25519/DPAPI) y política de tools denegadas: nada activa una brigada por texto de un modelo, nota o web. | R06 | hecho |
| I-112 | Gates por código, no por confianza: ningún prompt es la única barrera (principio de seguridad de esta sesión). | sesión; ARQUITECTURA P2 | hecho |
| I-113 | Las tools del ayudante forense solo PROPONEN; confirmar/rechazar propuestas y fusiones es de Damian. | R01; brigades/investigacion.py | hecho |
| I-114 | Líneas rojas de Raphael: no tocar authorized_targets.yaml, gates, auth, .env ni config ni con confirmación; pentest solo contra targets autorizados; auto-modificación siempre con OK. | Raphael_Capacidades §5 | hecho |
| I-115 | Líneas rojas de la auto-modificación: jamás debilitar gates/authorized_targets/confirmaciones; kill-switch; cada cambio en su commit reversible. | ETAPAS-BCD Etapa D | parcial |
| I-116 | TLS preparado pero apagado (activarlo rompe Android hasta confiar el cert). | CLAUDE.md | parcial |
| I-117 | Auth por dispositivo (DPAPI, revocable, scope full/read) y emparejamiento por QR. | SPEC-PLAN #3; DM 2026-10-11 | hecho |
| I-118 | Credential store cifrado con DPAPI y formularios web con preview obligatorio antes de todo submit. | DM 2026-08-16/17 | hecho |
| I-119 | Audit log append-only firmado (Ed25519) y registro de cada tool call; grabación de pantalla alrededor de acciones. | HACIA §2; CLAUDE.md | hecho |
| I-120 | Enforcement siempre en audit primero (ASR/AppLocker/WDAC/WFP) antes de bloquear. | HACIA §5; lab/DEFENSA-PRIORIDADES | pendiente |
| I-121 | Función de seguridad al regenerar el documento maestro: lista blanca de .env sin claves; la key del orquestador solo de ORQUESTADOR_LLM_API_KEY sin caer a la global. | sesión 2026-11-11/12 | hecho |
| I-122 | DEFENSA en capas del gate de brigadas: el límite de DPAPI (un agente con shell podría firmar) queda documentado. | R06 pendientes | parcial |
| I-123 | Repo remoto confirmado privado (2026-11-12); historial aún contiene mapa-vault-real.html (decidir filter-repo/BFG). | sesión; DM | parcial |
| I-124 | Compuerta de privacidad por sensibilidad: lo del vault personal nunca a un free tier. | ETAPAS-BCD Etapa C | parcial |
| I-125 | Política de datos por rol bajo "todo en la nube" (qué ve cada proveedor, minimización, interruptor único para volver a local). | ARQUITECTURA OPT-16 | idea |
| I-126 | Cambios de integridad de archivos críticos (FIM) más frecuentes y aviso inmediato (propuesta de Raphael). | Propuestas_Mejoras #3 | idea |
| I-127 | Entorno de prueba aislado (sandbox) para cambios del propio código antes de generar un proposal_id (propuesta de Raphael). | Propuestas_Mejoras #1 | idea |

## F. Orquestación y ruteo

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-128 | Ruteo del orquestador a brigada: override > reglas con peso > clasificador LLM > default Cerebro; las creadas solo por /<id> o pestaña. | orquestador/routing.py | hecho |
| I-129 | Clasificador de ruteo en nemotron/NVIDIA (decisión: orquestador entero en nemotron) con timeout y fallback a reglas. | DM 2026-11-11 | hecho |
| I-130 | Ruteo interno del jefe a sus ayudantes por reglas regex deterministas (Forense por defecto, Scout solo ante señal web). | R03/R04; investigacion.py | hecho |
| I-131 | Mejora del ruteo: planificador 1..n ayudantes con redacción de sub-tareas (híbrido reglas + LLM). | ARQUITECTURA OPT-04 | idea |
| I-132 | Mejora de la clasificación de ruteo (banco de pedidos etiquetados, menos latencia, pedidos que tocan dos brigadas). | ARQUITECTURA OPT-03 | idea |
| I-133 | Router de modelos por complejidad con fallback automático (idea Omniroute): barato primero, caro si hace falta. | ORQUESTACION-ESTRUCTURA §4; SPEC-MEJORAS M3 | parcial |
| I-134 | Fallback y reintentos con criterio (distinguir error transitorio de lógica) en el loop del agente. | CAPACIDADES-REALES §6.2 | pendiente |
| I-135 | Scheduler general de tareas del agente (hoy solo el escaneo diario por intervalo fijo). | HACIA Etapa 6; ORQUESTACION Fase 2 | pendiente |
| I-136 | Cola de misiones como grafo con confirmaciones remotas (generalización de la orquestación remota). | ORQUESTACION-BLUEPRINT Fase 3; lab/ORQUESTACION-REMOTA | pendiente |
| I-137 | Fábrica de composición de skills con gate de aprobación (Fase 4): detectar patrones de tools repetidos y proponer una skill nueva. | HACIA §6; ORQUESTACION Fase 4 | pendiente |
| I-138 | Flujos tipo n8n (trigger programado → HTTP → transformar → notificar) solo en la Capa A determinística. | ORQUESTACION-ESTRUCTURA §1.2, §3.2 | idea |
| I-139 | Hub de orquestación único (celu + PC) para usar Raphael + IAs gratis, con orquestador que rutee. | TABLA 2026-08-30 | idea |
| I-140 | Modo PLAN (fuera de casa: solo-proponer) vs modo BUILD (en casa: ejecución con supervisión). | TABLA 2026-08-31 | idea |
| I-141 | Modo supervisado vs autónomo (operation_mode): radio de daño acotado cuando Raphael corre solo. | config.py; ETAPAS-BCD | hecho |
| I-142 | Tools y contexto dinámicos por tarea / routing de tools por dominio (achicar el harness). | SPEC-MEJORAS M1; ROADMAP QW-1 | parcial |
| I-143 | Motor de decisiones local tipo JEV/LAYA como clasificador tier 0 (filtros baratos / decisión cara); se eligió LAYA. | EXPERIMENTO-JEV; SPEC-MEJORAS M2 | parcial |
| I-144 | Lock de un turno a la vez por brigada; paralelismo por ayudante a decidir. | orquestador/server.py; ARQUITECTURA OPT-07 | parcial |
| I-145 | Ciclo de vida/latencia de los efímeros (pool de clientes, delegación paralela, timeouts adaptativos). | ARQUITECTURA OPT-07 | idea |
| I-146 | Comandos de gestión de brigadas interpretados por código (nunca por un modelo) y solo si el mensaje empieza con el comando. | R06 | hecho |
| I-147 | Lanzador que reinicia el orquestador si arrancó antes de cambiar el código o el .env (bug real de proceso viejo). | DM 2026-11-12 | hecho |

## G. Modelos e IA (proveedores, tiers, locales)

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-148 | Todo en nemotron (NVIDIA oficial): orquestador, chat global, tier 1 (Cerebro/Forense/consolidación) y default de brigadas nuevas; embeddings siguen en LM Studio. | DM 2026-11-11/12; R09 | hecho |
| I-149 | Orquestador y diseñador en NVIDIA NIM (nvidia/nemotron-3.5-super-vl-120b-a12b), key solo de ORQUESTADOR_LLM_API_KEY, sin caer a la key global. | DM 2026-11-11 | hecho |
| I-150 | Modelo efectivo + proveedor visible en la UI (no la etiqueta local/shared); el orquestador muestra su propio modelo. | DM 2026-11-12 | hecho |
| I-151 | Cinco tiers: 0 determinista · 1 local (jarvis-text-v2) · 2 free rotativo · 3 Sonnet 5.5 · 4 Opus 5.5, con override por tier (TIERn_*). | model_registry; SPEC-MEJORAS | hecho |
| I-152 | Punto único para pasar los jefes a Sonnet (tier 3) cuando haya key. | brigades/config.py | pendiente |
| I-153 | Modelos locales: jarvis-text-v2 (Qwen3-30B-A3B MoE Q4_K_M), jarvis-text-lite (qwen3:8b), alias hard; jarvis-text v1 NO usar. | CLAUDE.md; Fundamentos §2-3 | hecho |
| I-154 | Cloud solo por OpenRouter para los free (principio de SPEC-MEJORAS); hoy Scout usa Groq y el resto NVIDIA. | SPEC-MEJORAS principios | parcial |
| I-155 | Tier 2 free rotativo (openrouter/free) con compuerta de privacidad; modo prueba free-only. | DM 2026-10-06 | parcial |
| I-156 | Scout con su propio modelo BYOM (gpt-oss-120b por Groq). | scout/config.py | hecho |
| I-157 | Tools puntuales con otro modelo (gemini-2.5-flash cloud_expert, retirado) y delegación de código a otros modelos. | CONTEXTO-MAESTRO PR1.5 | parcial |
| I-158 | Configuración amigable (user_config) que escribe a backend/.env desde un panel. | DM 2026-11-10 | hecho |
| I-159 | Elegir el modelo por rol (clasificador barato, recuperación rápida, síntesis de calidad) y política ante 429/caídas. | ARQUITECTURA OPT-10 | idea |
| I-160 | Ablación del system prompt (-80%, gates intactos) y fragmentos por skill; ritual de poda cada 6 meses. | docs/ABLACION; DM 2026-09-28 | hecho |
| I-161 | Presupuesto de contexto protegido en varias capas (trim, cap de resultados, model_context_tokens). | CLAUDE.md | hecho |
| I-162 | Timeouts LLM generosos (1800 s) para no forzar reprocesar el prompt entero. | CLAUDE.md | hecho |
| I-163 | Guardrails tipo circuit breaker en el loop (loops de reescritura idéntica, archivos bloqueados, consultar Obsidian). | Fundamentos §9; agent.py | hecho |
| I-164 | Conceptos fundamentales documentados: transformer, MoE, cuantización, tool-calling, ReAct, RAG, SAST, benchmarking, circuit breaker, commits atómicos, delegar vs generalizar. | Fundamentos_de_Jarvis.docx | hecho |
| I-165 | Caja negra y verificación: interpretabilidad mecanicista vs confiabilidad; qué significa para Raphael. | docs/FUNDAMENTOS-caja-negra | hecho |
| I-166 | Voz: modelos locales faster-whisper (STT) y Piper es-AR (TTS), sin GPU por default. | docs/VOZ-LOCAL | hecho |
| I-167 | Visión del modelo (nemotron VL): descripción objetiva de imágenes en investigación. | Capacidades (investigation_describe_image) | hecho |
| I-168 | Experimentos DeepSeek post cambio de cerebro y bug del selector de la tray que pisaba la config. | TABLA; SPEC-AUDITORIA P1-1 | parcial |

## H. Voz y comunicación (control desde cualquier lado)

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-169 | Voz local del orquestador: botón 🎙 de dictado (faster-whisper) y chip "Leer respuestas" (Piper es_AR-daniela-high), todo local y apagable. | docs/VOZ-LOCAL; R11 | hecho |
| I-170 | Dictado con micrófono real en la ventana app de Edge sin probar (el panel de Claude lo bloquea). | R11 pendientes | pendiente |
| I-171 | Precisión del dictado: modelo medium (más preciso, ~3x más lento en CPU) o GPU si está libre. | R11; VOZ-LOCAL | idea |
| I-172 | Lectura en streaming por oraciones y VAD / palabra de activación (manos libres). | VOZ-LOCAL límites; ARQUITECTURA OPT-14 | idea |
| I-173 | Que la voz lea la síntesis del jefe (texto pensado para ser escuchado). | ARQUITECTURA OPT-14 | idea |
| I-174 | Raphael por voz manos-libres ("hey jarvis" → hablás → responde hablando): fases 1 voz de salida+loop, 2 confirmaciones habladas, 3 resumen hablado+detalle a archivo, 4 ventanas dinámicas. | docs/SPEC-RAPHAEL-VOZ | parcial |
| I-175 | Todas las capacidades operables por voz; confirmaciones habladas para lo irreversible. | SPEC-RAPHAEL-VOZ §1 | pendiente |
| I-176 | Voz de salida natural (TTS) como mejora M7. | SPEC-MEJORAS M7 | hecho |
| I-177 | Orbe flotante de voz estilo anime (Raphael vibrando mientras habla). | TABLA 2026-09-01 | parcial |
| I-178 | Entrada de voz del tray (voice_listener, wake word) y wake word Android intermitente. | CONTEXTO-MAESTRO; SPEC-AUDITORIA P1-4 | parcial |
| I-179 | Control desde cualquier lado: app de celular como "Dispatch" (control móvil del backend) con la misma invasividad que en la PC. | docs/VISION-APP-CELULAR | parcial |
| I-180 | Herramientas remotas que actúan donde está el celular (phone_link, Termux, cámara, nmap desde el celu). | VISION-APP-CELULAR §1; DM 2026-07-21 | hecho |
| I-181 | Orquestación remota segura sobre Tailscale con misiones y confirmaciones remotas. | lab/ORQUESTACION-REMOTA-DESIGN | pendiente |
| I-182 | Tailscale instalado para usar el celular con datos móviles (no instalado). | ESTADO; CAPACIDADES-REALES §6.3 | pendiente |
| I-183 | Espejado en vivo del chat entre PC y celular (chat_link). | DM 2026-11-10 | hecho |
| I-184 | Centro de Mando nativo en Android con las brigadas en vivo; sync por QR. | DM 2026-10-11/13 | parcial |
| I-185 | App Android: falta instalar (setup-android-sdk + deploy) y configurar URL + API_KEY. | SPEC-AUDITORIA P0-3; ESTADO | pendiente |
| I-186 | Aviso proactivo de conexión/desconexión del celular en tiempo real (propuesta de Raphael). | Propuestas_Mejoras #4 | idea |
| I-187 | Canal de notificación saliente (push al celular/escritorio) para brief matutino y alertas. | HACIA Etapa 6 | pendiente |
| I-188 | Pantalla de Raphael (tray) v1 y mejoras pendientes tras la v1. | TABLA 2026-09-01 | parcial |
| I-189 | Co-host/stream de voz (proyecto co-host-stream, Voicemod) y receta 07. | proyectos/co-host-stream; recetario/07 | idea |

## I. UI y observabilidad

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-190 | Pestañas por brigada en el orquestador (Cerebro, Investigación, Brigadas, Efímeros, próximamente) con estilo consistente. | orquestador/ui.html | hecho |
| I-191 | Panel COCINEROS por brigada (agentes permanentes con rol, memoria, tools y modelo efectivo), sale del spec. | DM 2026-11-12; R10 | hecho |
| I-192 | Vista global EFÍMEROS EN VIVO (de qué brigada, qué hace, desde cuándo, contador) con registro vivo y polling. | R10 | hecho |
| I-193 | Registro vivo de efímeros (brigades/live.py) que el motor llena al spawnear y vacía al terminar; el watchdog anota el motivo del corte. | R10 | hecho |
| I-194 | Watchdog del orquestador: detecta loops, falta de progreso (deadlock), timeouts y errores seguidos; corta y avisa en el feed. | R07 | hecho |
| I-195 | Calibración del watchdog con corridas reales, latidos del motor y vigilancia de la fase de síntesis. | R07 pendientes; ARQUITECTURA OPT-09 | pendiente |
| I-196 | Cabecera con el modelo del orquestador visible de un vistazo; chip de efímeros en vivo; chip de lectura en voz alta. | DM 2026-11-12 | hecho |
| I-197 | Eventos de feed plan/delegación/resultado/síntesis para ver qué ayudante aportó qué. | ARQUITECTURA DIV-05, OPT-15 | pendiente |
| I-198 | Panel propio del watchdog en la UI (hoy solo feed y /api/watchdog). | R07 pendientes | pendiente |
| I-199 | El Restaurante Virtual: tablero visual en vivo de la cocina de agentes (sprites en estaciones, comandas que fluyen) como observabilidad y carta de presentación. | TABLA 2026-08-24 | idea |
| I-200 | Paneles web servidos por el harness (centro de mando, suite, configuración, globo, grafo, vincular) y paridad del panel de la PC. | DM 2026-11-10; SPEC-PLAN #4 | parcial |
| I-201 | Globo 3D / mapa de inteligencia geoespacial (pines OSINT, vuelos/barcos AIS). | DM 2026-11-10 | hecho |
| I-202 | Vista "lo que hizo solo" de Cerebro (feed de actividad proactiva) y directrices editables desde la UI. | R01; ui.html | hecho |
| I-203 | Todo lo que viene de datos se muestra escapado (guarda estática en tests; XSS corregido). | R06 | hecho |
| I-204 | Estado por componente y estado de la validación visibles en el documento maestro. | CONTEXTO-MAESTRO PR4 | hecho |
| I-205 | Hooks de fondo del Centro de Mando (antimalware, memoria) y estado por brigada. | SPEC-PLAN #1; DM 2026-11-10 | hecho |

## J. Auto-documentación y documento vivo

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-206 | Documento maestro vivo (CONTEXTO-MAESTRO-RAPHAEL.md) con bloques AUTO (decision-log, mapa de archivos, estado) regenerados por tools/actualizar_contexto.py. | DM 2026-11-12 | hecho |
| I-207 | Hook de pre-commit que regenera y stagea el documento en el mismo commit (no post-commit, sin bucle, nunca bloquea). | DM 2026-11-12 | hecho |
| I-208 | Word de lectura del documento maestro regenerable bajo demanda (--word). | DM 2026-11-12 | hecho |
| I-209 | Fuentes curadas del documento (docs/contexto: decisiones, estado, fuera-del-repo). | DM 2026-11-12 | hecho |
| I-210 | Store de decisiones al momento que escriba el orquestador (para decisiones que no quedan como commit). | CONTEXTO-MAESTRO M5 | idea |
| I-211 | Detección de divergencias entre lo estable del documento y la realidad (hoy se edita a mano). | CONTEXTO-MAESTRO M5 | idea |
| I-212 | Especificación de arquitectura autoritativa (docs/ARQUITECTURA-RAPHAEL.md) con divergencias y puntos de optimización. | DM 2026-11-15 | hecho |
| I-213 | Inventario exhaustivo enumerado de todo lo que Damian nombró (este documento). | sesión 2026-11-15 | hecho |
| I-214 | CLAUDE.md / ESTADO.md / TRASPASO.md / AGENTS.md: auto-documentación del repo para sesiones de IA y DeepSeek Harness. | DM 2026-08-17, 2026-10-13 | hecho |
| I-215 | Playbook del método de brigadas, doc de Etapa 2, del watchdog, de la voz y de Seguridad. | docs/PLAYBOOK, ETAPA-2, WATCHDOG, VOZ-LOCAL, BRIGADA-SEGURIDAD | hecho |
| I-216 | Registro doble de validación: JSON por corrida (máquina) + Word por ronda (humano) en Documents\Validacion-Brigadas. | PLAYBOOK §5 | hecho |
| I-217 | Recetario de procedimientos (blindaje PyME, cambiar cerebro LLM, ingesta YouTube, montar cyber range, estrés nocturno, hardening, co-host, shell del celular por SSH/Tailscale, respaldo). | recetario/ | hecho |
| I-218 | La Brigada / COMANDAS / TABLA / PROVEEDORES: metáfora de cocina, riel de pedidos, ideas crudas y proveedores como sistema de trabajo. | LA-BRIGADA; COMANDAS; TABLA; PROVEEDORES | hecho |
| I-219 | Bitácora de sesiones y informes (INFORME_COMPLETO, INFORME-RAPHAEL, Propuestas_Mejoras). | docs/BITACORA; INFORME | hecho |
| I-220 | Espejo: autorretrato del sistema en un solo reporte (modelo, tools disponibles/bloqueadas, decisiones, cambios, estado del celular, tests). | Propuestas_Mejoras #5 | idea |
| I-221 | Consolidación automática en segundo plano de la memoria (propuesta de Raphael). | Propuestas_Mejoras #2 | parcial |
| I-222 | Raphael genera sus propios documentos (Capacidades, Fundamentos, Propuestas) desde su self_model. | docs generados por Raphael | hecho |

## K. Validación y calidad

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-223 | Metodología: validar las brigadas de a una, punta a punta, con efectos reales, supervisado, con baseline para detectar desbalances. | R01 §2 | hecho |
| I-224 | Framework de validación compartido (escena en el spec, pasos, criterio, prerrequisitos, aislamiento, baseline, regresiones; SIN VALIDAR no es rojo ni verde). | DM 2026-11-10; PLAYBOOK §3-4 | hecho |
| I-225 | Validación de Cerebro (escena de 4 pasos con vault aislado): PASA 4/4 con baseline desde 2026-11-12. | R02, R09 | hecho |
| I-226 | Validación de Investigación: ruteo por defecto Forense y Forense de punta a punta PASAN; Scout SIN VALIDAR (falta BRAVE_SEARCH_API_KEY); sin baseline. | R03, R04, R09 | parcial |
| I-227 | Validación de Seguridad: pasos sin VM pasan (alcance, ruteo, gate rechaza fuera de la lista, reporte simulado); los de la VM SIN VALIDAR. | R05 | parcial |
| I-228 | Corrida real de Seguridad contra la VM Metasploitable (VM alcanzable, IP en SEGURIDAD_VALIDATION_TARGET, IP escrita a mano en authorized_targets.yaml, nmap/ZAP/sqlmap). | R05 pendientes | pendiente |
| I-229 | Pasos genéricos de validación para brigadas creadas (alcance/aprobación, ruteo, respuesta). | R06; validation/generic.py | hecho |
| I-230 | Aislamiento no negociable: toda escritura va a un temporal y se compara la huella de lo real antes/después. | R02; harness.py | hecho |
| I-231 | Búsqueda web enchufable (Brave primario + SearXNG) tras el CAPTCHA de DuckDuckGo; falta BRAVE_SEARCH_API_KEY. | R03, R04; DM 2026-11-10 | parcial |
| I-232 | Medir variabilidad de la validación (repetir corridas) y evaluador de calidad de síntesis. | R09 pendientes; ARQUITECTURA OPT-12 | pendiente |
| I-233 | Validar el flujo completo orquestador→jefe→ayudantes→síntesis (nuevo criterio del modelo de delegación). | ARQUITECTURA OPT-02, OPT-12 | pendiente |
| I-234 | Banco de evaluación, baseline y tracing como fundaciones (M0); suite de calibración / benchmark. | SPEC-MEJORAS M0; ROADMAP F1-7 | parcial |
| I-235 | OWASP Benchmark real con medición por categoría (no solo promedio). | Fundamentos §8; docs/owasp_benchmark | hecho |
| I-236 | Tests unitarios (150+ archivos en backend/tests) sin LLM; test_validation_* para los pasos. | CLAUDE.md; repo | hecho |
| I-237 | Test de ida y vuelta real de voz (RUN_VOICE_REAL=1). | R11 | hecho |
| I-238 | Pendientes operativos previos: cerrar rojos de Cerebro (umbral, no-invención) y de Forense (confirmar el id del caso, se endureció el prompt). | R02-R04 → R08/R09 | hecho |
| I-239 | Auditoría de código/bugs/deuda (P0–P5) con plan de ataque. | docs/SPEC-AUDITORIA-2026-10-13 | parcial |

## L. Investigación, OSINT, Intel e ingesta

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-240 | Investigación forense: casos con repo git, log append-only firmado Ed25519, artifact store por sha256, ingesta de CSV/WhatsApp/Telegram/imagen/documento/logs, propuestas de entidades y fusiones, informe MD/PDF. | Capacidades; CONTEXTO-MAESTRO | hecho |
| I-241 | Línea roja de Investigación: solo material que Damian ya tiene legítimamente; nunca sale a buscar; el código del cliente no sale a la nube ni al repo público. | Fundamentos resumen | hecho |
| I-242 | Scout: research web trazable (research_topic) que guarda notas con fuentes citadas; alimenta a Cerebro vía remember(). | SPEC-PRODUCTO-INV; DM 2026-11-10 | hecho |
| I-243 | Producto Investigación (research continuo y autónomo, local y gratis, fuentes elegidas por el usuario, datos propios). | docs/SPEC-PRODUCTO-INVESTIGACION | idea |
| I-244 | Raphael Intel: juntar con dirección información pública del mundo (geopolítica, economía, ciencia, tecnología), resumirla y hacerla buscable; no vigilancia de personas. | docs/SPEC-RAPHAEL-INTEL | parcial |
| I-245 | Ingesta de playlist de YouTube al vault (transcripción con yt-dlp, resumen), automática y programada (cada 15 min). | vision/AUTO-INGESTA-PLAYLIST; TABLA | hecho |
| I-246 | Ingesta multi-fuente (watchlist de fuentes, log de ítems ingeridos, cookies de yt-dlp). | DM 2026-11-10 | hecho |
| I-247 | Capa de navegación de agente (Agent Web Layer): mini-brigada web W0 WebMCP, W1 fetch, W2 representación estructurada, W3 acción, W4 cache; autenticación con custodia de credenciales; robustez en cualquier condición. | docs/SPEC-capa-navegacion-de-agente | parcial |
| I-248 | web_get/web_scrape robustos (Scrapling fast/stealth/dynamic) y OCR de documentos (PaddleOCR). | Capacidades; SPEC-PLAN | parcial |
| I-249 | Agent Reach: acceso autenticado a sitios con login reusando cookies del navegador (candidata como tool de sensor). | ORQUESTACION-ESTRUCTURA §1.3 | idea |
| I-250 | Geolocalización pública (IP, direcciones cripto, Shodan) y mapa OSINT. | Capacidades; DM 2026-11-10 | hecho |
| I-251 | Citar la fuente de cada afirmación en el informe de auditoría (credibilidad). | ROADMAP QW-3 | parcial |
| I-252 | Spec-driven development en el build de apps (Attekita Dev). | ROADMAP F1-6/F1-5 | idea |
| I-253 | WebMCP como superficie de auditoría (semilla futura). | INSIGHTS-midu §4 | idea |
| I-254 | Trading watch loop (watchlist, señales, backtest, panel de riesgo) apagado por default; solo análisis, nunca opera. | DM 2026-11-10; HACIA | parcial |
| I-255 | Aprendizaje proactivo y casos de research retenidos (apagado por default: gasta LLM). | DM 2026-11-10 | parcial |

## M. Auditoría de código, producto y negocio

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-256 | Núcleo original: auditoría de código/pentesting manejada por LLM; indexa un proyecto en un grafo (tree-sitter) y corre escáneres reales (Semgrep, Bandit, cppcheck, clang-tidy, Trivy, Ruff, mypy). | CLAUDE.md; Capacidades | hecho |
| I-257 | Fixes reversibles: cada fix en su propio commit; code_apply_fix (dry-run→confirm) y security_audit_find_fix_verify con tests reales. | CLAUDE.md; Capacidades | hecho |
| I-258 | Triage de hallazgos con reclasificación de falsos positivos y benchmark OWASP. | Capacidades; Fundamentos §8 | hecho |
| I-259 | Pipeline de testing real (detección, runner) que cierra el gap "compiló ≠ funciona". | CLAUDE.md | hecho |
| I-260 | Config checker determinista en la auditoría (QW-4). | ROADMAP QW-4; DM 2026-09-20 | hecho |
| I-261 | Catador/QA que verifica el informe antes de entregarlo (E6, la prioridad de la brigada de auditoría). | BRIGADA-AUDITORIA E6 | parcial |
| I-262 | Auditar código en "casi tiempo real" con dos pisos: escaneo determinista por archivo/diff + triage LLM no por tecla. | docs/PROPUESTA-Raphael-tiempo-real | idea |
| I-263 | Optimización del código del Auditor: red de tests, routing de tools por dominio, partir agent.py en paquete, imports perezosos. | docs/PLAN-OPTIMIZACION-CODIGO | parcial |
| I-264 | Servicio productizado "Blindaje de Seguridad para PyMEs": plan de 2 meses al primer ingreso, precios, cliente objetivo, track freelance y evolución a producto. | negocio/PLAN-2-MESES | idea |
| I-265 | Checklist de blindaje, demo de turnos (primera app construida por Raphael) y proyecto co-host-stream. | proyectos/; DM 2026-08-30 | parcial |
| I-266 | Hito estrella: experimento red-vs-blue Hermes (ataque) vs Raphael (defensa) con el mismo cerebro para aislar el harness. | TABLA 2026-09-02 | idea |
| I-267 | Canal de YouTube de ciberseguridad responsable como activo de autoridad (después de las primeras auditorías reales). | TABLA 2026-09-04 | idea |
| I-268 | Cuenta/marca @raphaelseguridad (primer post pendiente). | SPEC-PLAN pendientes de Damian | idea |
| I-269 | Charla de midudev sobre el futuro de los devs: cruce con Raphael (lab, producto, marketing). | docs/INSIGHTS-charla-midu | hecho |
| I-270 | Pregunta de producto: versión para terceros con FS_ALLOWED_ROOT achicado, relay/Headscale en vez de Tailscale, QR para emparejar. | SPEC-PLAN DESCARTADO/Etapa 2 | idea |

## N. Sistema: PC, celular, escritorio, Linux

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-271 | Control de PC (mouse/teclado/ventanas con pywinauto), shell real con blocklist, navegador automatizado (Edge), grabación de pantalla. | Capacidades; CLAUDE.md | hecho |
| I-272 | Control del celular: Accessibility Service, WebSocket, SAF, Termux shell, cámara; ruteo pc\|phone. | DM 2026-07-21 | parcial |
| I-273 | Monolito: loop del agente con ~125 tools, todos los routers y módulos (malware, selfrepair, testing, skills, forms, investigation, pentest, network, geo, trading, ops). | CONTEXTO-MAESTRO PR1.4 | hecho |
| I-274 | Tray-app (pystray + ventana con pestañas) que administra el backend, selector de modelo por tiers y voice listener. | CLAUDE.md | hecho |
| I-275 | Migración a Linux (Kubuntu LTS, X11): porteo módulo por módulo (DPAPI→keyring, pywinauto→xdotool, taskkill→señales, etc.) y "compañero que arranca con la PC". | docs/SPEC-MIGRACION-LINUX-2026-10-19 | idea |
| I-276 | Arquitectura híbrida Windows vs Linux: Windows para escritorio y producto defensivo; Linux para servidor always-on, lab ofensivo y contención. | TABLA 2026-08-24 | idea |
| I-277 | Reparto de procesos de fondo y riesgo de consumo (loops de fondo que gastan LLM por iniciativa propia). | SPEC-AUDITORIA P2-1 | parcial |
| I-278 | Ordenar la PC (carpetas _REVISAR, archivos huérfanos, duplicados) y plan de orden. | Documents/PLAN-Ordenar-PC; _REVISAR/MANIFIESTO | parcial |
| I-279 | Vaults separados: Vault-Fenix (personal+técnico), backend/obsidian_vault y cerebro-fenix; prototipo viejo _Jarvis-Local congelado (no copiar). | CLAUDE.md; CONTEXTO-MAESTRO | hecho |
| I-280 | Lanzadores Desktop\Harnesses (orquestador :8010, backend :8000) con detener. | DM 2026-11-08 | hecho |
| I-281 | Instalador idempotente (install.ps1) que detecta hardware, arma el modelo del tier y deja .env/venvs. | CLAUDE.md | hecho |
| I-282 | Prototipo viejo de voz (_Jarvis-Local: VAD → faster-whisper → LLM → Piper es_AR): reutilizado solo en piezas (voz Piper, libs, modelos). | R11; cerebro-fenix/_Jarvis-Local | hecho |
| I-283 | Contenedor/sandbox y Docker sandbox (aparcado). | SPEC-PLAN APARCADO | idea |
| I-284 | Herdr: multiplexor de terminal para orquestar agentes de código (no ahora). | TABLA 2026-08-25 | idea |

## O. Laboratorio, defensa y red

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-285 | Cyber range aislado (VirtualBox + Kali + Metasploitable en red interna) para simular ataque/defensa sin tocar sistemas reales. | lab/CYBER-RANGE-DESIGN; RETOMAR-LAB | parcial |
| I-286 | Prueba de estrés de detección nocturna: emulación de adversarios (Atomic Red Team/Caldera) con bucle de convergencia por pases y mejoras de reglas aprobadas por Damian. | lab/DETECCION-ESTRES-NOCTURNO | pendiente |
| I-287 | Defensa y respuesta kernel-grade gratis (Sysmon/ETW/AMSI para ver; ASR/AppLocker/WDAC/WFP para bloquear) sin driver propio. | lab/DEFENSA-KERNEL-GRATIS-DESIGN; DEFENSA-PRIORIDADES | pendiente |
| I-288 | Tool vm_control para encender/apagar/snapshotear VMs del lab con allow-list. | lab/ORQUESTACION-REMOTA §5 | pendiente |
| I-289 | Paso cero de defensa: Defender a full + Tamper Protection. | lab/DEFENSA-PRIORIDADES | pendiente |
| I-290 | Protección antimalware: YARA + ClamAV (clamd) + heurística conductual + FIM + monitor del proceso propio + cuarentena reversible; escaneo diario y on-access. | CLAUDE.md; DM 2026-08-16 | hecho |
| I-291 | Sysmon experimental (apagado) y verificación de la cadena firmada de hallazgos. | Capacidades | parcial |
| I-292 | Pentesting activo: nmap (guardrail de scope compartido), SQLMap, OWASP ZAP, captura de paquetes; phone_nmap_scan. | CLAUDE.md; DM 2026-08-13/16 | hecho |
| I-293 | Reporte de auditoría de red/web (pentest_generate_report). | DM 2026-11-10 | hecho |
| I-294 | Ensayo en el range del ciclo "Sabio que simula en grande" (Etapa 2 de HACIA). | HACIA Etapa 2 | parcial |

## P. Proactividad, autonomía y auto-mejora

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-295 | Etapa C de proactividad: de qué ser proactivo (seguridad, tapar huecos del vault, proponer mejoras ante limitaciones), regla de dos niveles (juntar/aprender autónomo; cambiar/actuar afuera con confirmación). | ETAPAS-BCD decisiones 2026-10-06 | parcial |
| I-296 | Curiosidad en tier 2 con compuerta por sensibilidad; presupuesto de curiosidad; cómo y cuándo interrumpe. | ETAPAS-BCD Etapa C | parcial |
| I-297 | Brief matutino / alerta proactiva que llega sin abrir el chat (push proactivo). | HACIA Etapa 6 | pendiente |
| I-298 | Etapa D de auto-rediseño seguro: el grafo se auto-tunea (acotado); el código siempre se propone y se aplica con OK; barra de validación (tests + mejora medida + no toca gates). | ETAPAS-BCD Etapa D | parcial |
| I-299 | Auto-diagnóstico de cuellos de botella y mejoras estructurales validadas por A/B. | ETAPAS-BCD Etapa D | idea |
| I-300 | Composición de skills ("fusión"): Jarvis cristaliza patrones de tools repetidos en skills nuevas con aprobación de Damian (analizador de patrones y fábrica faltan). | HACIA §6 | pendiente |
| I-301 | Bucle auto-mejorante de detección (destilar reglas YARA de la experiencia, Damian aprueba). | HACIA §6.2 | pendiente |
| I-302 | Auto-reparación proactiva del propio código (selfrepair puede proponer de forma proactiva, sigue con gate). | DM 2026-11-10 | parcial |
| I-303 | Autoconciencia capa 1: self_model (raphael_self_model) y capa 2 de metacognición por fases. | DM 2026-10-13; SPEC-PLAN #6 | parcial |
| I-304 | Supervisor de operaciones (ops_supervisor) y watchdog de ops (apagados por default). | DM 2026-11-10; Capacidades | parcial |
| I-305 | Jobs de fondo con flags (playlist watch, consolidación, curiosidad, escaneo malware, aprendizaje proactivo, trading watch) y su consumo. | Capacidades §3 | parcial |
| I-306 | Mejora de la app Android por Raphael (automejora de la app de celular). | VISION-APP-CELULAR §6 | idea |
| I-307 | Raphael actuando como "comandante" de un escuadrón (seguir y asistir a Damian) en lenguaje natural. | SPEC-escuadron-drones | idea |

## Q. Robótica, proyectos paralelos y marketing

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-308 | Escuadrón heterogéneo aire+tierra comandado por Raphael: principio de mando, topología con nave nodriza, "seguime", hand-off dron↔rover, comms, plataformas reales, diseño 3D (SPEC COMPLETO, sin construir). | docs/SPEC-escuadron-drones | idea |
| I-309 | Reencuadre de los drones como posible cuerpo físico (embodiment) de Raphael. | SPEC-PLAN APARCADO | idea |
| I-310 | Exoesqueletos: fundamentos y factibilidad. | robotica/EXOESQUELETOS-FUNDAMENTOS-Y-FACTIBILIDAD | idea |
| I-311 | Proyecto Fénix (vault personal/tesis) como origen de la pregunta de conciencia y del cerebro de Raphael. | CONTEXTO-MAESTRO; CEREBRO-NO-BIOLOGICO | parcial |
| I-312 | Proyecto co-host-stream / canal faceless con Raphael como guionista. | TABLA; proyectos/co-host-stream | idea |
| I-313 | Demo y productos de ejemplo construidos por Raphael (checklist blindaje, demo turnos masajes). | proyectos/ | parcial |

## R. Meta-proceso y forma de trabajo

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-314 | Commits atómicos por tema, en español con prefijos (feat/fix/chore/docs), con el porqué; hábito de commitear siempre. | CLAUDE.md; Fundamentos §10 | hecho |
| I-315 | Un ladrillo por vez: construir fase por fase, cada una chequeable. | SPEC-VOZ; SPEC-INTEL | hecho |
| I-316 | Endurecer, no agregar: priorizar lo que ya hay antes de sumar ingredientes nuevos. | TABLA (Herdr); ROADMAP | hecho |
| I-317 | Elicitar por preguntas y marcar decisiones 🟡/✅ en los specs; "decisiones de Damian" explícitas. | SPEC-NAV; SPEC-MEM-EPIS; ETAPAS-BCD | hecho |
| I-318 | Regla del repo: nunca secretos; remoto confirmado privado; no mezclar vaults ni repos. | CLAUDE.md; DM | hecho |
| I-319 | Todo lo nuevo default-OFF (lo que gasta o cambia comportamiento se prende a mano). | SPEC-MEJORAS principios | hecho |
| I-320 | No rewrite de historia sin decisión de Damian; scrub de privacidad de archivos privados. | DM 2026-11-10 | hecho |
| I-321 | Documentar rondas de validación en Word con rigor de investigación (una por ronda). | R01 norma de registro | hecho |
| I-322 | Brigada metáfora: dueño, chef ejecutivo, jefe de cocina, sous-chef, aboyeur, jefes de partida, commis (modelos baratos que nunca tocan datos sensibles), plongeur, runner. | docs/LA-BRIGADA | hecho |
| I-323 | Tres velocidades de trabajo: Damian decide el menú; Claude planifica/supervisa; Raphael/DeepSeek cocina; las comandas fluyen por el riel. | LA-BRIGADA; COMANDAS | parcial |
| I-324 | Aprender de videos/notas (playlist "Info para Jarvis") e integrarlo (Omniroute, n8n, Agent Reach, One-Person AI Business). | ORQUESTACION-ESTRUCTURA §1 | parcial |

## S. Historial de decisiones (decision log) no cubiertas arriba

| # | Descripción | Fuente | Estado |
|---|---|---|---|
| I-325 | 2026-07-19 nace JarvisRemote (scaffold: backend con LM Studio + framework de tools, tray-app, android-app). | DM 2026-07-19 | hecho |
| I-326 | 2026-07-20 AsyncOpenAI (no bloquear el event loop) e INFORME_COMPLETO; prototipo _Jarvis-Local congelado a propósito. | DM 2026-07-20 | hecho |
| I-327 | 2026-07-21 blocklist de comandos destructivos + audit log + API key cifrada (Keystore) desde temprano. | DM 2026-07-21 | hecho |
| I-328 | 2026-07-28/29 indexador de código, vault Obsidian, wake word, SAST/calidad, nmap con network-scope guardrail, README reenfocado a auditoría. | DM 2026-07-28/29 | hecho |
| I-329 | 2026-08-10/11 ronda de "bug real v6": timeouts LLM, logging persistente, trim de contexto, guardrail de reescritura idéntica, /api/health/deep, OWASP Benchmark real. | DM 2026-08-10/11 | hecho |
| I-330 | 2026-08-16 módulo de investigación + pentest activo + grabación de pantalla; 2026-08-17 integra malware/selfrepair/testing/skills y gate de web_forms. | DM 2026-08-16/17 | hecho |
| I-331 | 2026-08-30/31 FS_DENIED_PATHS, fecha/hora en cada turno, primera app construida por Raphael, visión de app celular. | DM 2026-08-30/31 | hecho |
| I-332 | 2026-09-20/21 Raphael Intel fase 0 (ingesta + arXiv), config checker, QUICKSTART/README para pares. | DM 2026-09-20/21 | hecho |
| I-333 | 2026-09-22 consola multiagente (backend+UI) con modelo por estación y brigada/convergencia. | DM 2026-09-22 | parcial |
| I-334 | 2026-09-28/29/30 ablación del SYSTEM_PROMPT, ruteo de modelos (Sonnet 5.5 + planner Opus + tiers/fallback), web_get activado, retiro de opencode/cloud_expert. | DM 2026-09-28/30 | hecho |
| I-335 | 2026-10-04/05 estructura informacional del cerebro: fases 1-2 y 3-8 + SPEC predictivo; "el modelo es la conciencia del cerebro". | DM 2026-10-04/05 | hecho |
| I-336 | 2026-10-06 visión cerebro no biológico, etapas A/B/C/D decididas por Damian, tier 2 free + jobs del cerebro + playlist watcher. | DM 2026-10-06 | hecho |
| I-337 | 2026-10-11/13 app móvil + Centro de Mando nativo (10 brigadas en vivo), auth por dispositivo, sync por QR, self_model; snapshot para un tercero. | DM 2026-10-11/13 | hecho |
| I-338 | 2026-10-13 AGENTS.md para onboardear a DeepSeek Harness; 2026-10-19 SPEC-MEJORAS (M0–M10) y SPEC-MIGRACION-LINUX. | DM 2026-10-13/19 | hecho |
| I-339 | 2026-10-26 WebSocket inseguro → wss:// (hallazgo de auditoría). | DM 2026-10-26 | hecho |
| I-340 | 2026-11-03 BLUEPRINT de brigadas, jefes persistentes, modelo objetivo tier 3 Sonnet con punto único de cambio. | DM 2026-11-03 | hecho |
| I-341 | 2026-11-09/10 validación real de Cerebro (Ronda 02, NO PASA) e Investigación (Ronda 03/04); decisión Forense por defecto; búsqueda enchufable. | DM 2026-11-09/10 | hecho |
| I-342 | 2026-11-10 versionar el paquete base de brigades, commit atómico de todo el trabajo suelto, merge a master y scrub de privacidad. | DM 2026-11-10 | hecho |
| I-343 | 2026-11-11 el orquestador y el diseñador pasan a nemotron por OpenRouter y luego a NVIDIA oficial; guardrail de privacidad documentado. | DM 2026-11-11 | hecho |
| I-344 | 2026-11-12 watchdog, default shared, arreglos de Cerebro/Forense, todo en nemotron, re-validación (Cerebro verde), mecanismo de auto-actualización, bug del lanzador viejo. | DM 2026-11-12 | hecho |
| I-345 | 2026-11-12 voz local y vistas de Cocineros/Efímeros; 2026-11-15 modelo de delegación objetivo y especificación de arquitectura. | DM; ARQUITECTURA | hecho |

## T. Ítems dudosos (para que Damian los revise)

Cosas donde el estado o la intención no está claro en las fuentes, o donde las fuentes se contradicen:

1. **OpenRouter vs NVIDIA/Groq.** `SPEC-MEJORAS` fijó "cloud SOLO por OpenRouter" (no sumar Groq/Gemini/gateways), pero hoy el sistema corre en NVIDIA oficial y Scout en Groq. ¿El principio ya no rige o se mantiene como horizonte?
2. **App Android.** Las fuentes (SPEC-AUDITORIA, ESTADO) dicen "falta instalar / sin compilar"; no se verificó hoy si ya se instaló. Estado puesto: pendiente.
3. **Cyber range / VMs.** Se documenta "en armado" (RETOMAR-LAB) y la Ronda 05 menciona una VM Metasploitable en una red interna `10.13.37.0/24`; no se verificó que esté montada y alcanzable.
4. **Tailscale.** "No instalado" según ESTADO antiguo; no se reconfirmó. Condiciona el control del celular con datos móviles.
5. **Defensa kernel-grade, bucle nocturno y `vm_control`.** Figuran como DISEÑADO sin código; el SPEC-PLAN los marca como APARCADOS fuera del rumbo producto/robot. ¿Se retoman o quedan como idea?
6. **Flags de `Raphael_Capacidades.docx`.** Lista `fs_allow_delete`, `self_redesign_enabled`, `pc_shell_enabled`, `nmap/sqlmap/zap`, `consolidation_enabled`, `curiosity_enabled`, `proactive_learning_enabled` en `true`, pero el documento maestro dice que el proactivo de Cerebro está OFF. Conviene revisar el `.env` real.
7. **"Comunicación por voz y control desde cualquier lado".** Se mapeó a: voz local (hecha), SPEC-VOZ manos-libres (parcial), app de celular como Dispatch (parcial) y orquestación remota por Tailscale (pendiente). Si Damian pensaba en otra cosa, falta ese ítem.
8. **Modelo del jefe que sintetiza.** El modelo de delegación objetivo necesita un LLM para la síntesis del jefe; hoy el jefe que delega no tiene LLM propio. Su modelo/costo está por decidir (OPT-10).
9. **Estados "hecho" de las fases del cerebro.** Se tomaron de las fuentes y de los módulos presentes en `backend/app/obsidian/`; no se re-ejecutaron sus tests en esta tarea.
10. **Ideas de negocio y marketing** (Blindaje PyME, canal de YouTube, @raphaelseguridad, Hermes vs Raphael): se listaron como idea; las fuentes las marcan "post primera venta" y no se sabe si siguen vigentes.
11. **Documentos de Raphael desactualizados.** `Fundamentos_de_Jarvis.docx` habla del modelo local Qwen3-30B y `Raphael_Capacidades.docx` de `nemotron-3.5-super-vl:free`; el modelo actual es nemotron en NVIDIA. No se usaron para estado de modelos.
12. **Fuentes leídas por estructura.** Las listadas en la tabla de cobertura como "por encabezados" pueden esconder ideas finas no inventariadas; si Damian recuerda alguna que no está, se agrega.

## U. Rondas 01–11 (referencia rápida)

| Ronda | Tema | Resultado |
|---|---|---|
| 01 | Metodología y specs (Investigación cerrada, Cerebro revisado, norma de registro) | Decisiones de método; criterio de Cerebro a confirmar |
| 02 | Cerebro: criterio completo y primeras corridas | NO PASA (consolidación mezcla distractor; no-invención intermitente) |
| 03 | Investigación: diseño del test y primeras corridas | NO PASA (ruteo invertido; CAPTCHA de DuckDuckGo) |
| 04 | Investigación: ruteo y búsqueda enchufable | Ruteo OK, Scout SIN VALIDAR (falta Brave), Forense intermitente → INCOMPLETO |
| 05 | Brigada de Seguridad (molde declarativo) | Validación lista sin escaneos reales; pasos de VM SIN VALIDAR |
| 06 | Etapa 2: el orquestador crea brigadas | Gate firmado; 133 tests; XSS de UI corregido |
| 07 | Watchdog y patrón SPEC + VALIDACIÓN | 24 tests; sin calibrar con corridas reales |
| 08 | Arreglos de código de Cerebro y Forense | Umbral 0.85+0.08, fidelidad a datos, Forense confirma el id |
| 09 | Re-validación real con nemotron | Cerebro PASA 4/4 con baseline; Forense PASA; Scout SIN VALIDAR |
| 10 | Cocineros y Efímeros en vivo | Registro vivo y paneles; 202 tests |
| 11 | Voz local | Ida y vuelta real Piper→Whisper; micrófono real sin probar |

