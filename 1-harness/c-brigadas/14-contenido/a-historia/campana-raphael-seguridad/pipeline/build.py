# -*- coding: utf-8 -*-
"""Genera videos verticales 1080x1920 (voz TTS espeak-ng + subtitulos + texto en pantalla) a partir de casos_*.py.
Uso: python3 build.py <salida> [n ...]   (sin n = los 20)"""
import sys, os, subprocess, wave, textwrap, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from casos_1 import CASOS_1
from casos_2 import CASOS_2
W, H = 1080, 1920
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
VOZ, VEL, PAUSA = os.environ.get("RAPHAEL_VOZ", "es-419"), os.environ.get("RAPHAEL_VEL", "158"), 0.30
CIERRE = "Seguí Raphael Seguridad para más casos reales."
SECC = [("gancho", "ALERTA", (190, 30, 45)), ("caso", "EL CASO REAL", (20, 90, 170)),
        ("problema", "EL PROBLEMA", (200, 110, 10)), ("solucion", "LA SOLUCIÓN", (20, 140, 80))]

def font(p, s): return ImageFont.truetype(p, s)

def wrap(draw, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def frame(path, color, etiqueta, grande, sub, prog, n, pie=False):
    im = Image.new("RGB", (W, H), (12, 16, 28)); d = ImageDraw.Draw(im)
    for y in range(H):  # degradado vertical suave con el color de la seccion
        k = 0.30 * (1 - y / H)
        d.line([(0, y), (W, y)], fill=tuple(int(12 + (c - 12) * k) for c in color))
    d.text((60, 70), "RAPHAEL SEGURIDAD", font=font(FB, 40), fill=(235, 240, 250))
    d.text((W - 60, 76), f"{n:02d}/20", font=font(FB, 34), fill=(150, 160, 180), anchor="ra")
    d.rounded_rectangle([60, 190, 60 + d.textlength(etiqueta, font=font(FB, 46)) + 60, 270], 20, fill=color)
    d.text((90, 202), etiqueta, font=font(FB, 46), fill="white")
    fg = font(FB, 92); y = 420
    for ln in wrap(d, grande, fg, W - 120)[:5]:
        d.text((60, y), ln, font=fg, fill="white"); y += 112
    fs = font(FB, 60); lines = wrap(d, sub, fs, W - 160)[-6:]
    h = len(lines) * 78 + 50; top = 1500 - h // 2 - 20
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.rounded_rectangle([40, top, W - 40, top + h], 28, fill=(0, 0, 0, 170)); im.paste(ov, (0, 0), ov); d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines): d.text((W // 2, top + 25 + i * 78), ln, font=fs, fill="white", anchor="ma")
    if pie: d.text((W // 2, 1790), "Fuentes en la descripción", font=font(FR, 38), fill=(170, 180, 200), anchor="ma")
    d.rectangle([0, H - 14, int(W * prog), H], fill=color)
    im.save(path)

def tts(text, out):
    subprocess.run(["espeak-ng", "-v", VOZ, "-s", VEL, "-w", out, text], check=True)

def build(c, outdir):
    work = os.path.join(outdir, "_tmp_%02d" % c["n"]); os.makedirs(work, exist_ok=True)
    items = []  # (seccion, etiqueta, color, grande, frase, pie)
    for k, et, col in SECC:
        for fr in c[k]: items.append((et, col, c["pantalla"][k], fr, False))
    items.append(("RAPHAEL SEGURIDAD", (90, 70, 190), "Más casos reales de IA y ciberseguridad", CIERRE, True))
    wavs, durs = [], []
    for i, it in enumerate(items):
        p = os.path.join(work, f"s{i:02d}.wav"); tts(it[3], p); wavs.append(p)
        with wave.open(p) as w: durs.append(w.getnframes() / w.getframerate() + PAUSA)
    total = sum(durs); acc = 0.0; srt = []; lst = []
    for i, it in enumerate(items):
        png = os.path.join(work, f"f{i:02d}.png")
        frame(png, it[1], it[0], it[2], it[3], (acc + durs[i]) / total, c["n"], it[4])
        lst += [f"file '{png}'", f"duration {durs[i]:.3f}"]
        def ts(t): return "%02d:%02d:%02d,%03d" % (t // 3600, t % 3600 // 60, t % 60, int(t % 1 * 1000))
        srt.append(f"{i+1}\n{ts(acc)} --> {ts(acc+durs[i]-PAUSA)}\n{it[3]}\n")
        acc += durs[i]
    lst.append(f"file '{png}'")
    open(os.path.join(work, "l.txt"), "w").write("\n".join(lst))
    # audio concatenado con pausas
    with wave.open(wavs[0]) as w0: params = w0.getparams()
    ap = os.path.join(work, "audio.wav")
    with wave.open(ap, "wb") as wo:
        wo.setparams(params)
        for p in wavs:
            with wave.open(p) as w: wo.writeframes(w.readframes(w.getnframes()))
            wo.writeframes(b"\x00\x00" * int(params.framerate * PAUSA * params.nchannels))
    base = f"{c['n']:02d}-{c['slug']}"
    mp4 = os.path.join(outdir, base + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(work, "l.txt"),
                    "-i", ap, "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                    "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", mp4], check=True)
    open(os.path.join(outdir, base + ".srt"), "w").write("\n".join(srt))
    import shutil; shutil.rmtree(work)
    return base, total

if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    sel = {int(x) for x in sys.argv[2:]}
    for c in CASOS_1 + CASOS_2:
        if sel and c["n"] not in sel: continue
        b, t = build(c, out); print(b, round(t, 1), "s", flush=True)
