"""Cargador: encuentra las brigadas por su `manifest.yaml`, las arma y las monta o desmonta según la instalación.

Dónde busca (sucesor de `raphael_harness.cargador`):
  1. PRODUCCIÓN: paquetes instalados que declaran un entry point en el grupo `raphael.brigades`. El entry point apunta
     al paquete de la brigada (`saludo = "raphael_saludo"`); su `manifest.yaml` va adentro del paquete.
  2. DESARROLLO: carpetas (`dev_dirs` o la variable `RAPHAEL_DEV`, separadas por `;` o `:`). Se busca `manifest.yaml`
     hasta 4 niveles de profundidad. La carpeta del manifiesto (y su `src/` si existe) se agrega a `sys.path`, sin
     instalar nada. No entra en `codigo-actual`, `.venv`, `node_modules` ni carpetas ocultas.
  Si el mismo id aparece en los dos lados, gana el instalado y queda un aviso.

Armar una brigada (`build`) chequea, en este orden, y si algo falla NO se monta (las demás siguen):
  contrato compatible -> edición -> config contra `config_schema` -> cocineros (`entry` = clase Cook) -> jefe
  (`chief` = BrigadeSpec o función que lo devuelve) -> tools con `entry` (función o `Tool`).

`apply()` deja montado exactamente lo que la instalación tiene activo: monta lo que falta, desmonta lo que sobra.
Si la instalación nombra un orquestador (`orchestrator.entry`, 2.1), `apply()` lo arma y lo pone primero; si falla,
queda el orden simple del harness y el error en el reporte (`errors["_orchestrator"]`).

Brigadas creadas por borrador (H6): si el cargador recibe un `DraftStore`, sus brigadas ACTIVAS (firma y hash que
verifican) aparecen como encontradas con origen "draft" y se montan como cualquier otra (al final, porque usan tools de
las demás). Una que deja de verificar se desmonta en el próximo `apply()`.
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib import metadata, resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .contract import CONTRACT_VERSION, Cook, Orchestrator
from .engine import BrigadeSpec
from .installation import BrigadeToggle, save_installation
from .manifest import Manifest, load_manifest, manifest_from
from .tools import Tool, parameters_of

if TYPE_CHECKING:
    from .drafts import DraftStore
    from .runtime import Runtime

GROUP = "raphael.brigades"
ORCHESTRATOR_GROUP = "raphael.orchestrators"
MANIFEST_FILE = "manifest.yaml"
SKIP_DIRS = {"codigo-actual", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".git"}
MAX_DEPTH = 4


class LoadError(Exception):
    """Una brigada que no se puede armar. El mensaje dice por qué, en castellano."""


@dataclass
class Found:
    manifest: Manifest
    source: str                     # "installed" | "folder" | "draft"
    path: Path | None = None        # el manifest.yaml
    roots: tuple[Path, ...] = ()    # lo que se agrega a sys.path para importar sus entries
    chief_factory: Callable[[], BrigadeSpec] | None = None   # borradores: el spec sale del almacén, no de un import

    @property
    def id(self) -> str:
        return self.manifest.id


@dataclass
class Bundle:
    manifest: Manifest
    cooks: dict[str, Cook] = field(default_factory=dict)
    chief: BrigadeSpec | None = None
    tools: list[Tool] = field(default_factory=list)
    setup: Callable[..., Any] | None = None       # registra las tools sin `entry` al montar
    health: Callable[..., Any] | None = None      # healthcheck: al montar y cada 5 min
    warnings: list[str] = field(default_factory=list)


# --- resolver entries ---------------------------------------------------------------------------------------------------
def resolve(entry: str, roots: Iterable[Path] = ()) -> Any:
    """'paquete.modulo:Nombre' (o 'paquete.modulo:Clase.atributo') -> el objeto. LoadError si no existe."""
    for r in roots:
        if str(r) not in sys.path:
            sys.path.insert(0, str(r))
    mod_name, _, attr = entry.partition(":")
    try:
        obj: Any = importlib.import_module(mod_name)
    except Exception as exc:  # noqa: BLE001 - un import roto es un error de ESA brigada
        raise LoadError(f"no se pudo importar '{mod_name}': {type(exc).__name__}: {exc}") from exc
    for part in attr.split("."):
        if not hasattr(obj, part):
            raise LoadError(f"'{mod_name}' no tiene '{attr}'")
        obj = getattr(obj, part)
    return obj


# --- config de la brigada contra su config_schema (subconjunto chico de JSON Schema) -----------------------------------------
_CHECK = {"string": lambda v: isinstance(v, str), "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
          "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
          "boolean": lambda v: isinstance(v, bool), "array": lambda v: isinstance(v, list),
          "object": lambda v: isinstance(v, dict), "null": lambda v: v is None}


def validate_config(schema: dict, data: Any, where: str = "config") -> list[str]:
    """Errores de `data` contra `schema`: type, properties, required, enum, items, additionalProperties, minimum,
    maximum. Un schema vacío acepta todo."""
    if not schema:
        return []
    errors: list[str] = []
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind] if kind else []
    if kinds and not any(_CHECK.get(k, lambda v: True)(data) for k in kinds):
        return [f"{where}: tiene que ser {' o '.join(kinds)}"]
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{where}: tiene que ser uno de {schema['enum']}")
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{where}: mínimo {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{where}: máximo {schema['maximum']}")
    if isinstance(data, dict):
        props = schema.get("properties") or {}
        for req in schema.get("required") or []:
            if req not in data:
                errors.append(f"{where}.{req}: falta")
        for k, v in data.items():
            if k in props:
                errors += validate_config(props[k], v, f"{where}.{k}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{where}.{k}: no está en el esquema")
    if isinstance(data, list) and isinstance(schema.get("items"), dict):
        for i, v in enumerate(data):
            errors += validate_config(schema["items"], v, f"{where}[{i}]")
    return errors


# --- descubrir ----------------------------------------------------------------------------------------------------------
def _walk(root: Path, depth: int = 0) -> Iterable[Path]:
    if depth > MAX_DEPTH or not root.is_dir():
        return
    f = root / MANIFEST_FILE
    if f.is_file():
        yield f
        return   # una brigada no tiene otra adentro
    try:
        children = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return
    for p in children:
        if p.name in SKIP_DIRS or p.name.startswith("."):
            continue
        yield from _walk(p, depth + 1)


def _from_folder(path: Path) -> Found:
    folder = path.parent
    roots = tuple(r for r in (folder / "src", folder) if r.is_dir())
    return Found(load_manifest(path), "folder", path, roots)


def _from_entry_points() -> tuple[list[Found], list[str]]:
    out, warnings = [], []
    for ep in metadata.entry_points(group=GROUP):
        try:
            pkg = ep.value.split(":")[0]
            ref = resources.files(pkg) / MANIFEST_FILE
            if not ref.is_file():
                raise LoadError(f"el paquete {pkg} no trae {MANIFEST_FILE}")
            path = Path(str(ref))
            out.append(Found(load_manifest(path), "installed", path, ()))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"entry point '{ep.name}' ({ep.value}): {exc}")
    return out, warnings


def dev_dirs_from_env() -> list[Path]:
    raw = os.environ.get("RAPHAEL_DEV", "")
    return [Path(p) for p in re.split(r"[;" + os.pathsep + "]", raw) if p.strip()]


def discover(dev_dirs: Iterable[str | Path] = (), *, installed: bool = True) -> tuple[dict[str, Found], list[str]]:
    """({id: Found}, avisos). Un manifiesto roto es un aviso, no un error: las demás brigadas se encuentran igual."""
    found: dict[str, Found] = {}
    warnings: list[str] = []
    if installed:
        eps, w = _from_entry_points()
        warnings += w
        for f in eps:
            found[f.id] = f
    for d in [*map(Path, dev_dirs), *([] if dev_dirs else dev_dirs_from_env())]:
        for path in _walk(Path(d)):
            try:
                f = _from_folder(path)
            except Exception as exc:  # noqa: BLE001 - yaml o esquema inválido
                warnings.append(f"{path}: manifiesto inválido: {str(exc).splitlines()[0][:200]}")
                continue
            if f.id in found:
                prev = found[f.id]
                warnings.append(f"la brigada '{f.id}' aparece dos veces ({prev.path} y {path}): queda "
                                f"{'la instalada' if prev.source == 'installed' else 'la primera'}")
                continue
            found[f.id] = f
    return found, warnings


# --- armar ----------------------------------------------------------------------------------------------------------------
def build(found: Found, *, edition: str, config: dict | None = None) -> Bundle:
    """Instancia lo que declara el manifiesto. LoadError con el primer problema (nada queda a medias)."""
    m = found.manifest
    if not m.supports_contract(CONTRACT_VERSION):
        raise LoadError(f"'{m.id}' pide el contrato {m.contract}; el núcleo es {CONTRACT_VERSION}")
    if edition not in m.editions:
        raise LoadError(f"'{m.id}' no corre en la edición {edition} (solo {', '.join(sorted(m.editions))})")
    errors = validate_config(m.config_schema, config or {})
    if errors:
        raise LoadError(f"'{m.id}': config inválida: " + "; ".join(errors[:6]))
    b = Bundle(m)
    for c in m.cooks:
        cls = resolve(c.entry, found.roots)
        if not (isinstance(cls, type) and issubclass(cls, Cook)):
            raise LoadError(f"'{m.id}': el cocinero '{c.id}' ({c.entry}) no es una clase Cook")
        try:
            b.cooks[c.id] = cls()
        except Exception as exc:  # noqa: BLE001
            raise LoadError(f"'{m.id}': no se pudo crear el cocinero '{c.id}': {exc}") from exc
    if found.chief_factory is not None:
        try:
            b.chief = found.chief_factory()
        except KeyError as exc:
            raise LoadError(f"'{m.id}': el borrador ya no está activo (su aprobación no verifica)") from exc
    elif m.chief:
        spec = resolve(m.chief, found.roots)
        if callable(spec) and not isinstance(spec, BrigadeSpec):
            spec = spec()
        if not isinstance(spec, BrigadeSpec):
            raise LoadError(f"'{m.id}': {m.chief} no es un BrigadeSpec")
        b.chief = spec
    for attr in ("setup", "health"):
        entry = getattr(m, attr)
        if entry:
            fn = resolve(entry, found.roots)
            if not callable(fn):
                raise LoadError(f"'{m.id}': {attr} ({entry}) no es una función")
            setattr(b, attr, fn)
    allowed = {t.name for t in m.tools_for(edition)}
    for t in m.tools:
        if t.entry is None:
            continue
        if t.name not in allowed:
            b.warnings.append(f"{m.id}: la tool '{t.name}' no se carga en la edición {edition}")
            continue
        obj = resolve(t.entry, found.roots)
        if isinstance(obj, Tool):
            b.tools.append(Tool(t.name, obj.fn, obj.description or t.description, obj.parameters))
        elif callable(obj):
            b.tools.append(Tool(t.name, obj, t.description or (inspect.getdoc(obj) or "").split("\n")[0],
                                parameters_of(obj)))
        else:
            raise LoadError(f"'{m.id}': la tool '{t.name}' ({t.entry}) no es una función")
    return b


# --- el cargador sobre un runtime -----------------------------------------------------------------------------------------
class Loader:
    def __init__(self, runtime: Runtime, dev_dirs: Iterable[str | Path] = (), *, installed: bool = True,
                 installation_path: str | Path | None = None, drafts: DraftStore | None = None) -> None:
        self.runtime = runtime
        self.drafts = drafts
        self.installation_path = Path(installation_path) if installation_path else None
        self.dev_dirs = list(dev_dirs)
        self.installed = installed
        self.found: dict[str, Found] = {}
        self.warnings: list[str] = []
        self.errors: dict[str, str] = {}
        self._orchestrator_entry: str | None = None   # el entry del orquestador ya puesto (para no rearmarlo)
        runtime.loader = self                         # el catálogo del runtime suma lo que se puede montar
        self.refresh()

    def refresh(self) -> dict[str, Found]:
        self.found, self.warnings = discover(self.dev_dirs, installed=self.installed)
        self._merge_drafts()
        return self.found

    def non_draft_ids(self) -> set[str]:
        """Ids que un borrador no puede tomar: las brigadas instaladas o en carpeta."""
        return {i for i, f in self.found.items() if f.source != "draft"}

    def _merge_drafts(self) -> None:
        for bid in [i for i, f in self.found.items() if f.source == "draft"]:
            del self.found[bid]
        if self.drafts is None:
            return
        for rec in self.drafts.list():
            bid = rec["draft"]["id"]
            if rec["state"] != "activa":
                continue
            if bid in self.found:
                self.warnings.append(f"el borrador activo '{bid}' choca con una brigada instalada: no se usa")
                continue
            d = rec["draft"]
            manifest = manifest_from({"id": bid, "name": d["name"], "version": "1.0.0", "contract": ">=2.0,<3",
                                      "description": d["purpose"], "chief": "raphael_core.drafts:compile_spec"})
            self.found[bid] = Found(manifest, "draft", chief_factory=lambda i=bid: self.drafts.active_spec(i))

    def catalog(self) -> list[dict]:
        """Lo que se puede montar, para el panel ("Agregar brigadas")."""
        inst = self.runtime.installation
        out = []
        for bid, f in sorted(self.found.items()):
            m = f.manifest
            out.append({"id": bid, "name": m.name, "version": m.version, "description": m.description,
                        "source": f.source, "mounted": bid in self.runtime.brigades,
                        "active": bid in inst.active_brigades(), "chief": bool(m.chief),
                        "cooks": [c.id for c in m.cooks], "tools": [t.name for t in m.tools_for(inst.edition)],
                        "editions": sorted(m.editions), "compatible": m.supports_contract(CONTRACT_VERSION),
                        "error": self.errors.get(bid)})
        return out

    async def mount(self, brigade: str) -> list[str]:
        f = self.found.get(brigade)
        if f is None:
            raise LoadError(f"no encontré la brigada '{brigade}' (¿falta su manifest.yaml?)")
        inst = self.runtime.installation
        try:
            b = build(f, edition=inst.edition, config=inst.brigade_config(brigade))
            notes = await self.runtime.mount(b.manifest, b.cooks, chief=b.chief, tools=b.tools, setup=b.setup,
                                             health=b.health)
        except Exception as exc:
            self.errors[brigade] = str(exc)
            self.runtime.audit.record("brigada_no_montada", who="cargador", brigada=brigade, error=str(exc)[:300])
            raise
        self.errors.pop(brigade, None)
        return b.warnings + notes

    async def _try_mount(self, bid: str, report: dict) -> None:
        try:
            report["warnings"] += await self.mount(bid)
            report["mounted"].append(bid)
        except Exception as exc:  # noqa: BLE001
            report["errors"][bid] = str(exc)

    async def unmount(self, brigade: str, export: bool = True) -> dict:
        return await self.runtime.unmount(brigade, export=export)

    async def set_active(self, brigade: str, active: bool) -> dict:
        """Activa o desactiva una brigada en la instalación (lo que hace "Agregar brigadas" del panel), la monta o
        desmonta y guarda la instalación si hay ruta. Si montar falla, la brigada vuelve a quedar inactiva."""
        self._merge_drafts()
        if active and brigade not in self.found:
            raise LoadError(f"no encontré la brigada '{brigade}'")
        inst = self.runtime.installation
        prev = inst.brigades.get(brigade)
        inst.brigades[brigade] = BrigadeToggle(active=active, config=dict(prev.config) if prev else {})
        try:
            report = await self.apply()
        finally:
            if active and brigade in self.errors:
                inst.brigades[brigade] = BrigadeToggle(active=False, config=dict(prev.config) if prev else {})
            self.runtime.audit.record("brigada_activada" if active else "brigada_desactivada", who="usuario",
                                      brigada=brigade, error=self.errors.get(brigade))
            if self.installation_path:
                save_installation(inst, self.installation_path)
        return report

    def _orchestrator_roots(self) -> list[Path]:
        roots: list[Path] = []
        for d in [*self.dev_dirs, *dev_dirs_from_env()]:
            p = Path(d)
            roots += [p, p / "src"] if (p / "src").is_dir() else [p]
        return roots

    def build_orchestrator(self, entry: str, config: dict | None = None) -> Orchestrator:
        """Arma el orquestador: 'paquete.modulo:Clase' o el nombre de un entry point de `raphael.orchestrators`."""
        if ":" not in entry:
            eps = [ep for ep in metadata.entry_points(group=ORCHESTRATOR_GROUP) if ep.name == entry]
            if not eps:
                raise LoadError(f"no hay un orquestador instalado con el nombre '{entry}' (grupo {ORCHESTRATOR_GROUP})")
            try:
                cls = eps[0].load()
            except Exception as exc:  # noqa: BLE001
                raise LoadError(f"no se pudo cargar el orquestador '{entry}': {type(exc).__name__}: {exc}") from exc
        else:
            cls = resolve(entry, self._orchestrator_roots())
        if not (isinstance(cls, type) and issubclass(cls, Orchestrator)):
            raise LoadError(f"'{entry}' no es una clase Orchestrator")
        try:
            orch = cls()
            orch.configure(dict(config or {}))
        except Exception as exc:  # noqa: BLE001
            raise LoadError(f"no se pudo crear el orquestador '{entry}': {type(exc).__name__}: {exc}") from exc
        return orch

    def apply_orchestrator(self) -> str | None:
        """Pone el orquestador que pide la instalación (si cambió). Devuelve el error, o None."""
        ref = self.runtime.installation.orchestrator
        if ref is None:
            if self._orchestrator_entry is not None:   # la instalación ya no pide uno: vuelve el orden simple
                self.runtime.set_orchestrator(None)
                self._orchestrator_entry = None
            return None
        if ref.entry == self._orchestrator_entry and self.runtime.orchestrator is not None:
            return None
        try:
            orch = self.build_orchestrator(ref.entry, ref.config)
        except LoadError as exc:
            self.errors["_orchestrator"] = str(exc)
            self.runtime.audit.record("orquestador_no_montado", who="cargador", entry=ref.entry, error=str(exc)[:300])
            return str(exc)
        self.runtime.set_orchestrator(orch)
        self._orchestrator_entry = ref.entry
        self.errors.pop("_orchestrator", None)
        return None

    async def apply(self) -> dict:
        """Deja montado lo activo en la instalación. Una brigada que falla no frena a las otras."""
        self._merge_drafts()
        report: dict[str, Any] = {"mounted": [], "unmounted": [], "errors": {}, "warnings": list(self.warnings)}
        orch_error = self.apply_orchestrator()
        if orch_error:
            report["errors"]["_orchestrator"] = orch_error
        active = self.runtime.installation.active_brigades()
        stale = [b for b in self.runtime.brigades if b not in active or b not in self.found]
        for bid in stale:
            await self.unmount(bid)
            report["unmounted"].append(bid)
            if bid in active:
                self.errors[bid] = report["errors"][bid] = "dejó de estar disponible (¿borrador desactivado?)"
        # primero las que no son borradores; después se revisan los borradores (usan tools que registran las demás)
        pending = [b for b in active if b not in self.runtime.brigades and b not in report["errors"]]
        first = [b for b in pending if b in self.found and self.found[b].source != "draft"]
        for bid in first:
            await self._try_mount(bid, report)
        self._merge_drafts()
        for bid in [b for b in pending if b not in first]:
            await self._try_mount(bid, report)
        return report
