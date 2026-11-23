"""Placeholder double-jump effect: a strip of 32x32 frames (an expanding, fading pixel ring + sparks).

    .venv/bin/python tools/make_double_jump_fx.py
Writes godot/assets/sprites/player/fx_double_jump.png. Paint over it (any number of square frames side by side,
frame size = the strip's height) and the game picks it up as is.
"""
import math
import os

from PIL import Image, ImageDraw

D = os.path.join(os.path.dirname(__file__), "..", "godot", "assets", "sprites", "player")
S, N = 32, 6
WHITE, LIGHT, MID = (255, 255, 255, 255), (190, 225, 255, 255), (120, 170, 235, 255)


def frame(i):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    t = i / (N - 1)
    rx, ry = 4 + 11.5 * t, 2 + 4.5 * t
    cx, cy = S / 2 - 0.5, S / 2 + 3
    col = WHITE if i < 2 else (LIGHT if i < 4 else MID)
    if i < N - 1:
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=col, width=2 if i < 3 else 1)
    for k in range(6):                         # sparks flying outward and down
        a = math.pi * (0.1 + 0.8 * k / 5)
        r = 3 + 11 * t
        x, y = cx + math.cos(a) * r * 1.2, cy + math.sin(a) * r * 0.6 + 2 * t
        if i < N - 1 and (k + i) % 2 == 0:
            d.point((round(x), round(y)), fill=col)
    return im


strip = Image.new("RGBA", (S * N, S), (0, 0, 0, 0))
for i in range(N):
    strip.paste(frame(i), (S * i, 0))
strip.save(os.path.join(D, "fx_double_jump.png"))
bg = Image.new("RGBA", strip.size, (30, 104, 52, 255)); bg.alpha_composite(strip)
bg.resize((strip.width * 5, strip.height * 5), Image.NEAREST).save("/tmp/fb/fx.png")
print("wrote", strip.size)
