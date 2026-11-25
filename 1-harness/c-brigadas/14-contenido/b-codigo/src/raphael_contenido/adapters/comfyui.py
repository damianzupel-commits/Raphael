"""ComfyUI (imagen con Flux.1 Schnell y video con Wan 2.2) corriendo en la GPU de la PC. Adaptador real, simulado y "sin servidor".

Portado de `app/tools/image_gen.py`, `video_gen.py` y `_comfyui_shared.py` de JarvisRemote: los workflows son los mismos.
Queda sin portar (pendiente, ver el log): arrancar y cerrar ComfyUI solo, y descargar de la VRAM el modelo de Ollama mientras se
genera. Hoy ComfyUI tiene que estar prendido (`COMFYUI_URL`, por defecto http://127.0.0.1:8188).
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from pathlib import Path

from .http import Http, ServicioError
from .http import http as real_http

FPS = 16


def _round_to_16(v: int) -> int:
    return max(256, min(1536, round(v / 16) * 16))


def image_workflow(prompt: str, width: int, height: int, seed: int) -> dict:
    w, h = _round_to_16(width), _round_to_16(height)
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-schnell-Q4_K_S.gguf"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors",
                                                         "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
                                                   "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                   "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": f"raphael_img_{seed}"}},
    }


def video_workflow(prompt: str, duration_seconds: float, seed: int) -> dict:
    length = max(5, (round(FPS * duration_seconds) // 4) * 4 + 1)   # Wan necesita 4k+1 cuadros
    lora = "wan2.2_t2v_lightx2v_4steps_lora_v1.1_{}_noise.safetensors"
    return {
        "1": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2.1_VAE.safetensors"}},
        "3": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf"}},
        "4": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf"}},
        "5": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["3", 0], "lora_name": lora.format("high"), "strength_model": 1.0}},
        "6": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["4", 0], "lora_name": lora.format("low"), "strength_model": 1.0}},
        "7": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["5", 0], "shift": 5.0}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["6", 0], "shift": 5.0}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 0], "text": prompt}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 0], "text": "blurry, low quality, static, distorted"}},
        "11": {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": 480, "height": 480, "length": length, "batch_size": 1}},
        "12": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["7", 0], "positive": ["9", 0], "negative": ["10", 0],
                                                            "latent_image": ["11", 0], "add_noise": "enable", "noise_seed": seed, "steps": 4,
                                                            "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "start_at_step": 0,
                                                            "end_at_step": 2, "return_with_leftover_noise": "enable"}},
        "13": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["8", 0], "positive": ["9", 0], "negative": ["10", 0],
                                                            "latent_image": ["12", 0], "add_noise": "disable", "noise_seed": 0, "steps": 4,
                                                            "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "start_at_step": 2,
                                                            "end_at_step": 4, "return_with_leftover_noise": "disable"}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["2", 0]}},
        "15": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": FPS}},
        "16": {"class_type": "SaveVideo", "inputs": {"video": ["15", 0], "filename_prefix": f"raphael_gen_{seed}", "format": "auto",
                                                      "codec": "auto"}},
    }


def output_file(entry: dict) -> dict:
    for node in entry.get("outputs", {}).values():
        for key in ("images", "gifs", "videos"):
            if node.get(key):
                return node[key][0]
    raise ServicioError(f"ComfyUI no devolvió ningún archivo de salida: {str(entry)[:200]}")


class ComfyUI:
    mode = "real"

    def __init__(self, base_url: str, output_dir: str | Path, *, http: Http = real_http,
                 sleep: Callable[[float], None] = time.sleep, poll: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self._http, self._sleep, self._poll = http, sleep, poll

    def up(self) -> bool:
        try:
            self._http("GET", f"{self.base_url}/system_stats", timeout=5)
            return True
        except ServicioError:
            return False

    def _run(self, workflow: dict, timeout: float) -> Path:
        if not self.up():
            raise ServicioError(f"ComfyUI no está prendido en {self.base_url}. Abrilo y probá de nuevo.")
        pid = self._http("POST", f"{self.base_url}/prompt", json_body={"prompt": workflow}, timeout=30).get("prompt_id")
        if not pid:
            raise ServicioError("ComfyUI no aceptó el trabajo.")
        deadline, errors = time.monotonic() + timeout, 0
        while time.monotonic() < deadline:
            try:
                data = self._http("GET", f"{self.base_url}/history/{pid}", timeout=10)
                errors = 0
            except ServicioError as exc:
                errors += 1       # tres fallas seguidas = ComfyUI se cayó a mitad de la generación
                if errors >= 3:
                    raise ServicioError("ComfyUI dejó de responder durante la generación (probablemente se cayó).") from exc
                self._sleep(self._poll)
                continue
            if pid in data:
                f = output_file(data[pid])
                return self.output_dir / f.get("subfolder", "") / f["filename"]
            self._sleep(self._poll)
        raise ServicioError(f"ComfyUI no terminó en {int(timeout)} s.")

    def image(self, prompt: str, width: int = 512, height: int = 512) -> dict:
        path = self._run(image_workflow(prompt, width, height, random.randint(0, 2**32 - 1)), timeout=600)
        return {"path": str(path), "width": _round_to_16(width), "height": _round_to_16(height), "simulado": False}

    def video(self, prompt: str, seconds: float = 1.0) -> dict:
        path = self._run(video_workflow(prompt, seconds, random.randint(0, 2**32 - 1)), timeout=1800)
        return {"path": str(path), "seconds": seconds, "simulado": False}


class ComfyMock:
    """ComfyUI de mentira: deja un archivo chico en `output_dir` y no usa la GPU."""

    mode = "mock"

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.calls: list[tuple[str, str]] = []

    def up(self) -> bool:
        return True

    def _file(self, kind: str, ext: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        p = self.output_dir / f"sim_{kind}_{len(self.calls)}.{ext}"
        p.write_bytes(b"SIMULADO")
        return p

    def image(self, prompt: str, width: int = 512, height: int = 512) -> dict:
        self.calls.append(("image", prompt))
        return {"path": str(self._file("img", "png")), "width": _round_to_16(width), "height": _round_to_16(height), "simulado": True}

    def video(self, prompt: str, seconds: float = 1.0) -> dict:
        self.calls.append(("video", prompt))
        return {"path": str(self._file("gen", "mp4")), "seconds": seconds, "simulado": True}


class ComfySinServidor:
    """Real pero sin `COMFYUI_URL`/GPU configurada: avisa en vez de intentar."""

    mode = "sin_clave"

    def up(self) -> bool:
        return False

    def image(self, prompt: str, width: int = 512, height: int = 512) -> dict:
        raise ServicioError("Falta COMFYUI_URL y COMFYUI_OUTPUT_DIR (ComfyUI prendido en esta PC).")

    video = image
