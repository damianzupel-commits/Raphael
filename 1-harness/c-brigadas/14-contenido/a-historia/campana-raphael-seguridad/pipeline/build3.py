# -*- coding: utf-8 -*-
"""Raphael Seguridad v3: videos verticales con personajes y escenas animadas (OpenMoji, CC BY-SA 4.0).
Subtitulos palabra por palabra, entrada animada del texto clave, glitch y flash en cada corte,
barra de progreso por secciones, musica sintetizada con ducking bajo la voz y whoosh en transiciones.
Requiere ffmpeg, espeak-ng, Pillow y numpy. Uso: python3 build2.py <salida> [n ...] [-j N]"""
import sys, os, subprocess, wave, math, random
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from casos_1 import CASOS_1
from casos_2 import CASOS_2
from escenas import ESCENAS, CTA as CTA_ESC, VILLANOS, MASCOTA, ZAP, CHECK
ICONOS = os.environ.get("RAPHAEL_ICONOS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconos"))
_ic = {}
_st = {}
def sticker(code):
    """Recorta el margen del emoji y le pone borde blanco tipo sticker (fondo oscuro)."""
    if code not in _st:
        im = Image.open(os.path.join(ICONOS, code + ".png")).convert("RGBA")
        im = im.crop(im.getchannel("A").getbbox()); s = max(im.size)
        sq = Image.new("RGBA", (s, s), (0, 0, 0, 0)); sq.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
        sq = sq.resize((400, 400), Image.LANCZOS); pad = 28
        big = Image.new("RGBA", (456, 456), (0, 0, 0, 0)); big.paste(sq, (pad, pad), sq)
        al = big.getchannel("A").point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(23)).filter(ImageFilter.GaussianBlur(1.5))
        out = Image.new("RGBA", big.size, (255, 255, 255, 0)); out.putalpha(al)
        out.alpha_composite(big); _st[code] = out
    return _st[code]
def icon(code, size, rot=0):
    size = max(8, int(size) // 6 * 6); rot = int(round(rot / 2.0)) * 2; k = (code, size, rot)
    if k not in _ic:
        im = sticker(code).resize((size, size), Image.LANCZOS)
        if rot: im = im.rotate(rot, resample=Image.BICUBIC)
        _ic[k] = im
    return _ic[k]

def paste_c(im, ic, cx, cy):
    im.paste(ic, (int(cx - ic.width / 2), int(cy - ic.height / 2)), ic)

def sombra(d, cx, cy, w):
    d.ellipse([cx - w / 2, cy - 18, cx + w / 2, cy + 18], fill=(0, 0, 0))

def dashed(d, x0, x1, y, col, off):
    x = x0 + (off % 36) - 36
    while x < x1:
        a, b = max(x, x0), min(x + 20, x1)
        if b > a: d.line([(a, y), (b, y)], fill=col, width=8)
        x += 36
    d.polygon([(x1, y), (x1 - 26, y - 18), (x1 - 26, y + 18)], fill=col)

def scene(im, d, esc, k, ts, now, col):
    tipo = esc[0]; cy = 965; mal = k == "problema"
    def pop(i): return ease_out_back((ts - 0.08 - 0.14 * i) / 0.35)
    def wob(code, i):
        if mal and (code in VILLANOS or tipo == "hero" and i == 0): return math.sin(now * 9 + i) * 9
        return 0
    if tipo == "flow":
        items = esc[1]; n = len(items); xs = [270, 810] if n == 2 else [175, 540, 905]; sz = 250 if n == 2 else 210
        lit = tuple(min(255, int(v * 0.8 + 50)) for v in col)
        for i in range(n - 1):
            if pop(i + 1) > 0.9: dashed(d, xs[i] + sz / 2 + 4, xs[i + 1] - sz / 2 - 4, cy, lit, now * 140)
        for i, c in enumerate(items):
            p = pop(i)
            if p <= 0.02: continue
            y = cy + math.sin(now * 3.1 + i * 1.7) * 12
            sombra(d, xs[i], cy + sz / 2 + 22, sz * 0.7 * min(p, 1))
            paste_c(im, icon(c, sz * p, wob(c, i)), xs[i], y)
        if pop(n) >= 1:
            pr = ((ts - 0.6) / 1.5) % 1; seg = pr * (n - 1); i = min(int(seg), n - 2); f = seg - i
            x = xs[i] + sz / 2 + (xs[i + 1] - xs[i] - sz) * f
            paste_c(im, icon(esc[2], 96), x, cy - 70 - abs(math.sin(f * math.pi)) * 60)
    elif tipo == "versus":
        a, b = esc[1]; sz = 280
        for i, (c, x0, dirx) in enumerate(((a, 250, 1), (b, 830, -1))):
            p = pop(i)
            if p <= 0.02: continue
            lunge = max(0, math.sin(now * 4 + i * math.pi)) * 30 * dirx
            sombra(d, x0, cy + sz / 2 + 20, sz * 0.7 * min(p, 1))
            paste_c(im, icon(c, sz * p, wob(c, i) + (6 * dirx if lunge else 0)), x0 + lunge, cy + math.sin(now * 3 + i) * 10)
        if pop(2) > 0:
            beat = (now % (60 / 102)) / (60 / 102)
            paste_c(im, icon(ZAP, 150 * pop(2) * (1.25 - 0.25 * min(1, beat * 3))), 540, cy - 20)
    else:
        cen, orb = esc[1][0], esc[2]; rx, ry = 380, 175
        pos = []
        for i, c in enumerate(orb):
            ang = now * 1.1 + i * 2 * math.pi / 3
            pos.append((math.sin(ang), c, 540 + math.cos(ang) * rx, cy + math.sin(ang) * ry, i))
        pos.sort()
        def draw_orb(e):
            s_, c, x, y, i = e; p = pop(i + 1)
            if p > 0.02: paste_c(im, icon(c, (110 + 35 * (s_ + 1) / 2) * p), x, y)
        for e in pos:
            if e[0] < 0: draw_orb(e)
        p = pop(0)
        if p > 0.02:
            sombra(d, 540, cy + 190, 260 * min(p, 1))
            paste_c(im, icon(cen, 320 * p, wob(cen, 0)), 540, cy + math.sin(now * 2.6) * 12)
        for e in pos:
            if e[0] >= 0: draw_orb(e)
    if k == "solucion":  # mascota de Raphael Seguridad aprobando la solucion
        p = ease_out_back((ts - 0.9) / 0.45)
        if p > 0:
            mx = 1180 - 240 * p; my = 1210 + math.sin(now * 3) * 8
            d.rounded_rectangle([mx - 210, my - 150, mx - 70, my - 60], 26, fill=(250, 250, 255))
            d.polygon([(mx - 95, my - 62), (mx - 70, my - 62), (mx - 60, my - 30)], fill=(250, 250, 255))
            paste_c(im, icon(CHECK, 66), mx - 140, my - 105)
            paste_c(im, icon(MASCOTA, 190, math.sin(now * 5) * 5), mx, my)

W, H, FPS, SR = 1080, 1920, 30, 22050
FD = "/usr/share/fonts/opentype/inter/"
F_BLACK, F_XB, F_MED = FD + "InterDisplay-Black.otf", FD + "Inter-ExtraBold.otf", FD + "Inter-Medium.otf"
F_MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf"
VOZ = os.environ.get("RAPHAEL_VOZ", "es-419")
YEL = (255, 214, 10)
SECC = [("gancho", "ALERTA", (235, 40, 60)), ("caso", "EL CASO", (40, 130, 255)),
        ("problema", "EL PROBLEMA", (255, 140, 20)), ("solucion", "LA SOLUCIÓN", (30, 200, 110))]
CTA_COL = (150, 90, 255)
CTA = ["Guardalo y compartilo con tu equipo.", "¿Vos qué hubieras hecho? Te leo en comentarios.",
       "Seguí Raphael Seguridad para más casos reales."]
_fc = {}
def F(p, s):
    k = (p, s)
    if k not in _fc: _fc[k] = ImageFont.truetype(p, s)
    return _fc[k]

def ease_out_back(x):
    x = min(max(x, 0), 1); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def ease_out(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3

# ---------------- audio ----------------
def tts(text, out, vel, pit):
    subprocess.run(["espeak-ng", "-v", VOZ, "-s", str(vel), "-p", str(pit), "-a", "180", "-w", out, text], check=True)
    with wave.open(out) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if sr != SR: a = np.interp(np.arange(0, len(a), sr / SR), np.arange(len(a)), a)
    nz = np.where(np.abs(a) > 0.02)[0]  # recorta silencios de los bordes para mas ritmo
    if len(nz): a = a[max(nz[0] - 200, 0): nz[-1] + 900]
    return a / (np.abs(a).max() + 1e-6) * 0.9

def lowpass(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)): acc += a * (x[i] - acc); y[i] = acc
    return y

def music(total, seed):
    rng = np.random.default_rng(seed); n = int(total * SR) + SR; t = np.arange(n) / SR
    bpm = 102; beat = 60 / bpm; out = np.zeros(n, np.float32)
    k_len = int(0.28 * SR); kt = np.arange(k_len) / SR
    kick = np.sin(2 * np.pi * (45 * kt + (120 - 45) * 0.05 * (1 - np.exp(-kt / 0.05)))) * np.exp(-kt / 0.09)
    hat = rng.standard_normal(int(0.04 * SR)); hat = (hat - lowpass(hat, 0.5)) * np.exp(-np.arange(len(hat)) / (0.008 * SR))
    roots = [55.0, 43.65, 65.41, 49.0]  # La m, Fa, Do, Sol
    nb = int(total / beat) + 2
    for b in range(nb):
        s = int(b * beat * SR)
        if s >= n: break
        if b % 4 in (0, 2) or (b % 8 == 7):
            e = min(n, s + k_len); out[s:e] += kick[:e - s] * 0.9
        for h in (0, 0.5):
            hs = int((b + h) * beat * SR); e = min(n, hs + len(hat))
            if hs < n: out[hs:e] += hat[:e - hs] * (0.25 if h else 0.12)
        r = roots[(b // 4) % 4]
        for h in (0, 0.5):
            bs = int((b + h) * beat * SR); bl = int(beat * 0.5 * SR); e = min(n, bs + bl)
            if bs >= n: continue
            bt = np.arange(e - bs) / SR
            saw = 2 * ((bt * r * (2 if h else 1)) % 1) - 1
            out[bs:e] += saw * np.exp(-bt / 0.12) * 0.22
    pad = np.zeros(n, np.float32)
    for i, r in enumerate(roots):
        s = int(i * 4 * beat * SR)
        while s < n:
            e = min(n, s + int(4 * beat * SR)); tt = np.arange(e - s) / SR
            env = np.minimum(1, tt / 0.4) * np.minimum(1, (4 * beat - tt) / 0.4)
            for m in (2, 3, 4.76):
                pad[s:e] += np.sin(2 * np.pi * r * m * tt) * env * 0.05
            s += int(16 * beat * SR)
    out += pad
    return out[: int(total * SR)] / (np.abs(out).max() + 1e-6)

def whoosh(dur=0.5, seed=0):
    rng = np.random.default_rng(seed); n = int(dur * SR); x = rng.standard_normal(n).astype(np.float32)
    y = np.empty_like(x); acc = 0.0
    for i in range(n):
        a = 0.02 + 0.5 * math.sin(math.pi * i / n) ** 2; acc += a * (x[i] - acc); y[i] = acc
    env = np.sin(np.pi * np.arange(n) / n) ** 1.5
    return y * env / (np.abs(y).max() + 1e-6)

def impact():
    n = int(0.9 * SR); t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (38 * t + 80 * 0.08 * (1 - np.exp(-t / 0.08)))) * np.exp(-t / 0.35)
    return boom * 0.9

# ---------------- linea de tiempo ----------------
def timeline(c, work):
    segs = []  # dict(sec, color, label, pantalla, text, start, dur, words=[(w,t0,t1)])
    voice = []; t = 0.35  # arranca con el golpe
    secs = [(k, et, col, c["pantalla"][k], c[k]) for k, et, col in SECC]
    secs.append(("cta", "TU TURNO", CTA_COL, "¿Y VOS QUÉ HUBIERAS HECHO?", CTA))
    sec_starts = []
    for si, (k, et, col, pant, frases) in enumerate(secs):
        if si: t += 0.32
        sec_starts.append((t, k, et, col, pant))
        for fi, fr in enumerate(frases):
            vel, pit = (178, 62) if k == "gancho" else (186, 54) if k != "cta" else (176, 58)
            a = tts(fr, os.path.join(work, f"v{si}_{fi}.wav"), vel, pit)
            d = len(a) / SR
            ws = fr.split(); wts = [len(w.strip(",.:¿?¡!")) + 2 + (5 if w[-1] in ",.:?!" else 0) for w in ws]
            tot = sum(wts); acc = 0; words = []
            for w, wt in zip(ws, wts):
                t0 = t + d * acc / tot; acc += wt; words.append((w, t0, t + d * acc / tot))
            segs.append(dict(sec=k, color=col, label=et, pantalla=pant, text=fr, start=t, dur=d, words=words))
            voice.append((t, a)); t += d + 0.12
    return segs, voice, sec_starts, t + 0.6

def mix(voice, sec_starts, total, seed):
    n = int(total * SR); v = np.zeros(n, np.float32)
    for st, a in voice:
        s = int(st * SR); e = min(n, s + len(a)); v[s:e] += a[: e - s]
    env = np.convolve(np.abs(v), np.ones(int(0.05 * SR)) / int(0.05 * SR), mode="same")
    duck = 1 - 0.72 * np.clip(env / 0.08, 0, 1)
    duck = np.convolve(duck, np.ones(int(0.15 * SR)) / int(0.15 * SR), mode="same")
    m = music(total, seed) * 0.30 * duck
    fx = np.zeros(n, np.float32)
    imp = impact(); fx[: len(imp)] += imp * 0.55
    for i, (st, *_r) in enumerate(sec_starts[1:]):
        w = whoosh(0.5, seed + i); s = max(0, int((st - 0.35) * SR)); e = min(n, s + len(w)); fx[s:e] += w[: e - s] * 0.35
    out = v * 0.95 + m + fx
    fade = int(0.6 * SR); out[-fade:] *= np.linspace(1, 0, fade)
    return np.clip(out / max(1.0, np.abs(out).max() / 0.97), -1, 1)

# ---------------- imagen ----------------
def make_bg(col):
    h2 = H + 120; im = Image.new("RGB", (W, h2), (8, 10, 18)); d = ImageDraw.Draw(im)
    for x in range(0, W, 60): d.line([(x, 0), (x, h2)], fill=(18, 22, 36), width=2)
    for y in range(0, h2, 60): d.line([(0, y), (W, y)], fill=(18, 22, 36), width=2)
    glow = Image.new("L", (W, h2), 0); gd = ImageDraw.Draw(glow)
    gd.ellipse([-300, -200, W + 300, 900], fill=120); gd.ellipse([200, 1300, W + 500, h2 + 400], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    colim = Image.new("RGB", (W, h2), col)
    return Image.composite(colim, im, glow.point(lambda p: int(p * 0.55)))

def wrap_words(d, words, f, maxw):
    lines, cur = [], []
    for w in words:
        test = " ".join(x[0] for x in cur + [w])
        if cur and d.textlength(test, font=f) > maxw: lines.append(cur); cur = [w]
        else: cur.append(w)
    if cur: lines.append(cur)
    return lines

def chunks_of(words, maxn=4):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxn or w[0][-1] in ".:?!" or (w[0][-1] == "," and len(cur) >= 2): out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def render_pantalla(text, col, big):
    f = F(F_BLACK, 104 if big else 86); tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = [(w, 0, 0) for w in text.upper().split()]
    lines = wrap_words(tmp, words, f, W - 140)[:4]
    lh = int(f.size * 1.08); h = lh * len(lines) + 40
    im = Image.new("RGBA", (W, h + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        s = " ".join(x[0] for x in ln)
        d.text((64, 10 + i * lh), s, font=f, fill="white", stroke_width=4, stroke_fill=(0, 0, 0))
    d.rectangle([64, h + 4, 64 + 220, h + 18], fill=col)
    return im

def is_key(w):
    return any(ch.isdigit() for ch in w) or "$" in w or "€" in w

def draw_caption(d, words, now, col, y_center, big=False):
    f = F(F_BLACK, 92 if big else 80)
    up = [(w.upper(), t0, t1) for w, t0, t1 in words]
    lines = wrap_words(d, up, f, W - 130)
    lh = int(f.size * 1.18); y = y_center - lh * len(lines) // 2
    for ln in lines:
        widths = [d.textlength(w[0], font=f) for w in ln]; sp = d.textlength(" ", font=f)
        x = (W - (sum(widths) + sp * (len(ln) - 1))) / 2
        for (w, t0, t1), ww in zip(ln, widths):
            if now < t0 - 0.02 and now > 0.05: x += ww + sp; continue  # aparece palabra por palabra
            active = t0 <= now < t1 + 0.05
            pop = ease_out_back((now - t0) / 0.12); dy = int((1 - pop) * 18)
            if active:
                d.rounded_rectangle([x - 12, y - 4 + dy, x + ww + 12, y + lh - 14 + dy], 16, fill=col)
            fill = "white" if active else (YEL if is_key(w) else "white")
            d.text((x, y + dy), w, font=f, fill=fill, stroke_width=7, stroke_fill=(0, 0, 0))
            x += ww + sp
        y += lh

def glitch(arr, rng, k):
    out = arr.copy()
    for _ in range(int(8 * k)):
        y0 = rng.integers(0, H - 80); hh = rng.integers(8, 70); sh = rng.integers(-60, 60)
        out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], sh, axis=1)
    sh = int(14 * k); out[:, :, 0] = np.roll(out[:, :, 0], sh, axis=1); out[:, :, 2] = np.roll(out[:, :, 2], -sh, axis=1)
    return out

def build(args):
    c, outdir = args
    work = os.path.join(outdir, "_tmp3_%02d" % c["n"]); os.makedirs(work, exist_ok=True)
    segs, voice, sec_starts, total = timeline(c, work)
    audio = mix(voice, sec_starts, total, c["n"])
    ap = os.path.join(work, "a.wav")
    with wave.open(ap, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((audio * 32767).astype(np.int16).tobytes())
    bgs = {k: make_bg(col) for _, k, _, col, _ in sec_starts}
    pants = {k: render_pantalla(p, col, k in ("gancho", "cta")) for _, k, _, col, p in sec_starts}
    caps = []
    for s in segs:
        for ch in chunks_of(s["words"]): caps.append((ch[0][1], ch[-1][2], ch, s))
    base = f"{c['n']:02d}-{c['slug']}"; mp4 = os.path.join(outdir, base + ".mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", ap, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                           "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest",
                           "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    rng = np.random.default_rng(c["n"]); nfr = int(total * FPS)
    sec_bounds = [s[0] for s in sec_starts] + [total]
    fl_t, fl_m = F(F_MONO, 34), F(F_MONO, 30)
    ci = 0
    for fi in range(nfr):
        now = fi / FPS
        si = max(i for i in range(len(sec_starts)) if sec_starts[i][0] <= now or i == 0)
        st, k, label, col, _ = sec_starts[si]; ts = now - st
        bg = bgs[k]; off = int((now * 45) % 60)
        im = bg.crop((0, off, W, off + H)); d = ImageDraw.Draw(im)
        # cabecera
        d.text((60, 70), "RAPHAEL", font=F(F_BLACK, 40), fill="white")
        d.text((60 + d.textlength("RAPHAEL ", font=F(F_BLACK, 40)), 70), "SEGURIDAD", font=F(F_BLACK, 40), fill=col)
        d.text((W - 60, 76), f"CASO {c['n']:02d}", font=fl_t, fill=(190, 200, 220), anchor="ra")
        # barra de progreso por secciones
        nseg = len(sec_starts); gap = 10; bw = (W - 120 - gap * (nseg - 1)) / nseg
        for i in range(nseg):
            x0 = 60 + i * (bw + gap); d.rounded_rectangle([x0, 140, x0 + bw, 150], 5, fill=(45, 50, 70))
            fr = 1 if i < si else (0 if i > si else min(1, (now - sec_bounds[i]) / (sec_bounds[i + 1] - sec_bounds[i])))
            if fr > 0: d.rounded_rectangle([x0, 140, x0 + max(10, bw * fr), 150], 5, fill=sec_starts[i][3] if i == si else (230, 235, 245))
        # etiqueta de seccion con pop
        p = 1 if k == "gancho" else ease_out_back(ts / 0.25); lf = F(F_MONO, 44); lw = d.textlength(label, font=lf)
        lx = 60 - int((1 - p) * 500)
        d.rounded_rectangle([lx, 210, lx + lw + 56, 290], 14, fill=col)
        blink = "_" if int(now * 2.5) % 2 == 0 else " "
        d.text((lx + 28, 222), label, font=lf, fill="white")
        d.text((lx + lw + 70, 222), blink, font=lf, fill=col)
        # texto clave: entra deslizando y respira
        pim = pants[k]; px = 0 if (k == "gancho") else int(-W * (1 - ease_out(ts / 0.35))); py = 360
        if k == "gancho" and ts < 1.6: px += int(rng.integers(-7, 8)); py += int(rng.integers(-5, 6))
        py += int(math.sin(now * 2.2) * 6)
        esc = CTA_ESC if k == "cta" else ESCENAS[c["n"]][k]
        scene(im, d, esc, k, ts, now, col)
        im.paste(pim, (px, py), pim)
        # subtitulos palabra por palabra
        while ci + 1 < len(caps) and caps[ci + 1][0] <= now: ci += 1
        cs, ce, ch, seg = caps[ci]
        if (now >= cs - 0.05 and now <= ce + 0.6) or ci == 0:
            draw_caption(d, ch, now, col, 1450, big=(k == "gancho"))
        # pie
        if k == "cta":
            d.text((W // 2, 1640), "@RaphaelSeguridad", font=F(F_BLACK, 64), fill=YEL, anchor="ma", stroke_width=5, stroke_fill="black")
            d.text((W // 2, 1730), "Fuentes en la descripción · Íconos: OpenMoji (CC BY-SA 4.0)", font=F(F_MONO, 24), fill=(180, 190, 210), anchor="ma")
        else:
            d.text((W // 2, 1800), "CASO REAL · FUENTES EN LA DESCRIPCIÓN", font=fl_m, fill=(140, 150, 175), anchor="ma")
        arr = np.asarray(im, dtype=np.uint8)
        # corte: glitch + flash
        if ts < 0.18 and si > 0 or 0.1 < now < 0.35:
            kk = 1 - ((ts if si else now - 0.1)) / 0.25
            arr = glitch(arr, rng, max(kk, 0.2))
            if ts < 0.07 and si > 0 or 0.1 < now < 0.16:
                arr = np.clip(arr.astype(np.int16) + 110, 0, 255).astype(np.uint8)
        # pulso al ritmo (102 bpm)
        bp = (now % (60 / 102)) / (60 / 102)
        if bp < 0.12 and k != "cta":
            arr = np.clip(arr.astype(np.int16) + int(10 * (1 - bp / 0.12)), 0, 255).astype(np.uint8)
        ff.stdin.write(arr.tobytes())
    ff.stdin.close(); ff.wait()
    srt = []
    def tsf(t): return "%02d:%02d:%02d,%03d" % (t // 3600, t % 3600 // 60, t % 60, int(t % 1 * 1000))
    for i, (cs, ce, ch, s) in enumerate(caps):
        srt.append(f"{i+1}\n{tsf(cs)} --> {tsf(ce + 0.1)}\n{' '.join(w[0] for w in ch)}\n")
    open(os.path.join(outdir, base + ".srt"), "w").write("\n".join(srt))
    import shutil; shutil.rmtree(work)
    return base, round(total, 1)

if __name__ == "__main__":
    a = sys.argv[1:]; j = 4
    if "-j" in a: i = a.index("-j"); j = int(a[i + 1]); del a[i:i + 2]
    out = a[0]; os.makedirs(out, exist_ok=True); sel = {int(x) for x in a[1:]}
    todo = [(c, out) for c in CASOS_1 + CASOS_2 if not sel or c["n"] in sel]
    with Pool(j) as p:
        for b, t in p.imap_unordered(build, todo): print(b, t, "s", flush=True)
