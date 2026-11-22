"""Generates levels/field_02.json from docs/level-design/layout.json.

    python tools/gen_field_02.py levels/field_02.json

The layout file holds the LEFT half; the right half is its mirror (x' = width - x - w).
Pieces centred on midfield are their own mirror and are written once.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_tools import Layout  # noqa: E402

lay = Layout()
mid = lay.W / 2
left = list(lay.pieces)
right = [lay.mirrored(p) for p in lay.pieces if abs(p["x"] + p["w"] / 2 - mid) > 1e-6]


def entry(p: dict) -> dict:
    r = lay.rect(p)
    d = {"x": round(r.x), "y": round(r.y), "w": round(r.w), "h": round(r.h)}
    if p["type"] == "thin":
        d["type"] = "thin"
    return d


platforms = [entry(p) for p in left] + [entry(p) for p in right]
yd = lambda n: lay.WALL + 10 * lay.yard + n * lay.yard  # x of the left team's n-yard line
floor = lay.floor
level = {
    "name": "Field 02",
    "width": lay.W,
    "height": lay.H,
    "wall_thickness": lay.WALL,
    "player_spawns": [[yd(5), floor - 24], [lay.W - yd(5), floor - 24]],
    "ball_spawn": [mid, 900],
    "yard_px": lay.yard,
    "platforms": platforms,
}
out = Path(sys.argv[1])
with out.open("w") as f:
    f.write("{\n")
    for k in ["name", "width", "height", "wall_thickness", "yard_px", "player_spawns", "ball_spawn"]:
        f.write(f'  "{k}": {json.dumps(level[k])},\n')
    f.write('  "platforms": [\n')
    f.write(",\n".join("    " + json.dumps(p) for p in platforms))
    f.write("\n  ]\n}\n")
print(len(platforms), "platforms ->", out)
