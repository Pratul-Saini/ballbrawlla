"""Make the red team's sprites from the blue ones by shifting the hue of the jersey and pants only.

    .venv/bin/python tools/make_team_sprites.py
Reads fball_navy.png / fball_navy_left.png and writes fball_red.png / fball_red_left.png (hand-editable afterwards).
Only strongly saturated blues move (jersey and pants); skin, helmet, shoes, gloves, outline and number stay.
"""
import colorsys
import os

import numpy as np
from PIL import Image

D = os.path.join(os.path.dirname(__file__), "..", "godot", "assets", "sprites", "player")
TARGET_HUE = 0.0          # red
SAT_BOOST = 1.0


def shift(src, dst):
    a = np.array(Image.open(os.path.join(D, src)).convert("RGBA"))
    out = a.copy()
    n = 0
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            r, g, b, al = (int(v) for v in a[y, x])
            if al == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if 0.50 <= h <= 0.72 and s > 0.45 and v > 0.3:       # blue, saturated, not the dark outline
                nr, ng, nb = colorsys.hsv_to_rgb(TARGET_HUE, min(1.0, s * SAT_BOOST), v)
                out[y, x, :3] = (round(nr * 255), round(ng * 255), round(nb * 255))
                n += 1
    Image.fromarray(out).save(os.path.join(D, dst))
    print(dst, "recoloured", n, "px")


shift("fball_navy.png", "fball_red.png")
shift("fball_navy_left.png", "fball_red_left.png")
