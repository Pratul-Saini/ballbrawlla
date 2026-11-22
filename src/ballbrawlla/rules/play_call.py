"""The play call phase of a down.

Offense (keyboard, mouse or controller - see gamepad.py for the buttons):
  1. Place the QB (only when the down lets the offense pick the spawn):
     drag the QB with the mouse, or move it with the arrows. It snaps to the
     nearest platform top inside the allowed region. Z / the button confirms.
  2. Aim: hold the mouse button and point (direction = angle, distance = power),
     or point the right stick (angle), or use left/right (angle) and up/down (power). X / the button locks in.
     Clicking the QB again (or Z) goes back to placing.
Defense: drag the Defender with the mouse, or move it with the arrows, inside
  its allowed region. Z / X / the button locks in.

Execution starts as soon as both sides are locked in. If the timer runs out
first, the play call restarts (same down) with everything kept as it was.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ballbrawlla.config import Tuning
from ballbrawlla.input import Intent
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.rules.down import ChooseInRegion, Down, defender_x_range, defender_min_yards, qb_x_range
from ballbrawlla.rules.field import Field, Spot
from ballbrawlla.rules.teams import Team


@dataclass
class CallMemory:
    """Last inputs per team, used as the defaults for the next play call."""

    qb_target: dict[Team, Spot] = field(default_factory=dict)
    aim: dict[Team, tuple[float, float]] = field(default_factory=dict)
    def_target: dict[Team, Spot] = field(default_factory=dict)


class PlayCall:
    def __init__(
        self,
        down: Down,
        field_: Field,
        t: Tuning,
        memory: CallMemory | None = None,
        defense_auto: bool = False,
    ) -> None:
        self.down = down
        self.field = field_
        self.t = t
        memory = memory or CallMemory()
        off, dfn = down.offense, down.defense

        self.timer = t.play_call_seconds
        self.restarts = 0

        # --- QB
        self.qb_lo, self.qb_hi = qb_x_range(down, field_)
        if isinstance(down.qb_spawn, ChooseInRegion):
            mid = (down.qb_spawn.start_yards + down.qb_spawn.end_yards) / 2
            target = memory.qb_target.get(off, Spot(field_.x_at(off, mid), field_.floor_y))
        else:
            target = down.qb_spawn.spot
        self.qb_spot = field_.spawn_spot(target, self.qb_lo, self.qb_hi)
        self.placing = down.offense_picks_spawn  # offense step: placing the QB vs aiming
        self._dragging_qb = False
        self._dragging_aim = False
        self.off_cursor = Vector2(self.qb_spot.x, self.qb_spot.y)

        # --- Aim
        default_aim = (45.0 if off.attack_dir > 0 else 135.0, (t.power_min + t.power_max) / 2)
        self.aim_angle, self.aim_power = memory.aim.get(off, default_aim)

        # --- Defender
        self.def_lo, self.def_hi = defender_x_range(down, field_, t)
        default_def = Spot(field_.x_at(off, defender_min_yards(down, field_, t) + 5), field_.floor_y)
        self.def_spot = field_.spawn_spot(memory.def_target.get(dfn, default_def), self.def_lo, self.def_hi)
        self._dragging_def = False
        self.def_cursor = Vector2(self.def_spot.x, self.def_spot.y)

        self.offense_locked = False
        self.defense_locked = defense_auto

    # ------------------------------------------------------------ queries

    @property
    def done(self) -> bool:
        return self.offense_locked and self.defense_locked

    def qb_center(self) -> Vector2:
        return self.qb_spot.center(self.t.player_height)

    def remember(self, memory: CallMemory) -> None:
        if self.down.offense_picks_spawn:
            memory.qb_target[self.down.offense] = self.qb_spot
        memory.aim[self.down.offense] = (self.aim_angle, self.aim_power)
        memory.def_target[self.down.defense] = self.def_spot

    # ------------------------------------------------------------ tick

    def update(self, offense: Intent, defense: Intent, dt: float) -> bool:
        """Apply both sides' input. Returns True once both are locked in."""
        self._update_offense(offense, dt)
        self._update_defense(defense, dt)
        if self.done:
            return True
        self.timer -= dt
        if self.timer <= 0:
            self.timer = self.t.play_call_seconds
            self.restarts += 1
        return False

    def _mouse_feet(self, intent: Intent) -> Vector2 | None:
        """Mouse points at the body; convert to the feet position used by spots."""
        if intent.mouse is None:
            return None
        return Vector2(intent.mouse[0], intent.mouse[1] + self.t.player_height / 2)

    def _update_offense(self, i: Intent, dt: float) -> None:
        if self.offense_locked:
            return
        can_place = self.down.offense_picks_spawn

        # Mouse
        if i.mouse_pressed and i.mouse is not None:
            near_qb = self.qb_center().distance_to(Vector2(i.mouse)) <= self.t.qb_grab_radius
            if can_place and (self.placing or near_qb):
                self.placing = True
                self._dragging_qb = True
            else:
                self._dragging_aim = True
        if not i.mouse_held:
            self._dragging_qb = self._dragging_aim = False
        if self._dragging_qb and (feet := self._mouse_feet(i)) is not None:
            self.off_cursor = feet
            self._snap_qb()
        if self._dragging_aim and i.mouse is not None:
            self._aim_at(Vector2(i.mouse))

        # Keyboard
        if self.placing:
            if i.move_x or i.vertical:
                self.off_cursor += Vector2(i.move_x, -i.vertical) * self.t.cursor_speed * dt
                self._snap_qb()
            confirm = i.z_pressed or i.button_pressed
            if confirm:
                self.placing = False
                self._dragging_qb = False
        else:
            if i.aim_stick is not None:  # controller: right stick points the throw
                self.aim_angle = math.degrees(math.atan2(i.aim_stick[1], i.aim_stick[0])) % 360
            self.aim_angle = (self.aim_angle - i.move_x * self.t.aim_rate * dt) % 360
            self.aim_power = self._clamp_power(self.aim_power + i.vertical * self.t.power_rate * dt)
            if i.z_pressed and can_place:
                self.placing = True
                self.off_cursor = Vector2(self.qb_spot.x, self.qb_spot.y)
            elif i.button_pressed:
                self.offense_locked = True
        if i.x_pressed:  # X locks in from either step
            self.placing = False
            self.offense_locked = True

    def _update_defense(self, i: Intent, dt: float) -> None:
        if self.defense_locked:
            return
        if i.mouse_pressed and i.mouse is not None:
            self._dragging_def = True
        if not i.mouse_held:
            self._dragging_def = False
        if self._dragging_def and (feet := self._mouse_feet(i)) is not None:
            self.def_cursor = feet
            self._snap_def()
        if i.move_x or i.vertical:
            self.def_cursor += Vector2(i.move_x, -i.vertical) * self.t.cursor_speed * dt
            self._snap_def()
        if i.z_pressed or i.x_pressed or i.button_pressed:
            self.defense_locked = True

    # ------------------------------------------------------------ helpers

    def _clamp_cursor(self, c: Vector2) -> None:
        lv = self.field.level
        c.x = min(max(c.x, 0), lv.width)
        c.y = min(max(c.y, 0), lv.height)

    def _snap_qb(self) -> None:
        self._clamp_cursor(self.off_cursor)
        spot = self.field.snap(self.off_cursor, self.qb_lo, self.qb_hi)
        if spot is not None:
            self.qb_spot = spot

    def _snap_def(self) -> None:
        self._clamp_cursor(self.def_cursor)
        spot = self.field.snap(self.def_cursor, self.def_lo, self.def_hi)
        if spot is not None:
            self.def_spot = spot

    def _aim_at(self, target: Vector2) -> None:
        d = target - self.qb_center()
        if d.length_squared() < 1:
            return
        self.aim_angle = math.degrees(math.atan2(-d.y, d.x)) % 360
        frac = min(1.0, d.length() / self.t.aim_drag_radius)
        self.aim_power = self._clamp_power(self.t.power_min + frac * (self.t.power_max - self.t.power_min))

    def _clamp_power(self, p: float) -> float:
        return min(self.t.power_max, max(self.t.power_min, p))
