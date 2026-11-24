"""Baja una voz de Piper (TTS) en español a tray-app/models/tts/.

Uso:
    python download_tts_voice.py           # baja la voz por default (es_ES-davefx-medium)
    python download_tts_voice.py --list    # muestra las voces disponibles
    python download_tts_voice.py es_MX-claude-high

Descarga el .onnx + .onnx.json desde el repo oficial rhasspy/piper-voices
(Hugging Face). Corre en tu PC (no en el entorno de asistencia).
"""

import sys
import urllib.request
from pathlib import Path

_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# nombre -> subruta dentro del repo (idioma/locale/voz/calidad)
VOICES = {
    # español de España
    "es_ES-davefx-medium": "es/es_ES/davefx/medium/es_ES-davefx-medium",       # masculina, clara (default)
    "es_ES-sharvard-medium": "es/es_ES/sharvard/medium/es_ES-sharvard-medium", # femenina
    "es_ES-carlfm-x_low": "es/es_ES/carlfm/x_low/es_ES-carlfm-x_low",          # liviana, más rápida
    # español de México (suena más "latino" / neutro que el de España)
    "es_MX-claude-high": "es/es_MX/claude/high/es_MX-claude-high",             # alta calidad
    "es_MX-ald-medium": "es/es_MX/ald/medium/es_MX-ald-medium",                # masculina
}

DEFAULT = "es_ES-davefx-medium"


def _download(url: str, dest: Path) -> None:
    print(f"  bajando {url}")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        f.write(r.read())
    print(f"  -> {dest}  ({dest.stat().st_size // 1024} KB)")


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if "--list" in args:
        print("Voces disponibles:")
        for name in VOICES:
            mark = "  (default)" if name == DEFAULT else ""
            print(f"  - {name}{mark}")
        return 0

    name = next((a for a in args if not a.startswith("-")), DEFAULT)
    if name not in VOICES:
        print(f"Voz desconocida: {name}. Usá --list para ver las opciones.")
        return 1

    sub = VOICES[name]
    out_dir = Path(__file__).parent / "models" / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Bajando voz '{name}' a {out_dir} ...")
    try:
        _download(f"{_BASE}/{sub}.onnx", out_dir / f"{name}.onnx")
        _download(f"{_BASE}/{sub}.onnx.json", out_dir / f"{name}.onnx.json")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR bajando la voz: {exc}")
        print("Verificá tu conexión, o bajá los archivos a mano desde:")
        print(f"  {_BASE}/{sub}.onnx")
        print(f"  {_BASE}/{sub}.onnx.json")
        return 1

    print("\nListo. Raphael va a usar esta voz al hablar.")
    print("Si querés otra, borrá los .onnx de models/tts/ y corré esto con otro nombre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
