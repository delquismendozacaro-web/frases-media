#!/usr/bin/env python3
"""Long-form thumbnail in the long-form #2 style.
usage: lf_thumb.py bg.png out.jpg "cosas que tus papás" "NUNCA" "te van a decir" [number]
1280x720, darkened background, big yellow number left, white lines with the middle word in yellow,
footer "frases de inspiración · reflexión para dormir".
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
BD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
Y, WH = (255, 196, 64), (248, 244, 236)


def main():
    bg, out, l1, l2, l3 = sys.argv[1:6]
    num = sys.argv[6] if len(sys.argv) > 6 else "7"
    im = Image.open(bg).convert("RGB")
    s = max(1280 / im.width, 720 / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x0, y0 = (im.width - 1280) // 2, (im.height - 720) // 2
    im = im.crop((x0, y0, x0 + 1280, y0 + 720))
    im = ImageEnhance.Brightness(im).enhance(0.55)
    shade = Image.new("L", (1280, 720))
    sd = ImageDraw.Draw(shade)
    for x in range(1280):
        sd.line([(x, 0), (x, 720)], fill=int(150 * max(0, 1 - x / 1100)))
    im = Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, shade)
    d = ImageDraw.Draw(im)
    fn = ImageFont.truetype(XB, 340)
    d.text((60, 70), num, font=fn, fill=Y, stroke_width=6, stroke_fill=(0, 0, 0))
    lines = [(l1, ImageFont.truetype(XB, 74), WH), (l2, ImageFont.truetype(XB, 120), Y),
             (l3, ImageFont.truetype(XB, 74), WH)]
    y = 175
    for t, f, c in lines:
        # shrink to fit
        size = f.size
        while d.textlength(t, font=f) > 1280 - 330 - 40 and size > 30:
            size -= 4
            f = ImageFont.truetype(XB, size)
        d.text((330, y), t, font=f, fill=c, stroke_width=5, stroke_fill=(0, 0, 0))
        y += int(size * 1.15) + 10
    d.text((70, 655), "frases de inspiración · reflexión para dormir", font=ImageFont.truetype(BD, 38),
           fill=(205, 196, 180))
    im.save(out, quality=92)
    print("ok", out)


if __name__ == "__main__":
    main()
