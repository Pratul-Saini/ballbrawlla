"""Builds docs/level-design/layout.json for the big field (left half; the right half mirrors it).

    python tools/build_field_05_layout.py

Scale: 48 px per yard, field 5824 x 2400. Heights are px above the floor. A "pipe" is a solid wall (24 px wide).

Two foundational skill moves (numbers measured with the real physics):
  PIPE HOP   The sky deck is broken so you must land on the 24 px top of a pipe to continue. Each leg is
             HOP px (a single jump crosses at most 220), and ledge-to-ledge past the pipe is over 340 px,
             so a double jump cannot skip it.
  SLIDE      Low tunnels (gap 32 px) of TUNNEL px total length. The slide covers about 150 px, so a longer
             tunnel gives a tighter start window (114 px: about 40 px, 0.12 s). Too early = crawl, too late = bonk.
Gates are pipes with three doors: a slide slot (floor), a 140 px window (mid deck), and a hop on top (sky).
"""

import json
from pathlib import Path

W, H, WALL, YD = 5824, 2400, 32, 48
DECK, SKY, STEP = 280, 840, 140
HOP = 190            # a hop leg onto a pipe or off one (single jump max is 220)
HARD_HOP = 214       # the tightest legs
SLOT = 32            # gap under a pipe or a tunnel roof (crouch is 30)
pieces: list[dict] = []


def thin(pid, x, top, w, role=""):
    pieces.append({"id": pid, "type": "thin", "x": x, "w": w, "top": top, "role": role})


def solid(pid, x, top, h, w=24, role=""):
    pieces.append({"id": pid, "type": "solid", "x": x, "w": w, "top": top, "h": h, "role": role})


def gate(name, x, tunnel=0):
    """A pipe from the slot up to the sky deck, with a window at deck height. `tunnel` adds a low roof on its right."""
    solid(f"{name}_lo", x, DECK, DECK - SLOT, role="pipe sill: slide slot below, walkable top")
    solid(f"{name}_hi", x, SKY, SKY - (DECK + STEP), role="pipe above the window: its top is a hop target")
    if tunnel:
        solid(f"{name}_tun", x + 24, SLOT + 24, 24, w=tunnel, role="tunnel roof: slide")


def ladder(name, xs, base=DECK):
    """Zig-zag thin ledges one tier apart (base+140, +280, +420) up to just under the sky deck."""
    for i, x in enumerate(xs, 1):
        thin(f"{name}{i}", x, base + STEP * i, 80, "ladder")


# ======================================================================== end zone and gate 0 (x 32 to 512)
gate("g0", 488, tunnel=90)                     # tunnel length 24 + 90 = 114 px
thin("shelf", 100, DECK, 380, "pocket shelf at deck height: the window leads onto it (scores)")

# ======================================================================== segment 1 (x 512 to 1000): the QB zone
thin("qb", 512, 140, 480, "QB ledge: first 10 yd, single-jump height")
thin("D1a", 512, DECK, 150, "deck: flush with the g0 sill, so it walks through the window")
thin("D1b", 742, DECK, 110); thin("D1c", 912, DECK, 88, "deck: flush with the g1 sill")
ladder("L1_", [780, 690, 760])
thin("SK1", 512 + HOP, SKY, 108, "sky: HOP onto g0's top (a score) or g1's top")
gate("g1", 1000, tunnel=0)

# ======================================================================== segment 2 (x 1024 to 1472): the bulwark
# A pipe 120 px thick: its slot is a 120 px slide tunnel, its window is a 120 px corridor, its top is a wide landing.
solid("B2_lo", 1180, DECK, DECK - SLOT, w=120, role="bulwark sill: 120 px slide tunnel below, walkable top")
solid("B2_hi", 1180, SKY, SKY - (DECK + STEP), w=120, role="bulwark above the window: wide landing at 840")
thin("D2a", 1024, DECK, 150, "deck")
thin("D2b", 1300, DECK, 172, "deck: leaves the bulwark window and meets the g2 sill")
thin("R2", 1060, 140, 90, "ramp: ground to deck, before the bulwark")
thin("L2_1", 1320, 420, 80, "ladder"); thin("L2_2", 1380, 560, 80, "ladder"); thin("L2_3", 1320, 700, 80, "ladder")
gate("g2", 1472, tunnel=90)

# ======================================================================== segments 3 and 4 (x 1496 to 2432): the great slab
# A mass 700 px wide and 200 thick. Under it: a covered corridor (deck and ground). On it: a wide plateau.
# Above it: the sky hops, with a pipe standing on the slab.
solid("GS", 1640, 700, 200, w=700, role="great slab: plateau on top, covered corridor underneath")
thin("GA", 1500, 420, 70, "ladder to the slab"); thin("GB", 1560, 560, 70, "last step: flush with the slab face, hop onto the plateau")
thin("D3a", 1496, DECK, 130, "deck: flush with the g2 sill, enters the corridor")
thin("D3b", 1700, DECK, 200, "deck under the slab")
solid("TR", 1760, DECK + SLOT + 24, 24, w=114, role="tunnel roof under the slab: slide (114 px)")
thin("D3c", 1980, DECK, 200, "deck under the slab")
thin("D4", 2340, DECK, 92, "deck: leaves the corridor, flush with the g4 sill")
thin("R3", 1660, 140, 90, "ramp: ground to deck"); thin("R4", 2090, 140, 90, "ramp: ground to deck")
solid("P1", 1946, SKY, SKY - 700, role="pipe standing on the slab: the middle sky hop")
thin("SKa", 1686, SKY, 70, "sky: first landing past g2"); thin("SKb", 2160, SKY, 70, "sky: last landing before g4")
gate("g4", 2432, tunnel=0)

# ======================================================================== segment 5 (x 2456 to 2912): the hub, centred on midfield
solid("HS", 2612, 560, 100, w=600, role="hub slab: a 600 px stage at 560, centred")
thin("HA1", 2470, 420, 80, "ladder to the hub"); thin("HB1", 2522, 560, 80, "last step: flush with the slab face")
thin("HA", 2852, 700, 120, "hub apex (centred): hop up from the slab")
thin("D5a", 2456, DECK, 130, "deck under the hub"); thin("D5b", 2666, DECK, 140, "deck"); thin("D5c", 2842, DECK, 140, "hub deck (centred)")
thin("R5", 2700, 140, 90, "ramp: ground to deck")
thin("SK5", 2432 + 24 + HOP, SKY, 100, "sky"); thin("SKc", 2822, SKY, 180, "sky deck (centred)")

layout = {
    "_comment": "Generated by tools/build_field_05_layout.py. LEFT half only; the right half mirrors it: x' = width - x - w. "
                "'top' = height of the top above the floor (px). Thin ledges are 12 px thick; solids use 'h'. "
                "Check with: python tools/layout_tools.py check",
    "arena": {"width": W, "height": H, "wall": WALL, "yard_px": YD},
    "thin_thickness": 12,
    "frames": [],
    "zones": [{"id": "pocket", "name": "End zone pocket (scoring floor)", "x0": 32, "x1": 488, "frame": "F1"}],
    "pieces": pieces,
    "moves": [{"from": "floor", "to": "pocket", "how": "slide", "note": "32 px slot under g0"}],
}
out = Path(__file__).resolve().parents[1] / "docs" / "level-design" / "layout.json"
out.write_text(json.dumps(layout, indent=1) + "\n")
print(len(pieces), "left-half pieces ->", out.relative_to(out.parents[2]))
