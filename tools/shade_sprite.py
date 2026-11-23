"""Re-shade a flat pixel-art sprite: light from the top left, per-material colour ramps, dithered gradients.

    .venv/bin/python tools/shade_sprite.py IN.png OUT.png

Materials are found by colour in the hand-drawn sprite (jersey blue, skin, navy pants, black shoes/gloves).
Outlines, the number, white stripes and the hand-placed grey highlights are left untouched.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# ramps run light -> dark; thresholds are where each step starts on the 0..1 shade value
RAMPS = {
    "jersey": dict(colors=[rgb(c) for c in ("#9cc6ff", "#639bff", "#4f82e2", "#3f65bb", "#324d94")],
                   cuts=[-9, 0.20, 0.50, 0.70, 0.90]),
    "skin":   dict(colors=[rgb(c) for c in ("#a2653f", "#8f563b", "#7a4a3a", "#663931")],
                   cuts=[-9, 0.30, 0.66, 0.90]),
    "pants":  dict(colors=[rgb(c) for c in ("#3b3a60", "#2c2b4a", "#222034", "#1a1829", "#121120")],
                   cuts=[-9, 0.16, 0.42, 0.68, 0.90]),
    "pants_navy": dict(colors=[rgb(c) for c in ("#5873c4", "#4562ae", "#364f8f", "#2a3d70", "#1f2e56")],
                       cuts=[-9, 0.16, 0.42, 0.68, 0.90]),
    "pants_gray": dict(colors=[rgb(c) for c in ("#c4c9d6", "#a4abbc", "#868ea3", "#6c748a", "#555b70")],
                       cuts=[-9, 0.16, 0.42, 0.68, 0.90]),
    "pants_white": dict(colors=[rgb(c) for c in ("#ffffff", "#eff1f8", "#d7dcea", "#b6bdd0", "#939bb3")],
                        cuts=[-9, 0.16, 0.42, 0.68, 0.90]),
    "shoes":  dict(colors=[rgb(c) for c in ("#ffffff", "#e6e9f2", "#bcc3d4", "#8b93aa", "#5a6078")],
                   cuts=[-9, 0.16, 0.40, 0.66, 0.88]),
    "black":  dict(colors=[rgb(c) for c in ("#3a3a52", "#232236", "#0f0f1a", "#000000")],
                   cuts=[-9, 0.12, 0.34, 0.80]),
}


def run_len(mask, dx, dy, limit=4):
    """How many consecutive surface pixels lie in direction (dx,dy) starting from each pixel (excluding itself)."""
    h, w = mask.shape
    out = np.zeros(mask.shape, int)
    alive = mask.copy()
    for k in range(1, limit + 1):
        sh = np.zeros_like(mask)
        ys = slice(max(0, -dy * k), h - max(0, dy * k))
        xs = slice(max(0, -dx * k), w - max(0, dx * k))
        yd = slice(max(0, dy * k), h + min(0, dy * k))
        xd = slice(max(0, dx * k), w + min(0, dx * k))
        sh[ys, xs] = mask[yd, xd]
        alive &= sh
        out += alive
    return out


def shade(mask, surface, ramp, fold=0.0, seed=0):
    """Return (ys, xs, colours) for the pixels of `mask`. `surface` is the wider shape used for edge distances."""
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return ys, xs, []
    lab, n = ndimage.label(surface, structure=np.ones((3, 3)))
    dr = np.minimum(run_len(surface, 1, 0), run_len(surface, 0, 1))
    ul = np.minimum(run_len(surface, -1, 0), run_len(surface, 0, -1))
    cols = []
    bbox = {}
    for i in range(1, n + 1):
        yy, xx = np.where(lab == i)
        bbox[i] = (xx.min(), xx.max(), yy.min(), yy.max())
    for y, x in zip(ys, xs):
        x0, x1, y0, y1 = bbox[lab[y, x]]
        u = ((x - x0) + (y - y0)) / max(1, (x1 - x0) + (y1 - y0))
        s = 0.12 + 0.78 * u
        d = dr[y, x]
        s += {0: 0.34, 1: 0.14}.get(d, 0.0)          # darker where the lit side ends (bottom/right edges)
        e = ul[y, x]
        s -= {0: 0.32, 1: 0.10}.get(e, 0.0)          # lighter along top/left edges
        s += fold * np.sin(0.62 * x + 0.95 * y + seed)
        s += BAYER[y % 4, x % 4] * 0.09              # dither: turns band edges into checker texture
        idx = max(i for i, c in enumerate(ramp["cuts"]) if s >= c)
        cols.append(ramp["colors"][idx])
    return ys, xs, cols


def classify(a):
    c = a[..., :3].astype(int)
    op = a[..., 3] > 0

    def is_(h):
        return op & (c == rgb(h)).all(-1)
    jersey = is_("#639bff")
    skin = is_("#8f563b") | is_("#663931")
    return op, jersey, skin, is_("#000000"), is_("#222034")


def fix_leg_interior(out, ramp_name):
    """Leftover grey/black outline pixels inside the pants: outline colour at the silhouette, shadow tone inside."""
    H, W = out.shape[:2]
    outline = rgb("#222034")
    shadow = RAMPS[ramp_name]["colors"][-1]
    op = out[..., 3] > 0
    grey = {rgb("#595652"), rgb("#696a6a"), rgb("#847e87")}
    n = 0
    for y in range(55, 74):
        for x in range(20, 72):
            if not op[y, x]:
                continue
            c = tuple(out[y, x, :3].tolist())
            if c not in grey and c != (0, 0, 0):
                continue
            edge = any(not op[yy, xx] for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2)
                       if 0 <= yy < H and 0 <= xx < W)
            out[y, x, :3] = outline if edge else shadow
            n += 1
    return n


def main(src, dst, pants_kind="navy"):
    a = np.array(Image.open(src).convert("RGBA"))
    op, jersey, skin, black, navy = classify(a)
    out = a.copy()
    H, W = a.shape[:2]
    rows = np.arange(H)[:, None] * np.ones((H, W), int)
    cols = np.arange(W)[None, :] * np.ones((H, W), int)

    cloth = ndimage.binary_fill_holes(jersey)
    # shoes: the two feet, shaded as one light material inside a 1px outline
    shoe_front = op & (rows >= 74) & (cols >= 52)
    shoe_back = op & (rows >= 73) & (cols >= 20) & (cols <= 36)
    shoes = shoe_front | shoe_back
    shoe_in = shoes & ndimage.binary_erosion(op, iterations=1)
    # pants: everything below the waist that is not skin, shoe or the white sock; thick black bands become cloth
    sock = (rows >= 69) & (rows <= 73) & (cols >= 57) & (cols <= 62)
    legs = op & (rows >= 50) & ~shoes & ~skin
    in2 = ndimage.binary_erosion(op, iterations=2)
    stripe = legs & (a[..., :3] == WHITE_RGB).all(-1) & ~sock & (rows <= 72)
    pants = legs & (navy | black) & in2 & ~sock
    pants_surface = ndimage.binary_fill_holes(pants | stripe)
    # outline = what's left of black/navy at the silhouette; thick bands were absorbed into `pants`
    ramp = "pants_" + pants_kind
    jobs = [
        (jersey, cloth, "jersey", 0.03, 0.0),
        (skin, skin, "skin", 0.0, 0.0),
        (pants, pants_surface, ramp, 0.03, 1.7),
        (shoe_in, shoes, "shoes", 0.0, 0.0),
    ]
    big_black = black & in2 & (rows < 50)
    jobs.append((big_black, big_black, "black", 0.0, 0.0))
    for mask, surface, name, fold, seed in jobs:
        ys, xs, cols_ = shade(mask, surface, RAMPS[name], fold, seed)
        for y, x, col in zip(ys, xs, cols_):
            out[y, x, :3] = col
    if pants_kind == "white":    # white pants: the stripe turns navy so it still shows
        out[stripe, :3] = rgb("#2a3d70")
    print("leg fix:", fix_leg_interior(out, ramp), "px")
    Image.fromarray(out).save(dst)
    print("changed", int((out != a).any(-1).sum()), "pixels;", len({tuple(p) for p in out[op].tolist()}), "colours")


WHITE_RGB = (255, 255, 255)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "navy")
