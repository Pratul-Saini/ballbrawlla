"""The environment: a rectangular arena of static platforms.

Floor, ceiling and side walls are generated from the arena size, so every level
is enclosed. Everything else (floating or connected, horizontal or vertical) is
just a rectangle listed in the level file.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2


@dataclass
class Platform:
    rect: AABB
    kind: str = "platform"  # "platform" or "bound"; only affects rendering


@dataclass
class Level:
    width: float
    height: float
    platforms: list[Platform] = field(default_factory=list)
    wall_thickness: float = 32
    player_spawn: Vector2 = field(default_factory=lambda: Vector2(100, 100))  # player center
    ball_spawn: Vector2 = field(default_factory=lambda: Vector2(200, 100))    # ball center
    name: str = "untitled"

    def __post_init__(self) -> None:
        t, w, h = self.wall_thickness, self.width, self.height
        bounds = [
            AABB(0, h - t, w, t),  # floor
            AABB(0, 0, w, t),      # ceiling
            AABB(0, 0, t, h),      # left wall
            AABB(w - t, 0, t, h),  # right wall
        ]
        self.platforms = [Platform(r, "bound") for r in bounds] + self.platforms
        self.solids: list[AABB] = [p.rect for p in self.platforms]


def load_level(path: str | Path) -> Level:
    data = json.loads(Path(path).read_text())
    return Level(
        width=data["width"],
        height=data["height"],
        wall_thickness=data.get("wall_thickness", 32),
        platforms=[Platform(AABB(p["x"], p["y"], p["w"], p["h"])) for p in data["platforms"]],
        player_spawn=Vector2(data["player_spawn"]),
        ball_spawn=Vector2(data["ball_spawn"]),
        name=data.get("name", Path(path).stem),
    )
