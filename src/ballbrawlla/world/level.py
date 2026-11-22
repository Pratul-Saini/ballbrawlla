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


SOLID = "solid"
THIN = "thin"
_TYPES = (SOLID, THIN)


@dataclass
class Platform:
    rect: AABB
    kind: str = "platform"  # "platform" or "bound"; only affects rendering
    platform_type: str = SOLID  # "solid" blocks from all sides; "thin" is one-way

    def __post_init__(self) -> None:
        if not (isinstance(self.platform_type, str) and self.platform_type in _TYPES):
            raise ValueError(
                f"invalid platform type {self.platform_type!r} (expected 'thin' or 'solid')"
            )

    @property
    def is_thin(self) -> bool:
        return self.platform_type == THIN


@dataclass
class Level:
    width: float
    height: float
    platforms: list[Platform] = field(default_factory=list)
    wall_thickness: float = 32
    # Player centers, one per player slot (reused round-robin if there are fewer).
    player_spawns: list[Vector2] = field(default_factory=lambda: [Vector2(100, 100)])
    ball_spawn: Vector2 = field(default_factory=lambda: Vector2(200, 100))  # ball center
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
        # Boundaries first, then solid platforms in input order; thin kept separate.
        self.solids: list[AABB] = [p.rect for p in self.platforms if not p.is_thin]
        self.thin: list[AABB] = [p.rect for p in self.platforms if p.is_thin]

    def spawn_for(self, player_index: int) -> Vector2:
        return Vector2(self.player_spawns[player_index % len(self.player_spawns)])


def _platform_from_dict(p: dict) -> Platform:
    return Platform(AABB(p["x"], p["y"], p["w"], p["h"]), platform_type=p.get("type", SOLID))


def level_from_dict(data: dict) -> Level:
    spawns = data.get("player_spawns") or [data["player_spawn"]]
    return Level(
        width=data["width"],
        height=data["height"],
        wall_thickness=data.get("wall_thickness", 32),
        platforms=[_platform_from_dict(p) for p in data["platforms"]],
        player_spawns=[Vector2(s) for s in spawns],
        ball_spawn=Vector2(data["ball_spawn"]),
        name=data.get("name", "untitled"),
    )


def level_to_dict(level: Level) -> dict:
    """Inverse of level_from_dict (boundary walls are regenerated, so omitted)."""
    return {
        "name": level.name,
        "width": level.width,
        "height": level.height,
        "wall_thickness": level.wall_thickness,
        "player_spawns": [[s.x, s.y] for s in level.player_spawns],
        "ball_spawn": [level.ball_spawn.x, level.ball_spawn.y],
        "platforms": [_platform_to_dict(p) for p in level.platforms if p.kind == "platform"],
    }


def _platform_to_dict(p: Platform) -> dict:
    d = {"x": p.rect.x, "y": p.rect.y, "w": p.rect.w, "h": p.rect.h}
    if p.is_thin:
        d["type"] = THIN
    return d


def load_level(path: str | Path) -> Level:
    data = json.loads(Path(path).read_text())
    data.setdefault("name", Path(path).stem)
    return level_from_dict(data)
