"""Generates levels/field_01.json (run: python tools/gen_field_01.py levels/field_01.json): 100-yard field + two 10-yard end zones at 24 px/yard.
Left half is authored; the right half mirrors it. Thin = one-way ledges, solid = obstacles."""
import json, sys

W, H, T = 2944, 1080, 32
FLOOR = H - T            # 1048
YD = 24
GOAL_L = T + 10 * YD     # 272: left goal line, x of yard 0
def yd(y): return GOAL_L + y * YD   # x of the left team's y-yard line

left = [
    # --- left end zone: ledges stepping up the wall (a scoring target and a 2nd route)
    ("thin",  T,        920, 120, 16),
    ("thin",  150,      800, 100, 16),
    ("thin",  T,        680, 130, 16),
    # --- 0-15: QB region; gentle start
    ("solid", yd(6),    FLOOR - 40, 70, 40),          # knee-high block
    ("thin",  yd(3),    930, 150, 16),
    ("thin",  yd(9),    820, 140, 16),
    # --- 15-30
    ("solid", yd(17),   FLOOR - 150, 24, 150),        # wall: double jump or go over
    ("thin",  yd(13),   700, 130, 16),
    ("thin",  yd(19),   930, 160, 16),
    ("thin",  yd(22),   800, 120, 16),
    ("thin",  yd(26),   670, 140, 16),
    ("solid", yd(24),   430, 24, 240),                # hanging wall for wall-jumps
    # --- 30-45
    ("solid", yd(31),   FLOOR - 42, 200, 10),         # low slab (32px gap): slide/crouch under or hop on
    ("thin",  yd(30),   900, 120, 16),
    ("thin",  yd(35),   780, 150, 16),
    ("thin",  yd(32),   560, 130, 16),
    ("thin",  yd(39),   650, 120, 16),
    ("solid", yd(41),   FLOOR - 110, 60, 110),        # step block
    ("thin",  yd(43),   900, 110, 16),
    ("thin",  yd(37),   440, 120, 16),
]

# Midfield (symmetric about x = W/2)
mid = W / 2
center = [
    ("solid", mid - 12, FLOOR - 200, 24, 200),        # tall midfield wall
    ("thin",  mid - 110, 820, 220, 16),               # bridge over it
    ("thin",  mid - 70, 600, 140, 16),
    ("thin",  mid - 160, 700, 70, 16),
    ("thin",  mid + 90, 700, 70, 16),
]

def mirror(p):
    kind, x, y, w, h = p
    return (kind, W - x - w, y, w, h)

plats = left + center + [mirror(p) for p in left]
out = []
for kind, x, y, w, h in plats:
    d = {"x": round(x), "y": round(y), "w": w, "h": h}
    if kind == "thin":
        d["type"] = "thin"
    out.append(d)

level = {
    "name": "Field 01",
    "width": W, "height": H, "wall_thickness": T,
    "player_spawns": [[yd(5), FLOOR - 24], [W - yd(5), FLOOR - 24]],
    "ball_spawn": [mid, 300],
    "platforms": out,
}
with open(sys.argv[1], "w") as f:
    f.write("{\n")
    for k in ["name", "width", "height", "wall_thickness", "player_spawns", "ball_spawn"]:
        f.write(f'  "{k}": {json.dumps(level[k])},\n')
    f.write('  "platforms": [\n')
    f.write(",\n".join("    " + json.dumps(p) for p in out))
    f.write("\n  ]\n}\n")
print(len(out), "platforms")
