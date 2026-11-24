#!/usr/bin/env python3
"""Historias reales story builder (rebuilt Nov 23 2026 to match the week-1/2 look).

usage: build_story.py job.json out.mp4
job = {
  "voice": "path.wav", "images": ["1.png", ...],
  "sentences": ["line", ...],      # narration lines (without frase/close)
  "frase": "…", "close": "…",
  "tag": "Historias reales · 22",
  "music": "music-track2.wav", "music_vol": 0.12
}
Look: 1080x1920 30fps, slow zoom on each still, white captions with black stroke
centred ~y1410, small dark tag pill at top, white frase box (shown while the frase
and close are spoken), red "Suscríbete" pill bottom-left with a bobbing arrow for the
last 3 s, music bed under the voice.
"""
import json, os, re, subprocess, sys, math, tempfile, textwrap
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
XBOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
if not os.path.exists(XBOLD):
    XBOLD = BOLD


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit("ffmpeg failed")
    return r


def duration(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p]).decode().strip())


def silences(wav):
    r = subprocess.run(["ffmpeg", "-i", wav, "-af", "silencedetect=n=-35dB:d=0.28", "-f", "null", "-"],
                       capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(st, en))


def segment(texts, wav):
    """Return [(start,end)] per text. Chooses len(texts)-1 pauses so each sentence's duration best
    matches its character count at the voice's average speaking rate (dynamic programming), with a
    small bonus for longer pauses (sentence ends pause longer than commas)."""
    T = duration(wav)
    sil = silences(wav)
    lead = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0
    tail = sil[-1][0] if sil and sil[-1][1] > T - 0.05 else T
    gaps = [(s, e) for s, e in sil if s > lead + 0.2 and e < tail - 0.2]
    n = len(texts)
    ch = [max(len(t), 1) for t in texts]
    speech = (tail - lead) - sum(e - s for s, e in gaps)
    r = speech / sum(ch)
    G = len(gaps)
    if G < n - 1:
        # not enough pauses: fall back to proportional cuts
        cuts, acc = [], 0
        for x in ch[:-1]:
            acc += x
            t = lead + (tail - lead) * acc / sum(ch)
            cuts.append((t, t))
        gaps, G = cuts, len(cuts)
    INF = float("inf")
    # point j: 0 = lead, 1..G = gaps, G+1 = tail
    st = [lead] + [g[0] for g in gaps] + [tail]   # where speech before this point ends
    en = [lead] + [g[1] for g in gaps] + [tail]   # where speech after this point starts
    glen = [0] + [g[1] - g[0] for g in gaps] + [0]
    inner = lambda a, b: sum(glen[a + 1:b])       # pauses inside a sentence

    def cost(k, a, b):
        d = st[b] - en[a] - inner(a, b)
        exp = ch[k] * r
        return (d - exp) ** 2 / max(exp, 0.5) - (0.4 * glen[b] if b <= G else 0)

    dp = [[INF] * (G + 2) for _ in range(n + 1)]
    bk = [[-1] * (G + 2) for _ in range(n + 1)]
    dp[0][0] = 0
    for k in range(n):
        lo, hi = k + 1, (G + 1 if k == n - 1 else G)
        for b in range(lo, hi + 1):
            if k == n - 1 and b != G + 1:
                continue
            for a in range(k, b):
                if dp[k][a] == INF:
                    continue
                c = dp[k][a] + cost(k, a, b)
                if c < dp[k + 1][b]:
                    dp[k + 1][b], bk[k + 1][b] = c, a
    pts, b = [], G + 1
    for k in range(n, 0, -1):
        pts.append(b)
        b = bk[k][b]
    pts.append(0)
    pts = pts[::-1]
    spans = [(en[pts[i]], st[pts[i + 1]]) for i in range(n)]
    return spans, T


def font(p, size):
    return ImageFont.truetype(p, size)


def wrap(draw, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if draw.textlength(t, font=f) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def caption_png(text, path):
    im = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = 70
    f = font(XBOLD, size)
    lines = wrap(d, text, f, 800)
    while len(lines) > 4 and size > 56:
        size -= 6
        f = font(XBOLD, size)
        lines = wrap(d, text, f, 900)
    lh = int(size * 1.12)
    h = lh * len(lines)
    y0 = (700 - h) // 2
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, y0 + i * lh), ln, font=f, fill="white", stroke_width=6, stroke_fill="black")
    im.save(path)
    return 1410 - 350  # overlay y so block centre sits at ~1410


def tag_png(text, path):
    f = font(BOLD, 30)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = tmp.textlength(text, font=f)
    pw, ph = int(tw + 44), 56
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=ph // 2, fill=(20, 20, 20, 190))
    d.text(((pw - tw) / 2, 10), text, font=f, fill="white")
    im.save(path)
    return (W - pw) // 2, 212


def frase_png(text, path):
    f = font(BOLD, 52)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = wrap(tmp, text, f, 840)
    lh = 64
    bh = lh * len(lines) + 70
    bw = 915
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=26, fill=(255, 255, 255, 246))
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        d.text(((bw - tw) / 2, 30 + i * lh), ln, font=f, fill=(17, 17, 17))
    im.save(path)
    return (W - bw) // 2, 1420 - bh // 2


def pill_png(path):
    pw, ph = 384, 96
    im = Image.new("RGBA", (pw, ph + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=ph // 2, fill=(255, 0, 0, 255))
    # bell
    cx, cy = 56, 46
    d.pieslice((cx - 24, cy - 30, cx + 24, cy + 18), 180, 360, fill="white")
    d.rectangle((cx - 24, cy - 6, cx + 24, cy + 14), fill="white")
    d.polygon([(cx - 32, cy + 22), (cx + 32, cy + 22), (cx + 24, cy + 12), (cx - 24, cy + 12)], fill="white")
    d.ellipse((cx - 8, cy + 22, cx + 8, cy + 34), fill="white")
    f = font(BOLD, 44)
    d.text((98, 22), "Suscríbete", font=f, fill="white")
    # arrow
    ax = 192
    d.polygon([(ax - 18, ph + 18), (ax + 18, ph + 18), (ax, ph + 40)], fill="white")
    im.save(path)
    return 48, 1645


def main():
    job = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    tmpd = tempfile.mkdtemp(prefix="story_")
    texts = job["sentences"] + [job["frase"], job["close"]]
    spans, vdur = segment(texts, job["voice"])
    T = round(vdur + 0.8, 3)
    imgs = job["images"]
    n = len(imgs)
    per = T / n
    xf = 0.4

    # 1) background: zooming stills with short crossfades
    parts = []
    for i, p in enumerate(imgs):
        d = per + (xf if i < n - 1 else 0)
        frames = int(math.ceil(d * FPS)) + 1
        o = os.path.join(tmpd, f"bg{i}.mp4")
        zin = i % 2 == 0
        z = "min(1+0.0009*on,1.12)" if zin else "max(1.12-0.0009*on,1.0)"
        vf = (f"scale=1296:2304:flags=lanczos,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={W}x{H}:fps={FPS},format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", p, "-vf", vf, "-frames:v", str(frames),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", o])
        parts.append((o, d))
    bg = os.path.join(tmpd, "bg.mp4")
    if n == 1:
        bg = parts[0][0]
    else:
        args, fc, prev, off = [], [], "0:v", 0.0
        for o, _ in parts:
            args += ["-i", o]
        for i in range(1, n):
            off += parts[i - 1][1] - xf
            lab = f"x{i}"
            fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={xf}:offset={off:.3f}[{lab}]")
            prev = lab
        run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(fc), "-map", f"[{prev}]",
             "-t", str(T), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", bg])

    # 2) overlays
    ov = []  # (png, x, y_expr, t0, t1)
    tx, ty = tag_png(job.get("tag", ""), os.path.join(tmpd, "tag.png"))
    ov.append((os.path.join(tmpd, "tag.png"), tx, str(ty), 0, max(2.0, spans[0][1])))
    nn = len(job["sentences"])
    for i in range(nn):
        p = os.path.join(tmpd, f"cap{i}.png")
        y = caption_png(job["sentences"][i], p)
        s, e = spans[i]
        e2 = spans[i + 1][0] if i + 1 < len(spans) else e
        ov.append((p, 0, str(y), max(0, s - 0.05), e2 - 0.02))
    fx, fy = frase_png(job["frase"], os.path.join(tmpd, "frase.png"))
    ov.append((os.path.join(tmpd, "frase.png"), fx, str(fy), spans[nn][0] - 0.05, T))
    px, py = pill_png(os.path.join(tmpd, "pill.png"))
    ov.append((os.path.join(tmpd, "pill.png"), px, f"{py}+6*sin(2*PI*1.3*t)", T - 3.0, T))

    args = ["-i", bg]
    for o in ov:
        args += ["-loop", "1", "-i", o[0]]
    fc, prev = [], "0:v"
    for k, (_, x, y, t0, t1) in enumerate(ov, start=1):
        lab = f"o{k}"
        fc.append(f"[{prev}][{k}:v]overlay=x={x}:y='{y}':enable='between(t,{t0:.3f},{t1:.3f})':shortest=0:eof_action=pass[{lab}]")
        prev = lab
    vid = os.path.join(tmpd, "vid.mp4")
    run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(fc), "-map", f"[{prev}]",
         "-t", str(T), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", vid])

    # 3) audio: voice + music bed
    mv = job.get("music_vol", 0.12)
    if job.get("music"):
        afc = (f"[0:a]aresample=48000,apad=whole_dur={T}[v];"
               f"[1:a]aresample=48000,volume={mv},afade=t=in:d=1.0,afade=t=out:st={T-1.2:.2f}:d=1.2,atrim=0:{T}[m];"
               f"[v][m]amix=inputs=2:duration=first:normalize=0[a]")
        ains = ["-i", job["voice"], "-stream_loop", "-1", "-i", job["music"]]
    else:
        afc = f"[0:a]aresample=48000,apad=whole_dur={T}[a]"
        ains = ["-i", job["voice"]]
    run(["ffmpeg", "-v", "error", "-y", "-i", vid, *ains, "-filter_complex", afc.replace("[0:a]", "[1:a]", 1).replace("[1:a]aresample=48000,volume", "[2:a]aresample=48000,volume") if job.get("music") else afc.replace("[0:a]", "[1:a]"),
         "-map", "0:v", "-map", "[a]", "-t", str(T), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    json.dump({"spans": spans, "T": T}, open(out + ".timing.json", "w"), indent=1)
    print("ok", out, T)


if __name__ == "__main__":
    main()
