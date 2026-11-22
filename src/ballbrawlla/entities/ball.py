"""The ball: a circle under gravity that bounces off every platform.

Solid platforms bounce it from every side. Thin platforms are one-way: the
ball lands on them from above and passes through from below and the sides.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ballbrawlla.config import Tuning
from ballbrawlla.physics.body import Body
from ballbrawlla.physics.collision import ABOVE_TOP_TOL, bounce, circle_vs_aabb
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2

if TYPE_CHECKING:
    from ballbrawlla.entities.player import Player


def _near(rects, x: float, y: float, margin: float) -> list:
    """The rects that can touch the ball this tick: those overlapping the square of half-size `margin` around it.
    Cheap float compares only, so a level with hundreds of platforms costs the ball almost nothing."""
    x0, x1, y0, y1 = x - margin, x + margin, y - margin, y + margin
    return [r for r in rects if r.x < x1 and r.x + r.w > x0 and r.y < y1 and r.y + r.h > y0]


class Ball:
    def __init__(self, spawn: Vector2, tuning: Tuning) -> None:
        self.t = tuning
        self.radius = tuning.ball_radius
        self.body = Body(pos=Vector2(spawn), gravity=tuning.ball_gravity)
        self.held_by: Player | None = None
        self.resting = False  # sitting on a floor (normal pointing up)

    @property
    def pos(self) -> Vector2:
        return self.body.pos

    @property
    def vel(self) -> Vector2:
        return self.body.vel

    def release(self, pos: Vector2, vel: Vector2) -> None:
        self.held_by = None
        self.body.pos = Vector2(pos)
        self.body.vel = Vector2(vel)
        self.resting = False

    def update(self, dt: float, solids: list[AABB], thin: list[AABB] = ()) -> None:
        if self.held_by is not None:
            self.body.pos = self.held_by.hand_pos()
            self.body.vel = Vector2()
            return

        self.body.integrate_velocity(dt)

        # Sub-step so a fast ball never moves more than half its radius per step
        # (prevents tunnelling through thin platforms).
        travel = self.body.vel.length() * dt
        steps = max(1, math.ceil(travel / (self.radius * 0.5)))
        sub_dt = dt / steps
        self.resting = False

        # Broad phase: only platforms within reach of this tick's whole path. A bounce never speeds the ball up and
        # a push-out is at most one radius, so travel + 2 radii (+ slack) covers everything it can touch.
        reach = travel + 2 * self.radius + 2
        solids = _near(solids, self.body.pos.x, self.body.pos.y, reach)
        thin = _near(thin, self.body.pos.x, self.body.pos.y, reach)

        for _ in range(steps):
            prev_bottom = self.body.pos.y + self.radius
            vy = self.body.vel.y
            self.body.pos += self.body.vel * sub_dt
            for s in solids:
                c = circle_vs_aabb(self.body.pos, self.radius, s)
                if c is None:
                    continue
                self.body.pos += c.normal * c.depth
                self.body.vel = bounce(
                    self.body.vel,
                    c.normal,
                    self.t.ball_restitution,
                    self.t.ball_bounce_friction,
                    self.t.ball_rest_speed,
                )
                if c.normal.y < -0.7:
                    self.resting = abs(self.body.vel.y) < 1e-6
            if vy > 0:
                for t in thin:
                    if (
                        prev_bottom <= t.top + ABOVE_TOP_TOL
                        and circle_vs_aabb(self.body.pos, self.radius, t) is not None
                    ):
                        self.body.pos.y = t.top - self.radius
                        self.body.vel = bounce(
                            self.body.vel,
                            Vector2(0, -1),
                            self.t.ball_restitution,
                            self.t.ball_bounce_friction,
                            self.t.ball_rest_speed,
                        )
                        self.resting = abs(self.body.vel.y) < 1e-6

        if self.resting:
            self.body.vel.x *= max(0.0, 1 - self.t.ball_rolling_drag * dt)
