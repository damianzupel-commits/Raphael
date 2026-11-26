"""Prueba los adaptadores REALES de Ingesta contra la red de verdad, una sola vez en la PC (la nube no tiene salida).

No usa claves ni modelo ni escribe en el vault: solo trae y muestra. Para YouTube hace falta `pip install yt-dlp`.

Uso (desde la carpeta raphael):
    python 1-harness\\c-brigadas\\10-ingesta\\c-salud\\mantenimiento\\probar_real.py
    python ...\\probar_real.py --video https://www.youtube.com/watch?v=<id> --lista https://www.youtube.com/playlist?list=<id>
Sale con 0 si todo lo probado anduvo y con 2 si algo falló (con el motivo)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "b-codigo" / "src"))

from raphael_ingesta.adapters import make
from raphael_ingesta.adapters.youtube import video_id_of
from raphael_ingesta.model import SourceError


def _try(name: str, fn) -> bool:
    try:
        print(f"  OK    {name}: {fn()}")
        return True
    except SourceError as exc:
        print(f"  FALLA {name}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001 - es un script de diagnóstico: que cuente qué pasó
        print(f"  FALLA {name}: {type(exc).__name__}: {exc}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", help="un video de YouTube con subtítulos")
    ap.add_argument("--lista", help="una lista de reproducción pública")
    ap.add_argument("--fuentes", action="store_true", help="probar las fuentes públicas (una búsqueda de 2 ítems por fuente)")
    ap.add_argument("--pagina", default="https://example.org/", help="una página web pública")
    args = ap.parse_args()
    results = []
    arxiv, web, yt = make("arxiv", "real"), make("web", "real"), make("youtube", "real")
    print("Ingesta · prueba contra la red real")
    results.append(_try("arXiv búsqueda", lambda: f"{len(arxiv.search('cat:cs.AI', 2))} papers"))
    results.append(_try("web", lambda: _describe(web.fetch(args.pagina))))
    results.append(_try("web bloquea localhost", lambda: _must_fail(lambda: web.fetch("http://localhost:8000/"))))
    if args.lista:
        results.append(_try("YouTube lista", lambda: f"{len(yt.list_playlist(args.lista))} videos"))
    if args.video:
        vid = video_id_of(args.video)
        results.append(_try("YouTube video", lambda: f"{len(yt.fetch_video(vid).text)} caracteres de transcripción"))
    if args.fuentes:
        from raphael_ingesta.adapters.fuentes import sources

        fu = make("fuentes", "real")
        for fid in sources():
            results.append(_try(f"fuente {fid}", lambda fid=fid: f"{len(fu.search(fid, 2))} ítems"))
    if not (args.lista or args.video):
        print("  (YouTube no se probó: pasá --video y --lista)")
    print("Resultado:", "todo bien" if all(results) else "hay fallas")
    return 0 if all(results) else 2


def _describe(item) -> str:
    return f"«{item.title}» ({len(item.text)} caracteres)"


def _must_fail(fn) -> str:
    try:
        fn()
    except SourceError as exc:
        return f"rechazada ({exc.reason})"
    raise AssertionError("debería haber rechazado la dirección")


if __name__ == "__main__":
    raise SystemExit(main())
