"""Revisa un vault ANTES de conectarlo al Cerebro. Solo lee: no escribe, no borra, no llama a ningún modelo.

Uso (desde cualquier carpeta; necesita las dependencias de la brigada: pyyaml y pydantic):
    python revisar_vault.py "C:\\Users\\dam\\Vault-Fenix"
    python revisar_vault.py "C:\\Users\\dam\\Vault-Fenix" --sensibles "02-Fénix,07-Conciencia,01-Bitácora"

Dice cuántas notas va a leer la brigada y en qué carpetas, cuáles saltea (sistema de Obsidian, plantillas, ilegibles),
cuántas pasan el tope de texto a embeber, qué carpetas quedarían marcadas como sensibles (sin bloquearlas) y cuántas
notas hay que embeber. No muestra el contenido de ninguna nota.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "b-codigo" / "src"))

from raphael_memoria.brain import EMBED_MAX_CHARS, embedding_text
from raphael_memoria.config import MemoriaConfig
from raphael_memoria.vault import Vault


def revisar(root: Path, sensibles: list[str], excluidas: list[str]) -> dict:
    vault = Vault(root, excluded_dirs=excluidas)
    notas = vault.list_notes()
    todos = [p for p in root.rglob("*.md") if p.is_file()]
    por_carpeta: dict[str, int] = {}
    largas = 0
    for n in notas:
        por_carpeta[n.folder] = por_carpeta.get(n.folder, 0) + 1
        if len(f"{n.title}\n{n.category}\n{' '.join(n.tags)}\n{n.content}") > EMBED_MAX_CHARS:
            largas += 1
    leidos = {(root / f"{n.id}.md").resolve() for n in notas}
    salteadas = [p for p in todos if p.resolve() not in leidos]
    sistema = [p for p in salteadas if any(part.startswith((".", "_")) for part in p.relative_to(root).parts[:-1])]
    ilegibles = [p for p in salteadas if p not in sistema and p.relative_to(root).parts[0] not in set(excluidas)]
    marcadas = {d: por_carpeta.get(d, 0) for d in sensibles}
    return {"notas": len(notas), "por_carpeta": dict(sorted(por_carpeta.items())), "archivos_md": len(todos),
            "salteados_de_sistema": len(sistema), "salteados_por_excluidos": len(salteadas) - len(sistema) - len(ilegibles),
            "ilegibles": [p.relative_to(root).as_posix() for p in ilegibles], "mas_largas_que_el_tope": largas,
            "sensibles": marcadas, "sensibles_inexistentes": [d for d, n in marcadas.items() if n == 0],
            "a_embeber": len(notas), "tope_caracteres": EMBED_MAX_CHARS, "muestra_texto": len(embedding_text(notas[0])) if notas else 0}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vault", help="carpeta del vault (Obsidian)")
    ap.add_argument("--sensibles", default="", help="carpetas a marcar como sensibles, separadas por coma")
    ap.add_argument("--excluidas", default="", help="carpetas que no se leen, separadas por coma")
    a = ap.parse_args(argv)
    root = Path(a.vault).expanduser()
    if not root.is_dir():
        print(f"No existe la carpeta: {root}")
        return 2
    MemoriaConfig()  # falla acá, y no a mitad del chequeo, si falta una dependencia de la brigada
    r = revisar(root, [d.strip() for d in a.sensibles.split(",") if d.strip()], [d.strip() for d in a.excluidas.split(",") if d.strip()])
    print(f"Vault: {root}\nNotas que va a leer Memoria: {r['notas']} (de {r['archivos_md']} archivos .md)")
    for carpeta, n in r["por_carpeta"].items():
        marca = "  [sensible: marcada, no bloqueada]" if carpeta in r["sensibles"] else ""
        print(f"  {carpeta}: {n}{marca}")
    print(f"Salteados: {r['salteados_de_sistema']} de sistema o plantillas (carpetas que empiezan con . o _), "
          f"{r['salteados_por_excluidos']} por carpeta excluida, {len(r['ilegibles'])} ilegibles")
    for p in r["ilegibles"][:20]:
        print(f"  no se pudo leer: {p}")
    print(f"Notas más largas que el tope de {r['tope_caracteres']} caracteres (se embebe solo el comienzo): {r['mas_largas_que_el_tope']}")
    for d in r["sensibles_inexistentes"]:
        print(f"Aviso: la carpeta marcada como sensible «{d}» no tiene notas (¿se escribe distinto?)")
    print(f"Notas a embeber con el modelo local: {r['a_embeber']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
