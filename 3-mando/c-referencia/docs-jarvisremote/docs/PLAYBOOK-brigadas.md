# Playbook del método de brigadas (Etapa 1)

> Cómo se define, se ejecuta y se valida una brigada de Raphael. Corto a propósito: el *por qué* de
> la arquitectura (jefes, ayudantes, defensas) está en `BLUEPRINT-habilidades-y-defensas-brigadas.md`;
> esto es el *cómo*. Etapa 1 = brigadas declarativas + framework de validación compartido.
> (Etapa 2, aparte: que el orquestador pueda **crear** brigadas con borrador + OK de Damian.)

## 1. Qué es un brigade spec

Una brigada ya no es una clase escrita a mano: es un `BrigadeSpec` (`backend/brigades/spec.py`), un dato
que el **motor genérico** (`backend/brigades/engine.py`, `GenericChief`) ejecuta. Declara todo lo
estructuralmente común:

| Campo | Qué declara |
|---|---|
| `id`, `name`, `purpose` | identidad y para qué existe |
| `prompt` | la ESPECIALIZACIÓN del jefe: con qué criterio planifica y sintetiza (`str`, o un builder sin args). El jefe no tiene tools ni le habla al usuario; la persona y las directrices de Damian gobiernan la **voz del orquestador**, no este prompt |
| `client` | `"local"` (modelo de esta PC, privacidad = defensa) o `"shared"` (modelo compartido de las brigadas). Es solo el **default del tipo**: cada rol resuelve su modelo por capas y se cambia por `.env` sin tocar el spec (§1.2) |
| `tools` | techo de privilegio del jefe (`None` = unión de las tools de sus ayudantes) |
| `ayudantes` + `routing` | ayudantes efímeros (**al menos uno**: no existe la brigada que responde directo), cada uno con su `config`, `client_model`, `tool_names`. Las reglas de ruteo marcan los **candidatos**: ninguna matchea → el `default` (el más pasivo); una → ese ayudante; dos o más → el jefe planifica cuáles hacen falta y si corren en paralelo |
| `skills` | capacidades que la brigada expone a la Suite (si delega, salen de los ayudantes) |
| `helper_timeout` | timeout por ayudante (default 900 s, env `BRIGADE_AYUDANTE_TIMEOUT_SECONDS`) |
| `tool_modules` | módulos de `app.tools` que registran las tools de la brigada y que el arranque liviano **no** carga (ej. pentest: traen `phone_link`/scapy). El registro los importa al instanciar el jefe: el orquestador liviano arranca igual y solo paga el costo si se usa la brigada |
| `validation` | la **escena de validación** (ver §3) |
| `watch` | qué se espera de la **ejecución** (`WatchSpec`: duración, progreso, repeticiones, errores) para que el watchdog del orquestador la vigile (ver §7 y `WATCHDOG-orquestador.md`) |

El motor mantiene la interfaz de siempre (`run` / `config` / `model`), la memoria persistente del jefe y las defensas del
chokepoint (timeout y fallo contenidos por ayudante, todo lo recibido marcado como DATO). Ejemplos reales:

- **Cerebro** (`brigades/cerebro.py` → `SPEC`): un ayudante efímero (`cerebro-recuperador`); el jefe sintetiza y reporta (desde el 2026-11-15 ninguna brigada responde directo: ver `docs/ARQUITECTURA-RAPHAEL.md` §0).
- **Investigación** (`brigades/investigacion.py` → `SPEC`): dos ayudantes (Forense por defecto, Scout solo ante señal web explícita).

- **Seguridad** (`brigades/seguridad.py` → `SPEC`, ver `docs/BRIGADA-SEGURIDAD.md`): primera brigada nueva armada con este método; dos ayudantes (escaneo / reporte pasivo), reusa las tools de pentest existentes y hereda el gate de `authorized_targets.yaml`.

- **Video** (`brigades/video.py` → `SPEC`, ver `docs/BRIGADA-VIDEO.md`): seis ayudantes por oficio (montaje, imagen, sonido, subtítulos, clips, info pasivo); sus tools solo trabajan en una carpeta fija y nunca tocan el original.

Scout sigue como entrada *legacy* del registro (nació antes del molde); las brigadas nuevas van por spec.

**Brigadas creadas por el orquestador (Etapa 2).** Además de escribir un `SPEC` a mano, el orquestador puede generar una brigada desde una
descripción: queda como **borrador no operativo** y solo se activa con la aprobación firmada de Damian sobre el hash exacto de su contenido.
Su spec se compila desde un JSON (no trae código) y hereda pasos de validación genéricos. Ver `ETAPA-2-crear-brigadas.md`.

### 1.1 Cómo corre un turno (flujo decidido: Ayudantes → Jefe → Orquestador → Usuario)

1. **Ruteo** (`orquestador/routing.py`): reglas primero; el clasificador solo si las reglas no deciden. Un saludo o charla corta lo contesta el orquestador directo, sin brigada.
2. **Plan** del jefe: elige entre los ayudantes candidatos (evento `plan`).
3. **Ayudantes**: trabajan con sus tools y devuelven un `ResultadoAyudante` (eventos `delegacion`, `tool`, `tool_result`, `resultado_ayudante`).
4. **Síntesis** del jefe: arma el `ReporteInterno` (eventos `sintesis`, `reporte`). Las cifras del reporte tienen que estar en los resultados o en el pedido; si el modelo no cumple el contrato, se reintenta y después sale un reporte **degradado**, marcado como tal.
5. **Voz** del orquestador (`orquestador/voz.py`): redacta el mensaje para Damian a partir del reporte y un verificador determinista comprueba que sea fiel (eventos `comunicacion`, `final`). Si no lo logra, sale un mensaje por plantilla.

**Trabajo conjunto.** Si el pedido trae señal explícita de más de una brigada, cada una hace los pasos 2–4 por separado y en paralelo, y el mando del orquestador (`orquestador/mando.py`) reparte el pedido antes, une los reportes por código y concluye sobre ellos antes del paso 5 (`turno.run_conjunto`). Si una brigada necesita el resultado de otra, el reparto lo declara y corren en cadena (DAG): el reporte de la primera le llega a la segunda como `contexto`, separado del pedido. Una brigada no necesita nada especial para participar: alcanza con que entregue su `ReporteInterno`.

El único `final` que ve el usuario es el del orquestador. Los contratos están en `brigades/contracts.py`; el `final` trae los
`tiempos` por fase. Mientras espera a un modelo o a un ayudante, el motor emite `latido` para el watchdog.

### 1.2 Modelo y costo por rol

Cada rol (orquestador, voz, cada jefe, cada ayudante) resuelve su modelo así, de más específico a más general
(`brigades/config.py`, `resolve_role_model`): override del rol en `.env` → default del tipo (`shared` / `local`) → global.
Perillas de equilibrio calidad/eficiencia, todas en `.env.example`:

| Perilla | Default | Para qué |
|---|---|---|
| `ORQUESTADOR_ROUTING_RAZONAMIENTO`, `BRIGADE_PLAN_RAZONAMIENTO`, `ORQUESTADOR_VOZ_RAZONAMIENTO` | off | estas fases no necesitan que el modelo razone |
| `BRIGADE_SINTESIS_RAZONAMIENTO` | auto | primer intento sin razonar; razona solo en el reintento |
| `BRIGADE_FALLBACK_LLM_*`, `ORQUESTADOR_FALLBACK_LLM_*` | sin respaldo | modelo de respaldo si el principal cae (con su propia key) |
| `ROLES_EN_LOCAL` + `MODELO_LOCAL_*` | vacío | fuerza roles a un modelo de esta PC; auditoría en `GET /api/privacidad` |
| `ORQUESTADOR_CHARLA_DIRECTA` | 1 | saludos y charla corta sin despertar a una brigada |

Un rol que lee el vault y corre en la nube saca tus notas a ese proveedor: la revisión de un borrador lo advierte y
`/api/privacidad` lo lista.

## 2. Agregar una brigada

1. Crear `backend/brigades/<id>.py` con el prompt del jefe y el `BrigadeSpec` en una constante `SPEC`, con sus `AyudanteSpec` + `Routing` (al menos un ayudante).
2. Registrarla: una línea en `_SPECS` de `backend/brigades/registry.py` (`"<id>": "brigades.<id>:SPEC"`).
3. Si usa tools de módulos que el arranque liviano no carga, sumarlos a `KEEP` en `backend/orquestador/slim_tools.py`.
4. Si debe entrar al auto-ruteo, sumar sus reglas en `orquestador/routing.py` y sus pedidos etiquetados en `orquestador/banco_ruteo.py` (el test del banco exige que las reglas no se equivoquen).
5. Escribir su escena de validación (§3) y correrla hasta tener una corrida verde: eso fija el baseline.
6. Tests unitarios sin LLM (ruteo, tools por ayudante, defensas) como los de `tests/test_brigade_investigacion.py`. La suite corre sin red: el LLM del jefe y el de la voz están anulados por default (`tests/conftest.py`); el test que necesite uno, inyecta uno falso.

Regla de importación: **importar un spec o una escena no debe cargar `app.tools`** (solo dataclasses; lo pesado
va perezoso dentro de funciones). El arranque liviano tiene que poder correr antes de importar `brigades.chief`.

## 3. La escena de validación

Vive en el spec (`ValidationSpec`, por convención en `brigades/<id>_scene.py`):

- `scene`: datos **fijos** (notas semilla, pedidos, directrices). Su hash (`scene_hash`) versiona el baseline: si
  cambia la escena, el baseline deja de ser comparable y hay que usar `--rebaseline`. El orden de las claves importa.
- `facts`: constantes de la escena que no entran al hash.
- `steps`: lista de `StepSpec(id, label, runner, gate, needs, prereq)`. `runner` es `"modulo:funcion"`, una
  `async def paso(ctx) -> Step` (en `validation/<id>.py`). `gate=True`: si no pasa, los siguientes no corren.
  `needs`: claves de `ctx.shared` que debe haber producido otro paso. `prereq`: chequeo propio del paso; si falta algo,
  el paso queda **SIN VALIDAR** (no rojo).
- `criterion`: criterio de éxito. Hoy: PASA si **todos** los pasos pasan y el aislamiento está intacto. SIN VALIDAR deja la corrida INCOMPLETA, nunca verde.
- `prerequisites`: prerrequisitos globales por nombre (`local_stack` = Ollama con el modelo local + embeddings).
- `isolate_settings` / `isolate_env`: stores extra que hay que redirigir a un temporal (casos, vaults, claves…).
- `baseline_keys`, `base_metrics`, `banner`, `teardown`: qué métricas se comparan, qué modelos se registran, cabecera y limpieza.

Cada paso recibe un `RunContext`: `ctx.scene`, `ctx.facts`, `ctx.env` (entorno aislado), `ctx.metrics` (lo que se
guarda para el baseline), `ctx.shared` (datos entre pasos), `ctx.timeout`.

**Aislamiento (no negociable):** toda escritura va a un temporal (`validation/harness.py`); antes y después se toma la
huella del vault, el estado, el `audit.log` y los stores reales, y si algo real cambió la validación **falla**.

## 4. Correr la validación

Desde `backend/` (requiere el modelo de cada rol accesible —hoy nemotron en NVIDIA, con su key en `.env`— y los embeddings locales en LM Studio):

```powershell
.venv\Scripts\python.exe -m validation.todas                          # TODAS las brigadas + tablero
.venv\Scripts\python.exe -m validation.todas cerebro                  # una
.venv\Scripts\python.exe -m validation.todas cerebro investigacion    # varias
.venv\Scripts\python.exe -m validation.todas --listar                 # qué brigadas tienen escena
.venv\Scripts\python.exe -m validation.cerebro                        # atajo de una sola brigada (idem investigacion)
```

Opciones: `--keep` (conserva los stores de prueba), `--rebaseline` (reescribe el baseline; solo si la corrida pasa),
`--strict` (los desbalances vs baseline también fallan), `--timeout N` (segundos por turno de modelo).
Salida: `0` pasó · `1` falló · `2` no se pudo validar o quedó incompleta (falta un prerrequisito).

El **tablero** final muestra, por brigada: resultado, pasos (PASS/FAIL/SIN VALIDAR/NO CORRIÓ) y cómo quedó contra su
baseline (desbalances y **regresiones**: un paso que pasaba en el baseline y ahora no).

Lo que una validación evalúa como «respuesta» es el mensaje final del orquestador, y además comprueba que sea fiel al reporte.

**Medir sin validar** (no tocan el vault ni fijan baseline):

```powershell
.venv\Scripts\python.exe -m validation.medir todo --n 3            # latencia por fase (ruteo, síntesis, voz, turno) con datos inventados
.venv\Scripts\python.exe -m validation.calibrar_consolidacion      # umbral/brecha de consolidación contra una verdad etiquetada (solo lee)
```

## 5. Dónde vive cada cosa (registro doble)

| Qué | Dónde | Versionado |
|---|---|---|
| Spec y escena | `backend/brigades/<id>.py`, `<id>_scene.py` | sí |
| Funciones de los pasos | `backend/validation/<id>.py` | sí |
| Framework / tablero | `backend/validation/framework.py`, `todas.py` | sí |
| **Baseline** (se fija en la primera corrida verde) | `backend/validation/baselines/<id>.json` | sí |
| **Registro JSON** de cada corrida (máquina) | `backend/validation/results/<id>/<fecha>.json` + `latest.json`; tablero en `results/_tablero/` | no (artefactos; env `VALIDATION_RESULTS_DIR` lo redirige) |
| **Word por ronda** (lectura humana, supervisión) | `C:\Users\dam\Documents\Validacion-Brigadas\` | fuera del repo |

El JSON trae: veredicto, resultado por paso (con cada chequeo y el detalle de lo que pasó), métricas, baseline
(estado, desbalances, regresiones), prerrequisitos faltantes, aislamiento y entorno (commit, python). El Word de cada
ronda se redacta a partir de ese JSON; el JSON es la fuente de verdad.

## 6. Reglas del método

- Las validaciones existentes son la red de seguridad de cualquier cambio al motor o a un spec: si una **empeora** respecto de su baseline/corrida previa, se frena y se avisa.
- Un paso que no se puede probar (falta una key, un servicio) se declara **SIN VALIDAR**; nunca se maquilla como verde ni se convierte en rojo engañoso.
- Los modelos varían entre corridas: un chequeo de calidad de respuesta puede oscilar. Se compara contra el baseline y se mira la tendencia, no una corrida suelta.
- No se debilitan gates (scope de pentest, dry-run→confirm, flags, sandbox de FS) para que una validación pase.
- Una optimización nunca afloja un verificador: si hace falta velocidad, se quita razonamiento o texto del prompt, y el contrato y el chequeo de cifras siguen igual.

## 7. El patrón estándar: SPEC + VALIDACIÓN, vigilado por el watchdog

Toda brigada (y, hacia adentro, toda unidad de trabajo de un jefe o ayudante) se define con **dos piezas que viajan juntas**:

| Pieza | Responde a | Dónde |
|---|---|---|
| **SPEC** | *Qué hace*: quién es, con qué modelo, qué tools, qué ayudantes y cómo se rutea, y **qué se espera de su ejecución** (`watch`: duración esperada, progreso, no repetirse, errores tolerados) | `BrigadeSpec` (+ `WatchSpec`) |
| **VALIDACIÓN** | *Cuándo está bien*: la escena fija, los pasos y el **criterio de éxito** | `ValidationSpec` (§3) |

Reglas del estándar:

1. **Sin validación no hay brigada operativa.** Una brigada creada por el orquestador no se acepta como borrador sin su `validacion`
   (Etapa 2); una escrita a mano no tiene baseline hasta tener su primera corrida verde.
2. **El spec declara, no improvisa.** Lo que el orquestador, el motor y el watchdog saben de una brigada sale de su spec: no hay umbrales escondidos en el código.
3. **El watchdog vigila la ejecución contra el spec.** Mientras la validación dice *si el resultado es correcto* (offline, con escena fija), el watchdog dice
   *si la corrida en vivo se comporta como el spec declara*: termina en el tiempo esperado (por defecto, el timeout de ayudante que ya existe),
   avanza (no pasa más de `stall_seconds` sin eventos nuevos), no se repite (`max_repeats` llamadas o respuestas idénticas) y no acumula errores (`max_errors`).
   Si no se cumple, corta al ayudante o jefe colgado y lo avisa en el feed del orquestador. Ver `WATCHDOG-orquestador.md`.
4. **Defensivo, no destructivo.** El watchdog solo corta corridas y avisa; no toca gates ni ejecuta tools.
5. **Cuando se agrega una brigada** (§2), el spec lleva su `watch` si sus tiempos son atípicos (ej. Seguridad: escaneos largos y callados) y su escena de validación cubre el camino
   feliz y el de fallo.

