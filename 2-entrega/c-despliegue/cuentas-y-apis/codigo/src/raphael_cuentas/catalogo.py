"""Catálogo de cuentas y APIs externas. Es la única lista: la plantilla de claves y la lista de Damián salen de acá.

Nunca guarda valores de claves: solo los NOMBRES de las variables de entorno y dónde se consiguen.
Los endpoints de verificación son solo de lectura. Los marcados `supuesto` hay que confirmarlos contra la
documentación vigente del proveedor antes de confiar en ellos (no se pudieron probar con cuentas reales).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Var:
    nombre: str
    secreta: bool = True          # si es secreta, el chequeo muestra solo "cargada" y los últimos 4
    obligatoria: bool = True      # obligatoria para que la cuenta cuente como lista
    ayuda: str = ""
    defecto: str = ""             # valor no secreto que va precargado en la plantilla


@dataclass(frozen=True)
class Cuenta:
    id: str
    nombre: str
    edicion: str                  # "personal", "empresas" o "ambas"
    para_que: str
    donde_se_saca: str
    donde_se_pega: str            # archivo o pantalla donde se carga el valor
    que_se_prueba: str            # qué comando o acción confirma que anda
    vars: tuple[Var, ...] = ()
    requerida: bool = True        # False = opcional o de desarrollo
    sin_clave: str = ""           # qué hace Raphael si falta
    verificacion: str = ""        # id del verificador (ver adaptadores.py); "" = no se puede probar sola
    costo: str = ""
    notas: str = ""
    supuestos: tuple[str, ...] = field(default_factory=tuple)

    def obligatorias(self) -> tuple[Var, ...]:
        return tuple(v for v in self.vars if v.obligatoria)


RAPHAEL_ENV = "`raphael.env` (pantalla Configuración, `/config`)"

CUENTAS: tuple[Cuenta, ...] = (
    Cuenta(
        id="openrouter", nombre="OpenRouter (IA en la nube de Empresas)", edicion="empresas",
        para_que="La voz de la Secretaria con la dueña, el ruteo y los cocineros de Empresas. Principal DeepSeek V4 Flash, "
                 "con data_collection=deny.",
        donde_se_saca="openrouter.ai → Keys → Create key (empieza con sk-or-). El saldo ya lo cargaste.",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas probar openrouter` (consulta la clave y el saldo restante).",
        vars=(Var("OPENROUTER_API_KEY", ayuda="Empieza con sk-or-"),),
        sin_clave="Responde por reglas y lo avisa.", verificacion="openrouter",
        costo="Pago por uso, tope mensual en modelos.yaml (hoy USD 5, supuesto).",
        supuestos=("Endpoint GET /api/v1/auth/key y su respuesta: confirmar en openrouter.ai/docs.",),
    ),
    Cuenta(
        id="nvidia", nombre="NVIDIA build.nvidia.com (IA en la nube de Raphael personal)", edicion="personal",
        para_que="El resto de las brigadas de Raphael personal (todo lo que no es sensible), según tu decisión del 25 nov. "
                 "Sus términos no permiten clientes reales: no se usa en Empresas.",
        donde_se_saca="build.nvidia.com → iniciar sesión → cualquier modelo → Get API Key (empieza con nvapi-).",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas probar nvidia` (lista los modelos con la clave).",
        vars=(Var("NVIDIA_API_KEY", ayuda="Empieza con nvapi-"),),
        sin_clave="Las brigadas no sensibles caen a reglas y lo avisan.", verificacion="nvidia", costo="Gratis (con topes).",
        supuestos=("Endpoint GET /v1/models con Bearer en integrate.api.nvidia.com.",),
    ),
    Cuenta(
        id="local_llm", nombre="Modelo local (Ollama o LM Studio en tu PC)", edicion="personal",
        para_que="Todo lo sensible de Raphael personal: Seguridad, Investigación, Memoria y Operaciones. Si no está prendido, "
                 "Raphael avisa y NO manda lo sensible a la nube.",
        donde_se_saca="Instalá Ollama (ollama.com) o LM Studio (lmstudio.ai) y bajá un modelo. No lleva clave.",
        donde_se_pega=RAPHAEL_ENV + " (solo la dirección, que ya viene con el valor por defecto)",
        que_se_prueba="`cuentas probar local_llm` (con el programa prendido y un modelo bajado).",
        vars=(Var("LOCAL_LLM_URL", secreta=False, defecto="http://127.0.0.1:11434", obligatoria=False,
                  ayuda="Ollama: http://127.0.0.1:11434 · LM Studio: http://127.0.0.1:1234"),
              Var("LOCAL_LLM_KIND", secreta=False, defecto="ollama", obligatoria=False, ayuda="ollama o lmstudio")),
        sin_clave="Lo sensible se queda sin modelo y cae a reglas; nunca sube a la nube.", verificacion="local_llm",
        costo="Gratis (usa tu PC).",
        notas="Poner el modelo local en el escalón `local` de modelos.yaml es trabajo del harness y del orquestador.",
    ),
    Cuenta(
        id="meta_webhook", nombre="Meta · app y webhook", edicion="empresas",
        para_que="Que Meta le avise a Raphael de cada mensaje y que Raphael verifique que el aviso es de Meta.",
        donde_se_saca="developers.facebook.com → crear app (tipo Business) → Configuración → Básica (clave secreta). "
                      "El token de verificación lo inventás vos.",
        donde_se_pega=RAPHAEL_ENV + "; el mismo token de verificación va en la app de Meta.",
        que_se_prueba="`cuentas chequear --real` y que Meta acepte el webhook con la URL pública + /webhook/meta.",
        vars=(Var("META_VERIFY_TOKEN", ayuda="Texto largo inventado por vos"), Var("META_APP_SECRET"),
              Var("META_MODE", secreta=False, defecto="mock", obligatoria=False, ayuda="mock o real")),
        sin_clave="Con META_MODE=mock no manda nada a nadie.",
        costo="Gratis. Que cada clienta conecte las suyas exige ser Tech Provider (CONTEXT.md §6).",
    ),
    Cuenta(
        id="meta_whatsapp", nombre="WhatsApp Cloud API (número de prueba)", edicion="empresas",
        para_que="Recibir y responder mensajes de WhatsApp de la clienta.",
        donde_se_saca="Meta Business → Usuarios del sistema → generar token permanente; WhatsApp → Configuración de la API → "
                      "Phone number ID del número de prueba.",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas probar meta_whatsapp` (lee el número; no manda nada).",
        vars=(Var("META_WA_TOKEN"), Var("META_WA_PHONE_ID", secreta=False),
              Var("META_GRAPH_VERSION", secreta=False, defecto="v26.0", obligatoria=False)),
        sin_clave="No hay WhatsApp.", verificacion="meta_whatsapp",
        costo="Número de prueba gratis; conversaciones reales se cobran.",
        notas="Meta/WhatsApp está a medio configurar: completar la app y el número de prueba.",
        supuestos=("GET /{version}/{phone_id}?fields=display_phone_number con Bearer: confirmar en la doc de Meta.",),
    ),
    Cuenta(
        id="meta_instagram", nombre="Instagram (mensajes directos)", edicion="empresas",
        para_que="Recibir y responder DMs de la cuenta profesional.",
        donde_se_saca="developers.facebook.com → tu app → Instagram API with Instagram Login → generar token de la cuenta "
                      "profesional de prueba.",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas probar meta_instagram` (lee el usuario; no manda nada).",
        vars=(Var("META_IG_TOKEN"),
              Var("META_IG_HOST", secreta=False, defecto="graph.instagram.com", obligatoria=False,
                  ayuda="graph.instagram.com o graph.facebook.com")),
        requerida=False, sin_clave="No hay Instagram.", verificacion="meta_instagram", costo="Gratis.",
        supuestos=("GET /{version}/me?fields=username con Bearer: confirmar en la doc de Meta.",),
    ),
    Cuenta(
        id="mercado_pago", nombre="Mercado Pago (cobros de Empresas)", edicion="empresas",
        para_que="Generar links de cobro y enterarse de los pagos. Adaptador real y simulado; cobrar siempre pide aprobación "
                 "de la dueña.",
        donde_se_saca="mercadopago.com.ar/developers → Tus integraciones → crear aplicación → Credenciales (Access Token de "
                      "prueba primero, después el de producción).",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas probar mercado_pago` (lee el usuario de la cuenta; no cobra nada).",
        vars=(Var("MP_ACCESS_TOKEN"), Var("MP_WEBHOOK_SECRET", obligatoria=False, ayuda="Para firmar los avisos de pago"),
              Var("MP_MODE", secreta=False, defecto="mock", obligatoria=False, ayuda="mock o real")),
        sin_clave="Con MP_MODE=mock no cobra nada; con transferencia sigue andando.", verificacion="mercado_pago",
        costo="Comisión por cobro (ver tarifas vigentes en Mercado Pago).",
        supuestos=("GET https://api.mercadopago.com/users/me con Bearer: confirmar en la doc de Mercado Pago.",),
        notas="El conector de cobros vive en la brigada Empresas (pieza 15); esta pieza solo guarda y prueba las credenciales.",
    ),
    Cuenta(
        id="transferencia", nombre="Transferencia bancaria (datos de la cuenta de la dueña)", edicion="empresas",
        para_que="Mostrarle al cliente a dónde transferir. La dueña confirma a mano cuando entra la plata.",
        donde_se_saca="Los datos de la cuenta de la dueña (los pasa ella).",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas chequear` (formato de CBU/CVU de 22 dígitos).",
        vars=(Var("TRANSFER_TITULAR", secreta=False), Var("TRANSFER_CBU_CVU", secreta=False, ayuda="22 dígitos"),
              Var("TRANSFER_ALIAS", secreta=False, obligatoria=False), Var("TRANSFER_BANCO", secreta=False, obligatoria=False)),
        sin_clave="No ofrece transferencia como medio de pago.", verificacion="formato_cbu",
        notas="Son datos personales de la dueña, no claves: igual quedan solo en el archivo local.",
    ),
    Cuenta(
        id="tailscale", nombre="Tailscale Funnel (túnel hasta el VPS)", edicion="ambas",
        para_que="Dirección pública https para el webhook de Meta y la app del celular, con el servidor corriendo en tu PC.",
        donde_se_saca="Ya está andando: `tailscale funnel status` muestra la URL (https://<pc>.<tailnet>.ts.net).",
        donde_se_pega=RAPHAEL_ENV + " (RAPHAEL_PUBLIC_URL, sin barra al final)",
        que_se_prueba="`cuentas probar tailscale` (pide /api/v1/health por la URL pública).",
        vars=(Var("RAPHAEL_PUBLIC_URL", secreta=False),),
        sin_clave="Solo se ve desde la propia PC.", verificacion="url_publica", costo="Gratis en el plan personal.",
        notas="Mientras no haya VPS (decisión del 24 nov). Con el túnel, /config queda visible desde internet y pide la clave.",
    ),
    Cuenta(
        id="duckdns", nombre="DuckDNS (dominio gratis para el VPS)", edicion="empresas",
        para_que="Nombre fijo para el VPS cuando haya uno. No hace falta mientras corra con Tailscale.",
        donde_se_saca="duckdns.org → iniciar sesión → crear subdominio; el token está arriba en la página.",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas chequear` (formato). No se prueba en vivo: actualizar el dominio "
                                                  "cambia la IP registrada.",
        vars=(Var("DUCKDNS_TOKEN"), Var("DUCKDNS_DOMAIN", secreta=False, ayuda="Solo el subdominio, sin .duckdns.org")),
        requerida=False, sin_clave="Se usa el túnel.", costo="Gratis.",
    ),
    Cuenta(
        id="hetzner", nombre="Hetzner (VPS)", edicion="empresas",
        para_que="El servidor en la nube de Empresas, cuando haya una clienta que pague (todavía no hay medio de pago: "
                 "decisión del 24 nov).",
        donde_se_saca="console.hetzner.cloud → proyecto → Seguridad → Tokens de API (lectura y escritura). No abrir la cuenta "
                      "hasta que haya con qué pagar.",
        donde_se_pega=RAPHAEL_ENV, que_se_prueba="`cuentas probar hetzner` (lista servidores; solo lectura).",
        vars=(Var("HCLOUD_TOKEN"),), requerida=False, sin_clave="El servidor sigue en tu PC.", verificacion="hetzner",
        costo="Referencia CX33; precio a confirmar en hetzner.com/cloud.",
        supuestos=("GET https://api.hetzner.cloud/v1/servers con Bearer: confirmar en docs.hetzner.cloud.",),
    ),
    Cuenta(
        id="tienda", nombre="Tienda de la clienta (Tiendanube, Shopify o WooCommerce)", edicion="empresas",
        para_que="Leer el catálogo de la clienta. Solo si usa una de esas tiendas.",
        donde_se_saca="El panel de la tienda de la clienta (ella autoriza).",
        donde_se_pega=RAPHAEL_ENV + " (piden reiniciar)", que_se_prueba="`cuentas chequear`.",
        vars=(Var("TIENDANUBE_TOKEN", obligatoria=False), Var("SHOPIFY_TOKEN", obligatoria=False),
              Var("WOO_KEY", obligatoria=False), Var("WOO_SECRET", obligatoria=False)),
        requerida=False, sin_clave="Sin catálogo conectado (puede usar feed JSON/CSV).",
    ),
    Cuenta(
        id="broker", nombre="Broker para Trading (sin elegir)", edicion="personal",
        para_que="Operar USD/JPY. Todavía no hay broker: el hilo de Trading propone 2 o 3. Toda ejecución, demo o real, "
                 "pide tu aprobación.",
        donde_se_saca="Pendiente: lo define Damián con la propuesta del hilo de Trading. No se abre ninguna cuenta.",
        donde_se_pega="Pendiente (el hilo de Trading deja su plantilla).", que_se_prueba="Trading corre contra un simulado.",
        vars=(), requerida=False, sin_clave="Trading usa el adaptador simulado.",
    ),
)

POR_ID = {c.id: c for c in CUENTAS}


def cuenta(id_: str) -> Cuenta:
    try:
        return POR_ID[id_]
    except KeyError:
        raise KeyError(f"cuenta desconocida: {id_} (hay: {', '.join(POR_ID)})") from None


def todas_las_vars() -> list[Var]:
    vistas: dict[str, Var] = {}
    for c in CUENTAS:
        for v in c.vars:
            vistas.setdefault(v.nombre, v)
    return list(vistas.values())
