#!/usr/bin/env python3
"""Long-form "reflexión para dormir" assembler (rebuilt Nov 24 2026 to match long-form #2).

usage: assemble_lf.py job.json out.mp4
job = {
  "segments": [ {"card": null | ["Capítulo 1", "Que les da miedo llamarte"],
                 "voice": "01.wav", "images": ["a.png", "b.png"]}, ... ],
  "music": "music-track2.wav", "music_vol": 0.10
}
Look: 1920x1080 30 fps, no captions, each still slowly zooming (alternating in/out) with 0.8 s
crossfades, a 3 s dark chapter card before each chapter ("Capítulo N", subtitle, short gold rule),
1.2 s of breathing room after each segment, music bed under everything. Writes out.mp4 and
out.chapters.txt (YouTube chapter list).
"""
import json, math, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
if not os.path.exists(SEMI):
    SEMI = BOLD
CARD = 3.0
TAIL = 1.2
XF = 0.8


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit("ffmpeg failed")


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p]).decode().strip())


def card_png(title, sub, path):
    im = Image.new("RGB", (W, H), (16, 17, 22))
    d = ImageDraw.Draw(im)
    f1, f2 = ImageFont.truetype(BOLD, 96), ImageFont.truetype(SEMI, 40)
    tw = d.textlength(title, font=f1)
    d.text(((W - tw) / 2, 395), title, font=f1, fill=(245, 242, 236))
    sw = d.textlength(sub, font=f2)
    d.text(((W - sw) / 2, 520), sub, font=f2, fill=(200, 196, 188))
    d.rectangle((W / 2 - 50, 590, W / 2 + 50, 594), fill=(214, 168, 72))
    im.save(path)


def stills(images, total, out, tmpd, tag):
    n = len(images)
    per = (total + XF * (n - 1)) / n
    parts = []
    for i, p in enumerate(images):
        frames = int(math.ceil(per * FPS)) + 1
        o = os.path.join(tmpd, f"{tag}_{i}.mp4")
        step = 0.10 / frames
        z = f"min(1+{step:.6f}*on,1.10)" if i % 2 == 0 else f"max(1.10-{step:.6f}*on,1.0)"
        vf = (f"scale=2160:1215:flags=lanczos,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={W}x{H}:fps={FPS},format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", p, "-vf", vf, "-frames:v", str(frames),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", o])
        parts.append(o)
    if n == 1:
        run(["ffmpeg", "-v", "error", "-y", "-i", parts[0], "-t", f"{total:.3f}", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "18", "-r", str(FPS), out])
        return
    args, fc, prev, off = [], [], "0:v", 0.0
    for o in parts:
        args += ["-i", o]
    for i in range(1, n):
        off += per - XF
        fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
        prev = f"x{i}"
    run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(fc), "-map", f"[{prev}]",
         "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out])


def main():
    job = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    tmpd = tempfile.mkdtemp(prefix="lf_")
    vlist, alist, chapters, t = [], [], [], 0.0
    for k, seg in enumerate(job["segments"]):
        if seg.get("card"):
            png = os.path.join(tmpd, f"card{k}.png")
            card_png(seg["card"][0], seg["card"][1], png)
            cv = os.path.join(tmpd, f"card{k}.mp4")
            run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(CARD), "-i", png,
                 "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={CARD-0.5}:d=0.5,format=yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", cv])
            vlist.append(cv)
            sil = os.path.join(tmpd, f"cs{k}.wav")
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", str(CARD), "-i", "anullsrc=r=48000:cl=mono", sil])
            alist.append(sil)
            chapters.append((t, f"{seg['card'][0].replace('Capítulo ', '')}. {seg['card'][1]}"))
            t += CARD
        elif k == 0:
            chapters.append((0.0, job.get("intro_label", "Introducción")))
        else:
            chapters.append((t, seg.get("label", "Cierre")))
        d = dur(seg["voice"]) + TAIL
        sv = os.path.join(tmpd, f"seg{k}.mp4")
        stills(seg["images"], d, sv, tmpd, f"s{k}")
        vlist.append(sv)
        sa = os.path.join(tmpd, f"sa{k}.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", seg["voice"], "-af", f"aresample=48000,pan=mono|c0=c0,apad=whole_dur={d:.3f}",
             "-t", f"{d:.3f}", sa])
        alist.append(sa)
        t += d
    lst = os.path.join(tmpd, "v.txt")
    open(lst, "w").write("".join(f"file '{v}'\n" for v in vlist))
    vid = os.path.join(tmpd, "video.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid])
    alst = os.path.join(tmpd, "a.txt")
    open(alst, "w").write("".join(f"file '{a}'\n" for a in alist))
    voice = os.path.join(tmpd, "voice.wav")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", alst, "-c", "pcm_s16le", voice])
    T = dur(voice)
    mv = job.get("music_vol", 0.10)
    afc = (f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[v];"
           f"[2:a]aresample=48000,volume={mv},afade=t=in:d=2,afade=t=out:st={T-3:.2f}:d=3,atrim=0:{T:.3f}[m];"
           f"[v][m]amix=inputs=2:duration=first:normalize=0[a]")
    run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", voice, "-stream_loop", "-1", "-i", job["music"],
         "-filter_complex", afc, "-map", "0:v", "-map", "[a]", "-t", f"{T:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    def ts(s):
        s = int(round(s)); return f"{s//60:02d}:{s%60:02d}"
    open(out + ".chapters.txt", "w").write("\n".join(f"{ts(a)} {b}" for a, b in chapters) + "\n")
    print("ok", out, round(T, 1), "s")


if __name__ == "__main__":
    main()
