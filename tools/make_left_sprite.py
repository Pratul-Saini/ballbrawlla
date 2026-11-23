"""Mirror the right-facing player sprite and put the jersey number back the right way round.

    .venv/bin/python tools/make_left_sprite.py
"""
import os

import numpy as np
from PIL import Image

D = os.path.join(os.path.dirname(__file__), "..", "godot", "assets", "sprites", "player")


def is_jersey(p):
    return p[3] > 0 and p[2] > 150 and int(p[2]) > int(p[0]) + 40 and p[0] < 200


def main():
    a = np.array(Image.open(os.path.join(D, "fball_navy.png")).convert("RGBA"))
    H, W = a.shape[:2]
    ys, xs = np.where((a[..., :3] == 255).all(-1) & (a[..., 3] > 0))
    sel = (ys >= 29) & (ys <= 40) & (xs >= 46) & (xs <= 66)
    y0, y1, x0, x1 = ys[sel].min() - 1, ys[sel].max() + 1, xs[sel].min() - 1, xs[sel].max() + 1
    print("number box x", x0, x1, "y", y0, y1)
    flipped = a[:, ::-1].copy()
    nx0 = W - 1 - x1
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            p = a[y, x]
            if p[3] and not is_jersey(p):
                flipped[y, nx0 + (x - x0)] = p
    Image.fromarray(flipped).save(os.path.join(D, "fball_navy_left.png"))
    # near-arm glove: the dark pixels of the right-hand fist (x >= 72, y 33..44)
    gy, gx = np.where((a[..., 3] > 0) & (a[..., :3].sum(-1) < 90))
    m = (gx >= 72) & (gy >= 33) & (gy <= 44)
    print("glove centre", float(gx[m].mean()), float(gy[m].mean()), "bbox", gx[m].min(), gx[m].max(), gy[m].min(), gy[m].max())
    bb = Image.fromarray(a).getbbox()
    print("sprite bbox", bb)
    both = Image.new("RGBA", (2 * 480 + 20, 480), (88, 140, 80, 255))
    for i, arr in enumerate((a, flipped)):
        b = Image.new("RGBA", (W, H), (88, 140, 80, 255))
        b.alpha_composite(Image.fromarray(arr))
        both.alpha_composite(b.resize((480, 480), Image.NEAREST), (i * 500, 0))
    both.save("/tmp/fb/leftright.png")


main()
