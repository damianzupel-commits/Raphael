"""Configuración de Raphael personal, sin pantalla: lo que lee y escribe la sección «Configuración» del panel.

Tres archivos, todos locales (carpeta de datos del panel o de Raphael personal), nunca en git:
  raphael.env          las variables y claves (se escribe atómico, conserva comentarios, permisos de usuario)
  modelos.usuario.yaml tus cambios sobre modelos.yaml: proveedores propios, rol→escalones, rol.id→escalones, privadas
  panel-config.json    apariencia, perfiles guardados e historial de cambios (para deshacer)

Reglas que no se tocan desde acá: lo que sale hacia afuera (publicar, pagar, mandar, borrar) SIEMPRE pide aprobación, el
pentest activo solo corre en la PC, Trading no ejecuta sin aprobación. Una brigada privada solo acepta proveedores que
corren en esta PC; sacarla de la lista exige confirmar (`confirmar_nube=True`).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from raphael_core.models.config import DEFAULT_PATH, LOOPBACK, ROLES, ModelsConfig, models_from

#: tipos de campo: texto, secreto (se oculta con el ojito), opción, sí/no, carpeta
SECCIONES = [
    ("ia", "Cerebro e IA", "roles, escalones, proveedores y modelo de cada brigada y cocinero"),
    ("claves", "Claves y cuentas", "NVIDIA, OpenRouter, Meta, Mercado Pago y las demás"),
    ("brigadas", "Brigadas", "prender, apagar y toda su configuración"),
    ("autonomia", "Autonomía y aprobaciones", "cuánto hace solo y cuánto te consulta"),
    ("acceso", "Acceso y celular", "dirección remota, Tailscale y modelo local"),
    ("voz", "Voz", "escuchar y hablar"),
    ("carpetas", "Carpetas y datos", "vault, repos, zonas permitidas"),
    ("apariencia", "Apariencia", "tema, color, letra, idioma y tono"),
    ("avanzado", "Avanzado", "todas las variables en crudo, historial, perfiles y exportar"),
]
NIVELES_AUTONOMIA = ("cauteloso", "equilibrado", "confiado")
SIEMPRE_PIDE = ("publicar", "pagar", "mandar mensajes", "borrar", "operar en trading", "pentest activo (solo en tu PC)")


@dataclass(frozen=True)
class Campo:
    nombre: str
    seccion: str
    etiqueta: str
    tipo: str = "texto"  # texto | secreto | opcion | bool | carpeta
    opciones: tuple[str, ...] = ()
    ayuda: str = ""
    reinicia: bool = False  # True = hace falta reiniciar para que tome efecto
    solo_local: bool = False  # dirección que tiene que ser de esta PC


def _c(nombre: str, seccion: str, etiqueta: str, tipo: str = "texto", ayuda: str = "", **kw) -> Campo:
    return Campo(nombre, seccion, etiqueta, tipo, ayuda=ayuda, **kw)


CAMPOS: tuple[Campo, ...] = (
    # claves y cuentas (los nombres son los de las plantillas *.env.plantilla de cada pieza)
    _c("NVIDIA_API_KEY", "claves", "NVIDIA (IA en la nube de Personal)", "secreto", "build.nvidia.com → Get API Key (nvapi-…)"),
    _c("OPENROUTER_API_KEY", "claves", "OpenRouter (IA de Empresas / escalón pago)", "secreto", "openrouter.ai → Keys (sk-or-…)"),
    _c("BRAVE_SEARCH_API_KEY", "claves", "Brave Search (Investigación)", "secreto", "brave.com/search/api, plan gratis"),
    _c("SEARXNG_URL", "acceso", "SearXNG (alternativa a Brave)", "texto", "Dirección de tu SearXNG"),
    _c(
        "VIRUSTOTAL_API_KEY",
        "claves",
        "VirusTotal (Antimalware, opcional)",
        "secreto",
        "Solo manda el hash de lo que ya dio positivo",
    ),
    _c("SHODAN_KEY", "claves", "Shodan (Geolocalización)", "secreto"),
    _c("AISSTREAM_KEY", "claves", "AISStream (barcos)", "secreto"),
    _c("FIRMS_MAP_KEY", "claves", "NASA FIRMS (incendios)", "secreto"),
    _c("WINDY_WEBCAMS_KEY", "claves", "Windy (cámaras)", "secreto"),
    _c("OPENWEATHER_KEY", "claves", "OpenWeather (clima)", "secreto"),
    _c("OPENCELLID_KEY", "claves", "OpenCellID (antenas)", "secreto"),
    _c("MP_ACCESS_TOKEN", "claves", "Mercado Pago: token", "secreto", "Primero el de prueba", reinicia=True),
    _c("MP_WEBHOOK_SECRET", "claves", "Mercado Pago: clave de avisos", "secreto", reinicia=True),
    _c("META_APP_SECRET", "claves", "Meta: clave secreta de la app", "secreto"),
    _c("META_VERIFY_TOKEN", "claves", "Meta: verify token", "secreto", "Lo inventás vos"),
    _c("META_WA_TOKEN", "claves", "WhatsApp: token", "secreto"),
    _c("META_IG_TOKEN", "claves", "Instagram: token", "secreto"),
    _c("IG_ACCESS_TOKEN", "claves", "Instagram publicar: token", "secreto"),
    _c("META_ADS_ACCESS_TOKEN", "claves", "Meta Ads: token", "secreto", "Activar anuncios gasta plata: siempre pide aprobación"),
    _c("HCLOUD_TOKEN", "claves", "Hetzner (solo cuando haya VPS)", "secreto", reinicia=True),
    _c("DUCKDNS_TOKEN", "claves", "DuckDNS", "secreto", reinicia=True),
    # acceso y celular
    _c("RAPHAEL_PUBLIC_URL", "acceso", "Dirección para el celular", ayuda="La de Tailscale (https://….ts.net)"),
    _c("LOCAL_LLM_KIND", "acceso", "Modelo local: programa", "opcion", opciones=("ollama", "lmstudio")),
    _c(
        "LOCAL_LLM_URL", "acceso", "Modelo local: dirección", ayuda="Solo de esta PC, ej. http://127.0.0.1:11434", solo_local=True
    ),
    _c("OLLAMA_MODEL", "acceso", "Ollama: modelo", ayuda="El de `ollama list`"),
    _c("LMSTUDIO_MODEL", "acceso", "LM Studio: modelo", ayuda="El que tenés cargado"),
    _c("MEMORIA_EMBEDDINGS_BASE_URL", "acceso", "Embeddings de Memoria: dirección", solo_local=True),
    _c("MEMORIA_EMBEDDINGS_MODEL", "acceso", "Embeddings de Memoria: modelo", ayuda="nomic-embed-text"),
    # voz
    _c("RAPHAEL_VOZ_MODO", "voz", "Modo de voz", "opcion", opciones=("auto", "local", "mock", "off"), reinicia=True),
    _c("VOICE_PIPER_VOICE", "voz", "Voz de Piper (archivo .onnx)", "carpeta", reinicia=True),
    _c("VOICE_PYTHON", "voz", "Python de la voz (si hace falta)", "carpeta", reinicia=True),
    # carpetas y datos
    _c("RAPHAEL_VAULT_DIR", "carpetas", "Vault de Obsidian", "carpeta", "Vacío = las notas quedan en el almacén"),
    _c("MEMORIA_VAULT_PATH", "carpetas", "Vault de Memoria", "carpeta"),
    _c("RAPHAEL_REPAIR_ROOT", "carpetas", "Repo de Raphael (Autorreparación)", "carpeta"),
    _c("SEGURIDAD_REPOS", "carpetas", "Repos que Seguridad puede auditar", "texto", "Rutas separadas con ;"),
    _c("OPERACIONES_CARPETA_SEGURA", "carpetas", "Operaciones: carpeta segura", "carpeta"),
    _c("OPERACIONES_FS_RAICES", "carpetas", "Operaciones: carpetas permitidas", "texto", "Rutas separadas con ;"),
    _c("OPERACIONES_FS_SUPERVISADO", "carpetas", "Operaciones: carpetas supervisadas", "texto", "Rutas separadas con ;"),
    _c("OPERACIONES_FS_PROHIBIDAS", "carpetas", "Operaciones: carpetas prohibidas", "texto", "Rutas separadas con ;"),
    # autonomía (el panel guarda el nivel; lo que sale hacia afuera sigue pidiendo aprobación pase lo que pase)
    _c("RAPHAEL_AUTONOMIA", "autonomia", "Nivel de autonomía", "opcion", opciones=NIVELES_AUTONOMIA),
)
POR_NOMBRE = {c.nombre: c for c in CAMPOS}


@dataclass(frozen=True)
class Servicio:
    nombre: str
    variable: str
    prefijos: tuple[str, ...] = ()  # cómo empieza la clave de ese servicio (para reconocerla sola)
    ayuda: str = ""
    reinicia: bool = False


#: los servicios que Raphael sabe usar. El orden importa para reconocer: el prefijo más específico va primero.
SERVICIOS: tuple[Servicio, ...] = (
    Servicio("NVIDIA", "NVIDIA_API_KEY", ("nvapi-",), "build.nvidia.com → Get API Key"),
    Servicio("OpenRouter", "OPENROUTER_API_KEY", ("sk-or-",), "openrouter.ai → Keys"),
    Servicio("Brave Search", "BRAVE_SEARCH_API_KEY", ("BSA",), "brave.com/search/api"),
    Servicio("Groq", "GROQ_API_KEY", ("gsk_",), "console.groq.com"),
    Servicio("Hugging Face", "HF_TOKEN", ("hf_",), "huggingface.co/settings/tokens"),
    Servicio("Google (Gemini)", "GEMINI_API_KEY", ("AIza",), "aistudio.google.com"),
    Servicio("Anthropic", "ANTHROPIC_API_KEY", ("sk-ant-",), "console.anthropic.com"),
    Servicio("OpenAI", "OPENAI_API_KEY", ("sk-proj-", "sk-"), "platform.openai.com"),
    Servicio("GitHub", "GITHUB_TOKEN", ("ghp_", "github_pat_", "gho_"), ""),
    Servicio("Mercado Pago", "MP_ACCESS_TOKEN", ("APP_USR-", "TEST-"), "Primero el de prueba", True),
    Servicio("Shodan", "SHODAN_KEY"),
    Servicio("VirusTotal", "VIRUSTOTAL_API_KEY", (), "Solo manda el hash de lo que ya dio positivo"),
    Servicio("AISStream (barcos)", "AISSTREAM_KEY"),
    Servicio("NASA FIRMS (incendios)", "FIRMS_MAP_KEY"),
    Servicio("Windy (cámaras)", "WINDY_WEBCAMS_KEY"),
    Servicio("OpenWeather (clima)", "OPENWEATHER_KEY"),
    Servicio("OpenCellID (antenas)", "OPENCELLID_KEY"),
    Servicio("Mercado Pago: clave de avisos", "MP_WEBHOOK_SECRET", reinicia=True),
    Servicio("Meta: clave secreta de la app", "META_APP_SECRET"),
    Servicio("Meta: verify token", "META_VERIFY_TOKEN", ayuda="Lo inventás vos"),
    Servicio("WhatsApp", "META_WA_TOKEN"),
    Servicio("Instagram", "META_IG_TOKEN"),
    Servicio("Instagram (publicar)", "IG_ACCESS_TOKEN"),
    Servicio("Meta Ads", "META_ADS_ACCESS_TOKEN", ayuda="Activar anuncios gasta plata: siempre pide aprobación"),
    Servicio("Hetzner", "HCLOUD_TOKEN", reinicia=True),
    Servicio("DuckDNS", "DUCKDNS_TOKEN", reinicia=True),
)
SERVICIO_POR_VARIABLE = {sv.variable: sv for sv in SERVICIOS}


def detectar_servicio(clave: str) -> Servicio | None:
    """Reconoce el servicio por cómo empieza la clave (nvapi- es NVIDIA, sk-or- es OpenRouter…). None = no se sabe."""
    c = clave.strip()
    mejor: tuple[int, Servicio] | None = None
    for sv in SERVICIOS:
        for p in sv.prefijos:
            if c.startswith(p) and (mejor is None or len(p) > mejor[0]):
                mejor = (len(p), sv)
    return mejor[1] if mejor else None


def variable_para(nombre: str) -> str:
    """Nombre escrito a mano → variable. «Mi Servicio» → MI_SERVICIO_API_KEY (si ya es un nombre de variable, se respeta)."""
    n = nombre.strip()
    for sv in SERVICIOS:
        if n.lower() == sv.nombre.lower():
            return sv.variable
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", n) and len(n) >= 3:
        return n
    base = re.sub(r"[^A-Za-z0-9]+", "_", n).strip("_").upper()
    if not base or not base[0].isalpha():
        raise ValueError("el nombre del servicio: letras y números, empezando con una letra")
    return base if base.endswith(("_KEY", "_TOKEN", "_SECRET")) else base + "_API_KEY"


_NOMBRE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LINEA = re.compile(r"^[\x21-\x7e]+$")
APARIENCIA_BASE = {
    "tema": "oscuro",
    "acento": "#35e0ff",
    "letra": 10,
    "densidad": "normal",
    "idioma": "es",
    "nombre": "Raphael",
    "tono": "cercano",
}
OPCIONES_APARIENCIA = {
    "tema": ("oscuro", "claro", "automatico"),
    "densidad": ("compacta", "normal", "comoda"),
    "idioma": ("es", "en"),
    "tono": ("formal", "cercano", "breve"),
}


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for ln in text.splitlines():
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", ln)
        if m and not ln.lstrip().startswith("#"):
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def _escribir_atomico(path: Path, text: str, *, privado: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".raphael-cfg-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        if privado:
            with contextlib.suppress(OSError):
                os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def es_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in LOOPBACK


@dataclass
class Configuracion:
    """Lee y escribe la configuración. `modelos_base`: el yaml de modelos sobre el que se aplican tus cambios."""

    env_file: Path
    usuario_file: Path
    panel_file: Path
    modelos_base: Path = DEFAULT_PATH
    environ: dict[str, str] = field(default_factory=lambda: os.environ)  # el entorno del proceso (se aplica en caliente)

    # --- variables y claves ---------------------------------------------------------------------------------------
    def env(self) -> dict[str, str]:
        return parse_env(self.env_file.read_text(encoding="utf-8-sig", errors="replace")) if self.env_file.is_file() else {}

    def validar(self, nombre: str, valor: str) -> str:
        """Valor limpio o ValueError (en español, sin repetir el valor). Acepta cualquier variable con nombre válido:
        el modo avanzado es libre; los campos conocidos suman sus propias reglas."""
        if not _NOMBRE.match(nombre):
            raise ValueError(f"«{nombre}» no es un nombre de variable válido")
        v = valor.strip()
        if not v:
            raise ValueError(f"{nombre} está vacío (para sacarla usá «quitar»)")
        if len(v) > 800 or "\n" in v or "\r" in v:
            raise ValueError(f"{nombre} tiene que ser una sola línea corta")
        c = POR_NOMBRE.get(nombre)
        if c is not None:
            if c.tipo == "secreto" and not _LINEA.match(v):
                raise ValueError(f"{nombre} tiene espacios o caracteres raros: copiala de nuevo, entera")
            if c.tipo == "opcion" and v.lower() not in c.opciones:
                raise ValueError(f"{nombre} es una de: {', '.join(c.opciones)}")
            if c.solo_local and not es_local(v):
                raise ValueError(f"{nombre} corre en esta PC: http://127.0.0.1:<puerto>")
            if c.tipo == "opcion":
                v = v.lower()
        if c is None and self._es_secreta(nombre) and not _LINEA.match(v):
            raise ValueError(f"{nombre} tiene espacios o caracteres raros: copiala de nuevo, entera")
        if nombre == "RAPHAEL_PUBLIC_URL" and not v.startswith("https://"):
            raise ValueError("la dirección pública empieza con https://")
        if "\x00" in v or "#" in v and c is not None and c.tipo == "secreto":
            raise ValueError(f"{nombre} tiene caracteres que no sirven en una clave")
        return v

    def aplicar(
        self, poner: Mapping[str, str] | None = None, quitar: list[str] | None = None, *, quien: str = "panel"
    ) -> list[str]:
        """Valida todo primero (si algo está mal no se cambia nada), guarda en raphael.env y en el entorno del
        proceso, y anota el cambio en el historial. Devuelve los nombres que piden reiniciar."""
        cambios: dict[str, str | None] = {}
        for n, v in (poner or {}).items():
            cambios[n] = self.validar(n, v)
        for n in quitar or []:
            if not _NOMBRE.match(n):
                raise ValueError(f"«{n}» no es un nombre de variable válido")
            cambios[n] = None
        if not cambios:
            return []
        antes = self.env()
        self._escribir_env(cambios)
        for n, v in cambios.items():
            if v is None:
                self.environ.pop(n, None)
            else:
                self.environ[n] = v
        self._historia({"que": "env", "quien": quien, "antes": {n: antes.get(n) for n in cambios}, "despues": dict(cambios)})
        return sorted(n for n in cambios if n in POR_NOMBRE and POR_NOMBRE[n].reinicia)

    def _escribir_env(self, cambios: Mapping[str, str | None]) -> None:
        lines = self.env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines() if self.env_file.is_file() else []
        visto: set[str] = set()
        out: list[str] = []
        for ln in lines:
            m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", ln)
            if m and m.group(1) in cambios and not ln.lstrip().startswith("#"):
                visto.add(m.group(1))
                if cambios[m.group(1)] is not None:
                    out.append(f"{m.group(1)}={cambios[m.group(1)]}")
            else:
                out.append(ln)
        out += [f"{k}={v}" for k, v in cambios.items() if v is not None and k not in visto]
        _escribir_atomico(self.env_file, "\n".join(out) + "\n")

    def claves(self) -> list[dict]:
        """Las claves ya cargadas (cualquier variable secreta de raphael.env), con el nombre del servicio."""
        out = []
        for n, v in sorted(self.env().items()):
            if not self._es_secreta(n):
                continue
            sv = SERVICIO_POR_VARIABLE.get(n)
            out.append({"variable": n, "servicio": sv.nombre if sv else n, "valor": v, "reinicia": bool(sv and sv.reinicia)})
        return out

    def agregar_clave(self, clave: str, servicio: str = "", *, quien: str = "panel") -> tuple[str, list[str]]:
        """Guarda una clave. Si no decís el servicio, se reconoce por el formato; si no se reconoce, hay que elegirlo o
        escribirlo. Devuelve (variable, variables que piden reiniciar)."""
        clave = clave.strip()
        if not clave:
            raise ValueError("pegá la clave")
        if servicio.strip():
            variable = variable_para(servicio)
        else:
            sv = detectar_servicio(clave)
            if sv is None:
                raise ValueError("no reconozco esta clave: elegí el servicio o escribí su nombre")
            variable = sv.variable
        return variable, self.aplicar({variable: clave}, quien=quien)

    def vista(self) -> list[dict]:
        """Lo que se muestra: los secretos se ven con el ojito en la pantalla (decisión de Damián), pero nunca van a
        la auditoría ni al historial exportado."""
        env = self.env()
        return [
            {
                "nombre": c.nombre,
                "seccion": c.seccion,
                "etiqueta": c.etiqueta,
                "tipo": c.tipo,
                "ayuda": c.ayuda,
                "opciones": c.opciones,
                "reinicia": c.reinicia,
                "valor": env.get(c.nombre, ""),
            }
            for c in CAMPOS
        ]

    # --- modelos ---------------------------------------------------------------------------------------------------
    def _usuario(self) -> dict:
        if self.usuario_file.is_file():
            return yaml.safe_load(self.usuario_file.read_text(encoding="utf-8")) or {}
        return {}

    def _base(self) -> dict:
        return yaml.safe_load(Path(self.modelos_base).read_text(encoding="utf-8")) or {}

    def modelos_datos(self, usuario: dict | None = None) -> dict:
        """El yaml efectivo: la base con tus cambios encima (proveedores y overrides se suman o pisan por nombre;
        roles y privadas se reemplazan si las tocaste)."""
        base, u = self._base(), (self._usuario() if usuario is None else usuario)
        out = json.loads(json.dumps(base))
        for k in ("providers", "tiers", "roles", "overrides"):
            out.setdefault(k, {}).update(u.get(k, {}))
        for k in ("private", "paid_cap_usd_month"):
            if k in u:
                out[k] = u[k]
        return out

    def modelos(self) -> ModelsConfig:
        return models_from(self.modelos_datos())

    def _guardar_modelos(self, usuario: dict, *, quien: str, que: str) -> ModelsConfig:
        cfg = models_from(self.modelos_datos(usuario))  # valida referencias antes de guardar nada
        self._revisar_privadas(cfg)
        antes = self._usuario()
        _escribir_atomico(self.usuario_file, yaml.safe_dump(usuario, allow_unicode=True, sort_keys=True), privado=False)
        self._historia({"que": "modelos", "quien": quien, "detalle": que, "antes_usuario": antes, "despues_usuario": usuario})
        return cfg

    @staticmethod
    def _revisar_privadas(cfg: ModelsConfig) -> None:
        """Una brigada privada solo puede quedar con proveedores de esta PC: se avisa antes de guardar algo que la
        dejaría sin ninguno (en ese caso sigue por reglas, nunca por la nube: lo garantiza la pasarela)."""
        for tier, nombres in cfg.tiers.items():
            if tier == "local":
                for n in nombres:
                    if not cfg.providers[n].is_local and cfg.providers[n].base_url:
                        raise ValueError(f"el proveedor «{n}» está en el escalón local pero no corre en esta PC")

    def agregar_proveedor(
        self,
        nombre: str,
        base_url: str,
        modelo: str,
        api_key_env: str = "",
        *,
        rpm: int | None = None,
        usd_in: float = 0.0,
        usd_out: float = 0.0,
        escalon: str = "",
    ) -> ModelsConfig:
        """Cualquier API compatible con OpenAI. La clave no se guarda acá: solo el nombre de su variable."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", nombre):
            raise ValueError("el nombre del proveedor: minúsculas, números, guion; sin espacios")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("la dirección empieza con http:// o https://")
        if base_url.startswith("http://") and not es_local(base_url):
            raise ValueError("una API remota tiene que ser https://")
        if api_key_env and not _NOMBRE.match(api_key_env):
            raise ValueError("el nombre de la variable de la clave no es válido")
        if not modelo.strip():
            raise ValueError("falta el modelo")
        u = self._usuario()
        spec = {
            "base_url": base_url.strip(),
            "model": modelo.strip(),
            "api_key_env": api_key_env,
            "usd_per_million_in": usd_in,
            "usd_per_million_out": usd_out,
        }
        if rpm:
            spec["rpm"] = rpm
        u.setdefault("providers", {})[nombre] = spec
        if escalon:
            tiers = {**self.modelos_datos().get("tiers", {}), **u.get("tiers", {})}
            lista = list(tiers.get(escalon, []))
            if escalon == "local" and not es_local(base_url):
                raise ValueError("el escalón local es solo para modelos que corren en esta PC")
            if nombre not in lista:
                lista.append(nombre)
            u.setdefault("tiers", {})[escalon] = lista
        return self._guardar_modelos(u, quien="panel", que=f"proveedor {nombre}")

    def quitar_proveedor(self, nombre: str) -> ModelsConfig:
        u = self._usuario()
        if nombre not in u.get("providers", {}):
            raise ValueError("solo se quitan los proveedores que agregaste vos")
        u["providers"].pop(nombre)
        for t, lista in list(u.get("tiers", {}).items()):
            u["tiers"][t] = [p for p in lista if p != nombre]
        for t, lista in self.modelos_datos().get("tiers", {}).items():
            if nombre in lista and t not in u.get("tiers", {}):
                u.setdefault("tiers", {})[t] = [p for p in lista if p != nombre]
        return self._guardar_modelos(u, quien="panel", que=f"quitar proveedor {nombre}")

    def poner_rol(self, rol: str, escalones: list[str]) -> ModelsConfig:
        if rol not in ROLES:
            raise ValueError(f"rol desconocido: {rol}")
        u = self._usuario()
        u.setdefault("roles", {})[rol] = list(escalones)
        return self._guardar_modelos(u, quien="panel", que=f"rol {rol} → {','.join(escalones) or '—'}")

    def poner_destino(self, rol: str, destino: str, proveedores: list[str]) -> ModelsConfig:
        """Modelo y API de UNA brigada o cocinero (`rol.id`): arma un escalón propio con esos proveedores en orden.
        Si el destino es privado, solo se aceptan proveedores que corren en esta PC."""
        if rol not in ROLES or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", destino):
            raise ValueError("rol o id inválido")
        cfg = self.modelos()
        for p in proveedores:
            if p not in cfg.providers:
                raise ValueError(f"no existe el proveedor «{p}»")
            if destino in cfg.private and not cfg.providers[p].is_local:
                raise ValueError(f"«{destino}» es solo-local: «{p}» no corre en esta PC")
        u = self._usuario()
        clave = f"{rol}.{destino}"
        if proveedores:
            tier = f"propio-{rol}-{destino}".replace(".", "-")
            u.setdefault("tiers", {})[tier] = list(proveedores)
            u.setdefault("overrides", {})[clave] = [tier]
        else:  # volver a lo de la base
            u.get("overrides", {}).pop(clave, None)
            u.get("tiers", {}).pop(f"propio-{rol}-{destino}".replace(".", "-"), None)
            if clave in self._base().get("overrides", {}):
                u.setdefault("overrides", {})[clave] = []
        return self._guardar_modelos(u, quien="panel", que=f"{clave} → {','.join(proveedores) or 'base'}")

    def privadas(self) -> list[str]:
        return list(self.modelos().private)

    def poner_privadas(self, ids: list[str], *, confirmar_nube: bool = False) -> ModelsConfig:
        """Agregar a la lista solo-local es libre; sacar una exige `confirmar_nube=True` (sus datos podrían ir a la nube)."""
        actual = self.privadas()
        sacadas = sorted(set(actual) - set(ids))
        if sacadas and not confirmar_nube:
            raise PermissionError("sacar de solo-local puede mandar datos a la nube: " + ", ".join(sacadas))
        for i in ids:
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", i):
                raise ValueError(f"id inválido: {i}")
        u = self._usuario()
        u["private"] = list(dict.fromkeys(ids))
        return self._guardar_modelos(u, quien="panel", que=f"solo-local: {','.join(ids)}")

    def tope_pago(self, usd: float) -> ModelsConfig:
        if usd < 0:
            raise ValueError("el tope no puede ser negativo")
        u = self._usuario()
        u["paid_cap_usd_month"] = float(usd)
        return self._guardar_modelos(u, quien="panel", que=f"tope pago {usd}")

    def resumen_destinos(self) -> list[dict]:
        """Cada rol y cada override: a qué proveedores y modelos apunta hoy (para mostrarlo en la pantalla)."""
        cfg = self.modelos()

        def provs(chain: list[str]) -> list[str]:
            return [f"{p} ({cfg.providers[p].model})" for t in chain for p in cfg.tiers.get(t, [])]

        filas = [{"clave": r, "escalones": cfg.roles.get(r, []), "proveedores": provs(cfg.roles.get(r, []))} for r in ROLES]
        filas += [{"clave": k, "escalones": v, "proveedores": provs(v)} for k, v in sorted(cfg.overrides.items())]
        return filas

    # --- apariencia y autonomía ------------------------------------------------------------------------------------
    def _panel(self) -> dict:
        if self.panel_file.is_file():
            try:
                return json.loads(self.panel_file.read_text(encoding="utf-8"))
            except ValueError:
                return {}
        return {}

    def _guardar_panel(self, d: dict) -> None:
        _escribir_atomico(self.panel_file, json.dumps(d, ensure_ascii=False, indent=2), privado=False)

    def apariencia(self) -> dict:
        return {**APARIENCIA_BASE, **self._panel().get("apariencia", {})}

    def poner_apariencia(self, **cambios: object) -> dict:
        for k, v in cambios.items():
            if k not in APARIENCIA_BASE:
                raise ValueError(f"no existe el ajuste «{k}»")
            if k in OPCIONES_APARIENCIA and v not in OPCIONES_APARIENCIA[k]:
                raise ValueError(f"{k} es una de: {', '.join(OPCIONES_APARIENCIA[k])}")
            if k == "acento" and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)):
                raise ValueError("el color es #rrggbb")
            if k == "letra" and not (8 <= int(v) <= 20):
                raise ValueError("el tamaño de letra va de 8 a 20")
            if k == "nombre" and not (1 <= len(str(v).strip()) <= 30):
                raise ValueError("el nombre va de 1 a 30 caracteres")
        d = self._panel()
        antes = {k: self.apariencia()[k] for k in cambios}
        d.setdefault("apariencia", {}).update(cambios)
        self._guardar_panel(d)
        self._historia({"que": "apariencia", "quien": "panel", "antes": antes, "despues": dict(cambios)})
        return self.apariencia()

    def autonomia(self) -> str:
        return self.env().get("RAPHAEL_AUTONOMIA") or "equilibrado"

    # --- historial, deshacer, perfiles, exportar -------------------------------------------------------------------
    def _historia(self, entrada: dict) -> None:
        d = self._panel()
        h = d.setdefault("historial", [])
        h.append(
            {
                "n": (h[-1]["n"] + 1) if h else 1,
                "cuando": datetime.now().isoformat(timespec="seconds"),
                **entrada,
                "deshecho": False,
            }
        )
        d["historial"] = h[-200:]
        self._guardar_panel(d)

    def historial(self, limite: int = 50) -> list[dict]:
        """Sin valores de claves: solo qué variable cambió y si se puso o se sacó."""
        out = []
        for e in reversed(self._panel().get("historial", [])[-limite:]):
            if e["que"] == "env":
                que = ", ".join(f"{k}: {'sacada' if e['despues'][k] is None else 'puesta'}" for k in e["despues"])
            elif e["que"] == "modelos":
                que = e.get("detalle", "")
            else:
                que = ", ".join(f"{k}={v}" for k, v in e["despues"].items())
            out.append({"n": e["n"], "cuando": e["cuando"], "area": e["que"], "que": que, "deshecho": e["deshecho"]})
        return out

    def deshacer(self) -> str:
        """Revierte el último cambio que no esté deshecho."""
        d = self._panel()
        for e in reversed(d.get("historial", [])):
            if e["deshecho"]:
                continue
            if e["que"] == "env":
                cambios = {k: v for k, v in e["antes"].items()}
                self._escribir_env(cambios)
                for k, v in cambios.items():
                    if v is None:
                        self.environ.pop(k, None)
                    else:
                        self.environ[k] = v
            elif e["que"] == "modelos":
                _escribir_atomico(
                    self.usuario_file, yaml.safe_dump(e["antes_usuario"], allow_unicode=True, sort_keys=True), privado=False
                )
            else:
                d.setdefault("apariencia", {}).update(e["antes"])
            d = self._panel()
            for x in d["historial"]:
                if x["n"] == e["n"]:
                    x["deshecho"] = True
            if e["que"] == "apariencia":
                d.setdefault("apariencia", {}).update(e["antes"])
            self._guardar_panel(d)
            return f"Deshecho el cambio {e['n']} ({e['que']})."
        return "No hay cambios para deshacer."

    def guardar_perfil(self, nombre: str) -> None:
        """Un perfil guarda la configuración SIN claves: variables que no son secretas, modelos y apariencia."""
        if not re.fullmatch(r"[\w .-]{1,40}", nombre):
            raise ValueError("el nombre del perfil: letras, números, espacios, punto o guion")
        d = self._panel()
        d.setdefault("perfiles", {})[nombre] = self.exportar()
        self._guardar_panel(d)

    def perfiles(self) -> list[str]:
        return sorted(self._panel().get("perfiles", {}))

    def cargar_perfil(self, nombre: str) -> None:
        p = self._panel().get("perfiles", {}).get(nombre)
        if p is None:
            raise ValueError("no existe ese perfil")
        self.importar(p)

    def exportar(self) -> dict:
        env = self.env()
        publicas = {n: v for n, v in env.items() if not self._es_secreta(n)}
        return {"version": 1, "variables": publicas, "modelos": self._usuario(), "apariencia": self.apariencia()}

    def importar(self, datos: Mapping) -> list[str]:
        if datos.get("version") != 1:
            raise ValueError("este archivo no es una configuración exportada de Raphael")
        poner = {n: v for n, v in datos.get("variables", {}).items() if not self._es_secreta(n)}
        reinicia = self.aplicar(poner, quien="importar")
        if datos.get("modelos") is not None:
            self._guardar_modelos(datos["modelos"], quien="importar", que="importar modelos")
        if datos.get("apariencia"):
            self.poner_apariencia(**{k: v for k, v in datos["apariencia"].items() if k in APARIENCIA_BASE})
        return reinicia

    @staticmethod
    def _es_secreta(nombre: str) -> bool:
        c = POR_NOMBRE.get(nombre)
        if c is not None:
            return c.tipo == "secreto"
        return bool(re.search(r"(KEY|TOKEN|SECRET|PASSWORD|CLAVE|PASS)$|_CLAVE_|API_KEY", nombre))


def rutas_por_defecto(data_dir: Path, project_root: Path | None = None) -> dict[str, Path]:
    """Dónde viven los archivos: el `raphael.env` de Raphael personal si existe (`.data/personal`), si no el del panel.
    RAPHAEL_ENV_FILE manda sobre todo."""
    env = os.environ.get("RAPHAEL_ENV_FILE")
    personal = (project_root / ".data" / "personal") if project_root else None
    if env:
        env_file = Path(env)
    elif personal is not None and personal.is_dir():
        env_file = personal / "raphael.env"
    else:
        env_file = data_dir / "raphael.env"
    base = os.environ.get("RAPHAEL_PANEL_MODELS")
    if not base and project_root is not None:
        cand = project_root / "2-entrega" / "c-despliegue" / "personal" / "modelos.personal.yaml"
        base = str(cand) if cand.is_file() else ""
    return {
        "env_file": env_file,
        "usuario_file": data_dir / "modelos.usuario.yaml",
        "panel_file": data_dir / "panel-config.json",
        "modelos_base": Path(base) if base else DEFAULT_PATH,
    }
