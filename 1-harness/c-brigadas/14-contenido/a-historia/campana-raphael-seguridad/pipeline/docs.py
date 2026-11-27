# -*- coding: utf-8 -*-
"""Genera GUIONES.md (los 20 guiones) y casos.json a partir de casos_*.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from casos_1 import CASOS_1
from casos_2 import CASOS_2
from build import CIERRE
SEC = [("gancho", "Gancho (0-5 s)"), ("caso", "El caso real"), ("problema", "El problema"), ("solucion", "La solución")]
out = ["# Raphael Seguridad: 20 guiones de IA y ciberseguridad\n",
 "Formato vertical 9:16, 45-90 s, español. Cada video: gancho, caso real, problema y solución. Todos los datos salen de las fuentes enlazadas en cada guion; no se agregó nada que esas fuentes no respalden.\n",
 "**Estado:** borradores. Nada se publicó. Publicar necesita la aprobación de Damian.\n",
 "## Índice\n"] + [f"{c['n']}. {c['titulo']}" for c in CASOS_1 + CASOS_2] + [""]
for c in CASOS_1 + CASOS_2:
    out.append(f"\n---\n\n## {c['n']}. {c['titulo']}\n")
    for k, et in SEC:
        out.append(f"**{et}**  \n*Texto en pantalla:* `{c['pantalla'][k]}`\n")
        out.append(" ".join(c[k]) + "\n")
    out.append(f"**Cierre:** {CIERRE}\n")
    out.append(f"**Descripción:** {c['descripcion']}\n\n**Hashtags:** {c['hashtags']}\n")
    out.append("**Fuentes:**\n" + "\n".join(f"- [{t}]({u})" for t, u in c['fuentes']) + "\n")
open(sys.argv[1], "w").write("\n".join(out))
json.dump(CASOS_1 + CASOS_2, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
