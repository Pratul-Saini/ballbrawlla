"""Contact sheet of every frame of every set (team x facing), one row per tag, scaled up nearest-neighbour.

    .venv/bin/python tools/aseprite/contact_sheet.py [anim_dir] [out_png] [set ...]
"""
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SETS = ["navy", "navy_left", "red", "red_left"]
SIZE = 96
SCALE = 2
BG = (88, 140, 80, 255)
GROUND = (60, 60, 60, 255)


def load(anim_dir, name):
    with open(os.path.join(anim_dir, name + ".json")) as f:
        meta = json.load(f)
    return Image.open(os.path.join(anim_dir, name + ".png")).convert("RGBA"), meta


def closeup(anim_dir, out, name="navy", tag="run", scale=4):
    """One row of one tag at scale x, nearest neighbour, ground line (row 85) and frame numbers."""
    sheet, meta = load(anim_dir, name)
    t = [t for t in meta["meta"]["frameTags"] if t["name"] == tag][0]
    n = t["to"] - t["from"] + 1
    x0, x1 = 16, 84  # crop the empty margins, the art lives in x 20..80
    cw, ch = (x1 - x0) * scale, 92 * scale
    pad = 6
    img = Image.new("RGBA", (n * (cw + pad) + pad, ch + 20), BG)
    d = ImageDraw.Draw(img)
    for k in range(n):
        fr = meta["frames"][t["from"] + k]["frame"]
        tile = sheet.crop((fr["x"] + x0, fr["y"], fr["x"] + x1, fr["y"] + 92)).resize((cw, ch), Image.NEAREST)
        x = pad + k * (cw + pad)
        d.line([(x, 86 * scale), (x + cw, 86 * scale)], fill=GROUND, width=1)
        img.alpha_composite(tile, (x, 20))
        d.line([(x, 20 + 86 * scale), (x + cw, 20 + 86 * scale)], fill=(255, 255, 0, 255), width=1)
        d.text((x + 2, 4), f"{name} {tag} {k + 1}", fill=(255, 255, 255, 255))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.convert("RGB").save(out)
    print("close-up ->", out, img.size)


def main():
    anim_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "godot/assets/sprites/player/anim")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, ".agents/tasks/smooth-run-jump/contact-sheet.png")
    sets = sys.argv[3:] or SETS
    cell = SIZE * SCALE
    pad = 4
    tags = None
    blocks = []
    for name in sets:
        sheet, meta = load(anim_dir, name)
        frames = meta["frames"]
        tags = [(t["name"], t["from"], t["to"]) for t in meta["meta"]["frameTags"]]
        blocks.append((name, sheet, frames))
    # two rows per set: the run cycle, then every other tag in a single row
    ROWS = [["run"], ["idle", "jump", "apex", "fall", "land"]]
    by_tag = {t[0]: t for t in tags}
    row_h = cell + pad + 12
    block_h = len(ROWS) * row_h + 18
    max_n = max(sum(by_tag[t][2] - by_tag[t][1] + 1 for t in row) for row in ROWS)
    W = max_n * (cell + pad) + pad
    H = block_h * len(blocks)
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)
    for bi, (name, sheet, frames) in enumerate(blocks):
        y0 = bi * block_h
        d.text((4, y0 + 2), name, fill=(255, 255, 255, 255))
        for ri, row in enumerate(ROWS):
            y = y0 + 18 + ri * row_h + 12
            k = 0
            for tag in row:
                _, a, b = by_tag[tag]
                for n, fi in enumerate(range(a, b + 1)):
                    fr = frames[fi]["frame"]
                    tile = sheet.crop((fr["x"], fr["y"], fr["x"] + fr["w"], fr["y"] + fr["h"]))
                    tile = tile.resize((cell, cell), Image.NEAREST)
                    x = pad + k * (cell + pad)
                    d.text((x, y - 12), f"{tag} {n + 1}", fill=(255, 255, 255, 255))
                    d.line([(x, y + 85 * SCALE + SCALE), (x + cell, y + 85 * SCALE + SCALE)], fill=GROUND)
                    img.alpha_composite(tile, (x, y))
                    k += 1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.convert("RGB").save(out)
    print("contact sheet ->", out, img.size)
    if len(sys.argv) <= 1:
        closeup(os.path.join(ROOT, "godot/assets/sprites/player/anim"),
                os.path.join(ROOT, ".agents/tasks/smooth-run-jump/run-cycle-closeup.png"))


if __name__ == "__main__":
    main()
