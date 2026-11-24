# Raphael para pymes — contexto maestro para construir y lanzar el producto

> Documento de traspaso. Quien lo lea (una persona o una sesión de IA) tiene que poder
> construir y lanzar el producto sin la conversación original. Fecha: 2026-11-18.
> Spec resumido con diagramas: https://claude.ai/artifact/Xia9EcY3KYQYMk6PoDqUJq
> Spec anterior del caso de la diseñadora: `docs/SPEC-ENCARGOS-AUTOMATICOS.md`.

---

## 1. Qué es y qué problema resuelve

**Raphael para pymes** es un asistente con IA que se instala en la empresa del cliente y
automatiza la atención por WhatsApp e Instagram, la toma de pedidos/encargos, los cobros
(señas), la agenda de turnos y los avisos de estado. Lo repetitivo lo hace solo; lo que
compromete al negocio (precio final, pagos, turnos, reclamos) lo aprueba una persona.

- **Cliente objetivo v1:** negocios de encargos y servicios, empezando por ropa a medida /
  hecha a mano (caso real: una diseñadora, la "clienta" de este repo).
- **Problemas que ataca:** mensajes fuera de horario sin respuesta, preguntas repetidas,
  presupuestos a mano, pagos sin orden ("¿te llegó la seña?"), turnos superpuestos,
  "¿ya está mi pedido?", y bots genéricos que inventan respuestas.
- **Promesa:** "Automatizá lo repetitivo; las decisiones siguen siendo tuyas."
- **Dueño del producto:** Damián (Rosario, Argentina). Él hace los push; el código se
  commitea en local y él decide cuándo publicar.

## 2. Decisiones ya tomadas (no reabrir sin motivo)

| # | Decisión | Por qué |
|---|---|---|
| D1 | **Un solo núcleo de código + un perfil por empresa.** Nunca código propio por cliente. | Mantener 20 versiones es imposible. |
| D2 | **Reglas antes que IA.** Flujos, cálculos y permisos están programados; la IA interpreta texto y redacta. | Predecible, barato, no inventa. Es lo que hoy funciona en este repo. |
| D3 | **El bot propone, la persona decide.** Precio final, confirmar pago, confirmar turno y reclamos requieren humano. | Confianza del cliente y responsabilidad. |
| D4 | **No inventa.** Solo responde con la info cargada; lo demás lo anota como duda y lo deriva. | Evitar promesas falsas. |
| D5 | **Brigadas modulares** (cada una sirve sola y también coordinada por el orquestador). | Se venden por separado y se suman. |
| D6 | **El modelo de IA es configuración**, elegido por rol y por plan. | Planes con distinto costo; cambiar proveedor sin tocar código. |
| D7 | **Se instala en la empresa** (mini PC provisto) + **relay mínimo en la nube** para WhatsApp/Instagram. | Datos en la empresa; la PC del local se apaga y no tiene IP pública. |
| D8 | **Modelos gratis solo para desarrollo.** | Límites bajos, cambian sin aviso, algunos usan los datos. |
| D9 | **Primero un rubro** (encargos/ropa a medida), después otros. | Vender algo concreto es más fácil que "Raphael para todo". |
| D10 | Reglas de la clienta piloto: seña 50%; cuando la clienta dice que transfirió, el bot avisa y la dueña confirma; recordatorio de prueba/retiro con anticipación (3 días por defecto); se piden todos los datos incluidas medidas; tono voseo con emojis; plazo urgente → se marca URGENTE y no se promete; siempre pedir nombre; precio = base + recargos; si no hay precio en la tabla, se le pregunta a la dueña y la clienta recibe "te mandamos el presupuesto"; medidas por chat o presencial; turnos: el bot pregunta el día y la dueña confirma; autonomía: todo menos el precio final; canales WhatsApp e Instagram. | Q&A con Damián. |

## 3. Estado actual del código (base del producto)

Repo `cliente-ropa-ia` ("Mi Tienda IA"), FastAPI multi-tenant + PWA. Demo en Render (plan
gratis, disco efímero): https://mi-tienda-ia.onrender.com/app/ — login demo `+5491100000000`,
el código aparece en pantalla. `main` al día con `origin/main` (HEAD 36be470).

| Área | Dónde | Estado |
|---|---|---|
| Multi-tenant (empresas, usuarios, OTP, sesiones, secretos cifrados) | `app/tenancy/` (`tenants.py`, `auth.py`, `db.py`, `vault.py`, `oauth.py`, `runtime.py`) | Hecho. Cada tenant tiene `data/tenants/{id}/`. |
| Harness: router de intenciones, orquestador, brigadas, políticas, auditoría, memoria | `app/harness/` | Hecho. Intents por regex (`intents.py`), políticas AUTO/CONFIRMAR (`policies.py`), `JefeEncargos` y otras en `brigades.py`. |
| Recepción de encargos (flujo conversacional completo) | `app/recepcion.py`, `app/harness/enc_parsing.py` | Hecho: prenda, ocasión, fecha (con confirmación de fecha numérica), detalles, referencias, medidas o turno, nombre; preguntas frecuentes a mitad de flujo; reclamo → humano; compra de stock no abre encargo. |
| Encargos, precios, recargos, presupuesto sugerido, seña, estados, avisos | `app/encargos.py`, `app/precios.py` | Hecho. |
| Pagos: aviso de transferencia → "Me llegó" → confirmado + aviso | `app/main.py` (`/api/encargos/{n}/pago`) | Hecho. |
| Agenda / calendario de entregas, publicaciones y turnos | `/api/agenda` | Hecho (sin hora exacta ni recordatorio todavía). |
| FAQ con búsqueda (extractivo sin LLM, generativo con LLM) | `app/faq/` | Hecho. |
| Gateway LLM OpenAI-compatible (OpenRouter, DeepSeek, Ollama, LM Studio) | `app/llm.py`, `.env` `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY` | Hecho, **un solo modelo global** (falta por rol y por plan). |
| Conectores WhatsApp, Instagram, Facebook, Mercado Pago, Tiendanube | `app/connectors/` | Mock completo; real implementado pero **sin app de Meta aprobada**. |
| Marketing (calendario y programador de publicaciones) | `app/marketing/` | Hecho. |
| Editor de video de reels | `app/video/editor.py` | Hecho; falla en Render sin diagnosticar (buscar `ffmpeg falló` en logs). |
| PWA de la dueña (🧵 encargos, 📅 calendario, probador de clienta, ⚙️ ajustes) | `web/app/index.html` | Hecho. |
| Tests | `tests/` (12 archivos, ~200 tests) | Pasan, salvo 3 que solo fallan en el sandbox Linux (mimetypes). |
| Deploy | `render.yaml`, `Dockerfile` | Demo en modo mock. |

Pendiente conocido del piloto: turnos con fecha y hora + recordatorio N días antes (entrega 3
del spec de encargos); conectar WhatsApp/Instagram reales (Meta App Review, plantillas);
disco persistente; caso "Ese mismo" al confirmar caption; revisión legal de privacidad.

## 4. Arquitectura objetivo

```
WhatsApp / Instagram ──► Relay en la nube (solo reenvía, no guarda) ──► Equipo del cliente (mini PC)
                                                                         │
Panel de la dueña (PWA) ──── aprobaciones ─────────────────────────────►│ Orquestador
                                                                         │  ├─ Brigadas: Atención · Encargos · Cobros · Agenda · Avisos
                                                                         │  ├─ Policy Engine (automático / aprobación / siempre humano)
                                                                         │  ├─ Perfil de empresa (datos, reglas, plan)  ◄── lo único distinto por cliente
                                                                         │  ├─ Capa de modelos (elige IA por rol y plan) ──► Modelos (nube o local)
                                                                         │  ├─ Base de datos + backups cifrados
                                                                         │  └─ Registro de uso ──► Panel de soporte de Damián (estado y uso, sin datos)
```

### 4.1 Perfil de empresa (nuevo — entrega 1)

Un archivo por tenant, `data/tenants/{id}/perfil.yaml` (o tabla equivalente), validado con
pydantic. Todo lo específico del negocio sale del código y entra acá:

```yaml
empresa:
  nombre: "Taller Ejemplo"
  rubro: encargos_ropa_medida        # plantilla de flujo a usar
  duena: "Nombre"
  tono: voseo_emojis                 # voseo_emojis | voseo_formal | usted
  zona_horaria: America/Argentina/Buenos_Aires
plan: pro                            # basico | pro | privado | premium
brigadas: [atencion, encargos, cobros, agenda, avisos]
informacion:                         # lo único que el bot puede afirmar
  horarios: "Lun a sáb de 10 a 19"
  envios: "A todo el país por correo"
  medios_pago: ["transferencia"]
  faq: faq/                          # carpeta de FAQ del tenant (ya existe)
cobros:
  sena_pct: 50
  alias: "taller.ejemplo"
  titular: "Nombre Apellido"
encargos:
  datos_obligatorios: [prenda, ocasion, fecha, detalles, medidas, nombre]
  medidas: [chat, presencial]
  urgente_si_dias_menor_a: 15
agenda:
  recordatorio_dias_antes: 3
  franjas: ["jue 16:00-19:00", "sab 10:00-13:00"]
politicas:                           # solo puede endurecer los defaults, nunca relajar los bloqueados
  enviar_presupuesto: aprobacion
  confirmar_pago: aprobacion
  confirmar_turno: aprobacion
  reclamos: humano
limites:
  mensajes_mes: 3000
```

Reglas: el núcleo lee el perfil al iniciar y en cada cambio; los textos fijos del bot
(saludos, pedidos de datos) son plantillas por `rubro` + `tono`; los valores por defecto viven
en el código y el perfil los sobrescribe.

### 4.2 Capa de modelos (nuevo — entrega 2)

Extender `app/llm.py` para resolver el modelo **por rol y por plan**:

```yaml
# config/modelos.yaml (del producto, no del cliente)
roles: [intencion, redaccion, resumen, vision]
planes:
  basico:  {intencion: economico_nube, redaccion: economico_nube, resumen: economico_nube}
  pro:     {intencion: bueno_nube,     redaccion: bueno_nube,     resumen: local}
  privado: {intencion: local,          redaccion: local,          resumen: local}
proveedores:
  economico_nube: {base_url: ..., model: ..., api_key_env: LLM_KEY_ECONOMICO}
  bueno_nube:     {base_url: ..., model: ..., api_key_env: LLM_KEY_BUENO}
  local:          {base_url: "http://localhost:11434/v1", model: ...}
```

- Si el modelo falla o se pasa el tope → caer a reglas/extractivo (ya existe ese modo) y avisar.
- Cada llamada registra: tenant, rol, modelo, tokens in/out, costo estimado, latencia.
- Cálculos, estados, avisos y permisos **nunca** pasan por la IA.

### 4.3 Registro de uso y panel de soporte (entregas 2 y 4)

- Tabla `uso` (tenant, fecha, mensajes, llamadas por rol, tokens, costo estimado).
- El equipo del cliente envía al panel de soporte, cada 15 min: versión, vivo, errores
  (sin texto de conversaciones), uso agregado. Nada de datos personales.

## 5. Brigadas v1 — funciones y criterios de aceptación

| Brigada | Hace sola | Requiere a la persona | Acepta cuando… |
|---|---|---|---|
| Atención | Responde con la info del perfil/FAQ; anota dudas sin respuesta; detecta reclamos y se retira | Responder dudas nuevas; atender reclamos | Ante una pregunta no cargada responde "te lo confirma {negocio}" y crea la duda; ante un reclamo no responde más y avisa. |
| Encargos | Recepción paso a paso; presupuesto sugerido (base + recargos); estados | Precio final; aceptar urgentes | Ningún presupuesto sale sin "Aprobar"; un pedido urgente queda marcado URGENTE sin prometer fecha. |
| Cobros | Calcula seña; registra "ya transferí"; avisa | Confirmar "Me llegó" | El bot nunca da un pago por recibido; tras "Me llegó" la clienta recibe la confirmación. |
| Agenda | Pregunta día/franja; arma calendario; recordatorio N días antes | Confirmar o proponer otro horario | No hay dos turnos confirmados en la misma franja; el recordatorio sale `recordatorio_dias_antes`. |
| Avisos | Avisa al cambiar el estado (solo si el pedido vino de WhatsApp/Instagram) | — | Cada cambio de estado genera exactamente un aviso. |
| Supervisión (interna) | Registra cada acción y verifica políticas | Revisar alertas | Toda acción bloqueada que se intente queda registrada y no se ejecuta. |

**Pruebas obligatorias:** cada brigada tiene conversaciones de prueba con resultado esperado
(estilo `tests/test_recepcion.py`). Una versión no se instala si falla una sola.

## 6. Policy Engine

| Nivel | Acciones |
|---|---|
| Automático | Responder con info cargada, tomar datos, calcular presupuesto sugerido, avisar cambios de estado, anotar dudas, enviar recordatorios |
| Aprobación (botón en el panel) | Enviar presupuesto, confirmar pago, confirmar turno, aceptar urgente, cancelar pedido |
| Siempre humano | Reclamos, preguntas sin respuesta cargada, devoluciones de dinero |

Implementado parcialmente en `app/harness/policies.py` (AUTO / CONFIRMAR). Falta: leer niveles
del perfil (solo endureciendo) y el nivel "siempre humano" explícito.

## 7. Instalación en la empresa (entrega 4)

| Pieza | Especificación |
|---|---|
| Hardware | Mini PC provisto por Damián (vendido/alquilado, a definir), prendido 24/7. Plan Privado: hardware con capacidad para modelo local (a definir modelo y mínimos). |
| Sistema | Linux con Docker; servicio que arranca solo; `python -m app` como hoy. |
| Relay | Servicio chico en la nube (FastAPI) que recibe webhooks de Meta, valida firma y reenvía al equipo por túnel saliente (WebSocket o Cloudflare Tunnel). No persiste mensajes. |
| Instalador | Script de un paso: instala, pide clave de licencia, crea tenant, abre el asistente del perfil. |
| Actualizaciones | Automáticas; antes de aplicar corre los tests; si fallan, vuelve a la versión anterior. |
| Licencia | Clave por cliente, validación periódica contra el panel; si vence, modo solo lectura (no borra nada). |
| Backups | Diario, cifrado (`TOKEN_ENCRYPTION_KEY` ya existe), retención 30 días; copia externa si el cliente acepta. |
| Panel de soporte | Web de Damián: lista de instalaciones, versión, estado, errores, uso y costo. Sin conversaciones. |

## 8. Planes comerciales

| Plan | IA | Brigadas | Notas |
|---|---|---|---|
| Básico | Modelo pago económico en la nube, con tope | 1–2 | Poco volumen |
| Pro | Modelo bueno en la nube + local para tareas fijas | 5 | Volumen medio |
| Privado | Todo local en el mini PC | 5 | Nada sale de la empresa |
| Premium (después) | Modelo top + soporte prioritario | 5 + nuevas | Empresas grandes |

Precio: cuota mensual fija que cubra el consumo del plan con margen; **se fija tras medir un
mes real de Mi Tienda IA** (registro de uso). Al llegar al tope: respuestas por reglas, aviso a
la dueña, nunca se corta la atención. Para el desarrollo propio de Damián: Nemotron
(orquestador) y Grok (jefes/ayudantes); modelo local sin elegir.

## 9. Privacidad, seguridad y legal

- En Básico/Pro los mensajes pasan por un proveedor de IA externo: se informa por contrato.
  En Privado nada sale del equipo.
- Panel de soporte sin datos personales; base y backups cifrados; login de la dueña con OTP.
- Registro de cada acción del bot (ya existe `audit.py`).
- **Ley 25.326** (datos personales, Argentina): el cliente es responsable de los datos de sus
  clientes; Raphael es encargado del tratamiento → contrato + política de privacidad.
  **Revisar con abogado antes de vender.**
- Confirmar que los términos de cada proveedor de IA permiten uso dentro de un producto
  revendido. WhatsApp Business: plantillas aprobadas para mensajes fuera de la ventana de 24 h;
  los "Estados" de WhatsApp no tienen API.

## 10. Hoja de ruta (cada entrega empieza solo si la anterior cumple su condición)

| Entrega | Tareas | Condición para seguir |
|---|---|---|
| 1. Núcleo + perfil | Crear esquema de perfil (§4.1) con pydantic; mover precios, seña, alias, tono, textos y datos del negocio al perfil; plantillas por rubro+tono; políticas leídas del perfil; migrar el tenant demo | Mi Tienda funciona igual y pasan todos los tests |
| 2. Modelos + uso | Capa de modelos por rol/plan (§4.2); tabla `uso`; tope por plan con caída a reglas; vista de uso en ajustes | Un mes de consumo real medido |
| 3. Canales reales | App de Meta + App Review; plantillas; relay; turnos con hora + recordatorio; disco persistente | La clienta atiende clientes reales dos semanas |
| 4. Instalable | Imagen Docker para mini PC; instalador; licencia; actualizaciones con tests; backups; panel de soporte | Una instalación nueva sin tocar código |
| 5. Primeros clientes | 2–3 negocios del mismo rubro; contrato + privacidad; precios fijados | Pagan el segundo mes |

**Siguiente paso concreto:** entrega 1.

## 11. Checklist de lanzamiento

- [ ] Entregas 1 a 4 completas y con sus condiciones cumplidas
- [ ] App de Meta aprobada (WhatsApp + Instagram) y plantillas aprobadas
- [ ] Contrato de servicio + política de privacidad revisados por abogado
- [ ] Precio de cada plan fijado con consumo medido
- [ ] Mini PC definido (modelo, costo, venta o alquiler) y una unidad de prueba instalada
- [ ] Panel de soporte funcionando con alertas
- [ ] Guía de alta de cliente (cómo se carga el perfil) y guía para la dueña
- [ ] Canal de contacto definido (falta en los videos: el cierre no tiene contacto)
- [ ] Videos explicativos publicados (ver §13)
- [ ] Caso de estudio de la clienta piloto con datos reales

## 12. Preguntas abiertas

1. ¿El mini PC se vende, se alquila o va incluido en la cuota?
2. ¿Qué modelo local para el plan Privado y qué hardware mínimo?
3. ¿Qué modelos concretos en Básico y Pro?
4. ¿Relay propio (costo fijo de Damián) o túnel directo en el equipo del cliente?
5. ¿Soporte: quién, en qué horario, por qué canal?
6. ¿El perfil lo carga Damián o hay un asistente de configuración?
7. ¿Segundo rubro después de ropa a medida?
8. ¿El bot se presenta como asistente/IA ante los clientes? (recomendado: sí)

## 13. Material de marketing ya hecho

- 10 videos explicativos verticales (9:16, 31–45 s, voz femenina sintetizada, música suave),
  formato: EL PROBLEMA → CÓMO FUNCIONA (paso a paso por brigada) → EN RESUMEN (la regla) →
  "Así funciona Raphael. Automatización para pymes." Temas: precio aprobado por la dueña, no
  inventa, reclamos, pagos, turnos, avisos, preguntas repetidas, brigadas, fin de semana,
  tiempo para el oficio. Montos y nombres de ejemplo son inventados: reemplazar por reales.
- Plan de contenido: primero los 10 explicativos, después videos de flujos reales de trabajo.
- Documento de capacidades/dudas/respuestas para la clienta:
  https://claude.ai/artifact/N34iN45N9SThVBRMa6dhjS

## 14. Cómo trabajar en este repo

- Python 3.12; `pip install -r requirements-dev.txt`; correr `python -m app`.
- Tests: `python -m pytest -q tests` (en Linux fallan 3 por `mimetypes`: subir foto, PWA
  instalable, video; en Windows pasan).
- `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`; modos `CONNECTOR_MODE`/`*_MODE` = mock|real;
  `DEMO_MODE=true` muestra el código de login.
- Finales de línea: `app/harness/brigades.py`, `intents.py` y `policies.py` usan CRLF; el resto LF.
  Al editar, preservar el final de línea de cada archivo (si `git diff --stat` explota, se rompió).
- Commits locales con el autor del último commit; **Damián hace el push**.
- Si quedan locks de git (`.git/*.lock`), moverlos a `.git/stale-*` (el borrado puede estar
  bloqueado en la carpeta).
