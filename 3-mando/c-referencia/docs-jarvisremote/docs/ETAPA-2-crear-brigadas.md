# Etapa 2 — El orquestador crea brigadas (borrador + OK de Damian)

Construye sobre la Etapa 1 (`PLAYBOOK-brigadas.md`: brigade spec declarativo + motor genérico + framework de validación).
Damian describe una brigada; el orquestador genera un **borrador** desde el molde; **nada es operativo hasta que Damian lo activa**.

## La línea roja

Una brigada creada nace en estado **borrador** y **no es operativa**: no se rutea, no corre, no aparece como activa, no tiene
pestaña, no entra a `validation.todas` y el router HTTP responde 404. Solo pasa a **activa** con una acción explícita de Damian
sobre el **hash exacto** del contenido que revisó.

Cómo se hace cumplir (`backend/brigades/draft_store.py`) — no es un campo «estado» que cualquiera pueda cambiar:

| Garantía | Qué impide |
|---|---|
| La aprobación es sobre un **hash** (sha256) del contenido | Aprobar «lo que haya guardado»: si el borrador cambió entre la revisión y el OK, no se activa |
| La aprobación está **firmada** (Ed25519, clave privada con DPAPI, clave propia del almacén) | Escribir `"estado": "activa"` a mano, o con un `fs_write_file` de un jefe manipulado por prompt-injection; copiar la firma de otra brigada |
| «Activa» exige firma válida **y** que el contenido conserve el hash aprobado | Editar el borrador después de activarlo (lo desactiva solo) |
| Se **revalida en cada uso** (también entre procesos) | Que una política más estricta, o un id que choca, deje activa una brigada que ya no corresponde (falla cerrado) |
| Solo código determinístico activa | Un jefe, una nota o una página que escriban `/activar-brigada …`: los comandos se interpretan solo en el mensaje que **escribe Damian** y solo si **empieza** con el comando |

Límite honesto: DPAPI ata la clave a la cuenta de Windows, no al proceso. Un agente con shell sin restricciones (`pc_run_command` del
Raphael completo, que no es un sandbox) podría en teoría firmar. El gate protege contra edición de archivos y contra los jefes de
brigada (que no tienen shell). Defensa en profundidad opcional: agregar `backend/data/brigades_creadas/` a `FS_DENIED_PATHS`.

## Qué es un borrador

JSON puro (esquema cerrado en `backend/brigades/factory.py`; plantillas en `backend/brigades/ejemplos.py`): `id`, `nombre`, `proposito`,
`prompt` (la ESPECIALIZACIÓN del jefe: con qué criterio sintetiza), `modelo` (`local`/`shared`: el LLM propio del jefe), `ayudantes`
(**obligatorio, de 1 a 4**; cada uno con `modo`, `descripcion`, `prompt`, `modelo`, `tools`) + `ruteo` (`reglas` en orden de prioridad +
`default`; con un solo ayudante alcanza `"reglas": []`), un `watch` **opcional** (vigilancia dentro de rangos, ver `WATCHDOG-orquestador.md`) y una `validacion` **obligatoria** (`criterio`, `prerequisitos`, `pasos` de tipo
`ruteo` —al menos uno— o `respuesta`). Desde el 2026-11-15 **no existe la brigada "directa"** (decisión de Damian: el jefe nunca responde
directo ni tiene tools; coordina, sintetiza y le reporta al orquestador): un borrador sin ayudantes o con `tools` en el jefe se rechaza.

- **Validación estricta** (`validate_draft`): el borrador puede venir de un modelo y se trata como dato no confiable. Se rechazan campos
  desconocidos, tools inexistentes o **denegadas**, regex inválidas o con cuantificadores anidados, ids que chocan, ayudantes sin ruteo,
  brigadas que delegan sin validar su ruteo, validación ausente. Devuelve **todos** los errores juntos.
- **Política de tools** (`backend/brigades/tool_catalog.py`, catálogo leído con `ast` sin importar nada): *denegadas* (no se conceden por
  borrador: shell, autoedit de código, borrado, credenciales, control de PC/celular, confirmar/rechazar por Damian, nube con costo),
  *sensibles* (permitidas, marcadas ⚠ en la revisión: escriben, escanean la red, salen a internet, controlan un navegador) y normales.
  Los `tool_modules` salen del catálogo, nunca del borrador.
- **Compilación** (`compile_spec`): mismas piezas que Cerebro/Investigación/Seguridad (`BrigadeSpec`, `AyudanteSpec`, `Routing`,
  `ValidationSpec`) y un bloque de seguridad fijo al final de todos los prompts (instrucción vs dato; no esquivar gates).
- **Hereda del molde su validación**: pasos genéricos declarativos (`backend/validation/generic.py`): `alcance` (siempre: activa, firmada,
  es lo aprobado, menor privilegio), `ruteo` (ayudante esperado, sin modelo) y `respuesta` (con el modelo; si falta Ollama/embeddings/key
  queda SIN VALIDAR, nunca rojo). Se corre con `python -m validation.todas <id>` una vez activada.
- Las brigadas creadas **no entran al auto-ruteo**: se usan con `/<id> pedido` o desde su pestaña. Activar una no cambia adónde van
  los pedidos de las demás.

## Cómo se usa

**Chat del orquestador** (comandos interpretados por código, solo al inicio del mensaje):

| Comando | Qué hace |
|---|---|
| `/crear-brigada <descripción>` | El modelo del **orquestador** diseña un borrador (con reintentos si no valida) y muestra la revisión con su hash. No activa nada |
| `/revisar-brigada <id>` | La revisión completa |
| `/activar-brigada <id> <hash>` | **Activa** (aprobación firmada sobre ese hash exacto) |
| `/desactivar-brigada <id>` | Vuelve a borrador (reversible) |
| `/descartar-brigada <id>` | Borra un borrador (una activa no se descarta) |
| `/brigadas` | Lista activas y borradores |

**UI** (pestaña **Brigadas**): describir la brigada o cargar un ejemplo → el borrador aparece en «NO OPERATIVOS» → «Revisar» muestra
prompts enteros, tools con su nivel, dónde corre cada modelo, ruteo, validación, advertencias y hash → «✓ Activar» pide confirmación
(con las tools de alto privilegio y el hash) y envía el hash revisado. Las activas aparecen como pestañas propias («CREADA»). En la revisión se puede
**editar el JSON** del borrador y **restaurar** una de sus últimas 5 versiones; las dos cosas dejan un borrador con hash nuevo, nunca activan.

**API** (token del orquestador, solo 127.0.0.1): `GET /api/brigadas`, `GET /api/brigadas/{id}`, `POST /api/brigadas/borrador` (JSON, sin
modelo), `POST /api/brigadas/crear` (descripción), `POST /api/brigadas/{id}/activar` `{hash}`, `POST …/restaurar` `{hash}` (vuelve a una versión anterior del
borrador; una activa no se pisa), `POST …/desactivar`, `DELETE /api/brigadas/{id}`.

## Ejemplo

```text
/crear-brigada Una brigada que consulte lo que ya sé del vault y, si le pido investigar, salga a la web y deje una nota.
→ BORRADOR «Radar técnico» (id: radar-tecnico) — NO está activo. … ⚠ research_topic — sale a internet y escribe notas …
  Hash del contenido: 5dde64a60fa9   Para activar: /activar-brigada radar-tecnico 5dde64a60fa9
/activar-brigada radar-tecnico 5dde64a60fa9
→ ✓ Brigada 'radar-tecnico' ACTIVADA con tu aprobación … Ya podés usarla con /radar-tecnico <pedido>
python -m validation.todas radar-tecnico        # alcance + ruteo: PASS
```

## Dónde vive cada cosa

| Qué | Dónde |
|---|---|
| Catálogo y política de tools | `backend/brigades/tool_catalog.py` |
| Fábrica (esquema, validación, revisión, compilación) | `backend/brigades/factory.py`, ejemplos en `ejemplos.py` |
| Almacén + gate + firma | `backend/brigades/draft_store.py` → `backend/data/brigades_creadas/<id>.json` (+ `_claves/`; gitignoreado) |
| Registro dinámico (solo activas verificadas) | `backend/brigades/registry.py` |
| Diseñador (descripción → borrador, modelo del orquestador) | `backend/brigades/designer.py` |
| Pasos de validación genéricos | `backend/validation/generic.py` |
| Comandos, API y UI del orquestador | `backend/orquestador/brigadas.py`, `server.py`, `routing.py`, `ui.html` |

## Pendiente / límites

- El diseñador se probó con nemotron real (un intento, borrador válido); no hay una medición de cuántos intentos necesita con descripciones difíciles.

- Prompt-level, no argumentos: como en Seguridad, restricciones tipo «solo `detect`» las impone el prompt, no un filtro de argumentos de la tool.
- Una brigada creada no puede tener vault/embeddings propios, ni tools nuevas (eso es código y revisión humana), ni entrar al auto-ruteo.
- El historial guarda las últimas 5 versiones de un borrador, sin diff entre ellas. La aprobación firmada es siempre sobre el hash vigente: una versión vieja no sirve para activar.
- El catálogo ve las tools registradas con `@register_tool(name=…)` en `app/tools/`; una tool registrada de otra forma no figura.
