"""The football field laid over a level: yards, goal lines, end zones, and the
platform-top spots where a player may be spawned.

Layout (Team.LEFT attacks right):

  wall | LEFT end zone | 0 ......... 50 ......... 0 | RIGHT end zone | wall
         end_zone_yards   <------ field_yards ------>   end_zone_yards

The level's inner width (between the side walls) must equal
(field_yards + 2 * end_zone_yards) * yard_px, where yard_px is the level's own
`yard_px` if it sets one (bigger fields), otherwise Tuning.yard_px.
"""

from __future__ import annotations

from dataclasses import dataclass

from ballbrawlla.config import Tuning
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import Level

_SAMPLE_PX = 2.0  # resolution when scanning platform tops for free spawn space


@dataclass(frozen=True)
class Spot:
    """Where a player stands: x of their center, y of their feet (a platform top)."""

    x: float
    y: float

    def center(self, player_height: float) -> Vector2:
        return Vector2(self.x, self.y - player_height / 2)


@dataclass(frozen=True)
class Surface:
    """A run of platform top where a standing player fits. Valid center x in [x0, x1]."""

    x0: float
    x1: float
    y: float


class Field:
    def __init__(self, level: Level, tuning: Tuning) -> None:
        self.level = level
        self.t = tuning
        self.yard_px = level.yard_px or tuning.yard_px
        inner_left = level.wall_thickness
        inner_right = level.width - level.wall_thickness
        expected = (tuning.field_yards + 2 * tuning.end_zone_yards) * self.yard_px
        if abs((inner_right - inner_left) - expected) > 0.5:
            raise ValueError(
                f"level {level.name!r} inner width is {inner_right - inner_left:g}px but the field "
                f"needs {expected:g}px ({tuning.field_yards:g} + 2x{tuning.end_zone_yards:g} yards "
                f"at {self.yard_px:g}px/yard)"
            )
        self.inner_left = inner_left
        self.inner_right = inner_right
        ez = tuning.end_zone_yards * self.yard_px
        self.end_zone_px = ez
        self._goal = {Team.LEFT: inner_left + ez, Team.RIGHT: inner_right - ez}
        self.surfaces = self._find_surfaces()

    # ------------------------------------------------------------ yards

    def goal_line_x(self, team: Team) -> float:
        """x of the goal line in front of `team`'s own end zone."""
        return self._goal[team]

    def x_at(self, team: Team, yards: float) -> float:
        """x that is `yards` from `team`'s own goal line, toward the field.
        Negative yards are inside `team`'s own end zone."""
        return self._goal[team] + team.attack_dir * yards * self.yard_px

    def yards_from_goal(self, team: Team, x: float) -> float:
        return (x - self._goal[team]) * team.attack_dir / self.yard_px

    def in_end_zone(self, team: Team, x: float) -> bool:
        """True if x is inside `team`'s own end zone."""
        return self.yards_from_goal(team, x) < 0

    def x_range(self, team: Team, yards_a: float, yards_b: float) -> tuple[float, float]:
        a, b = self.x_at(team, yards_a), self.x_at(team, yards_b)
        return (min(a, b), max(a, b))

    @property
    def floor_y(self) -> float:
        return self.level.height - self.level.wall_thickness

    # ------------------------------------------------------------ spawn spots

    def _find_surfaces(self) -> list[Surface]:
        """Scan every platform top (and the floor) for runs where a standing player fits."""
        w, h = self.t.player_width, self.t.player_height
        solids = self.level.solids
        out: list[Surface] = []
        for plat in self.level.platforms:
            r = plat.rect
            if r.top < self.level.wall_thickness:  # ceiling / side walls
                continue
            lo = max(r.left, self.inner_left + w / 2)
            hi = min(r.right, self.inner_right - w / 2)
            run_start = None
            x = lo
            while x <= hi + 1e-9:
                box = AABB(x - w / 2, r.top - h, w, h)
                free = not any(box.overlaps(s) for s in solids)
                if free and run_start is None:
                    run_start = x
                if not free and run_start is not None:
                    out.append(Surface(run_start, x - _SAMPLE_PX, r.top))
                    run_start = None
                x += _SAMPLE_PX
            if run_start is not None:
                out.append(Surface(run_start, min(x - _SAMPLE_PX, hi), r.top))
        return [s for s in out if s.x1 >= s.x0]

    def snap(self, point: Vector2 | Spot, x_lo: float, x_hi: float) -> Spot | None:
        """Nearest valid standing spot to `point` (feet coords) with center x in [x_lo, x_hi]."""
        px, py = point.x, point.y
        best: Spot | None = None
        best_d = float("inf")
        for s in self.surfaces:
            a, b = max(s.x0, x_lo), min(s.x1, x_hi)
            if a > b:
                continue
            x = min(max(px, a), b)
            d = (x - px) ** 2 + (s.y - py) ** 2
            if d < best_d:
                best, best_d = Spot(x, s.y), d
        return best

    def spawn_spot(self, target: Vector2 | Spot, x_lo: float, x_hi: float) -> Spot:
        """Like snap(), but widens the range if nothing fits, so it always returns a spot."""
        for pad in (0.0, 3 * self.yard_px, float("inf")):
            spot = self.snap(target, x_lo - pad, x_hi + pad)
            if spot is not None:
                return spot
        raise ValueError("level has no surface a player can stand on")
