# Contrato de brigadas (versión 1)

Toda brigada de Raphael es un repo propio que cumple este contrato. El harness la carga, le da
un `Contexto` y es su único camino hacia el resto. **Una brigada nunca importa otra brigada.**

## Reglas

1. **Una brigada, un trabajo.** Si hace dos cosas distintas, son dos brigadas.
2. **Solo habla por el harness:** eventos (`ctx.publicar`), consultas (`ctx.consultar`) y acciones (`ctx.solicitar` o `Respuesta.acciones`).
3. **Todo lo que compromete al negocio es una `Accion`** y pasa por el Policy Engine. Nunca se manda un presupuesto, se confirma un pago o un turno "por fuera".
4. **No inventa.** Solo afirma lo que está en el perfil o en sus datos.
5. **Reglas antes que IA.** `ctx.ia(...)` puede devolver `None` en cualquier momento (sin modelo, falla, tope): la brigada tiene que seguir funcionando.
6. **Sus datos son suyos:** `ctx.datos` es su espacio; no lee los de otra.
7. **Se prueba sola** con `raphael_harness.testing.armar(MiBrigada())`.

## Esqueleto

```python
# src/raphael_mibrigada/brigada.py
from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel, Respuesta
from raphael_harness.texto import normalizar
from . import __version__


class MiBrigada(Brigada):
    nombre = "mibrigada"                       # el nombre que va en `brigadas:` del perfil
    version = __version__
    descripcion = "Qué hace, en una línea."
    acciones = {"hacer_algo": Nivel.APROBACION}  # nivel por defecto; el perfil solo puede endurecerlo
    eventos = ("encargo.creado",)               # lo que escucha del bus
    comandos = {"listar": "Qué devuelve"}       # órdenes del panel de la dueña

    def interes(self, msg, ctx):               # 0 a 1: qué tan suyo es el mensaje
        return 0.7 if "algo" in normalizar(msg.texto) else 0.0

    def en_curso(self, msg, ctx):              # ¿conversación abierta con este contacto?
        return ctx.datos.obtener("chats", msg.contacto) is not None

    def atender(self, msg, ctx):               # Respuesta o None (None = que lo vea otra)
        return Respuesta("Le paso tu pedido a la dueña 😊",
                         [Accion("hacer_algo", {"dato": 1}, "Resumen para el panel")])

    def ejecutar(self, accion, ctx):           # ya permitida; devuelve el texto para el cliente
        if accion.tipo != "hacer_algo":
            raise ErrorDeAccion("no sé hacer eso")
        ctx.publicar("algo.hecho", {"dato": accion.datos["dato"]})
        return "¡Listo!"

    def al_evento(self, evento, datos, ctx): ...
    def comando(self, nombre, datos, ctx): ...
    def tick(self, ahora, ctx): ...            # recordatorios y tareas programadas
```

```python
# src/raphael_mibrigada/__init__.py
__version__ = "0.1.0"
from .brigada import MiBrigada  # noqa: E402
BRIGADA = MiBrigada              # así la encuentra el harness en modo desarrollo
```

```toml
# pyproject.toml (así la encuentra instalada)
[project.entry-points."raphael.brigadas"]
mibrigada = "raphael_mibrigada:MiBrigada"
```

## Lo que ofrece el `Contexto`

| | |
|---|---|
| `ctx.perfil`, `ctx.negocio` | El perfil de la empresa (solo lectura) |
| `ctx.datos` | Su espacio: `guardar`, `obtener`, `listar`, `borrar`, `siguiente`, `actualizado` |
| `ctx.ahora()`, `ctx.hoy()` | El reloj del harness (controlable en pruebas) |
| `ctx.publicar(evento, datos)` | Bus de eventos |
| `ctx.solicitar(accion)` | Acción fuera de una respuesta (ej. desde un evento o `tick`) |
| `ctx.consultar("atencion", msg)` | Le pasa un mensaje a otra brigada y usa su respuesta |
| `ctx.ia(rol, mensajes)` | IA del plan o `None` |
| `ctx.instalada("agenda")` | Si otra brigada está presente |
| `ctx.registrar(que, **datos)` | Supervisión |

## Niveles de acción

| Nivel | Qué pasa |
|---|---|
| `Nivel.AUTO` | Se ejecuta y queda registrada |
| `Nivel.APROBACION` | Queda pendiente; la dueña aprueba (con cambios) o rechaza |
| `Nivel.HUMANO` | El bot se retira; una persona la resuelve (con o sin respuesta al cliente) |

Una acción que no conoce nadie se trata como `APROBACION`.

## Eventos en uso (v1)

| Evento | Lo publica | Lo escuchan |
|---|---|---|
| `encargo.creado` | encargos | — |
| `encargo.presupuesto_enviado` | encargos | cobros |
| `encargo.estado_cambiado` | encargos | avisos |
| `turno.pedido` | encargos | agenda |
| `turno.confirmado` | agenda | — |
| `pago.confirmado` | cobros | encargos |
| `conversacion.derivada` | atencion | encargos |
| `pendiente.creado` / `pendiente.rechazado` | harness | cobros (rechazado) |

Cambiar el nombre o los datos de un evento rompe a quien lo escucha: va en el CHANGELOG y en esta tabla.

## Versiones

- `CONTRATO` (en `contrato.py`) sube solo si este contrato cambia de forma incompatible. El
  harness no carga piezas con otro número.
- Cada repo usa versionado semántico en su `__init__.py` y lo anota en su `CHANGELOG.md`.
- Las brigadas declaran `raphael-harness>=0.1,<0.2`: un cambio de versión menor del harness no
  puede romperlas.
