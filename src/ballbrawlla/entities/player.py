"""The player: a kinematic AABB driven by a state machine.

Each tick:
  1. the current state reads the Intent and sets velocity / requests a transition
  2. gravity is applied (scaled and capped by the state)
  3. the box is moved and pushed out of solids, one axis at a time
  4. contacts are probed for the next tick's state logic
"""

from __future__ import annotations

import math
from collections.abc import Sequence

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
        self.role: str | None = None  # gameplay role (QB / WR / DEF) when in a match
        self.team: int | None = None
        self.can_throw = True          # WR and Defender can't throw
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
        # The wall I last clung to. I can't cling to it again until I've clung to a
        # different wall or landed (no climbing one wall by re-grabbing it).
        self.last_wall: AABB | None = None
        self.ball: Ball | None = None  # the ball in the world, set each tick
        self.pickup_requested = False  # resolved by Game after all players update
        self.pickup_buffer = 0         # ticks left on an armed Z press
        self.ball_trail: Sequence[Vector2] = ()  # host's recent Free-ball positions, set each tick
        self.aim_angle = 45.0          # degrees, 0 = right, 90 = up (full circle)
        self.aim_power = (tuning.power_min + tuning.power_max) / 2

        # Feet position the last time this player stood on a platform (where a play
        # restarts if they're tagged mid-air).
        self.last_ground = Vector2(spawn_center.x, spawn_center.y + self.h / 2)

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

    # ------------------------------------------------------------ walls

    def touching_wall(self, side: int) -> AABB | None:
        """The solid I'm pressed against on `side` (-1 left, +1 right), if any."""
        probe = self.box.shifted(side, 0)
        hits = [s for s in self._solids if probe.overlaps(s)]
        if not hits:
            return None
        return max(hits, key=lambda s: min(s.bottom, probe.bottom) - max(s.top, probe.top))

    def can_cling(self, side: int) -> bool:
        wall = self.touching_wall(side)
        return wall is not None and wall is not self.last_wall

    def will_clear_wall(self, side: int, up_held: bool = True) -> bool:
        """True if the rest of the current upward motion will lift my feet above the
        top of the wall I'm touching on `side` (-1 left, +1 right)."""
        vy = self.vel.y
        if vy >= 0:
            return False
        if self.jump_cut_ready and not up_held:
            vy *= self.t.jump_cut_multiplier  # releasing Up is about to cut this jump
        probe = self.box.shifted(side, 0)
        tops = [s.top for s in self._solids if probe.overlaps(s)]
        if not tops:
            return False
        rise = vy * vy / (2 * self.t.player_gravity)
        return rise >= self.box.bottom - min(tops)

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

    def pickup_distance(self) -> float | None:
        """Smallest distance from my center to the ball's current or recent positions.
        None if there is no ball, it is held, or I already hold it."""
        b = self.ball
        if b is None or b.held_by is not None or self.held_ball is not None:
            return None
        c = self.center
        return min(c.distance_to(q) for q in (b.pos, *self.ball_trail))

    def ball_in_grace_reach(self) -> bool:
        d = self.pickup_distance()
        return d is not None and d <= self.t.pickup_radius

    def _pickup_step(self, z_pressed: bool) -> None:
        """The one place a pickup is attempted. Game grants it at the end of the
        tick (closest requester wins if two players reach for it at once)."""
        if self.held_ball is not None:
            self.pickup_buffer = 0
            return
        if not self.state.allows_pickup:
            return
        if z_pressed:
            pass
        elif self.pickup_buffer > 0:
            self.pickup_buffer -= 1
        else:
            return
        if self.ball_in_grace_reach():
            self.pickup_requested = True
        elif z_pressed:
            self.pickup_buffer = self.t.pickup_buffer_ticks

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
        ball_trail: Sequence[Vector2] = (),
    ) -> None:
        self._solids = solids
        self.ball = ball
        self.ball_trail = ball_trail
        self._pickup_step(intent.z_pressed)

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
        if self.contacts.on_ground and self.state.name != "wall_cling":
            self.last_ground = Vector2(new_box.center.x, new_box.bottom)
