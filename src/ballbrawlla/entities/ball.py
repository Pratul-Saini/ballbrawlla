"""The ball: a circle under gravity that bounces off every platform."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ballbrawlla.config import Tuning
from ballbrawlla.physics.body import Body
from ballbrawlla.physics.collision import bounce, circle_vs_aabb
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2

if TYPE_CHECKING:
    from ballbrawlla.entities.player import Player


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

    def update(self, dt: float, solids: list[AABB]) -> None:
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

        for _ in range(steps):
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

        if self.resting:
            self.body.vel.x *= max(0.0, 1 - self.t.ball_rolling_drag * dt)
