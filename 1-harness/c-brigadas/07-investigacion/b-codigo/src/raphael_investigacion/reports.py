"""Grafo (métricas simples, sin dependencias) e informes del caso en Markdown, HTML o JSON.

El informe separa SIEMPRE lo confirmado de lo pendiente: lo que propuso un modelo o una regla y nadie confirmó va aparte y
marcado como no verificado. Cada nodo dice de qué artefacto (con su hash) y por qué vía (parser, modelo, manual) sale.
PDF: el HTML está pensado para imprimirse a PDF desde el navegador (no se suma una librería de PDF).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .casefile import CaseError, Cases
from .entities import Entities
from .timeline import build_timeline


def graph_metrics(nodes: list[dict], edges: list[dict], top: int = 10) -> dict:
    """Grados, componentes conexas y los nodos más conectados. Solo lo vivo (sin retractados)."""
    ids = {n["id"]: n for n in nodes}
    deg: dict[str, int] = dict.fromkeys(ids, 0)
    parent = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        if e["src"] in ids and e["dst"] in ids:
            deg[e["src"]] += 1
            deg[e["dst"]] += 1
            parent[find(e["src"])] = find(e["dst"])
    comps: dict[str, int] = {}
    for i in ids:
        comps[find(i)] = comps.get(find(i), 0) + 1
    ranked = sorted(deg.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    return {"nodes": len(ids), "edges": len(edges), "components": len(comps), "largest_component": max(comps.values(), default=0),
            "top_degree": [{"id": i, "tipo": ids[i]["tipo"], "label": label(ids[i]), "degree": d} for i, d in ranked if d]}


def label(node: dict) -> str:
    c = node["campos"]
    for k in ("etiqueta", "nombre", "ip_o_dominio", "handle", "descripcion", "contraparte"):
        if c.get(k):
            return str(c[k])[:80]
    return node["id"]


def neighbors(nodes: list[dict], edges: list[dict], node_id: str) -> list[dict]:
    by_id = {n["id"]: n for n in nodes}
    out = []
    for e in edges:
        other = e["dst"] if e["src"] == node_id else e["src"] if e["dst"] == node_id else None
        if other and other in by_id:
            out.append({"edge": e["tipo"], "node": other, "tipo": by_id[other]["tipo"], "label": label(by_id[other]),
                        "artefacto_origen": e["artefacto_origen"], "origen": e["origen"]})
    return out


class Reports:
    def __init__(self, cases: Cases) -> None:
        self.c = cases
        self.ent = Entities(cases)

    def graph(self, case: str) -> dict:
        return graph_metrics(self.c.nodes(case), self.c.edges(case))

    def timeline(self, case: str, gap_hours: float = 24.0) -> dict:
        return build_timeline(self.c.nodes(case, tipo="Evento"), gap_hours=gap_hours)

    def data(self, case: str) -> dict:
        info = self.c.get(case)
        nodes = self.c.nodes(case)
        origin_of: dict[str, list[dict]] = {}
        for e in self.c.edges(case):
            if e["tipo"] == "aparece_en":
                origin_of.setdefault(e["src"], []).append({"artefacto": e["artefacto_origen"], "origen": e["origen"],
                                                           "confianza": e["confianza"]})
        entities = [{"id": n["id"], "tipo": n["tipo"], "label": label(n), "campos": n["campos"],
                     "procedencia": origin_of.get(n["id"], [])} for n in nodes if n["tipo"] not in ("Archivo", "Evento")]
        return {"caso": {k: info[k] for k in ("id", "title", "description", "created_at", "status")},
                "generado": self.c.env.iso(), "artefactos": [{k: a[k] for k in ("sha256", "name", "size", "mime", "added_at")}
                                                             for a in self.c.artifacts(case)],
                "entidades": entities, "linea_de_tiempo": self.timeline(case), "grafo": self.graph(case),
                "fusiones_confirmadas": [f for f in self.ent.fusions(case, "confirmado")],
                "pendientes": {"propuestas": self.ent.proposals(case, "pendiente"), "fusiones": self.ent.fusions(case, "pendiente")},
                "retractado": [{"id": n["id"], "tipo": n["tipo"], "motivo": n.get("retracted_reason")}
                               for n in self.c.nodes(case, retracted=True) if n["retracted"]],
                "registro": self.c.verify_log(case)}

    def render(self, case: str, fmt: str = "md") -> str:
        d = self.data(case)
        if fmt == "json":
            return json.dumps(d, ensure_ascii=False, indent=2)
        md = self._markdown(d)
        if fmt == "md":
            return md
        if fmt == "html":
            return self._html(md, d["caso"]["title"])
        raise CaseError("formatos de informe: md, html o json")

    def export(self, case: str, fmt: str = "md") -> dict:
        text = self.render(case, fmt)
        folder = self.c.env.config.reports_dir
        if not folder:
            return {"path": "", "format": fmt, "text": text, "aviso": "no hay `reports_dir` configurada: el informe no se guardó en disco"}
        out = Path(folder)
        out.mkdir(parents=True, exist_ok=True)
        stamp = self.c.env.iso().replace(":", "").replace("-", "")
        path = out / f"{case}-{stamp}.{fmt}"
        path.write_text(text, encoding="utf-8")
        self.c.log(case, "exportar_informe", {"path": str(path), "format": fmt}, "persona")
        return {"path": str(path), "format": fmt, "chars": len(text)}

    @staticmethod
    def _markdown(d: dict) -> str:
        c, lines = d["caso"], []
        w = lines.append
        w(f"# Informe del caso: {c['title']}")
        w(f"\nCaso `{c['id']}` · estado {c['status']} · generado {d['generado']}")
        if c["description"]:
            w(f"\n{c['description']}")
        reg = d["registro"]
        w(f"\n**Registro de operaciones:** {reg['entries']} entradas, {'cadena íntegra' if reg['ok'] else 'CADENA ROTA: ' + reg['problem']}"
          f"{', firmado' if reg['signed'] else ', sin firma (falta INVESTIGACION_LOG_KEY)'}.")
        w("\n## Artefactos (evidencia entregada)")
        w("\n" + ("\n".join(f"- `{a['sha256']}` · {a['name']} · {a['size']} bytes · ingresado {a['added_at']}" for a in d["artefactos"])
                  or "_Sin artefactos._"))
        w("\n## Entidades confirmadas")
        if not d["entidades"]:
            w("\n_Ninguna._")
        for e in d["entidades"]:
            src = ", ".join(f"{p['origen']} ← `{p['artefacto'][:12]}…` (confianza {p['confianza']:.2f})" for p in e["procedencia"]) \
                or "sin artefacto de origen directo"
            w(f"- **{e['tipo']}** {e['label']} — {src}")
        if d["fusiones_confirmadas"]:
            w("\n## Identidades vinculadas (`mismo_que`)")
            for f in d["fusiones_confirmadas"]:
                w(f"- `{f['a']}` = `{f['b']}` — {f['razon']}")
        tl = d["linea_de_tiempo"]
        w("\n## Línea de tiempo")
        w(f"\n{len(tl['events'])} eventos" + (f", del {tl['first']} al {tl['last']}" if tl["first"] else "") + ".")
        for e in tl["events"][:200]:
            w(f"- {e['at']} — {e['text'][:160]}")
        if len(tl["events"]) > 200:
            w(f"- … y {len(tl['events']) - 200} más (ver el JSON)")
        for g in tl["gaps"]:
            w(f"- ⚠ hueco de {g['hours']} h entre {g['from']} y {g['to']}")
        g = d["grafo"]
        w(f"\n## Grafo\n\n{g['nodes']} nodos, {g['edges']} aristas, {g['components']} componentes (la mayor con "
          f"{g['largest_component']}).")
        for t in g["top_degree"]:
            w(f"- {t['tipo']} {t['label']}: {t['degree']} conexiones")
        pend = d["pendientes"]
        w("\n## Pendiente de confirmación (NO verificado)")
        if not pend["propuestas"] and not pend["fusiones"]:
            w("\n_Nada pendiente._")
        for p in pend["propuestas"]:
            w(f"- `{p['id']}` ({p['origen']}) {p['node']['tipo']}: {json.dumps(p['node']['campos'], ensure_ascii=False)[:160]}"
              f" — «{p['texto_fuente'][:100]}» · confianza {p['confianza_extraccion']:.2f}")
        for f in pend["fusiones"]:
            w(f"- `{f['id']}` posible fusión `{f['a']}` / `{f['b']}`: {f['razon']}")
        if d["retractado"]:
            w("\n## Retractado")
            for r in d["retractado"]:
                w(f"- `{r['id']}` ({r['tipo']}): {r['motivo']}")
        w("\n---\n_Lo no confirmado no es un hallazgo. Cada dato confirmado se rastrea hasta un artefacto con su hash._")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _html(md: str, title: str) -> str:
        body = []
        in_list = False
        for ln in md.splitlines():
            safe = html.escape(ln)
            if ln.startswith("- "):
                if not in_list:
                    body.append("<ul>")
                    in_list = True
                body.append(f"<li>{safe[2:]}</li>")
                continue
            if in_list:
                body.append("</ul>")
                in_list = False
            if ln.startswith("## "):
                body.append(f"<h2>{safe[3:]}</h2>")
            elif ln.startswith("# "):
                body.append(f"<h1>{safe[2:]}</h1>")
            elif ln.strip() and ln.strip() != "---":
                body.append(f"<p>{safe}</p>")
        if in_list:
            body.append("</ul>")
        css = "body{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem}li{margin:.2rem 0}"
        return (f"<!doctype html><html lang='es'><meta charset='utf-8'><title>{html.escape(title)}</title>"
                f"<style>{css}</style><body>{''.join(body)}</body></html>")
