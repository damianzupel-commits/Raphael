"""Suite de contrato y matriz de montaje: lo que toda brigada tiene que pasar para montarse en Raphael.

`run_contract_suite(ruta_al_manifest)` corre, sin red y sin modelos, los chequeos de DISENO-V2 §3.8:
  manifiesto válido · contrato compatible · corre en la edición · se arma (entries que existen, config válida) ·
  salud · se monta · setup registra sus tools · comandos y tools declarados (aviso) · solo ve su espacio ·
  sin imports de brigadas hermanas (AST) · contesta mensajes de prueba sin
  romper · solo pide acciones declaradas · NADA con aprobación o humano se ejecuta sin OK · el jefe (si tiene) reporta
  un contrato válido · en la nube no carga nada peligroso · se desmonta limpio (sin tools, políticas, suscripciones
  ni datos que el manifiesto mande borrar) · se puede volver a montar.

`run_matrix(brigadas)` arma la matriz: todas, cada una apagada, cada una sola y ninguna. En cada combinación monta,
recibe un mensaje, corre un tick, pide el estado y desmonta todo. Una combinación que rompe es un fallo con detalle.

Las dos devuelven resultados (no lanzan): la brigada los convierte en asserts en sus tests y el panel los muestra.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contract import CONTRACT_VERSION, Level
from ..engine import InternalReport
from ..installation import installation_from
from ..loader import Found, LoadError, build, discover
from ..manifest import load_manifest
from ..runtime import Runtime
from .ast_imports import find_cross_imports
from .clock import Clock

DEFAULT_MESSAGES = ("hola", "¿qué hacen?", "quiero un regalo", "")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SuiteResult:
    brigade: str
    edition: str
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def text(self) -> str:
        lines = [f"Suite de contrato · {self.brigade} · edición {self.edition}: {'OK' if self.ok else 'FALLA'}"]
        lines += [f"  {'✓' if c.ok else '✗'} {c.name}" + (f" — {c.detail}" if c.detail else "") for c in self.checks]
        return "\n".join(lines)


def packages_of(found: Found) -> set[str]:
    """Los paquetes de nivel superior de una brigada (carpetas con __init__.py en sus raíces)."""
    roots = found.roots or ((found.path.parent,) if found.path else ())
    return {p.name for r in roots if r.is_dir() for p in r.iterdir() if (p / "__init__.py").is_file()}


def _runtime(edition: str, brigade: str, config: dict | None) -> Runtime:
    inst = installation_from({"id": "suite", "edition": edition, "identity": {"assistant": "Raphael", "user": "Damian"},
                              "brigades": {brigade: {"active": True, "config": config or {}}}})
    return Runtime(inst, clock=Clock())


def _found(manifest: str | Path | Found) -> Found:
    if isinstance(manifest, Found):
        return manifest
    path = Path(manifest)
    if path.is_dir():
        path = path / "manifest.yaml"
    folder = path.parent
    return Found(load_manifest(path), "folder", path, tuple(r for r in (folder / "src", folder) if r.is_dir()))


def run_contract_suite(manifest: str | Path | Found, *, edition: str = "personal", config: dict | None = None,
                       messages: Iterable[str] = DEFAULT_MESSAGES, siblings: Iterable[str] = ()) -> SuiteResult:
    """`siblings`: paquetes de las OTRAS brigadas (para el chequeo AST). Ver `packages_of`."""
    checks: list[Check] = []
    name = str(manifest)

    def check(label: str, ok: bool, detail: str = "") -> bool:
        checks.append(Check(label, bool(ok), detail))
        return bool(ok)

    # 1-3: manifiesto, contrato, edición
    try:
        found = _found(manifest)
    except Exception as exc:  # noqa: BLE001
        check("manifiesto válido", False, str(exc).splitlines()[0][:300])
        return SuiteResult(name, edition, checks)
    m = found.manifest
    result = SuiteResult(m.id, edition, checks)
    check("manifiesto válido", True, f"{m.id} {m.version}")
    if not check("contrato compatible", m.supports_contract(CONTRACT_VERSION), f"pide {m.contract}, núcleo {CONTRACT_VERSION}"):
        return result
    if not check("corre en la edición", edition in m.editions, f"ediciones: {', '.join(sorted(m.editions))}"):
        return result

    # imports de hermanas (no necesita montar)
    others = set(siblings) - packages_of(found)
    if others:
        crossed = [x for r in (found.roots or (found.path.parent,)) for x in find_cross_imports(r, others)]
        check("sin imports de brigadas hermanas", not crossed,
              "; ".join(f"{c.file}:{c.line} importa {c.imported}" for c in crossed[:5]) if crossed else f"revisadas: "
              f"{', '.join(sorted(others))}")
    else:
        check("sin imports de brigadas hermanas", True, "no hay hermanas para comparar")

    # 4: se arma
    try:
        bundle = build(found, edition=edition, config=config)
    except LoadError as exc:
        check("se arma (entries y config)", False, str(exc))
        return result
    check("se arma (entries y config)", True, f"{len(bundle.cooks)} cocineros, jefe: {'sí' if bundle.chief else 'no'}, "
                                              f"{len(bundle.tools)} tools")

    rt = _runtime(edition, m.id, config)
    try:
        notes = rt.run(rt.mount(m, bundle.cooks, chief=bundle.chief, tools=bundle.tools, setup=bundle.setup,
                                health=bundle.health))
    except Exception as exc:  # noqa: BLE001
        check("se monta", False, str(exc))
        return result
    check("se monta", True, "; ".join(notes)[:300])

    # salud (el runtime ya corrió el healthcheck del manifiesto al montar)
    cook_ids = list(bundle.cooks)
    bad = []
    health = rt.status()["brigades"][m.id]["health"]
    if health is not None and not health["ok"]:
        bad.append(f"manifiesto: {health['detail']}")
    for cid, cook in bundle.cooks.items():
        try:
            h = cook.health(rt.context(m.id, cid))
            if not h.ok:
                bad.append(f"{cid}: {h.detail}")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{cid}: {exc}")
    check("salud", not bad, "; ".join(bad))

    # tools sin `entry`: las tiene que registrar su setup
    no_entry = [t.name for t in m.tools_for(edition) if t.entry is None]
    if no_entry:
        missing = [n for n in no_entry if rt.tools.get(n) is None]
        check("setup registra sus tools", not missing, ("faltan: " + ", ".join(missing)) if missing else
              ", ".join(no_entry))
    undeclared_tools = [t["name"] for t in rt.tools.list() if t["owner"] == m.id and t["name"] not in
                        {x.name for x in m.tools}]

    # comandos: los que ofrecen los cocineros tendrían que estar en el manifiesto (si no, se aceptan con aviso)
    offered = {c for cook in bundle.cooks.values() for c in (getattr(cook, "commands", None) or {})}
    undeclared_cmds = sorted(offered - set(m.commands))
    detail = []
    if undeclared_cmds:
        detail.append("comandos no declarados (el orquestador no los puede usar): " + ", ".join(undeclared_cmds))
    if undeclared_tools:
        detail.append("tools no declaradas (piden aprobación en cada uso): " + ", ".join(undeclared_tools))
    reads = sorted(c for c, spec in m.commands.items() if spec.read)
    check("comandos y tools declarados", True, "; ".join(detail) or (f"de lectura: {', '.join(reads)}" if reads else ""))

    # espacio propio
    wrong = [f"{cid}: {s.name}" for cid in cook_ids for s in (rt.context(m.id, cid).data, rt.context(m.id, cid).shared)
             if not (s.name == m.space or s.name.startswith(m.space + "/"))]
    check("solo ve su espacio", not wrong, "; ".join(wrong) if wrong else f"espacio '{m.space}'")

    # mensajes de prueba
    errors = []
    if cook_ids:
        for i, text in enumerate(messages):
            try:
                rt.run(rt.receive("prueba", f"suite-{i}", text, name="Suite"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{text!r}: {type(exc).__name__}: {exc}")
        failing = rt.audit.entries("evento_fallido") + rt.audit.entries("pieza_caida")
        errors += [f"{e['who']}: {e.get('error') or e.get('why', '')}"[:200] for e in failing]
        errors += [f"{cid}: {why}"[:200] for cid in cook_ids for why in rt.guard.history(f"{m.id}/{cid}")]
        check("contesta mensajes de prueba sin romper", not errors, "; ".join(errors[:4]))

        undeclared = sorted({e.get("tipo") for e in rt.audit.entries("accion")} - set(m.actions))
        check("solo pide acciones declaradas", not undeclared, ", ".join(str(u) for u in undeclared))

    # nada con aprobación o humano sin OK (acciones y tools)
    auto: dict[str, int] = {}
    for e in rt.audit.entries("accion"):
        if e.get("nivel") == Level.AUTO.value:
            auto[e["tipo"]] = auto.get(e["tipo"], 0) + 1
    executed: dict[str, int] = {}
    for e in rt.audit.entries("accion_ejecutada"):
        executed[e["tipo"]] = executed.get(e["tipo"], 0) + 1
    leaked = [f"{t} ({n} ejecutadas, {auto.get(t, 0)} automáticas)" for t, n in executed.items() if n > auto.get(t, 0)]
    pending = rt.approvals.list()
    check("nada con aprobación se ejecuta sin OK", not leaked,
          "; ".join(leaked) if leaked else f"{len(pending)} pendientes esperando a una persona")

    # el jefe
    if bundle.chief is not None:
        try:
            rep = rt.run(rt.ask(m.id, "prueba de la suite de contrato"))
            ok = isinstance(rep, InternalReport) and InternalReport.validate(rep.to_dict()) == rep
            check("el jefe reporta con el contrato", ok, "degradado (sin modelo), como se espera" if rep.degraded else "")
        except Exception as exc:  # noqa: BLE001
            check("el jefe reporta con el contrato", False, str(exc))
        missing = sorted({t for h in bundle.chief.helpers for t in h.tools} - set(rt.tools.names()))
        allowed_missing = {t.name for t in m.tools} - {t.name for t in m.tools_for(edition)}
        check("los efímeros tienen sus tools", set(missing) <= allowed_missing, ", ".join(missing))

    # nube
    if "cloud" in m.editions:
        try:
            cloud = build(found, edition="cloud", config=config)
            risky = {t.name for t in m.tools if t.dangerous or t.active_scan} & {t.name for t in cloud.tools}
            check("en la nube no carga nada peligroso", not risky, ", ".join(sorted(risky)))
        except LoadError as exc:
            check("en la nube no carga nada peligroso", False, str(exc))

    # desmontar limpio y volver a montar
    try:
        rt.run(rt.unmount(m.id))
        left = []
        if m.id in rt.brigades:
            left.append("sigue montada")
        if any(t["owner"] == m.id for t in rt.tools.list()):
            left.append("quedaron tools")
        if any(r["brigade"] == m.id for r in rt.policy.table()):
            left.append("quedaron políticas")
        if any(o.startswith(m.id + "/") for o in rt.bus.owners()):
            left.append("quedaron suscripciones")
        if m.uninstall.delete and rt.store.space(m.space).export(list(m.uninstall.delete)):
            left.append(f"quedaron datos de {', '.join(m.uninstall.delete)}")
        check("se desmonta limpio", not left, "; ".join(left))
        again = build(found, edition=edition, config=config)
        rt.run(rt.mount(m, again.cooks, chief=again.chief, tools=again.tools, setup=again.setup, health=again.health))
        rt.run(rt.unmount(m.id))
        check("se puede volver a montar", True)
    except Exception as exc:  # noqa: BLE001
        check("se desmonta limpio y se vuelve a montar", False, str(exc))
    return result


# --- matriz ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class MatrixRow:
    label: str
    brigades: tuple[str, ...]
    ok: bool
    detail: str = ""


def combinations(ids: list[str]) -> list[tuple[str, tuple[str, ...]]]:
    """Todas · cada una apagada · cada una sola · ninguna (sin repetir conjuntos)."""
    ids = sorted(ids)
    out: list[tuple[str, tuple[str, ...]]] = [("todas", tuple(ids))]
    out += [(f"sin {b}", tuple(x for x in ids if x != b)) for b in ids]
    out += [(f"solo {b}", (b,)) for b in ids]
    out.append(("ninguna", ()))
    seen, unique = set(), []
    for label, combo in out:
        if combo not in seen:
            seen.add(combo)
            unique.append((label, combo))
    return unique


def run_matrix(founds: dict[str, Found] | Iterable[str | Path], *, edition: str = "personal",
               configs: dict[str, dict] | None = None, message: str = "hola") -> list[MatrixRow]:
    if not isinstance(founds, dict):
        found_map: dict[str, Found] = {}
        for d in founds:
            fs, _ = discover([d], installed=False)
            found_map.update(fs)
        founds = found_map
    configs = configs or {}
    rows = []
    usable = [b for b, f in founds.items() if edition in f.manifest.editions]
    for label, combo in combinations(usable):
        inst = installation_from({"id": "matriz", "edition": edition,
                                  "brigades": {b: {"active": True, "config": configs.get(b, {})} for b in combo}})
        rt = Runtime(inst, clock=Clock())
        problems: list[str] = []
        try:
            for b in combo:
                bundle = build(founds[b], edition=edition, config=configs.get(b))
                rt.run(rt.mount(bundle.manifest, bundle.cooks, chief=bundle.chief, tools=bundle.tools,
                                setup=bundle.setup, health=bundle.health))
            rt.run(rt.receive("prueba", "matriz", message, name="Matriz"))
            rt.run(rt.tick())
            status: Any = rt.status()
            problems += [f"{b}/{c}: {why}"[:160] for b in combo for c in rt.brigades[b].cooks
                         for why in rt.guard.history(f"{b}/{c}")]
            if sorted(status["brigades"]) != sorted(combo):
                problems.append(f"el estado muestra {sorted(status['brigades'])}")
            for b in combo:
                rt.run(rt.unmount(b))
            problems += [f"{e['who']}: {e.get('error', '')}"[:160] for e in
                         rt.audit.entries("evento_fallido") + rt.audit.entries("pieza_caida")]
            if rt.brigades:
                problems.append("quedaron brigadas montadas")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{type(exc).__name__}: {exc}"[:300])
        rows.append(MatrixRow(label, combo, not problems, "; ".join(problems)))
    return rows


def matrix_text(rows: list[MatrixRow]) -> str:
    return "\n".join(f"  {'✓' if r.ok else '✗'} {r.label:<24} [{', '.join(r.brigades) or '—'}]"
                     + (f" — {r.detail}" if r.detail else "") for r in rows)


__all__ = ["Check", "DEFAULT_MESSAGES", "MatrixRow", "SuiteResult", "combinations", "matrix_text", "packages_of",
           "run_contract_suite", "run_matrix"]
