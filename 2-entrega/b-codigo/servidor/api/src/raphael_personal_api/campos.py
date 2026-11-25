"""Lo que se carga desde la pantalla de Configuración de Raphael personal, y el chequeo de arranque.

Las claves se guardan solo en `raphael.env` local (permisos de usuario, fuera de git) y nunca se devuelven completas.
Cada brigada que necesite una clave suya (broker, Meta, etc.) la declara en su `.env.plantilla`; para que aparezca acá
hay que sumarla a `FIELDS` (o al archivo a mano: el servidor la lee igual del entorno).
"""

from __future__ import annotations

from collections.abc import Mapping

from raphael_empresas_api.configuracion import Field
from raphael_empresas_api.entorno import Item

from . import cerebro

FIELDS: tuple[Field, ...] = (
    Field("NVIDIA_API_KEY", "ia", "Clave de NVIDIA (la nube)", help="build.nvidia.com → Get API Key (empieza con nvapi-)"),
    Field("OPENROUTER_API_KEY", "ia", "Clave de OpenRouter (opcional)", help="Solo si activás el escalón pago (tope en USD)"),
    Field("RAPHAEL_TOPE_PAGO_USD", "ia", "Tope de gasto en IA paga (USD por mes)", secret=False,
          help="0 o vacío = OpenRouter no se usa. Además el rol tiene que incluir el escalón pago"),
    Field("LOCAL_LLM_URL", "local", "Modelo local: dirección", secret=False, help="Ollama http://127.0.0.1:11434 · LM Studio :1234"),
    Field("LOCAL_LLM_KIND", "local", "Modelo local: programa", secret=False, help="ollama o lmstudio"),
    Field("OLLAMA_URL", "local", "Ollama: dirección", secret=False, help="Por defecto http://127.0.0.1:11434/v1 (esta PC)"),
    Field("OLLAMA_MODEL", "local", "Ollama: modelo", secret=False, help="El que muestra `ollama list`, ej. llama3.1:8b"),
    Field("LMSTUDIO_URL", "local", "LM Studio: dirección", secret=False, help="Por defecto http://127.0.0.1:1234/v1 (esta PC)"),
    Field("LMSTUDIO_MODEL", "local", "LM Studio: modelo", secret=False, help="Si hay un modelo cargado, usa el cargado"),
    *(Field(f"RAPHAEL_ROL_{r.upper()}", "roles", f"Rol {r}", secret=False,
            help="Escalones en orden: local, gratis, pago. Ej. local,gratis") for r in cerebro.ROLES),
    Field("RAPHAEL_PRIVADAS", "roles", "Brigadas solo-local (extra)", secret=False,
          help="Se suman a Seguridad, Investigación, Memoria y Operaciones. Ej. trading,legales"),
    Field("RAPHAEL_PUBLIC_URL", "red", "Dirección para el celular", secret=False, help="La de Tailscale (https://…ts.net)"),
    Field("RAPHAEL_VOZ_MODO", "voz", "Voz hablada", secret=False, help="auto, local, mock u off", live=False),
    Field("DUCKDNS_TOKEN", "cuentas", "DuckDNS: token (opcional)", help="duckdns.org, arriba en la página", live=False),
    Field("DUCKDNS_DOMAIN", "cuentas", "DuckDNS: subdominio", secret=False, help="Solo el subdominio, sin .duckdns.org", live=False),
    Field("HCLOUD_TOKEN", "cuentas", "Hetzner: token (opcional)", help="Solo cuando haya VPS", live=False),
)
BY_NAME = {f.name: f for f in FIELDS}


def extra_check(name: str, value: str) -> str:
    if name == "RAPHAEL_PUBLIC_URL" and not value.startswith("https://"):
        raise ValueError("la dirección pública empieza con https://")
    if name == "RAPHAEL_VOZ_MODO" and value.lower() not in ("auto", "local", "mock", "off"):
        raise ValueError("el modo de voz es auto, local, mock u off")
    return cerebro.check_field(name, value)


def check(env: Mapping[str, str], *, app_key_set: bool, probe: list[dict], pending: list[str], errors: Mapping[str, str],
          mounted: list[str], orchestrator_ok: bool) -> list[Item]:
    items = [
        Item("App", "ok" if app_key_set else "aviso",
             "clave de la app puesta" if app_key_set else "todavía no hay clave de la app", "`arrancar-personal.bat clave`"),
        Item("Orquestador", "ok" if orchestrator_ok else "falta",
             "montado (modo maestro)" if orchestrator_ok else "no se pudo montar el orquestador", "mirá el log del servidor"),
        Item("IA nube", "ok" if env.get("NVIDIA_API_KEY") else "aviso",
             "NVIDIA cargada" if env.get("NVIDIA_API_KEY") else "sin clave de NVIDIA: lo que no es privado cae a reglas",
             "build.nvidia.com → clave, y pegala en Configuración"),
    ]
    ready = cerebro.local_ready(probe)
    items.append(Item("IA local", "ok" if ready else "aviso",
                      "modelo local listo" if ready else "no hay modelo local prendido: las brigadas privadas van por reglas y "
                      "NO se manda nada sensible a la nube", "abrí Ollama (`ollama serve`) o LM Studio y cargá un modelo"))
    items.append(Item("Brigadas", "ok" if mounted else "info",
                      f"montadas: {', '.join(mounted)}" if mounted else "todavía no hay brigadas instaladas"))
    if pending:
        items.append(Item("Brigadas", "info", f"todavía no instaladas: {', '.join(pending)}"))
    items += [Item("Brigadas", "aviso", f"{b} no se pudo montar: {why[:160]}")
              for b, why in errors.items() if b != "_orchestrator"]
    items.append(Item("Celular", "ok" if env.get("RAPHAEL_PUBLIC_URL") else "info",
                      f"acceso remoto en {env['RAPHAEL_PUBLIC_URL']}" if env.get("RAPHAEL_PUBLIC_URL")
                      else "sin dirección para el celular (Tailscale): ver 2-entrega/c-despliegue/personal/LEEME.md"))
    return items
