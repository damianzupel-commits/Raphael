"""CLI de Raphael Scout — correrlo solo, fuera del monolito/FastAPI.

    cd backend
    python -m scout "investigá el estado de los LLM locales en 2026"

Sin argumentos entra en modo interactivo (un tema por línea, Ctrl-C para salir).
Imprime arriba a qué modelo/endpoint está apuntando Scout (BYOM), para confirmar
de un vistazo si estás usando, por ejemplo, tu Groq free o el modelo local.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from .config import load_scout_config
from .engine import run_scout
from .identity import SCOUT_NAME


def _banner() -> None:
    cfg = load_scout_config()
    print(f"── {SCOUT_NAME} ──")
    print(f"   modelo:  {cfg.model}")
    print(f"   endpoint:{cfg.base_url}")
    print(f"   captura: {cfg.capture_dir}")
    print("─" * 24)


async def _run_one(topic: str) -> None:
    text, _ = await run_scout(topic)
    print("\n" + text + "\n")


async def _interactive() -> None:
    print("Modo interactivo. Escribí un tema y Enter (Ctrl-C para salir).")
    while True:
        try:
            topic = input("scout> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not topic:
            continue
        await _run_one(topic)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Log a INFO para ver el progreso real (research_topic navegando, etc.).
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _banner()
    try:
        if argv:
            asyncio.run(_run_one(" ".join(argv)))
        else:
            asyncio.run(_interactive())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
