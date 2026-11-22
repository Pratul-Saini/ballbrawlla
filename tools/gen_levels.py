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

    def build(self, player_spawn_yards=5, ball_spawn_y=300) -> dict:
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
                [self.yd(player_spawn_yards), self.FLOOR - 24],
                [self.W - self.yd(player_spawn_yards), self.FLOOR - 24],
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


LEVEL_BUILDERS = {
    "field_01": field_01,
    "field_02": field_02,
    "field_03": field_03,
    "field_04": field_04,
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
