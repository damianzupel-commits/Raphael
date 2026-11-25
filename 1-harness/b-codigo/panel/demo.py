"""Lógica del panel del harness, sin ventana (así se prueba con pytest).

Desde H5 el panel corre un `Runtime` de verdad con el cargador de manifiestos: "Agregar brigadas" monta y desmonta
brigadas reales (las de `brigadas/` del proyecto que tengan `manifest.yaml` y las de ejemplo del paquete), y el chat,
los cocineros, los efímeros, las herramientas y las tareas salen del runtime. Lo montado y los datos de las brigadas
se guardan en `.datos/` (installation.yaml y raphael.sqlite), así que sobreviven a cerrar la app.
Las "pruebas en vivo" del Núcleo siguen usando un bus y un Guard aparte, para no ensuciar el runtime.
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

import raphael_core
from raphael_core import CONTRACT_VERSION, Loader, Runtime
from raphael_core.contract import Message
from raphael_core.drafts import DraftError, DraftInvalid, DraftStore, Signer, review_text
from raphael_core.events import EventBus
from raphael_core.installation import installation_from, load_installation, save_installation
from raphael_core.isolation import Guard
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, load_models
from raphael_core.store import Store

from config_modelo import Configuracion, rutas_por_defecto

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

STAGES = [
    ("H1", "Cimientos: contrato, manifiesto, instalación, almacén, bus, auditoría, aislamiento", "hecha"),
    ("H2", "Runtime, contextos, Policy Engine con confianza progresiva, pendientes", "hecha"),
    ("H3", "Modelos en 3 escalones, uso y compat v1 (Empresas corre sobre el v2)", "hecha"),
    ("H4", "Motor de brigadas: jefe, efímeros, reportes y tools", "hecha"),
    ("H5", "Cargador de manifiestos, montar y desmontar, suite de contrato", "hecha"),
    ("H6", "Brigadas creadas por borrador (opcional)", "hecha"),
    ("H7", "Jefe caído, comandos de lectura, salud periódica, setup de tools", "hecha"),
]

MODULES = [
    ("contract", "Contrato 2.0.0, niveles, mensajes, acciones"),
    ("manifest", "Esquema de manifest.yaml de cada brigada"),
    ("installation", "Edición, plan, brigadas activas, autonomía, confianza"),
    ("store", "SQLite con un espacio por brigada; exportar y purgar"),
    ("events", "Bus de eventos aislado, sync y async"),
    ("audit", "Quién, qué, cuándo y por qué; tacha secretos"),
    ("isolation", "Guard: timeouts y piezas caídas (fallas contadas por método)"),
    ("policy", "Policy Engine sin pisos, con confianza progresiva"),
    ("approvals", "Pendientes: aprobar, rechazar, resolver; ids validados"),
    ("context", "Lo que ve cada cocinero, el orquestador y la persona"),
    ("runtime", "Recibir, despachar, acciones, montar y desmontar, estado"),
    ("models", "Pasarela de modelos: pago, gratis y local; roles en orden; uso y topes"),
    ("engine", "Motor de brigadas: spec, jefe que planifica y sintetiza, efímeros con tools"),
    ("engine.reports", "Contratos efímero -> jefe -> orquestador (v2, en inglés), cifras con respaldo"),
    ("engine.live", "Tablero en vivo de los efímeros (activos y recientes)"),
    ("tools", "Gateway de tools: caja por efímero, edición y compuerta de política"),
    ("loader", "Cargador de manifiestos: encuentra, arma, monta y desmonta según la instalación"),
    ("testing.contract", "Suite de contrato y matriz de montaje (puerta de la fase 1)"),
    ("drafts", "Brigadas por borrador: revisión, hash y activación firmada"),
    ("compat.v1", "Raphael Empresas 0.4 sin cambios sobre el v2 (puente raphael_harness)"),
    ("text_es", "Fechas y texto en español rioplatense"),
    ("testing", "Reloj de prueba y chequeo AST de imports"),
]

EXAMPLE_MANIFEST = """\
id: saludo
name: Brigada de saludo
version: 1.0.0
contract: ">=2.0,<3"
cooks:
  - {id: saludador, entry: "raphael_saludo:Greeter"}
actions:
  saludar: {level: automatico}
  regalar: {level: aprobacion, tags: [spend]}
tools:
  - {name: leer_agenda}
  - {name: escanear_red, active_scan: true}
events:
  publishes: [saludo.hecho]
  consumes: [pendiente.creado]
"""


@dataclass
class BrigadeInfo:
    """Una brigada tal como está en `brigadas/` de la carpeta del proyecto (solo lectura)."""

    id: str
    number: str
    name: str
    description: str
    folder: Path
    cooks: list[str] = field(default_factory=list)
    manifest_path: Path | None = None
    manifest_ok: bool = False
    manifest_errors: list[str] = field(default_factory=list)
    contract_ok: bool = False
    mounted: bool = False
    mountable: bool = False          # el cargador la encontró por su manifest.yaml
    example: bool = False            # brigada de ejemplo del paquete (no es del proyecto)
    error: str | None = None         # por qué no se pudo montar la última vez
    chief: bool = False

    @property
    def state(self) -> str:
        if self.mounted:
            return "montada"
        if self.error:
            return "no se pudo montar"
        if self.mountable:
            return "sin montar"
        if self.manifest_path is None:
            return "sin manifiesto"
        return "manifiesto válido" if self.manifest_ok else "manifiesto con errores"


def find_project_root(start: Path = PACKAGE_ROOT) -> Path | None:
    """La carpeta del proyecto, subiendo desde el paquete: la del árbol (`CONTEXT.md` y `1-harness/c-brigadas/`),
    la del monorepo anterior (`CONTEXT.md` y `brigades/`) o la vieja (`00-LEEME.md` y `brigadas/`)."""
    for p in [start, *start.parents]:
        if brigades_dir(p) is not None and ((p / "CONTEXT.md").is_file() or (p / "00-LEEME.md").is_file()):
            return p
    return None


def brigades_dir(root: Path) -> Path | None:
    """La carpeta donde viven las brigadas: `1-harness/c-brigadas/` (árbol a/b/c), `brigades/` o `brigadas/` (viejas)."""
    for name in ("1-harness/c-brigadas", "brigades", "brigadas"):
        if (root / name).is_dir():
            return root / name
    return None


_README_TITLE = re.compile(r"^#\s*(\d+)-([a-z0-9-]+)\s*·\s*(.+?)\s*$")


def discover_brigades(root: Path | None, mounted: set[str] | frozenset[str] = frozenset()) -> list[BrigadeInfo]:
    """Lee `brigadas/NN-id/`: nombre y descripción del README, cocineros y, si hay, su `manifest.yaml` (fuera de
    `codigo-actual/`). No importa ni ejecuta nada de las brigadas."""
    bdir = brigades_dir(root) if root is not None else None
    if bdir is None:
        return []
    out: list[BrigadeInfo] = []
    for folder in sorted(p for p in bdir.iterdir() if p.is_dir()):
        m = re.match(r"^(?:(\d+)-)?([a-z0-9-]+)$", folder.name)
        if not m:
            continue
        number, bid = m.group(1) or "", m.group(2)
        if bid == ORCHESTRATOR:          # 00-orquestador vive con las brigadas, pero el panel lo muestra aparte
            continue
        name, description = bid.replace("-", " ").capitalize(), ""
        readme = folder / "README.md"
        if readme.is_file():
            lines = readme.read_text(encoding="utf-8", errors="replace").splitlines()
            t = _README_TITLE.match(lines[0]) if lines else None
            if t:
                name = t.group(3)
            elif lines and lines[0].startswith("# "):
                name = lines[0][2:].strip()
            para = next((ln.strip() for ln in lines[1:] if ln.strip() and not ln.startswith("#")), "")
            if "## Objetivo" in lines:
                i = lines.index("## Objetivo")
                para = next((ln.strip() for ln in lines[i + 1:] if ln.strip() and not ln.startswith("#")), para)
            description = re.sub(r"^Chat \d+ del proyecto Raphael\.\s*", "", para)
        cooks_dir = next((d for d in (folder / "a-historia" / "cocineros", folder / "cocineros") if d.is_dir()),
                         folder / "cocineros")
        cooks = sorted(p.name for p in cooks_dir.iterdir() if p.is_dir()) if cooks_dir.is_dir() else []
        info = BrigadeInfo(bid, number, name, description, folder, cooks, mounted=bid in mounted)
        manifests = sorted(p for p in folder.rglob("manifest.yaml") if "codigo-actual" not in p.parts)
        if manifests:
            info.manifest_path = manifests[0]
            try:
                man = manifest_from(yaml.safe_load(manifests[0].read_text(encoding="utf-8")) or {})
                info.manifest_ok, info.contract_ok = True, man.supports_contract()
                if man.id != info.id:          # la carpeta puede llamarse distinto que el id del manifiesto
                    info.id, info.mounted = man.id, man.id in mounted
            except (ValidationError, yaml.YAMLError, AttributeError, TypeError) as exc:
                info.manifest_errors = [str(exc).splitlines()[0][:200]]
        out.append(info)
    return out


ORCHESTRATOR = "orquestador"

#: borrador de ejemplo para la vista Borradores (usa la tool de la brigada de ejemplo "saludo": montala antes)
EXAMPLE_DRAFT = """{
  "id": "agenda-diaria",
  "name": "Agenda diaria",
  "purpose": "Contar qué hay en la agenda del día, tal cual.",
  "prompt": "Sos el jefe de la agenda diaria. Coordinás a tu efímero y reportás con precisión.",
  "private": false,
  "helpers": [
    {"mode": "agenda", "description": "lee la agenda del día",
     "prompt": "Sos el efímero de agenda. Usá leer_agenda y contá lo que hay, tal cual.",
     "tools": ["leer_agenda"]}
  ],
  "routing": {"rules": [], "default": "agenda"},
  "validation": {
    "criterion": "Cuenta los eventos del día sin inventar nada.",
    "steps": [{"id": "ruteo", "type": "routing", "cases": [{"message": "¿qué hay hoy?", "mode": "agenda"}]}]
  }
}
"""

#: datos de MUESTRA (inventados, se muestran marcados como muestra) para ver cómo queda la app con brigadas andando
SAMPLE_MOUNTED = ("memoria-cerebro", "investigacion", "raphael-empresas")
SAMPLE_TASKS = {
    "memoria-cerebro": [("Consolidar las notas de la semana", "en curso", "consolidador"),
                        ("Buscar el origen de una cita", "en cola", "recuperador")],
    "investigacion": [("Fuentes sobre baterías de estado sólido", "en curso", "scout"),
                      ("Guardar el informe en el vault", "aprobación", "ideas-y-prototipos")],
    "raphael-empresas": [("Responder una consulta de precio", "en curso", "atencion"),
                         ("Confirmar el turno del jueves 16 h", "aprobación", "agenda")],
}
SAMPLE_BUSY = {"consolidador", "scout", "atencion"}
SAMPLE_EPHEMERALS = [("efimero-scout-1", "investigacion", "buscar fuentes", "00:42"),
                     ("efimero-resumen-3", "memoria-cerebro", "resumir 12 notas", "00:08"),
                     ("efimero-precio-2", "raphael-empresas", "armar presupuesto", "00:03")]
SAMPLE_TOOLS = [("leer_archivo", "brigada y usuario", "automatico", True, None),
                ("buscar_web", "brigada", "automatico", True, "investigacion"),
                ("transcribir_audio", "usuario", "automatico", False, None),
                ("buscar_en_vault", "brigada y usuario", "automatico", True, "memoria-cerebro"),
                ("enviar_whatsapp", "brigada", "aprobacion", True, "raphael-empresas"),
                ("borrar_nota", "usuario", "humano", False, "memoria-cerebro")]
SAMPLE_CHAT = {
    ORCHESTRATOR: [("user", "¿Qué tienen en curso las brigadas?"),
                   ("brigade", "Tres tareas en curso y dos esperan tu aprobación: guardar el informe de baterías "
                               "(Investigación) y confirmar el turno del jueves (Raphael Empresas)."),
                   ("user", "Mostrame el del turno.")],
    "memoria-cerebro": [("user", "¿De dónde saqué la cita de Feynman que anoté ayer?"),
                        ("brigade", "La estoy buscando con el recuperador: por ahora aparece en una nota del 12/11 "
                                    "sin fuente. Te aviso si encuentro el origen.")],
    "investigacion": [("user", "Buscame fuentes serias sobre baterías de estado sólido."),
                      ("brigade", "El scout encontró 6 fuentes; armé un informe. Guardarlo en el vault necesita "
                                  "tu aprobación.")],
    "raphael-empresas": [("user", "¿Hay algo para aprobar?"),
                         ("brigade", "Sí: confirmar el turno del jueves a las 16 h para una clienta.")],
}


DEFAULT_INSTALLATION = {"id": "pc-damian", "edition": "personal", "plan": "privado",
                        "identity": {"assistant": "Raphael", "user": "Damián"}}
PANEL_CONTACT = "damian"


def build_gateway(store: Store, installation) -> ModelGateway | None:
    """La pasarela con `modelos.yaml` del paquete (o el que diga RAPHAEL_PANEL_MODELS, por ejemplo el de Raphael
    personal) y las claves del entorno. Nunca las lee de archivos."""
    try:
        path = os.environ.get("RAPHAEL_PANEL_MODELS")
        loader = os.environ.get("RAPHAEL_PANEL_MODELS_LOADER")       # "modulo:funcion" (ruta, entorno) -> config
        if loader:
            module, _, fn = loader.partition(":")
            config = getattr(importlib.import_module(module), fn)(path, dict(os.environ))
        else:
            config = load_models(path) if path else load_models()
        return ModelGateway(config,
                            Usage(store.space("_uso"), installation.limits.messages_month, datetime.now),
                            plan=installation.plan, edition=installation.edition, env=dict(os.environ))
    except Exception:  # noqa: BLE001 - sin modelos el panel anda igual: el jefe degrada y lo dice
        return None


def report_text(rep) -> str:
    """El reporte interno del jefe, legible. Lo de verdad lo redacta la voz del orquestador (pieza 02); acá se muestra
    tal cual, sin adornar ni completar nada."""
    lines = [rep.summary]
    lines += [f"• {f.text}" for f in rep.findings[:6]]
    if rep.not_found:
        lines.append("No encontrado: " + "; ".join(rep.not_found))
    if rep.pending_proposals:
        lines.append("Para aprobar: " + "; ".join(f"{p.id} ({p.description})" for p in rep.pending_proposals))
    if rep.failures:
        lines.append("Fallaron: " + "; ".join(f"{f.helper} ({f.reason})" for f in rep.failures))
    if rep.degraded:
        lines.append("⚠ " + (rep.warnings[0] if rep.warnings else "reporte degradado"))
    return "\n".join(lines)


class PanelState:
    def __init__(self, project_root: Path | None = None, data_dir: str | Path | None = None,
                 dev_dirs: list[Path] | None = None, models: ModelGateway | None | bool = True) -> None:
        # dónde se guarda todo: `.datos/` (o RAPHAEL_PANEL_DATA); ":memory:" en tests
        if data_dir is None:
            data_dir = os.environ.get("RAPHAEL_PANEL_DATA") or PACKAGE_ROOT / ".datos"
        memory = str(data_dir) == ":memory:"
        if memory:
            self.chat_store, rt_store, self.installation_path = Store(":memory:"), Store(":memory:"), None
        else:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            self.chat_store = Store(str(Path(data_dir) / "panel.sqlite"))
            rt_store = Store(str(Path(data_dir) / "raphael.sqlite"))
            self.installation_path = Path(data_dir) / "installation.yaml"
        if self.installation_path and self.installation_path.is_file():
            self.installation = load_installation(self.installation_path)
        else:
            self.installation = installation_from(DEFAULT_INSTALLATION)
            if self.installation_path:
                save_installation(self.installation, self.installation_path)
        gateway = build_gateway(rt_store, self.installation) if models is True else (models or None)
        self.runtime = Runtime(self.installation, store=rt_store, models=gateway)
        self.store = rt_store
        self.audit = self.runtime.audit
        # bus y guard de las "pruebas en vivo" (aparte del runtime)
        self.bus = EventBus(on_error=self._event_failed)
        self.guard = Guard(max_failures=3, on_down=self._piece_down)
        self.received: list[str] = []
        self.bus.subscribe("panel.ping", lambda e, d: self.received.append(d.get("n", "")), owner="eco-panel")
        self.project_root = project_root if project_root is not None else find_project_root()
        # Configuración desde el panel (claves, modelos por brigada, apariencia): raphael.env + modelos.usuario.yaml
        cfg_dir = Path(tempfile.mkdtemp(prefix="raphael-config-")) if memory else Path(data_dir)
        self.config = Configuracion(**rutas_por_defecto(cfg_dir, None if memory else self.project_root))
        if not memory:
            for k, v in self.config.env().items():
                os.environ.setdefault(k, v)          # lo que ya esté en el entorno de verdad manda
            self.reload_models()
        if dev_dirs is None:
            dev_dirs = [d for d in ((brigades_dir(self.project_root)) if self.project_root else None,
                                    PACKAGE_ROOT / "ejemplos") if d is not None and d.is_dir()]
        keys = Path(tempfile.mkdtemp(prefix="raphael-claves-")) if memory else Path(data_dir) / "claves"
        self.drafts = DraftStore(rt_store.space("_drafts"), Signer(keys),
                                 catalog=lambda: {n: self.runtime.tools.get(n) for n in self.runtime.tools.names()},
                                 taken_ids=lambda: self.loader.non_draft_ids())
        self.loader = Loader(self.runtime, dev_dirs, installation_path=self.installation_path, drafts=self.drafts)
        self.mount_report = Runtime.run(self.loader.apply())
        self.brigades: list[BrigadeInfo] = []
        self._rebuild()
        self.sample = False
        self._sample_tools_on = {t[0]: t[3] for t in SAMPLE_TOOLS}
        self.audit.record("inicio", who="panel", why="se abrió el panel", core=raphael_core.__version__,
                          brigadas_encontradas=len(self.brigades), montadas=self.mount_report["mounted"],
                          errores=self.mount_report["errors"])

    def reload_models(self) -> str:
        """Aplica en caliente la configuración de modelos y claves (sin reiniciar). Devuelve un aviso si no se pudo."""
        gw = self.runtime.models
        if gw is None:
            return "sin modelos configurados"
        try:
            gw.config = self.config.modelos()
            gw.set_env(dict(os.environ))
        except Exception as e:  # noqa: BLE001 - una configuración rota no tumba el panel: queda la anterior
            return f"no se pudo aplicar la configuración de modelos: {e}"
        return ""

    def _rebuild(self) -> None:
        """Junta lo que hay en `brigadas/` (README, cocineros) con lo que el cargador encontró por manifiesto."""
        infos = {b.id: b for b in discover_brigades(self.project_root)}
        examples = PACKAGE_ROOT / "ejemplos"
        for bid, f in self.loader.found.items():
            m = f.manifest
            info = infos.get(bid)
            if info is None:
                is_example = bool(f.path and examples in f.path.parents)
                number = "ej" if is_example else ("bor" if f.source == "draft" else "—")
                info = BrigadeInfo(bid, number, m.name, m.description, f.path.parent if f.path else Path("."),
                                   [c.id for c in m.cooks], example=is_example)
                infos[bid] = info
            info.manifest_path, info.manifest_ok, info.contract_ok = f.path, True, m.supports_contract()
            info.mountable, info.chief = True, bool(m.chief)
            if not info.cooks:
                info.cooks = [c.id for c in m.cooks]
            if not info.description:
                info.description = m.description
        for info in infos.values():
            info.mounted = info.id in self.runtime.brigades
            info.error = self.loader.errors.get(info.id)
        self.brigades = sorted(infos.values(), key=lambda b: (b.example, b.number, b.id))

    # --- brigadas por borrador (H6) -------------------------------------------------------------------------------------
    def draft_list(self) -> list[dict]:
        return [{"id": r["draft"]["id"], "name": r["draft"]["name"], "state": r["state"], "hash": r["hash"][:12],
                 "mounted": r["draft"]["id"] in self.runtime.brigades,
                 "invalid_approval": r.get("invalid_approval", False)} for r in self.drafts.list()]

    def draft_create(self, text: str) -> tuple[bool, str]:
        """Crea un BORRADOR desde JSON (nunca activo). Devuelve (ok, revisión en texto o errores)."""
        try:
            raw = json.loads(text)
        except ValueError as exc:
            return False, f"No es JSON válido: {exc}"
        try:
            rec = self.drafts.create(raw, origin="panel")
        except DraftInvalid as exc:
            return False, "El borrador no valida:\n- " + "\n- ".join(exc.errors)
        except DraftError as exc:
            return False, str(exc)
        self.audit.record("borrador_creado", who="usuario", brigada=rec["draft"]["id"], hash=rec["hash"][:12])
        return True, self.draft_review(rec["draft"]["id"])

    def draft_review(self, bid: str) -> str:
        rv = self.drafts.review(bid)
        extra = []
        if rv["current_errors"]:
            extra.append("Hoy NO valida: " + "; ".join(rv["current_errors"]))
        if rv["routing_failures"]:
            extra.append("Su ruteo no pasa sus propios casos: " + "; ".join(rv["routing_failures"]))
        state = "ACTIVA" if rv["state"] == "activa" else "borrador"
        text = review_text(rv)
        if state != "borrador":
            text = text.replace(" — NO está activo.", " — activa.")
        return f"Estado: {state}\n{text}" + ("\n\n" + "\n".join(extra) if extra else "")

    def draft_activate(self, bid: str, approved_hash: str) -> str:
        """La persona aprueba el hash que vio: se firma, se activa y se monta."""
        try:
            self.drafts.activate(bid, approved_hash, by=self.installation.identity.user or "persona")
        except DraftInvalid as exc:
            return "No se activó: " + "; ".join(exc.errors)
        except DraftError as exc:
            return f"No se activó: {exc}"
        except Exception as exc:  # noqa: BLE001 - p. ej. la clave de firma no se pudo crear o leer (DPAPI)
            return f"No se activó: no se pudo firmar la aprobación ({exc})"
        self.audit.record("borrador_activado", who="usuario", brigada=bid, hash=approved_hash[:12])
        return f"{bid} activada (firmada sobre {approved_hash[:12]}). " + self.mount(bid)

    def draft_deactivate(self, bid: str) -> str:
        try:
            self.drafts.deactivate(bid)
        except DraftError as exc:
            return str(exc)
        Runtime.run(self.loader.apply())
        self._rebuild()
        self.audit.record("borrador_desactivado", who="usuario", brigada=bid)
        return f"{bid} volvió a borrador y se desmontó."

    def draft_discard(self, bid: str) -> str:
        try:
            self.drafts.discard(bid)
        except DraftError as exc:
            return str(exc)
        self.audit.record("borrador_descartado", who="usuario", brigada=bid)
        return f"Borrador {bid} descartado."

    # --- montar y desmontar (lo que hace "Agregar brigadas") ------------------------------------------------------------
    def mount(self, bid: str) -> str:
        try:
            rep = Runtime.run(self.loader.set_active(bid, True))
        except Exception as exc:  # noqa: BLE001
            self._rebuild()
            return f"No se pudo montar {bid}: {exc}"
        self._rebuild()
        if bid in rep["errors"]:
            return f"No se pudo montar {bid}: {rep['errors'][bid]}"
        notes = [w for w in rep["warnings"] if w.startswith(bid)]
        return f"{bid} montada." + (f" Avisos: {'; '.join(notes)}" if notes else "")

    def unmount(self, bid: str) -> str:
        Runtime.run(self.loader.set_active(bid, False))
        self._rebuild()
        return f"{bid} desmontada. Sus datos quedan guardados salvo lo que su manifiesto manda borrar al desinstalar."

    # --- hooks
    def _event_failed(self, owner: str, event: str, exc: BaseException) -> None:
        self.audit.record("evento_fallido", who=owner, evento=event, error=repr(exc)[:200])

    def _piece_down(self, piece: str, reason: str) -> None:
        self.audit.record("pieza_caida", who=piece, why=reason)

    # --- brigadas y alcance (orquestador = todas; si no, una brigada) -------------------------------------------------
    def mounted(self) -> list[BrigadeInfo]:
        if self.sample:
            return [b for b in self.brigades if b.id in SAMPLE_MOUNTED]
        return [b for b in self.brigades if b.mounted]

    def brigade(self, bid: str) -> BrigadeInfo | None:
        return next((b for b in self.brigades if b.id == bid), None)

    def _in_scope(self, scope: str) -> list[BrigadeInfo]:
        bs = self.mounted()
        return bs if scope == ORCHESTRATOR else [b for b in bs if b.id == scope]

    def _name(self, bid: str) -> str:
        b = self.brigade(bid)
        return b.name if b else bid

    def cooks(self, scope: str) -> list[tuple[str, str, str]]:
        """(cocinero, brigada, estado) de las brigadas montadas en el alcance."""
        if self.sample:
            return [(c, b.name, "trabajando" if c in SAMPLE_BUSY else "en espera")
                    for b in self._in_scope(scope) for c in b.cooks]
        out = []
        for b in self._in_scope(scope):
            m = self.runtime.brigades.get(b.id)
            if m is None:
                continue
            for c in m.cooks:
                out.append((c, b.name, "caído" if self.runtime.guard.is_down(f"{b.id}/{c}") else "en espera"))
            if m.chief:
                state = "caído (doble clic)" if m.chief_down else "listo"
                out.append((f"jefe ({len(m.chief.spec.helpers)} efímeros)", b.name, state))
            if m.health_fn is not None and m.health["ok"] is False:
                h = m.health
                out.append(("salud", b.name, "caída" if h["down"] else f"mala ({h['fails']}/3)"))
        return out

    def revive_chief(self, brigade_name: str) -> str:
        """Revive el jefe caído de una brigada (por id o por nombre, como se ve en la lista)."""
        b = next((x for x in self.brigades if brigade_name in (x.id, x.name)), None)
        if b is None:
            return f"No encontré la brigada {brigade_name}."
        try:
            self.runtime.revive_chief(b.id)
        except Exception as exc:  # noqa: BLE001
            return f"No se pudo: {exc}"
        return f"El jefe de {b.name} volvió a estar habilitado."

    def tick(self) -> None:
        """Tareas programadas y healthcheck (cada 5 min por brigada). La ventana lo llama cada minuto."""
        Runtime.run(self.runtime.tick())

    def ephemerals(self, scope: str) -> list[tuple[str, str, str, str]]:
        """(efímero, brigada, tarea, tiempo): los que corren ahora y, debajo, los últimos que terminaron."""
        if self.sample:
            names = {b.id: b.name for b in self.brigades}
            return [(e, names.get(b, b), t, d) for e, b, t, d in SAMPLE_EPHEMERALS if scope in (ORCHESTRATOR, b)]
        snap = self.runtime.live.snapshot(None if scope == ORCHESTRATOR else scope)
        out = [(e["helper"], e["brigade_name"], e["task"], f"{e['seconds']:.0f}s") for e in snap["active"]]
        out += [(r["helper"], r["brigade_name"], r["task"], f"{r['outcome']} {r['seconds']:.0f}s")
                for r in snap["recent"][:6]]
        return out

    def tools(self, scope: str) -> list[tuple[str, str, str, bool]]:
        """(herramienta, de quién, nivel, activada)."""
        if self.sample:
            return [(n, who, lvl, self._sample_tools_on[n]) for n, who, lvl, _, owner in SAMPLE_TOOLS
                    if scope == ORCHESTRATOR or owner in (None, scope)]
        return [(t["name"], self._name(t["owner"]) if t["owner"] else "uso compartido", t["level"], t["enabled"])
                for t in self.runtime.tools.list() if scope == ORCHESTRATOR or t["owner"] in ("", scope)]

    def toggle_tool(self, name: str) -> bool:
        if self.sample:
            if name not in self._sample_tools_on:
                return False
            self._sample_tools_on[name] = not self._sample_tools_on[name]
            self.audit.record("herramienta", who="usuario", nombre=name, activada=self._sample_tools_on[name],
                              muestra=True)
            return self._sample_tools_on[name]
        if self.runtime.tools.get(name) is None:
            return False
        on = self.runtime.tools.set_enabled(name, not self.runtime.tools.enabled(name))
        self.audit.record("herramienta", who="usuario", nombre=name, activada=on)
        return on

    def tasks(self, scope: str) -> list[tuple[str, str, str, str]]:
        """(tarea, brigada, estado, quién): lo que corre ahora y lo que espera a una persona."""
        if self.sample:
            out = []
            for b in self._in_scope(scope):
                out += [(t, b.name, st, c) for t, st, c in SAMPLE_TASKS.get(b.id, [])]
            return out
        snap = self.runtime.live.snapshot(None if scope == ORCHESTRATOR else scope)
        out = [(e["task"] or "tarea", e["brigade_name"], "en curso", e["helper"]) for e in snap["active"]]
        for p in self.runtime.approvals.list(brigade=None if scope == ORCHESTRATOR else scope):
            state = "aprobación" if p["level"] == "aprobacion" else "te toca a vos"
            out.append((f"#{p['id']} {p['summary']}", self._name(p["brigade"]), state, p["cook"]))
        return out

    def approve(self, pid: int) -> str:
        res = Runtime.run(self.runtime.approve(pid))
        return f"#{pid}: {res.get('state')}" + (f" — {res.get('error')}" if res.get("error") else "")

    def reject(self, pid: int, why: str = "") -> str:
        Runtime.run(self.runtime.reject(pid, why or "rechazado desde el panel"))
        return f"#{pid} rechazado."

    # --- chat: uno por brigada (y uno del orquestador), guardado en disco ---------------------------------------------
    def chat(self, scope: str) -> list[dict]:
        if self.sample:
            name = self.brigade(scope).name if self.brigade(scope) else "Orquestador"
            return [{"role": r, "text": t, "who": "vos" if r == "user" else name, "when": "muestra"}
                    for r, t in SAMPLE_CHAT.get(scope, [])]
        return self.chat_store.space("_chat").list(scope)

    def _say(self, scope: str, role: str, who: str, text: str) -> None:
        sp = self.chat_store.space("_chat")
        sp.put(scope, sp.next(scope), {"role": role, "text": text, "who": who,
                                       "when": datetime.now().strftime("%d/%m %H:%M")})

    def send(self, scope: str, text: str) -> list[dict]:
        """Guarda el mensaje y se lo pasa al núcleo. Lo que vuelve es del runtime; si nadie puede responder, lo dice
        (no inventa). Puede tardar si hay un modelo de por medio: la ventana lo llama desde un hilo."""
        text = text.strip()
        if not text or self.sample:
            return self.chat(scope)
        self._say(scope, "user", "vos", text)
        self.audit.record("chat", who="usuario", alcance=scope)
        try:
            for role, who, reply in self._answer(scope, text):
                self._say(scope, role, who, reply)
        except Exception as exc:  # noqa: BLE001 - el chat nunca tumba al panel
            self._say(scope, "system", "harness", f"Falló al procesar el mensaje: {exc}")
        return self.chat(scope)

    def _answer(self, scope: str, text: str) -> list[tuple[str, str, str]]:
        rt = self.runtime
        if scope != ORCHESTRATOR:
            m = rt.brigades.get(scope)
            name = self._name(scope)
            if m is None:
                return [("system", "harness", f"{name} no está montada: montala desde «Agregar brigadas».")]
            if m.chief is not None:
                rep = Runtime.run(rt.ask(scope, text))
                return [("brigade", name, report_text(rep))]
            replies = []
            msg = Message("panel", PANEL_CONTACT, text, name="Damián")
            for cid in m.cooks:
                r = rt.consult_sync(scope, cid, msg, by="panel")
                if r is not None and r.text:
                    replies.append(("brigade", f"{name} · {cid}", r.text))
            Runtime.run(rt._settle())  # noqa: SLF001 - las acciones que pidieron quedan resueltas o pendientes
            return replies or [("system", "harness", f"Ningún cocinero de {name} tomó el mensaje.")]
        if rt.orchestrator is not None:        # en el panel habla la persona dueña, nunca un cliente
            seen = {p["id"] for p in rt.approvals.list()}
            reply = Runtime.run(rt.talk_to_owner(text, session="panel", channel="panel"))
            out = [("brigade", "Raphael", reply.text)]
            out += [("system", "harness", f"Quedó el pendiente #{p['id']} ({p['summary']}) en «Estado y tareas».")
                    for p in rt.approvals.list() if p["id"] not in seen]
            return out
        if not rt.brigades:
            return [("system", "harness", "No hay brigadas montadas. Agregalas con «Agregar brigadas». El orquestador "
                                          "de verdad es otra pieza (02); acá el núcleo reparte por interés.")]
        before = len(rt.outgoing(f"panel:{PANEL_CONTACT}"))
        pending_before = {p["id"] for p in rt.approvals.list()}
        Runtime.run(rt.receive("panel", PANEL_CONTACT, text, name="Damián"))
        out = [("brigade", "Raphael", m["text"]) for m in rt.outgoing(f"panel:{PANEL_CONTACT}")[before:]]
        new = [p for p in rt.approvals.list() if p["id"] not in pending_before]
        out += [("system", "harness", f"Quedó el pendiente #{p['id']} ({p['summary']}) en «Estado y tareas».")
                for p in new]
        return out or [("system", "harness", "Ninguna brigada tomó el mensaje.")]

    # --- lo que se muestra
    def _models_state(self) -> str:
        gw = self.runtime.models
        if gw is None:
            return "sin pasarela de modelos"
        label = gw.label("jefe")
        return label if label != "sin modelo" else "sin modelo (responde por reglas)"

    def status(self) -> dict:
        return {
            "core": raphael_core.__version__,
            "contract": CONTRACT_VERSION,
            "python": f"{platform.python_version()} ({sys.executable})",
            "edition": self.installation.edition,
            "installation": self.installation.id,
            "brigades": sorted(self.runtime.brigades),
            "models": self._models_state(),
            "pending": len(self.runtime.approvals.list()),
            "subscribers": sorted(self.bus.owners()),
            "down": [p for p in ("pieza-rota",) if self.guard.is_down(p)],
        }

    def audit_rows(self, last: int = 200) -> list[dict]:
        return list(reversed(self.audit.entries(last=last)))

    def event_rows(self) -> list[tuple[str, dict]]:
        return list(reversed(self.bus.history))

    # --- pruebas en vivo
    def ping(self) -> str:
        n = len(self.received) + 1
        self.bus.publish("panel.ping", {"n": n}, source="panel")
        self.audit.record("prueba_evento", who="panel", n=n)
        return f"Evento panel.ping #{n} publicado; el suscriptor 'eco-panel' lo recibió ({len(self.received)} en total)."

    def broken_subscriber(self) -> str:
        def roto(e: str, d: dict) -> None:
            raise RuntimeError("este suscriptor está roto a propósito")

        self.bus.subscribe("panel.roto", roto, owner="suscriptor-roto")
        self.bus.subscribe("panel.roto", lambda e, d: self.received.append("sano"), owner="suscriptor-sano")
        self.bus.publish("panel.roto", {}, source="panel")
        self.bus.unsubscribe("suscriptor-roto")
        self.bus.unsubscribe("suscriptor-sano")
        return "Un suscriptor roto falló: quedó en la auditoría y el otro suscriptor recibió el evento igual."

    def cycle(self) -> str:
        self.bus.subscribe("panel.a", lambda e, d: self.bus.publish("panel.b", {}), owner="ciclo-a")
        self.bus.subscribe("panel.b", lambda e, d: self.bus.publish("panel.a", {}), owner="ciclo-b")
        self.bus.publish("panel.a", {}, source="panel")
        self.bus.unsubscribe("ciclo-a")
        self.bus.unsubscribe("ciclo-b")
        return "Dos brigadas se rebotaban eventos: el bus cortó el ciclo y lo anotó en la auditoría."

    def fail(self) -> str:
        if self.guard.is_down("pieza-rota"):
            return "La pieza ya está caída: el harness no la vuelve a llamar hasta que la revivas."

        def rota() -> None:
            raise ValueError("falla de prueba")

        self.guard.call_sync("pieza-rota", rota)
        if self.guard.is_down("pieza-rota"):
            return "Tercera falla seguida: la pieza quedó caída."
        return f"La pieza falló ({self.guard.failures('pieza-rota')} de 3). A la tercera seguida queda caída."

    def revive(self) -> str:
        self.guard.revive("pieza-rota")
        self.audit.record("pieza_revivida", who="panel", pieza="pieza-rota")
        return "Pieza revivida: el contador volvió a cero."

    def secret(self) -> str:
        self.audit.record("prueba_secreto", who="panel", api_key="no-se-guarda",
                          nota="la clave sk-ejemplo1234567890 no tiene que quedar escrita")
        return "Se auditó un dato con una clave adentro: mirá la pestaña Auditoría, quedó tachada."

    # --- manifiestos
    def validate_manifest(self, text: str) -> tuple[bool, list[str]]:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            return False, [f"YAML inválido: {exc}"]
        if not isinstance(data, dict):
            return False, ["El manifiesto tiene que ser un mapa (clave: valor)."]
        try:
            m = manifest_from(data)
        except ValidationError as exc:
            lines = [f"{'.'.join(str(p) for p in e['loc']) or '(raíz)'}: {e['msg']}" for e in exc.errors()]
            return False, lines
        cloud = [t.name for t in m.tools_for("cloud")]
        hidden = [t.name for t in m.tools if t.name not in cloud]
        lines = [
            f"Brigada '{m.id}' {m.version}: válida.",
            f"Contrato pedido {m.contract}: {'compatible' if m.supports_contract() else 'INCOMPATIBLE'} con {CONTRACT_VERSION}.",
            f"Cocineros: {', '.join(c.id for c in m.cooks) or 'ninguno'}" + (f"; jefe: {m.chief}" if m.chief else ""),
            "Acciones: " + (", ".join(f"{a} = {s.level.value}{' (' + ', '.join(sorted(s.tags)) + ')' if s.tags else ''}"
                                      for a, s in m.actions.items()) or "ninguna"),
            f"Espacio de datos: {m.space}",
            f"Tools en la nube: {', '.join(cloud) or 'ninguna'}" + (f"; no se cargan: {', '.join(hidden)}" if hidden else ""),
        ]
        self.audit.record("manifiesto_validado", who="panel", brigada=m.id)
        return True, lines

    # --- tests
    def run_regression(self, timeout: float = 300) -> tuple[bool, str]:
        """La puerta de H3: toda la suite de Raphael Empresas sobre el v2 (scripts/regresion_empresas.py)."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        args = [sys.executable, str(PACKAGE_ROOT / "scripts" / "regresion_empresas.py")]
        if self.project_root is not None:
            args += ["--proyecto", str(self.project_root)]
        try:
            r = subprocess.run(args, cwd=PACKAGE_ROOT, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        except subprocess.TimeoutExpired:
            return False, f"La regresión tardó más de {timeout:.0f} s y se cortó."
        self.audit.record("regresion_empresas", who="panel", ok=r.returncode == 0)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()

    def run_tests(self, timeout: float = 180) -> tuple[bool, str]:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = {**os.environ, "PYTHONPATH": str(PACKAGE_ROOT / "src")}
        started = datetime.now()
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=PACKAGE_ROOT,
                               capture_output=True, text=True, timeout=timeout, env=env, creationflags=flags)
        except subprocess.TimeoutExpired:
            return False, f"Los tests tardaron más de {timeout:.0f} s y se cortaron."
        out = (r.stdout or "") + (r.stderr or "")
        secs = (datetime.now() - started).total_seconds()
        self.audit.record("tests", who="panel", ok=r.returncode == 0, segundos=round(secs, 1))
        return r.returncode == 0, out.strip() or f"pytest terminó con código {r.returncode}"
