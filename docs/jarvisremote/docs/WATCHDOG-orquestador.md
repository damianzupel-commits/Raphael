# Watchdog del orquestador

Capacidad del **orquestador**: vigila la ejecución de los **jefes** y **ayudantes** en curso, corta la que se cuelga y lo avisa en el feed.
Código: `backend/orquestador/watchdog.py`. Es **defensivo**: solo mira el feed de eventos, corta corridas colgadas y avisa. No ejecuta
tools, no escribe fuera de su propio registro y no toca ningún gate (scope de pentest, aprobación de brigadas, flags, sandbox).

## Qué vigila (contra lo que el spec declara)

| Detección | Cuándo dispara | Límite (spec `watch`, si falta: `.env`) |
|---|---|---|
| **loop** | La misma llamada (tool + argumentos) `max_repeats` veces en las últimas 10 **del mismo ayudante** (cubre también ciclos A-B-A-B), o la misma respuesta de tool (≥ 40 caracteres) otras tantas veces. Dos llamadas que solo difieren en mayúsculas, espacios o puntuación cuentan como la misma | `max_repeats` · `WATCHDOG_MAX_REPEATS` (4) |
| **sin progreso** (deadlock) | Ningún evento nuevo en el feed durante `stall_seconds`. Si el motor está latiendo (`latido`: sigue esperando a un modelo o a un ayudante), el límite se estira hasta 3×, nunca más | `stall_seconds` · `WATCHDOG_STALL_SECONDS` (300) |
| **timeout** | El turno supera la duración esperada | `max_seconds` · por defecto el **timeout de ayudante que ya existe** (`BRIGADE_AYUDANTE_TIMEOUT_SECONDS` o el de la brigada) + `WATCHDOG_MARGIN_SECONDS` (30) + `WATCHDOG_JEFE_SECONDS` (600, el tiempo del jefe para planificar y sintetizar) |
| **errores** | `max_errors` tools fallidas seguidas (un éxito reinicia la cuenta) | `max_errors` · `WATCHDOG_MAX_ERRORS` (5) |

Las llamadas `delegar:<ayudante>` no cuentan como loop. Respuestas cortas tipo `status: ok` tampoco (se repiten legítimamente), ni varios ayudantes en paralelo haciendo la misma búsqueda.
El margen del timeout hace que, cuando hay ayudante, salte primero el corte propio del jefe (informa mejor). El watchdog entonces solo lo **reporta**
(`action: "reported"`); si no hay corte previo, **corta él** (`action: "cut"`).

## Cómo corta y cómo reporta

1. Cada turno de `/api/chat` corre vigilado (`orquestador/turno.py` → `watchdog.supervise(...)`). Si el turno anda bien, el watchdog no emite nada.
2. Si una detección dispara, cancela la tarea del jefe (y con ella a su ayudante efímero, que vive adentro) y espera a que termine de cancelarse.
3. Emite un evento `{"type":"watchdog","action":"cut","reason":"loop|sin_progreso|timeout|errores","target":"ayudante X | jefe Y","detail":…,"message":"el watchdog cortó al … por …"}` y un `final` con `origen: "watchdog"` y `literal: true` (texto de código, no pasa por el modelo de la voz). Se puede reintentar.
4. La memoria persistente del jefe no se actualiza con un turno cortado (no llegó a cerrarse).

## Dónde se ve

- **Feed de la UI**: una fila 🐕 «Watchdog · el watchdog cortó al ayudante … por loop: …» (roja si cortó, neutra si solo reportó). Va escapado y queda a la vista aunque el chip «Proceso» esté en oculto.
- **API**: `GET /api/watchdog` (token del orquestador): estado, límites por defecto y las últimas intervenciones.
- **Registro**: `backend/data/watchdog/intervenciones.jsonl` (gitignoreado) y el log `orquestador.watchdog`.
- **Apagar**: `WATCHDOG_ENABLED=0` en `.env`.

## Declararlo en un spec

```python
SPEC = BrigadeSpec(..., watch=WatchSpec(stall_seconds=900, max_repeats=6))   # todo opcional
```

Seguridad lo hace (`stall_seconds=900`: nmap/ZAP/sqlmap pasan minutos sin emitir nada). Una brigada creada por el orquestador (Etapa 2)
puede declarar `watch` en su borrador, **dentro de rangos** y sin poder apagarlo: `max_seconds` 30–7200, `stall_seconds` 30–3600,
`max_repeats` 2–20, `max_errors` 1–20. Entra al hash que Damian aprueba y se ve en la revisión. Sin `watch`, usa los defaults.

## Límites honestos

- Solo ve eventos del feed. Un modelo que tarda minutos en una sola respuesta ya no queda mudo: el motor late cada `BRIGADE_LATIDO_SECONDS` (20) y eso le da hasta 3× de aire; una tool larga y callada dentro de un ayudante sigue dependiendo de `stall_seconds`.
- Cancelar corta lo que está en `await` (llamadas al modelo, esperas). Una tool síncrona que corre en un hilo termina sola.
- Un loop cuyos argumentos cambian de contenido (un contador, una marca de tiempo) no se detecta como loop: lo atrapan el timeout y los errores. Solo se igualan mayúsculas, espacios y puntuación, para no confundir trabajo legítimo (leer nota_1 … nota_8) con un loop.
- No reintenta ni reencola nada: corta y avisa; decidir qué hacer después es de Damian.
