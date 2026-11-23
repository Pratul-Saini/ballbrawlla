"""Automated checks over every frame of both teams and both facings (the exported sheets).

    .venv/bin/python tools/aseprite/check_frames.py [--split-dir DIR]

Exit code 1 when a check fails. Source = the hand-drawn fball_*.png. Checks:
  palette    no opaque colour outside the source palette, alpha only 0 or 255
  layers     (needs --split-dir) the split layers flatten back to the source, pixel for pixel
  gait       (needs --split-dir, uses the per-leg info rig.lua writes) idle: both feet on row 85. Run: in every
             frame exactly one foot is planted (lowest row 85) and the other is lifted at least LIFT rows; the planted
             foot is the front one in the contact frames; the planted leg alternates between the two halves of the
             cycle (and again at the loop point); no frame has both feet flat side by side
  foot line  lowest opaque row == 85 in every grounded frame, <= 85 in air frames
  bounds     nothing opaque on the outer border of the 96x96 frame (nothing clipped)
  orphans    single pixels with no 8-neighbour, not more than the source has
  holes      enclosed transparent pixels above row HOLE_ROWS (torso and pelvis), not more than the source has.
             The gap between two legs that touch lower down is real negative space and is not counted.
  black/white pure #000000 / #FFFFFF counts never above the source counts plus the count inside the source leg
             rows (a leg part may be used twice, e.g. two shoes in idle, which repeats its outline and stripe)
  hand       the ball-hand anchor sits on or next to opaque pixels of the arm
"""
import json
import os
import sys
from collections import deque

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLAYER = os.path.join(ROOT, "godot", "assets", "sprites", "player")
ANIM = os.path.join(PLAYER, "anim")
SOURCES = {"navy": "fball_navy", "navy_left": "fball_navy_left", "red": "fball_red", "red_left": "fball_red_left"}
GROUND_ROW = 85
HOLE_ROWS = 66   # enclosed transparent pixels on rows <= this count as holes
LIFT = 4         # the non-planted foot of a run frame is at least this many rows above the ground row
LEG_TOP = 65
GROUNDED = {"idle": None, "run": None, "land": None, "jump": [0]}  # tag -> frame offsets in tag (None = all)


def colors(a):
    m = a[..., 3] > 0
    return {tuple(int(v) for v in c) for c in a[m]}


def orphans(op):
    p = np.pad(op, 1)
    n = np.zeros(op.shape, int)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                n += p[1 + dy:1 + dy + op.shape[0], 1 + dx:1 + dx + op.shape[1]]
    return int((op & (n == 0)).sum())


def holes(op):
    return int(holes_map(op)[:HOLE_ROWS + 1].sum())


def holes_map(op):
    h, w = op.shape
    seen = np.zeros(op.shape, bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not op[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if not op[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not op[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return ~op & ~seen


def gait(name, legs, fails):
    """Gait assertions for one set. legs[i] = {tag, far: [lowest, x0, x1], near: [...]} per frame (right-facing
    coordinates are mirrored back for the _left sets, so 'front' is the facing side)."""
    facing = -1 if name.endswith("_left") else 1
    ok = True

    def bad(msg):
        nonlocal ok
        ok = False
        fails.append(f"{name} gait: {msg}")

    def centre(leg):
        return facing * (leg[1] + leg[2]) / 2

    idle = [l for l in legs if l["tag"] == "idle"]
    for k, l in enumerate(idle):
        if l["far"][0] != GROUND_ROW or l["near"][0] != GROUND_ROW:
            bad(f"idle#{k + 1}: both feet must be on row {GROUND_ROW}, got {l['far'][0]} / {l['near'][0]}")
    run = [l for l in legs if l["tag"] == "run"]
    planted = []
    for k, l in enumerate(run):
        lo = {"far": l["far"][0], "near": l["near"][0]}
        p = [n for n in lo if lo[n] == GROUND_ROW]
        o = [n for n in lo if lo[n] != GROUND_ROW]
        if len(p) != 1 or GROUND_ROW - lo[o[0]] < LIFT:
            bad(f"run#{k + 1}: need exactly one planted foot on {GROUND_ROW} and the other >= {LIFT} rows higher, got {lo}")
            planted.append(None)
            continue
        planted.append(p[0])
        if k % 4 in (0, 1) and not centre(l[p[0]]) > centre(l[o[0]]):  # contact and down frames
            bad(f"run#{k + 1}: planted foot is not in front of the trailing foot")
    n = len(planted)
    if n == 8 and None not in planted:
        if not (set(planted[:4]) != set(planted[4:]) or planted[0] != planted[4]):
            bad("the planted foot does not alternate between the two halves")
        if planted[0] == planted[4]:
            bad(f"contact frames 1 and 5 plant the same leg: {planted}")
        changes = sum(1 for i in range(n) if planted[i] != planted[(i + 1) % n])
        if changes != 2:
            bad(f"expected the planted foot to change twice per loop, got {changes}: {planted}")
    print(f"[{name}] gait: planted foot per run frame = {planted} -> {'ok' if ok else 'FAIL'}")


def count(a, rgb):
    return int(((a[..., :3] == rgb).all(-1) & (a[..., 3] > 0)).sum())


def main():
    split_dir = None
    if "--split-dir" in sys.argv:
        split_dir = sys.argv[sys.argv.index("--split-dir") + 1]
    with open(os.path.join(ANIM, "player_anim.json")) as f:
        anim = json.load(f)
    fails = []
    total = 0
    for name, src_name in SOURCES.items():
        src = np.array(Image.open(os.path.join(PLAYER, src_name + ".png")).convert("RGBA"))
        pal = colors(src)
        op0 = src[..., 3] > 0
        src_orph, src_holes = orphans(op0), holes(op0)
        src_black = count(src, (0, 0, 0)) + count(src[LEG_TOP:], (0, 0, 0))
        src_white = count(src, (255, 255, 255)) + count(src[LEG_TOP:], (255, 255, 255))
        if split_dir:
            flat = np.array(Image.open(os.path.join(split_dir, name + "_split_flat.png")).convert("RGBA"))
            ok = bool((flat == src).all())
            print(f"[{name}] layers flatten back to the source: {'ok' if ok else 'FAIL'}")
            if not ok:
                fails.append(f"{name}: split layers differ from source")
            with open(os.path.join(split_dir, name + "_legs.json")) as f:
                gait(name, json.load(f), fails)
        sheet = np.array(Image.open(os.path.join(ANIM, name + ".png")).convert("RGBA"))
        bad = {"palette": 0, "foot": 0, "bounds": 0, "orphans": 0, "holes": 0, "black": 0, "white": 0, "hand": 0}
        lowest_by_tag = {}
        for tag, t in anim["tags"].items():
            for k, i in enumerate(range(t["from"], t["to"] + 1)):
                total += 1
                x0, y0, w, h = anim["frames"][i]
                fr = sheet[y0:y0 + h, x0:x0 + w]
                op = fr[..., 3] > 0
                label = f"{name} {tag}#{k + 1} (frame {i + 1})"
                if not set(np.unique(fr[..., 3])) <= {0, 255} or not colors(fr) <= pal:
                    bad["palette"] += 1
                    fails.append(label + ": colour outside source palette or partial alpha")
                ys = np.where(op.any(1))[0]
                low = int(ys.max())
                lowest_by_tag.setdefault(tag, []).append(low)
                grounded = tag in GROUNDED and (GROUNDED[tag] is None or k in GROUNDED[tag])
                if (grounded and low != GROUND_ROW) or (not grounded and low > GROUND_ROW):
                    bad["foot"] += 1
                    fails.append(f"{label}: lowest opaque row {low}, grounded={grounded}")
                if op[0].any() or op[-1].any() or op[:, 0].any() or op[:, -1].any():
                    bad["bounds"] += 1
                    fails.append(label + ": opaque pixel on the frame border (clipped)")
                if orphans(op) > src_orph:
                    bad["orphans"] += 1
                    fails.append(f"{label}: {orphans(op)} orphan pixels (source {src_orph})")
                if holes(op) > src_holes:
                    bad["holes"] += 1
                    fails.append(f"{label}: {holes(op)} enclosed transparent pixels (source {src_holes})")
                if count(fr, (0, 0, 0)) > src_black:
                    bad["black"] += 1
                    fails.append(label + ": more pure black than the source")
                if count(fr, (255, 255, 255)) > src_white:
                    bad["white"] += 1
                    fails.append(label + ": more pure white than the source")
                hx, hy = anim["hands"][name][i]
                hx, hy = int(round(hx)), int(round(hy))
                near = op[max(0, hy - 2):hy + 3, max(0, hx - 2):hx + 3]
                if not near.any():
                    bad["hand"] += 1
                    fails.append(f"{label}: hand anchor ({hx},{hy}) is not on the sprite")
        print(f"[{name}] frames={sum(1 for _ in range(len(anim['frames'])))} source orphans={src_orph} holes={src_holes}"
              f" | failures: " + ", ".join(f"{k}={v}" for k, v in bad.items()))
        print(f"[{name}] lowest row per tag: " + "; ".join(f"{t}={v}" for t, v in lowest_by_tag.items()))
    if fails:
        print("\nFAILED:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print(f"all checks passed ({total} frame checks over 4 sets)")


if __name__ == "__main__":
    main()
