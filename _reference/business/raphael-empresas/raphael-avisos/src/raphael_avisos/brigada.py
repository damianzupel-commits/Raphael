"""Brigada Avisos: cuando cambia el estado de un pedido, el cliente se entera solo.

Escucha `encargo.estado_cambiado` y pide `avisar_estado` (automático). Solo avisa a clientes que
llegaron por un canal de mensajes (WhatsApp, Instagram). Un aviso por cambio de estado.
"""

from __future__ import annotations

from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel
from raphael_harness.texto import primer_nombre

from . import __version__

CANALES = ("whatsapp", "instagram", "prueba")
TEXTOS = {
    "confirmado": "¡Hola {c}! Recibimos tu seña, ya queda confirmado tu {p} (encargo #{n}). Te avisamos cuando empiece la confección 🧵",
    "en_confeccion": "¡Hola {c}! Ya estamos trabajando en tu {p} ✂️ Te contamos cómo va.",
    "prueba": "¡Hola {c}! Tu {p} está para probártelo 👗 ¿Qué día podés pasar?",
    "listo": "¡Hola {c}! Tu {p} está listo 🎀 ¿Cuándo lo retirás o coordinamos el envío?",
    "entregado": "¡Gracias {c}! Esperamos que disfrutes tu {p} 💛",
}


class Avisos(Brigada):
    nombre = "avisos"
    version = __version__
    descripcion = "Avisa automáticamente al cliente cada vez que cambia el estado de su pedido."
    acciones = {"avisar_estado": Nivel.AUTO}
    eventos = ("encargo.estado_cambiado",)
    comandos = {"enviados": "Avisos enviados"}

    def al_evento(self, evento, datos, ctx):
        estado = datos.get("estado")
        if estado not in TEXTOS or datos.get("origen") not in CANALES or not datos.get("contacto"):
            return
        clave = f"{datos['num']}:{estado}"
        if ctx.datos.obtener("enviados", clave):
            return                                   # un solo aviso por cambio
        ctx.datos.guardar("enviados", clave, {"num": datos["num"], "estado": estado, "contacto": datos["contacto"],
                                              "cuando": ctx.ahora().isoformat(timespec="seconds")})
        ctx.solicitar(Accion("avisar_estado", {"num": datos["num"], "estado": estado, "cliente": datos.get("cliente", ""),
                                               "descripcion": datos.get("descripcion", "pedido")},
                             f"Aviso a {datos.get('cliente')}: encargo #{datos['num']} pasó a {estado}", datos["contacto"]))

    def ejecutar(self, accion, ctx):
        if accion.tipo != "avisar_estado":
            raise ErrorDeAccion(f"avisos no ejecuta '{accion.tipo}'")
        d = accion.datos
        plantilla = TEXTOS.get(d.get("estado"))
        if not plantilla:
            return None
        return plantilla.format(c=primer_nombre(d.get("cliente", "")) or "", p=d.get("descripcion", "pedido"), n=d.get("num")).replace("¡Hola !", "¡Hola!")

    def comando(self, nombre, datos, ctx):
        if nombre == "enviados":
            return ctx.datos.listar("enviados")
        return super().comando(nombre, datos, ctx)
