# Plan comercial — del proyecto personal al producto

> Decisión de Damian (2026-11-16): llevar el orquestador a un producto comercial, manteniendo el corazón técnico y sin el
> tema artístico original. Idea: salir con el orquestador + Cerebro, Investigación y Seguridad; sumar brigadas a medida que
> pasen su validación; más adelante, la app de celular. Cada usuario usa sus propios modelos.
>
> Este documento lleva el estado. Nada acá promete ingresos: ordena qué falta para que otra persona pueda instalarlo y usarlo.

## Qué se vende (el corazón técnico)

| Pieza | Dónde está |
|---|---|
| Respuestas verificadas (cifras y fuentes contra el reporte) | `brigades/contracts.py`, `orquestador/voz.py` |
| Control humano: nada se activa sin aprobación firmada | `brigades/draft_store.py` |
| Privacidad por interruptor y auditoría de qué ve cada rol | `brigades/config.py` (`ROLES_EN_LOCAL`), `GET /api/privacidad` |
| Vigilancia de corridas | `orquestador/watchdog.py` |
| Modelo propio por rol, traído por el usuario | `brigades/config.py` (`resolve_role_model`) |
| Brigadas que trabajan solas o juntas (DAG) | `orquestador/turno.py`, `orquestador/mando.py` |

## Etapas

| # | Etapa | Estado |
|---|---|---|
| 1 | **Validar** Cerebro e Investigación con el flujo nuevo (`backend\\correr-validaciones.bat`) | ✅ Cerebro PASA 4 de 4 con baseline nuevo fijado (2026-11-16) y Forense pasa de punta a punta. Falta validar Scout (necesita `BRAVE_SEARCH_API_KEY` o `SEARXNG_URL`); sin eso Investigación no tiene baseline |
| 2 | **Despersonalizar**: nombre del asistente y del usuario por configuración, persona neutra | 🔨 primer paso hecho (ver abajo) |
| 3 | **Instalar en otra máquina**: instalador, configuración guiada de claves y carpetas, sin rutas fijas | ⏳ pendiente |
| 4 | **Primera versión pública**: orquestador + Cerebro + Investigación; Seguridad incluida pero apagada de fábrica | ⏳ pendiente |
| 5 | **Más brigadas**, cada una cuando pase su validación (Video es la siguiente) | ⏳ pendiente |
| 6 | **App de celular** como control remoto del asistente del usuario | ⏳ pendiente |

## Etapa 2 — qué quedó hecho y qué falta

Hecho (`brigades/identidad.py`, variables `IDENTIDAD_ASISTENTE`, `IDENTIDAD_USUARIO`, `IDENTIDAD_PERSONA`):

- Los prompts de sistema de todos los roles (orquestador, voz, mando, jefes, ayudantes), los títulos de los bloques de dato, las
  plantillas de respuesta, el reporte del sistema, los nombres de brigada del feed y el título de la UI salen con el nombre
  configurado. El contenido del usuario (pedidos, notas, reportes) no se toca.
- Con otro nombre de asistente, la voz usa una persona neutra, sin el personaje original.
- Sin configurar, la instalación de Damian queda exactamente igual.

Falta:

- El **nombre definitivo** del producto (decisión de Damian). El de fábrica sigue siendo el original.
- El chat del **monolito** (`app/agent.py`) todavía lleva la persona original; este paso cubre el orquestador y las brigadas.
- Textos de la **UI** con nombres propios (ayudas, pestañas) y comentarios del código.
- Las **directrices** y el **vault** son datos del usuario: una instalación nueva tiene que arrancar con los suyos, vacíos.
- Cambiar los valores de fábrica cuando haya nombre (un solo archivo).

## Decisiones tomadas (Damian, 2026-11-16)

- **Ingresos: gratis y abierto ahora, con la puerta abierta a cobrar más adelante.** Para no cerrarla:
  - Todo el código tiene un solo dueño (Damian). Si entran aportes de otros, que cedan o licencien sus derechos por escrito
    antes de aceptarlos: sin eso, después no se puede ofrecer una licencia comercial del conjunto.
  - Lo que se publique con una licencia abierta queda abierto para esa versión: el cobro futuro tiene que venir de otro lado.
    Caminos habituales: (a) núcleo abierto + brigadas, app de celular o sincronización pagas; (b) licencia que obliga a
    publicar cambios (tipo AGPL) + licencia comercial paga para quien no quiera esa obligación; (c) soporte e instalación.
  - Falta elegir la licencia concreta. Permisiva (MIT/Apache) da más adopción y deja que cualquiera lo revenda; una de tipo
    AGPL protege más el camino (b). Conviene revisarlo con un profesional antes de publicar.
- **Nombre: se queda «Raphael»** (se evaluó «Atlas» y se descartó: muy usado en software). Lo que sale es el personaje
  original (apodos, «la Gran Sabia»): las instalaciones nuevas van con la persona neutra (`IDENTIDAD_PERSONA=neutral`); la de
  Damian conserva la original. Pendiente al empaquetar: que la persona neutra sea el valor de fábrica. Antes de publicar,
  revisar que el nombre no esté registrado como marca en el rubro.

## Decisiones abiertas (de Damian)

1. **Licencia** concreta (ver arriba).
2. **Seguridad en el lanzamiento**: escanea redes; propuesta: incluida pero apagada, uso solo sobre equipos propios. Revisar el
   aspecto legal con un profesional antes de publicar.
3. **A quién** va la primera versión: hoy exige saber conseguir una clave de modelo o instalar uno local.

## Riesgos conocidos

- Depende de Windows en la firma de aprobaciones (DPAPI). Otra plataforma necesita otro almacén de claves.
- Cerebro necesita un vault de Obsidian y un motor de embeddings local: es la instalación más difícil para un usuario nuevo.
- Licencias de las dependencias sin revisar para uso comercial.
- Nada de lo construido desde el 2026-11-15 corrió todavía con datos reales.
