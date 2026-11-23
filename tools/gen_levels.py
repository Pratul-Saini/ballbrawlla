"""Generates the football field levels in levels/.

    python tools/gen_levels.py            # writes every level
    python tools/gen_levels.py field_03   # writes one

Every field is 100 yards plus two 10-yard end zones. Bigger levels use more
pixels per yard (`yard_px`) and more height. Each level is authored as its left
half (plus a symmetric center) and mirrored, so neither team has an easier route.

Movement budget used when placing platforms (see config.py):
  single jump ~150 px up, double jump ~250 px up, ~240 px across on one jump,
  slide/crouch fits a gap >= 30 px, wall cling + Up climbs any wall.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LEVELS = Path(__file__).resolve().parents[1] / "levels"
WALL = 32


class Builder:
    def __init__(self, name: str, yard_px: float, height: int, write_yard_px: bool = True) -> None:
        self.name = name
        self.YD = yard_px
        self.H = height
        self.W = 2 * WALL + 120 * yard_px
        self.FLOOR = height - WALL
        self.mid = self.W / 2
        self.write_yard_px = write_yard_px
        self.left: list[tuple] = []
        self.center: list[tuple] = []

    def yd(self, y: float) -> float:
        """x of the left team's y-yard line (negative = in the left end zone)."""
        return WALL + 10 * self.YD + y * self.YD

    # --- primitives (left half unless center=True)
    def solid(self, x, y, w, h, center=False):
        (self.center if center else self.left).append(("solid", x, y, w, h))

    def thin(self, x, y, w, h=16, center=False):
        (self.center if center else self.left).append(("thin", x, y, w, h))

    # --- shapes
    def tower(self, x, w, height, center=False):
        """Solid building standing on the floor."""
        self.solid(x, self.FLOOR - height, w, height, center)

    def crawl(self, x, w, gap=34, thick=12, center=False):
        """Low slab: slide/crouch underneath (gap >= 30) or hop on top."""
        self.solid(x, self.FLOOR - gap - thick, w, thick, center)

    def hang(self, x, top, height, w=24, center=False):
        """Floating vertical wall for wall-jumps."""
        self.solid(x, top, w, height, center)

    def ground(self, x0, x1, top, bottom=None, center=False):
        """Terrain: solid ground from x0 to x1 with its surface at `top`, filled down
        to the floor (or to `bottom`, leaving a corridor underneath)."""
        bottom = self.FLOOR if bottom is None else bottom
        self.solid(x0, top, x1 - x0, bottom - top, center)

    def build(self, player_spawn_yards=5, ball_spawn_y=300, player_spawn_y=None) -> dict:
        def mirror(p):
            kind, x, y, w, h = p
            return (kind, self.W - x - w, y, w, h)

        plats = self.left + self.center + [mirror(p) for p in self.left]
        out = []
        for kind, x, y, w, h in plats:
            d = {"x": round(x), "y": round(y), "w": w, "h": h}
            if kind == "thin":
                d["type"] = "thin"
            out.append(d)
        level = {
            "name": self.name,
            "width": self.W,
            "height": self.H,
            "wall_thickness": WALL,
            "player_spawns": [
                [self.yd(player_spawn_yards), player_spawn_y or self.FLOOR - 24],
                [self.W - self.yd(player_spawn_yards), player_spawn_y or self.FLOOR - 24],
            ],
            "ball_spawn": [self.mid, ball_spawn_y],
        }
        if self.write_yard_px:
            level["yard_px"] = self.YD
        level["platforms"] = out
        return level


def write(level: dict, path: Path) -> None:
    keys = [k for k in level if k != "platforms"]
    with open(path, "w") as f:
        f.write("{\n")
        for k in keys:
            f.write(f'  "{k}": {json.dumps(level[k])},\n')
        f.write('  "platforms": [\n')
        f.write(",\n".join("    " + json.dumps(p) for p in level["platforms"]))
        f.write("\n  ]\n}\n")


# ---------------------------------------------------------------- field_01

def field_01() -> dict:
    """The original field: mixed obstacles, one-way ledge tiers, a midfield wall."""
    b = Builder("Field 01", 24, 1080, write_yard_px=False)
    F, yd = b.FLOOR, b.yd
    b.thin(WALL, 920, 120); b.thin(150, 800, 100); b.thin(WALL, 680, 130)  # end zone ledges
    b.solid(yd(6), F - 40, 70, 40)            # knee-high block
    b.thin(yd(3), 930, 150); b.thin(yd(9), 820, 140)
    b.solid(yd(17), F - 150, 24, 150)         # wall: double jump or go over
    b.thin(yd(13), 700, 130); b.thin(yd(19), 930, 160); b.thin(yd(22), 800, 120); b.thin(yd(26), 670, 140)
    b.solid(yd(24), 430, 24, 240)             # hanging wall for wall-jumps
    b.solid(yd(31), F - 42, 200, 10)          # low slab (32px gap): slide/crouch under or hop on
    b.thin(yd(30), 900, 120); b.thin(yd(35), 780, 150); b.thin(yd(32), 560, 130); b.thin(yd(39), 650, 120)
    b.solid(yd(41), F - 110, 60, 110)         # step block
    b.thin(yd(43), 900, 110); b.thin(yd(37), 440, 120)
    m = b.mid
    b.solid(m - 12, F - 200, 24, 200, center=True)  # tall midfield wall
    b.thin(m - 110, 820, 220, center=True)          # bridge over it
    b.thin(m - 70, 600, 140, center=True)
    b.thin(m - 160, 700, 70, center=True)
    b.thin(m + 90, 700, 70, center=True)
    return b.build()


# ---------------------------------------------------------------- field_02

def field_02() -> dict:
    """Skyline: buildings of different heights with ledges up their sides, a
    wall-jump shaft between two towers, a high rooftop route, and a skyscraper
    at midfield you climb over or slide under."""
    b = Builder("Skyline", 28, 1500)
    F = b.FLOOR  # 1468
    # End zone: ledges stepping up to a rooftop-height lookout
    b.thin(WALL, 1340, 110); b.thin(160, 1230, 110); b.thin(WALL, 1120, 120); b.thin(170, 1010, 100)
    b.solid(396, F - 40, 60, 40)                       # knee-high block
    # Tower A with a fire-escape of ledges
    b.tower(536, 90, 260)                              # top 1208
    b.thin(456, 1340, 80); b.thin(456, 1240, 80)
    # Towers B and C with a narrow shaft between them (wall-jump up or go around)
    b.tower(704, 70, 420)                              # top 1048
    b.thin(634, 1130, 70)
    b.tower(844, 90, 340)                              # top 1128
    # High rooftop route
    b.thin(600, 900, 140); b.thin(820, 800, 120); b.thin(1040, 860, 120)
    # Stairs on the street under a footbridge
    b.solid(984, F - 70, 80, 70); b.solid(1064, F - 140, 70, 140)
    b.thin(956, 1180, 200)                             # footbridge
    b.thin(1100, 1080, 80)
    # Tower D, the tallest before midfield
    b.tower(1180, 110, 500)                            # top 968
    # Hanging billboard wall, a crawl gap and a ledge cluster
    b.hang(1320, 900, 260)
    b.crawl(1300, 120)
    b.thin(1348, 1300, 120); b.thin(1358, 950, 100); b.thin(1470, 1050, 110)
    b.tower(1480, 70, 300)                             # tower E, top 1168
    # Midfield skyscraper: climb the ledges either side, or slide through the 40px gap at its base
    m = b.mid
    b.solid(m - 60, 908, 120, F - 40 - 908, center=True)
    for y in (1360, 1250, 1140, 1030):
        b.thin(m - 160, y, 100, center=True)
        b.thin(m + 60, y, 100, center=True)
    b.thin(m - 400, 840, 160, center=True)
    b.thin(m + 240, 840, 160, center=True)
    return b.build(player_spawn_yards=1)


# ---------------------------------------------------------------- field_03

def field_03() -> dict:
    """Caverns: a low ceiling, hills and valleys, a tunnel with a crawlspace,
    stalactites, a wall-jump chimney, a pit, and a central rock column you pass
    through a mid-height window or crawl under."""
    b = Builder("Caverns", 30, 1200)
    F = b.FLOOR  # 1168
    b.thin(WALL, 1040, 120); b.thin(160, 930, 110); b.thin(WALL, 820, 120)  # end zone ledges
    # Hill
    b.solid(422, F - 50, 180, 50); b.solid(472, F - 110, 80, 60)
    # Tunnel: roof 90px above the floor, with a 36px crawlspace under a low rock
    b.solid(632, F - 120, 180, 30)
    b.solid(692, F - 90, 60, 54)
    # Stalactites
    b.solid(902, WALL, 40, 420)
    b.solid(1112, WALL, 50, 540)
    # Chimney: step in from below, wall-jump up, exit onto the ledge on top
    b.hang(932, 640, 300)
    b.hang(1036, 640, 300)
    b.thin(966, 1040, 60)
    b.thin(900, 610, 180)
    # Big stepped hill with overhanging ledges leading up to the chimney exit
    b.solid(1172, F - 80, 300, 80); b.solid(1222, F - 170, 160, 90)
    b.thin(1200, 860, 140); b.thin(1262, 740, 120)
    # Pit between two plateaus, stalactite above it
    b.solid(1412, F - 140, 100, 140); b.solid(1592, F - 140, 100, 140)
    b.solid(1532, WALL, 40, 640)
    b.thin(1600, 900, 80)
    # Central column: a 60px window at mid-height and a 36px crawl gap at the floor
    m = b.mid
    b.solid(m - 40, WALL, 80, 700 - WALL, center=True)
    b.solid(m - 40, 760, 80, F - 36 - 760, center=True)
    b.thin(m - 180, 760, 140, center=True)
    b.thin(m + 40, 760, 140, center=True)
    return b.build(player_spawn_yards=1, ball_spawn_y=730)  # ball starts in the column's window


# ---------------------------------------------------------------- field_04

def field_04() -> dict:
    """Archipelago: the tallest field. Floating islands (solid ones you must
    reach from the side, one-way ones you jump through), a staircase of
    stepping stones, a hanging wall to climb, and a central chimney up to a
    summit and a sky platform."""
    b = Builder("Archipelago", 32, 1800)
    F = b.FLOOR  # 1768
    # End zone: a tall ladder of ledges
    for i, y in enumerate((1640, 1520, 1400, 1280, 1160)):
        b.thin(WALL if i % 2 == 0 else 180, y, 140)
    b.solid(480, F - 40, 60, 40)                       # knee-high block
    b.solid(448, 1560, 200, 40)                        # island 1 (solid)
    for x, y in ((690, 1450), (770, 1350), (850, 1250), (930, 1150)):
        b.thin(x, y, 60)                               # stepping stones
    b.solid(1010, 1080, 260, 40)                       # island 2 (solid)
    b.thin(1100, 900, 120)                             # high perch
    b.crawl(928, 200)                                  # crawl gap on the floor
    b.solid(1056, F - 180, 30, 180)                    # wall: double jump
    b.thin(1300, 1560, 100); b.thin(1250, 1440, 80)
    b.solid(1330, 1300, 220, 40)                       # island 3 (solid)
    b.thin(1560, 1200, 90); b.thin(1560, 1060, 80)
    b.hang(1664, 1000, 300)                            # climbable wall up to island 5
    b.solid(1688, 930, 160, 40)                        # island 5 (solid)
    b.solid(1216, F - 60, 80, 60); b.solid(1472, F - 120, 40, 120); b.solid(1700, F - 40, 140, 40)
    b.thin(1504, 1440, 120)
    # Central chimney to the summit, sky platform above
    m = b.mid
    b.hang(m - 70, 1100, 468, center=True)
    b.hang(m + 46, 1100, 468, center=True)
    b.thin(m - 30, 1640, 60, center=True)             # step into the chimney
    b.thin(m - 150, 1040, 300, center=True)           # summit (one-way: jump up through it)
    b.thin(m - 100, 820, 200, center=True)            # sky platform
    return b.build(player_spawn_yards=1, ball_spawn_y=700)


# ---------------------------------------------------------------- field_06+ (lane levels)
#
# Lane levels, made for the smaller player (24 x 42). Design rules:
#   * Three stacked horizontal lanes ~280 px apart (more than a double jump), so
#     going UP a lane needs a connector you choose to use; any gap is a way DOWN.
#   * Lanes are broken into 4-9 yard segments with jumpable gaps (<= 4 yd) and
#     small height changes: no long runs on one platform.
#   * Connectors up: step ledges under gaps (two single jumps), chimneys (two walls
#     to wall-jump up between: one wall can't be climbed) and a few double-jump spots.
#   * Built around the throw (apex ~445 px): a QB on the ground lane can reach the
#     middle lane, a QB on the middle lane can reach the top lane.
#   * Mirrored, so both teams face the same field.
#
# Spans below are in yards from the left goal line: (start, end, dy) puts a
# segment from `start` to `end` at the lane height + dy. Spans ending past the
# 50 are centre pieces and must be symmetric (start + end == 100).


def _lane(b: Builder, y: float, spans, kind: str = "solid", thick: int = 24) -> None:
    for span in spans:
        a, z, dy = span if len(span) == 3 else (*span, 0)
        center = z > 50
        assert not center or a + z == 100, f"centre span {span} must be symmetric"
        add = b.solid if kind == "solid" else b.thin
        add(b.yd(a), y + dy, b.yd(z) - b.yd(a), thick, center=center)


def _steps(b: Builder, y: float, yards, w_yd: float = 1.5) -> None:
    """Thin step ledges (one-way) at height y, starting at each yard."""
    for a in yards:
        b.thin(b.yd(a), y, w_yd * b.YD)


def field_06() -> dict:
    """Scaffold: a building site of steel girders. Ground, girder lane and top
    lane, each broken into short sections that step up and down. Ladders of step
    ledges sit under the gaps; one wall shaft (a chimney) per side is the quick
    climb to the top lane. At midfield the top lane is cut, and the way across up there is
    over the crown on top of the scaffold."""
    b = Builder("Scaffold", 44, 1700)
    F = b.FLOOR                                  # 1668
    L2, L3, L4 = F - 280, F - 560, F - 838       # 1388, 1108, 830
    S12, S23, S34 = F - 140, F - 420, F - 700    # step ledge heights between lanes
    yd = b.yd
    # Ground lane: a few blocks to hop
    b.ground(yd(8), yd(11), F - 60)
    b.ground(yd(22), yd(26), F - 100)
    b.ground(yd(36), yd(37), F - 130)
    # Girder lane
    _lane(b, L2, [(-10, -5), (1, 7), (10, 15, -40), (18, 24), (27, 31, 40), (34, 41), (44, 56, -20)])
    # Top lane
    _lane(b, L3, [(-10, -6), (3, 8), (12, 19, -30), (23, 27), (31, 38, 30), (42, 47)])
    # Crown over midfield, and a lookout
    _lane(b, L4, [(46, 54)], kind="thin", thick=16)
    _steps(b, S34, [44])
    # Ladders: ground -> girders, girders -> top
    _steps(b, S12, [-8.5, 8, 16, 32, 42])
    _steps(b, S23, [-4, 9.5, 20.5, 39.5])
    # Wall shaft: a chimney from the girder at the 27 up to the top lane at the 31. Wall-jump
    # between the post on the girder and the one hanging from the top lane's end.
    b.hang(yd(28.5), L3 + 30, (L2 + 40) - (L3 + 30))
    b.hang(yd(31), L3 + 30, 122)
    return b.build(player_spawn_yards=0, ball_spawn_y=700)


def field_07() -> dict:
    """Canopy: a forest. The two upper lanes are one-way branches at uneven
    heights (jump up through them, land on them from above); pairs of tree trunks
    are chimneys to wall-jump up between lanes, with twig steps for anyone who doesn't. Roots
    break up the ground lane. The crown of the great tree at midfield is the
    highest catch point."""
    b = Builder("Canopy", 44, 1800)
    F = b.FLOOR                                  # 1768
    L2, L3, L4 = F - 280, F - 560, F - 840       # 1488, 1208, 928
    S12, S23 = F - 140, F - 420
    yd = b.yd
    # Roots
    b.ground(yd(9), yd(12), F - 50)
    b.ground(yd(24), yd(27), F - 80)
    b.ground(yd(38), yd(40), F - 40)
    # Branch lanes (one-way), uneven heights
    _lane(b, L2, [(-10, -5), (0, 5, -40), (8, 13, 20), (16, 22, -30), (25, 30, 40), (33, 38, -20),
                  (41, 46, 30), (48, 52, -50)], kind="thin", thick=16)
    _lane(b, L3, [(-10, -6), (2, 7, 30), (10, 17, -40), (21, 25, 20), (29, 35, -30), (39, 44, 40),
                  (47, 53, -60)], kind="thin", thick=16)
    _lane(b, L4, [(14, 18), (46, 54)], kind="thin", thick=16)  # lookout and the great tree's crown
    # Trunk pairs (chimneys): ground -> branches, branches -> upper branches. One trunk of
    # each ground pair stops 60 px up, so you walk under it into the chimney.
    b.hang(yd(5), L2, F - L2, w=28)              # gap at the 5-8: a tree...
    b.hang(yd(8) - 28, L2 + 20, (F - 60) - (L2 + 20), w=28)  # ...and a hanging trunk
    b.hang(yd(22), L2 + 10, (F - 60) - (L2 + 10), w=28)      # gap at the 22-25: a hanging trunk...
    b.hang(yd(25) - 28, L3 + 20, F - (L3 + 20), w=28)        # ...and a tall tree, also the left
    b.hang(yd(27), L3, (L2 + 40) - L3, w=28)     # side of the chimney on the branch at the 25-30
    b.hang(yd(41) - 28, L3 + 40, (L2 + 30) - (L3 + 40), w=28)  # chimney on the branch at the 41-46
    b.hang(yd(43), L3, (L2 + 30) - L3, w=28)
    # Twig steps
    _steps(b, S12, [-7, 14, 31, 39])
    _steps(b, S23, [-3, 8, 18, 36])
    return b.build(player_spawn_yards=0, ball_spawn_y=700)


def field_08() -> dict:
    """Undercity: subway, street, rooftops and skybridges. Buildings stand on the
    street and block it, so to get past one you either go over (fire escapes up,
    bridges across the roofs) or drop down a stairwell and run underneath. The
    subway is fast but low (84 px: no jumping, no passes reach you) and has
    turnstiles to slide under. Two tall towers carry a skybridge high over the
    middle block, and the tower at midfield is the high point of the map."""
    b = Builder("Undercity", 44, 1800)
    F = b.FLOOR                                  # 1768 (subway floor)
    street = F - 108                             # 1660: subway clearance 1684..1768 = 84 px
    yd = b.yd
    esc = 1.5 * b.YD                             # fire-escape ledge width
    # Street, with stairwells down to the subway between sections
    _lane(b, street, [(-10, -2), (1, 9), (12, 21), (24, 33), (36, 45), (47, 53)])
    # Turnstiles in the subway: 34 px gap, slide or crawl under
    for a in (16, 40):
        b.solid(yd(a), street + 24, 30, (F - 34) - (street + 24))
    # Buildings on the street (they block it): (start, end, roof)
    for a, z, roof in ((-9, -5, 1500), (2, 6, 1420), (14, 19, 1240), (26, 31, 1400), (38, 43, 1220)):
        b.ground(yd(a), yd(z), roof, bottom=street)
    b.ground(yd(48), yd(52), 1000, bottom=street, center=True)   # midfield tower
    # Fire escapes (one-way), each flight <= 145 px
    for x_yd, y in ((-4.5, 1580),                # end-zone building
                    (0.5, 1540),                 # building at the 2
                    (12.5, 1520), (11.0, 1380),  # tall building at the 14
                    (24.5, 1530),                # building at the 26
                    (36.5, 1515), (35.0, 1365),  # tall building at the 38
                    (46.5, 1515), (45.0, 1370), (46.5, 1225), (45.0, 1080)):  # midfield tower
        b.thin(yd(x_yd), y, esc)
    # Rooftop bridges (one-way), stepped where the roofs differ in height
    _lane(b, 0, [(7, 10, 1420), (10.5, 13, 1310),      # 2 -> tall 14
                 (20, 24.5, 1330),                     # tall 14 -> 26
                 (32, 34.5, 1390), (35, 37, 1290)],    # 26 -> tall 38
          kind="thin", thick=16)
    # Skybridge between the two tall buildings, high over the one at the 26
    _lane(b, 0, [(21, 25, 1110), (27.5, 31.5, 1100), (34, 37.5, 1110)], kind="thin", thick=16)
    return b.build(player_spawn_yards=-3, ball_spawn_y=700, player_spawn_y=street - 24)


# ---------------------------------------------------------------- field_09+
#
# Three-lane maps: bottom, middle and top lanes, 480-560 px apart (about twice a
# double jump), so nobody changes lane by accident. Each lane has its own small
# platforms (crates, perches) that can never reach the next lane. Middle and top
# floors are solid unless noted, so every way UP is a deliberate switch:
#   * stair: a zig-zag of one-way steps up through an opening in the upper floor
#   * climb: a chimney filling an opening, two walls to wall-jump up between
# Any gap in a lane is a way DOWN. Bottom<->middle and middle<->top switches sit
# at different yard lines, so each lane change is its own decision. Only the end
# zones have one tall stair through all three lanes, so every lane can score.


def _stair(b: Builder, a: float, lo: float, hi: float, gap_yd: float = 3.0) -> None:
    """Zig-zag one-way steps in the opening that starts at yard `a`, from a floor at
    `lo` up to a floor at `hi`. Each step is <= 140 px (one jump)."""
    k = -(-(lo - hi) // 140)                    # number of jumps
    step = (lo - hi) / k
    w = round(0.35 * gap_yd * b.YD)
    for i in range(1, int(k)):
        x = a + (0.1 if i % 2 else 0.55) * gap_yd
        b.thin(b.yd(x), lo - step * i, w)


def _climb(b: Builder, a: float, lo: float, hi: float, far_hi: float, w_yd: float = 3.0) -> None:
    """A chimney filling the opening from yard `a` to `a + w_yd`: one wall from the upper
    floor's end (top at `hi`) down to the lower floor (`lo`), and one from the far floor's
    end (top at `far_hi`) down to 60 px above it, so you walk under it into the chimney.
    Wall-jump up between them (one wall alone can't be climbed)."""
    b.solid(b.yd(a), hi, 24, lo - hi)
    x = b.yd(a + w_yd) - 24
    b.solid(x, far_hi, 24, (lo - 60) - far_hi)


def _perches(b: Builder, y: float, spans) -> None:
    _lane(b, y, spans, kind="thin", thick=16)


def _blocks(b: Builder, floor: float, items) -> None:
    """Solid blocks standing on a lane floor: (start, end, height)."""
    for a, z, h in items:
        b.ground(b.yd(a), b.yd(z), floor - h, bottom=floor, center=z > 50)


def field_09() -> dict:
    """Fortress: courtyard (bottom), ramparts (middle) and battlements (top).
    Stair towers and chimneys link the lanes at staggered points; a gate
    blocks the courtyard at midfield and a crown tops the keep."""
    b = Builder("Fortress", 56, 2000)
    F = b.FLOOR                                  # 1968
    MID, TOP = F - 480, F - 960                  # 1488, 1008
    # Bottom: courtyard
    _blocks(b, F, [(1, 3, 60), (11, 12, 110), (18, 20.5, 50), (27, 28, 110), (33, 36, 70), (43, 44, 110),
                   (48, 52, 140)])
    _perches(b, F - 128, [(7, 9.5), (15, 17), (23.5, 25.5), (30, 32), (39.5, 41.5)])
    # Middle: ramparts. Openings at -4 (end-zone tower), 4, 13 (wall), 21, 37 are switches; 29, 45 are gaps.
    _lane(b, MID, [(-10, -4), (-1, 4), (7, 13, -30), (16, 21), (24, 29, 30), (32, 37), (40, 45, -20), (47, 53)])
    _blocks(b, MID, [(1, 1.5, 60), (9, 9.5, 60), (25.5, 26, 60)])
    _perches(b, MID - 128, [(17, 19.5), (33, 35), (41, 43)])
    # Top: battlements. Openings at -4 (tower), 9, 26 (wall), 33 are switches; 17, 42 are gaps.
    _lane(b, TOP, [(-10, -4), (-1, 9), (12, 17, -30), (19, 26), (29, 33, 30), (36, 42), (44, 56, -40)])
    _perches(b, TOP - 128, [(5, 7), (21, 23), (38, 40)])
    _perches(b, TOP - 168, [(48.5, 51.5)])     # crown on the keep
    # Switches
    _stair(b, -4, F, TOP)                        # end-zone tower: bottom -> middle -> top
    for a, hi in ((4, MID), (21, MID), (37, MID)):
        _stair(b, a, F, hi)                      # bottom -> middle
    _climb(b, 13, F, MID - 30, MID)              # bottom -> middle
    _stair(b, 9, MID - 30, TOP)                  # middle -> top
    _stair(b, 33, MID, TOP)
    _climb(b, 26, MID + 30, TOP, TOP + 30)
    return b.build(player_spawn_yards=-7, ball_spawn_y=600)


def field_10() -> dict:
    """Mineshaft: the mine floor (bottom) with ore carts and low galleries, timber
    walkways (middle, one-way) at uneven heights, and the surface (top) with its
    head-frames. Shafts (stairs) and post chimneys connect the lanes at staggered
    points; chutes (gaps) drop you down. The crusher blocks the floor at midfield."""
    b = Builder("Mineshaft", 58, 2200)
    F = b.FLOOR                                  # 2168
    MID, TOP = F - 520, F - 1040                 # 1648, 1128
    # Bottom: mine floor
    _blocks(b, F, [(6, 7.5, 50), (13, 14.5, 50), (35, 36.5, 50), (38.5, 40, 50), (47, 53, 100)])
    _lane(b, F - 90, [(21, 25), (41, 44)], thick=20)  # low galleries: 70 px headroom
    _perches(b, F - 130, [(8, 10.5), (27, 29.5)])
    # Middle: timber walkways (one-way). Switch openings at -6, 2, 17 (post), 31, 44; gaps at 10, 25, 39.
    _lane(b, MID, [(-10, -6), (-3, 2), (5, 10, 40), (12, 17, -40), (20, 25), (27, 31, 50), (34, 39, -30),
                   (41, 44), (47, 53)], kind="thin", thick=16)
    _perches(b, MID - 130, [(6, 8), (21, 23.5), (35, 37)])
    # Top: the surface. Switch openings at -6, 9, 24, 38 (post); gaps at 16, 32, 46.
    _lane(b, TOP, [(-10, -6), (-3, 9), (12, 16, -40), (18, 24), (27, 32, 40), (34, 38), (41, 46, -30),
                   (48, 52)], thick=40)
    _blocks(b, TOP, [(1, 3, 120), (20, 21.5, 90), (35, 36, 140)])
    _perches(b, TOP - 130, [(5, 7), (28, 30), (42.5, 44.5), (48.5, 51.5)])
    # Switches
    _stair(b, -6, F, TOP)                        # end-zone shaft: bottom -> middle -> top
    for a, hi in ((2, MID), (31, MID + 50), (44, MID)):
        _stair(b, a, F, hi)                      # bottom -> middle
    _climb(b, 17, F, MID - 40, MID)              # bottom -> middle
    _stair(b, 9, MID + 40, TOP)                  # middle -> top
    _stair(b, 24, MID, TOP)
    _climb(b, 38, MID - 30, TOP, TOP - 30)
    return b.build(player_spawn_yards=-9, ball_spawn_y=600)


def field_11() -> dict:
    """Harbor: the docks (bottom) with piers and crates, ship decks (middle) with
    cabins, and crane gantries (top, one-way). Gangways (stairs) climb from the
    docks to the decks; pairs of masts hang from the gantries, chimneys from deck to sky.
    A breakwater blocks the docks at midfield."""
    b = Builder("Harbor", 60, 2400)
    F = b.FLOOR                                  # 2368
    MID, TOP = F - 560, F - 1120                 # 1808, 1248
    # Bottom: docks
    _blocks(b, F, [(7, 9, 60), (12, 14, 90), (20, 22, 40), (25, 27, 90), (34, 36, 60), (45, 46.5, 110),
                   (48, 52, 200)])
    _perches(b, F - 130, [(10, 12), (23, 24.5), (37.5, 39.5)])
    # Middle: ship decks. Switch openings at -4, 3, 15, 29, 41; gap at 23.
    _lane(b, MID, [(-10, -4), (-1, 3, -20), (6, 15), (18, 23, 40), (26, 29), (32, 41, -30), (44, 56)], thick=40)
    _blocks(b, MID, [(7, 9, 90), (20, 21.5, 70), (34, 36, 110)])
    _perches(b, MID - 130, [(11.5, 13.5), (27, 28.5), (38, 40)])
    # Top: gantries (one-way). Switch openings at -4, 10 (mast), 24.5 (mast), 36; gaps at 17, 31, 45.
    _lane(b, TOP, [(-10, -4), (-1, 10), (12.5, 17, -40), (20, 24.5), (27, 31, 40), (33, 36), (39, 45, -30),
                   (47, 53)], kind="thin", thick=16)
    _perches(b, TOP - 140, [(5, 7), (21, 23), (48.5, 51.5)])
    # Switches
    _stair(b, -4, F, TOP)                        # end-zone gangway: bottom -> middle -> top
    for a, hi in ((3, MID - 20), (15, MID), (29, MID), (41, MID)):
        _stair(b, a, F, hi)                      # gangways: bottom -> middle
    # Mast pairs: hang from the gantry ends either side of an opening, bottoms 140 px above
    # the deck. Jump up between them and wall-jump to the gantries.
    for a, far, far_dy in ((10, 12.5, -40), (24.5, 27, 40)):
        b.solid(b.yd(a), TOP, 24, (MID - 140) - TOP)
        b.solid(b.yd(far) - 24, TOP + far_dy, 24, (MID - 140) - (TOP + far_dy))
    _stair(b, 36, MID - 30, TOP)                 # middle -> top
    return b.build(player_spawn_yards=-7, ball_spawn_y=700)


# ---------------------------------------------------------------- field_12+
#
# Skill maps: three-lane maps (like 08-10) that add expert shortcuts next to the
# ordinary stairs. Every skill element was tuned on the real physics; the numbers
# are the timing window a player has (120 ticks = 1 s):
#
#   * Kick hatch (lane switch up): under the upper floor, near an opening, a column
#     stands with a 58 px slot between its top and the ceiling, and a wall hangs
#     70 px behind it. Wall-jump up that chimney into the slot, land on the column,
#     walk off toward the opening and air-jump as you clear the floor's edge to rise
#     through. With the column 28-32 px from the edge the window is 7-8 ticks; 16 px is
#     easier (13). Without the air jump it can't be done.
#   * Vault: a block cuts the middle lane, with a tunnel through it at balcony
#     height (220 px up). Double-jump onto the 40 px balcony (~9-tick window, and
#     only from the right take-off spot), then slide or crawl through. The balcony
#     is solid, so climbing the block's face just bonks you under it.
#   * Slide gauntlet: beams hang to 34 px above the middle lane, between pits.
#     Slide under each beam and hop each pit: one pit only works with a short hop,
#     the next only with a full jump. Falling drops you a lane.


KICK_SLOT, KICK_GAP = 58, 70  # px between the column and the ceiling; chimney width


def _kick_hatch(b: Builder, edge_yd: float, lo: float, hi: float, facing: int = 1, D: int = 32) -> None:
    """The upper floor (top at `hi`) ends at `edge_yd`; the opening is on the `facing`
    side. The column stands D px back from the edge, from KICK_SLOT px under the
    ceiling down to 140 px above the lower floor (`lo`), so the lower lane walks under
    it; the chimney wall hangs from the ceiling KICK_GAP px behind it, to the same
    height. The upper floor must be solid and 24 px thick (one-way floors let you climb
    straight through; thicker ones put the kick out of reach), and the opening 2.5
    yards wide."""
    x_edge = b.yd(edge_yd)
    col_x = x_edge - D - 24 if facing > 0 else x_edge + D
    wall_x = col_x - KICK_GAP - 24 if facing > 0 else col_x + 24 + KICK_GAP
    col_top = hi + 24 + KICK_SLOT
    b.solid(col_x, col_top, 24, (lo - 140) - col_top)
    b.solid(wall_x, hi + 24, 24, (lo - 140) - (hi + 24))


def _vault(b: Builder, a_yd: int, w_yd: int, lo: float, top_y: float, pad_h: int = 220, pad_w: int = 56,
           slot: int = 34) -> None:
    """A block across the middle lane from `a_yd` for `w_yd` yards, with a tunnel
    (`slot` px tall) at `pad_h` above the lane and a solid balcony on each side."""
    x0, x1 = b.yd(a_yd), b.yd(a_yd + w_yd)
    pad_y = lo - pad_h
    b.solid(x0, pad_y, x1 - x0, lo - pad_y)                  # below the tunnel
    b.solid(x0, top_y, x1 - x0, (pad_y - slot) - top_y)      # above it, flush with the top lane
    b.solid(x0 - pad_w, pad_y, pad_w, 24)                    # balconies
    b.solid(x1, pad_y, pad_w, 24)


GAUNTLET = [(40, 120, 30, 80), (40, 120, 50, 160), (40, 120, 40, 0)]  # (run-up, beam, exit, pit) px


def _gauntlet(b: Builder, a_yd: float, lane_y: float, ceil_y: float, parts=GAUNTLET) -> float:
    """Slide gauntlet on a lane starting at `a_yd`; beams hang from `ceil_y`.
    Returns the yard where it ends."""
    x = b.yd(a_yd)
    for run_up, beam, exit_, pit in parts:
        seg = run_up + beam + exit_
        b.solid(x, lane_y, seg, 24)
        b.solid(x + run_up, ceil_y, beam, (lane_y - 34) - ceil_y)
        x += seg + pit
    return (x - b.yd(0)) / b.YD


def field_12() -> dict:
    """Foundry: a slide gauntlet of press beams on the middle lane, a vault through
    the furnace block, and a kick hatch up to the top lane near the end zone."""
    b = Builder("Foundry", 56, 2000)
    F = b.FLOOR                                  # 1968
    MID, TOP = F - 480, F - 960                  # 1488, 1008
    # Bottom lane
    _blocks(b, F, [(1, 3, 60), (10, 11, 110), (19, 21, 50), (31, 32, 110), (38, 40, 70), (48, 52, 140)])
    _perches(b, F - 128, [(13, 15.5), (23, 25.5), (34, 36.5)])
    # Middle lane: gauntlet 12-27, vault 33-37 (6+ yards of clear runway each side)
    _lane(b, MID, [(-10, -4), (-1, 2), (5, 12)])
    end = _gauntlet(b, 12, MID, TOP + 24)       # 12 -> 27
    assert end == 27, end
    _lane(b, MID, [(27, 33), (37, 41), (44, 56)])
    _vault(b, 33, 4, MID, TOP)
    # Top lane
    _lane(b, TOP, [(-10, -4), (-1, 9), (11.5, 28), (30, 44), (47, 53, -40)])
    _perches(b, TOP - 128, [(3, 5), (19, 21)])
    _perches(b, TOP - 168, [(48.5, 51.5)])
    # Switches: ordinary
    _stair(b, -4, F, TOP)                        # end-zone tower
    _stair(b, 2, F, MID)                         # bottom -> middle
    _stair(b, 41, F, MID)
    _stair(b, 44, MID, TOP)                      # middle -> top
    # Switches: skill
    _kick_hatch(b, 9, MID, TOP, facing=1, D=32)  # middle -> top through the opening at the 9
    return b.build(player_spawn_yards=-7, ball_spawn_y=600)


def field_13() -> dict:
    """Aqueduct: a vault through the first arch of the middle lane, and two kick
    hatches (one hard, one easier) up to the water channel on top."""
    b = Builder("Aqueduct", 58, 2200)
    F = b.FLOOR                                  # 2168
    MID, TOP = F - 520, F - 1040                 # 1648, 1128
    # Bottom lane
    _blocks(b, F, [(1, 3, 60), (10, 11, 110), (21, 23, 50), (27, 28, 110), (34, 36, 70), (47, 53, 100)])
    _perches(b, F - 130, [(6, 8.5), (24, 26.5), (31, 33.5)])
    # Middle lane: the arch (vault) at the 4, with 7 yards of runway each side
    _lane(b, MID, [(-10, -6), (-3, 4), (8, 15), (18, 28), (30, 38), (41, 59)])
    _vault(b, 4, 4, MID, TOP)
    # Top lane: the channel
    _lane(b, TOP, [(-10, -6), (-3, 21), (23.5, 25), (28, 36), (38.5, 44), (44, 56, -40)])
    _perches(b, TOP - 130, [(14, 16), (40, 42), (48.5, 51.5)])
    # Switches: ordinary
    _stair(b, -6, F, TOP)                        # end-zone shaft
    _stair(b, 15, F, MID)                        # bottom -> middle
    _stair(b, 38, F, MID)
    _stair(b, 25, MID, TOP)                      # middle -> top
    # Switches: skill
    _kick_hatch(b, 36, MID, TOP, facing=1, D=32)  # hard: opening at the 36
    _kick_hatch(b, 21, MID, TOP, facing=1, D=16)  # easier: opening at the 21
    return b.build(player_spawn_yards=-9, ball_spawn_y=600)


def field_14() -> dict:
    """Citadel: a long slide gauntlet under the curtain wall, a vault through the
    gatehouse, and kick hatches facing both ways up to the walls."""
    b = Builder("Citadel", 60, 2400)
    F = b.FLOOR                                  # 2368
    MID, TOP = F - 560, F - 1120                 # 1808, 1248
    # Bottom lane
    _blocks(b, F, [(2, 4, 60), (12, 13, 110), (19, 21, 50), (31, 32, 110), (38, 40, 70), (47, 53, 200)])
    _perches(b, F - 130, [(6, 8.5), (15, 17.5), (34, 36.5)])
    # Middle lane: gauntlet 8-22, gatehouse vault 36-40 (7 yards of runway each side)
    _lane(b, MID, [(-10, -4), (-1, 8)])
    end = _gauntlet(b, 8, MID, TOP + 24)        # 8 -> 22
    assert end == 22, end
    _lane(b, MID, [(22, 26), (29, 36), (40, 60)])
    _vault(b, 36, 4, MID, TOP)
    # Top lane: the walls
    _lane(b, TOP, [(-10, -4), (-1, 4), (7, 25), (27.5, 31), (33, 43.5), (46, 54)])
    _perches(b, TOP - 140, [(14, 16), (48.5, 51.5)])
    # Switches: ordinary
    _stair(b, -4, F, TOP)                        # end-zone stair
    _stair(b, 26, F, MID)                        # bottom -> middle
    _stair(b, 4, MID, TOP)                       # middle -> top
    # Switches: skill
    _kick_hatch(b, 25, MID, TOP, facing=1, D=28)   # opening at the 25
    _kick_hatch(b, 46, MID, TOP, facing=-1, D=16)  # opening at the 43.5-46, kick to the left
    return b.build(player_spawn_yards=-7, ball_spawn_y=700)


LEVEL_BUILDERS = {
    "field_01": field_01,
    "field_02": field_02,
    "field_03": field_03,
    "field_04": field_04,
    "field_06": field_06,
    "field_07": field_07,
    "field_08": field_08,
    "field_09": field_09,
    "field_10": field_10,
    "field_11": field_11,
    "field_12": field_12,
    "field_13": field_13,
    "field_14": field_14,
}


def main(argv: list[str]) -> None:
    names = argv or list(LEVEL_BUILDERS)
    for name in names:
        level = LEVEL_BUILDERS[name]()
        path = LEVELS / f"{name}.json"
        write(level, path)
        print(f"wrote {path.name}: {level['name']}, {level['width']}x{level['height']}, "
              f"{len(level['platforms'])} platforms")


if __name__ == "__main__":
    main(sys.argv[1:])
