"""The player: a kinematic AABB driven by a state machine.

Each tick:
  1. the current state reads the Intent and sets velocity / requests a transition
  2. gravity is applied (scaled and capped by the state)
  3. the box is moved and pushed out of solids, one axis at a time
  4. contacts are probed for the next tick's state logic
"""

from __future__ import annotations

import math

from ballbrawlla.config import Tuning
from ballbrawlla.entities.ball import Ball
from ballbrawlla.entities.player_states import Airborne, State
from ballbrawlla.input import Intent
from ballbrawlla.physics.body import Body
from ballbrawlla.physics.collision import Contacts, box_is_free, move_aabb, probe_contacts
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2


class Player:
    def __init__(self, spawn_center: Vector2, tuning: Tuning, pid: int = 0) -> None:
        self.t = tuning
        self.pid = pid
        self.connected = True  # False for an empty network slot: not simulated, drawn dimmed
        self.w = tuning.player_width
        self.h = tuning.player_height
        top_left = Vector2(spawn_center.x - self.w / 2, spawn_center.y - self.h / 2)
        self.body = Body(pos=top_left, gravity=tuning.player_gravity)  # pos = top-left of box

        self.facing = 1
        self.contacts = Contacts()
        self.jumps_left = tuning.air_jumps
        self.jump_cut_ready = False   # True after a jump until Up is released / apex
        self.control_lock = 0.0       # seconds of ignored air control (after wall jump)

        self.held_ball: Ball | None = None
        self.ball: Ball | None = None  # the ball in the world, set each tick
        self.pickup_requested = False  # resolved by Game after all players update
        self.aim_angle = 45.0          # degrees, 0 = right, 90 = up (full circle)
        self.aim_power = (tuning.power_min + tuning.power_max) / 2

        self._solids: list[AABB] = []
        self.state: State = Airborne()
        self.state.enter(self)

    # ------------------------------------------------------------ geometry

    @property
    def vel(self) -> Vector2:
        return self.body.vel

    @property
    def box(self) -> AABB:
        return AABB(self.body.pos.x, self.body.pos.y, self.w, self.h)

    @property
    def center(self) -> Vector2:
        return self.box.center

    def hand_pos(self) -> Vector2:
        return self.center + Vector2(self.facing * self.w * 0.6, -self.h * 0.15)

    def set_height(self, new_h: float) -> bool:
        """Change height keeping feet planted. Fails (returns False) if blocked."""
        dy = self.h - new_h
        candidate = AABB(self.body.pos.x, self.body.pos.y + dy, self.w, new_h)
        if new_h > self.h and not box_is_free(candidate, self._solids):
            return False
        self.body.pos.y += dy
        self.h = new_h
        return True

    def can_stand(self) -> bool:
        full = self.t.player_height
        dy = self.h - full
        return box_is_free(AABB(self.body.pos.x, self.body.pos.y + dy, self.w, full), self._solids)

    # ------------------------------------------------------------ ball actions

    def ball_in_reach(self) -> bool:
        b = self.ball
        return (
            b is not None
            and b.held_by is None
            and self.held_ball is None
            and self.center.distance_to(b.pos) <= self.t.pickup_radius
        )

    def try_pickup(self) -> None:
        """Request the ball. Game grants it at the end of the tick (closest
        requester wins if two players reach for it at once)."""
        if self.ball_in_reach():
            self.pickup_requested = True

    def aim_direction(self) -> Vector2:
        a = math.radians(self.aim_angle)
        return Vector2(math.cos(a), -math.sin(a))  # y-down screen coords

    def throw(self) -> None:
        if self.held_ball is None:
            return
        d = self.aim_direction()
        if abs(d.x) > 1e-3:
            self.facing = 1 if d.x > 0 else -1
        self.held_ball.release(self.center, d * self.aim_power)
        self.held_ball = None

    # ------------------------------------------------------------ tick

    def change_state(self, new: State) -> None:
        self.state.exit(self)
        self.state = new
        self.state.enter(self)

    def update(
        self,
        intent: Intent,
        dt: float,
        solids: list[AABB],
        ball: Ball | None,
        thin: list[AABB] | tuple[AABB, ...] = (),
    ) -> None:
        self._solids = solids
        self.ball = ball

        nxt = self.state.update(self, intent, dt)
        if nxt is not None:
            self.change_state(nxt)

        if self.state.wants_full_height and self.h < self.t.player_height:
            self.set_height(self.t.player_height)

        self.body.integrate_velocity(dt, self.state.gravity_scale(self))
        self.body.vel.y = min(self.body.vel.y, self.state.max_fall_speed(self))

        new_box = move_aabb(self.box, self.body.vel, dt, solids, thin)
        self.body.pos.update(new_box.x, new_box.y)
        self.contacts = probe_contacts(new_box, solids, thin)
