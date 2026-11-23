"""Conservative pixel-art clean-up: lone pixels, dither speckle, 1px outline bumps and dents.

    .venv/bin/python tools/smooth_sprite.py IN.png OUT.png
Never touches white pixels (number, stripes, tape) or the sprite's overall silhouette beyond 1px nubs/notches.
"""
import sys
from collections import Counter

import numpy as np
from PIL import Image
from scipy import ndimage

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (1, -1), (-1, 1), (1, 1)]
WHITE = (255, 255, 255)


def nb(a, y, x, offs):
    h, w = a.shape[:2]
    for dy, dx in offs:
        yy, xx = y + dy, x + dx
        if 0 <= yy < h and 0 <= xx < w:
            yield yy, xx


def dark(c):
    return sum(c) < 160


def speckle_pass(a, protect):
    """Pixel whose 4-neighbours are mostly one other colour -> take that colour (only between similar tones)."""
    out = a.copy()
    n = 0
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x, 3] == 0 or protect[y, x]:
                continue
            me = tuple(a[y, x, :3].tolist())
            votes = Counter(tuple(a[yy, xx, :3].tolist()) for yy, xx in nb(a, y, x, N4) if a[yy, xx, 3])
            if not votes:
                continue
            col, cnt = votes.most_common(1)[0]
            if col == me or cnt < 3 or WHITE in votes and col == WHITE:
                continue
            if dark(col) != dark(me):          # don't blend outline <-> fill
                continue
            if sum(abs(p - q) for p, q in zip(col, me)) > 150:   # leave strong contrast (highlights) alone
                continue
            out[y, x, :3] = col
            n += 1
    return out, n


def silhouette_pass(a):
    out = a.copy()
    op = a[..., 3] > 0
    bumps = dents = 0
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            n4 = sum(1 for yy, xx in nb(a, y, x, N4) if op[yy, xx])
            n8 = sum(1 for yy, xx in nb(a, y, x, N8) if op[yy, xx])
            if op[y, x] and n4 <= 1 and n8 <= 2:         # nub: one pixel poking out
                out[y, x, 3] = 0
                bumps += 1
            elif not op[y, x] and n4 >= 3:               # notch: one pixel missing from the edge
                nbrs = [tuple(a[yy, xx].tolist()) for yy, xx in nb(a, y, x, N4) if op[yy, xx]]
                out[y, x] = Counter(nbrs).most_common(1)[0][0]
                dents += 1
    return out, bumps, dents


def lone_pixel_pass(a, protect):
    """A pixel with no 4-neighbour of its own colour, in the interior -> majority of its neighbours."""
    out = a.copy()
    n = 0
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x, 3] == 0 or protect[y, x]:
                continue
            me = tuple(a[y, x].tolist())
            ns = [tuple(a[yy, xx].tolist()) for yy, xx in nb(a, y, x, N4) if a[yy, xx, 3]]
            if len(ns) == 4 and me not in ns:
                col = Counter(ns).most_common(1)[0][0]
                if col[:3] != WHITE:
                    out[y, x] = col
                    n += 1
    return out, n


def main(src, dst):
    a = np.array(Image.open(src).convert("RGBA"))
    protect = (a[..., :3] == WHITE).all(-1)
    protect |= ndimage.binary_dilation(protect, iterations=1) & (a[..., :3].sum(-1) > 600)
    a0 = a.copy()
    a, s1 = speckle_pass(a, protect)
    a, s2 = speckle_pass(a, protect)
    a, lone = lone_pixel_pass(a, protect)
    a, bumps, dents = silhouette_pass(a)
    a, bumps2, dents2 = silhouette_pass(a)
    Image.fromarray(a).save(dst)
    comp = ndimage.label(a[..., 3] > 0, structure=np.ones((3, 3)))[1]
    print(f"speckle {s1}+{s2}, lone {lone}, bumps {bumps + bumps2}, dents {dents + dents2}; "
          f"changed {int((a != a0).any(-1).sum())} px; pieces {comp}; colours {len({tuple(p) for p in a[a[..., 3] > 0].tolist()})}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
