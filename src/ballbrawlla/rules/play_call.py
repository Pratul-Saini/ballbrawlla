"""The play call phase of a down.

Both sides move a real player with the same movement as in the play (run,
jump, double jump, wall-cling and climb, slide, crawl):

Offense (keyboard or controller - see gamepad.py for the buttons):
  1. Place the QB (only when the down lets the offense pick the spawn): move the
     QB around the level. It can only be confirmed while standing on a platform
     inside the yellow zone; where it stands becomes its spawn. Z / the button
     confirms.
  2. Aim: hold the mouse button and point (direction = angle, distance = power),
     or point the right stick (angle), or use left/right (angle) and up/down
     (power). X / the button locks in. Clicking the QB (or Z) goes back to moving it.
Defense: move the Defender the same way; it locks in (Z / X / the button) only
  while standing on a platform inside its zone.

With Tuning.throw_enabled False (the default) there is nothing to aim: step 2 does not exist, Z / X / the
button confirms the QB spot and locks the offense in directly (mouse and aim input are ignored), and a down
that fixes the QB spot starts with the offense already locked in.

Execution starts as soon as both sides are locked in. If the timer runs out
first, the play call restarts (same down) with everything kept as it was.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ballbrawlla.config import Tuning
from ballbrawlla.entities.player import Player
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

        # --- QB: a player the offense moves around (while placing)
        self.qb_lo, self.qb_hi = qb_x_range(down, field_)
        if isinstance(down.qb_spawn, ChooseInRegion):
            mid = (down.qb_spawn.start_yards + down.qb_spawn.end_yards) / 2
            target = memory.qb_target.get(off, Spot(field_.x_at(off, mid), field_.floor_y))
        else:
            target = down.qb_spawn.spot
        self.qb_spot = field_.spawn_spot(target, self.qb_lo, self.qb_hi)
        self.qb_player = self._player(self.qb_spot, off.attack_dir)
        self.qb_ok = True
        self.placing = down.offense_picks_spawn  # offense step: moving the QB vs aiming
        self._dragging_aim = False

        # --- Aim
        default_aim = (45.0 if off.attack_dir > 0 else 135.0, (t.power_min + t.power_max) / 2)
        self.aim_angle, self.aim_power = memory.aim.get(off, default_aim)

        # --- Defender: a player the defense moves around
        self.def_lo, self.def_hi = defender_x_range(down, field_, t)
        default_def = Spot(field_.x_at(off, defender_min_yards(down, field_, t) + 5), field_.floor_y)
        self.def_spot = field_.spawn_spot(memory.def_target.get(dfn, default_def), self.def_lo, self.def_hi)
        self.def_player = self._player(self.def_spot, dfn.attack_dir)
        self.def_ok = True

        self.offense_locked = not t.throw_enabled and not down.offense_picks_spawn   # nothing to decide
        self.defense_locked = defense_auto

    def _player(self, spot: Spot, facing: int) -> Player:
        p = Player(spot.center(self.t.player_height), self.t)
        p.facing = facing
        p.can_throw = False
        for _ in range(2):          # settle onto the spot: contacts, then the Grounded state
            self._move(p, Intent(), 0.0)
        return p

    # ------------------------------------------------------------ queries

    @property
    def done(self) -> bool:
        return self.offense_locked and self.defense_locked

    @staticmethod
    def feet(p: Player) -> Vector2:
        return Vector2(p.center.x, p.box.bottom)

    def qb_center(self) -> Vector2:
        """Where the QB is drawn and aimed from."""
        return Vector2(self.qb_player.center)

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

    def _move(self, p: Player, intent: Intent, dt: float) -> None:
        lv = self.field.level
        p.update(intent, dt, lv.solids, None, thin=lv.thin)

    def _standing_spot(self, p: Player, lo: float, hi: float) -> tuple[Spot | None, bool]:
        """The spawn spot under the player's feet, and whether it counts: standing on
        a platform (not jumping, not clinging) inside [lo, hi]. Standing on a
        platform's edge counts too; the spot is then moved inward (by at most half a
        body width) so the spawn is fully on the platform."""
        if not p.contacts.on_ground or p.vel.y < 0 or p.state.name == "wall_cling":
            return None, False
        feet = self.feet(p)
        spot = self.field.snap(feet, lo, hi)
        ok = (spot is not None and abs(spot.y - feet.y) <= 1
              and abs(spot.x - feet.x) <= self.t.player_width / 2)
        return spot, ok

    def _update_offense(self, i: Intent, dt: float) -> None:
        if self.offense_locked:
            return
        can_place = self.down.offense_picks_spawn

        if not self.t.throw_enabled:
            self._move(self.qb_player, i, dt)
            spot, self.qb_ok = self._standing_spot(self.qb_player, self.qb_lo, self.qb_hi)
            if self.qb_ok:
                self.qb_spot = spot
            if (i.z_pressed or i.x_pressed or i.button_pressed) and self.qb_ok:
                self.placing = False
                self.offense_locked = True
            return

        # Mouse: aiming only (and clicking the QB to go back to moving it)
        if i.mouse_pressed and i.mouse is not None:
            near_qb = self.qb_center().distance_to(Vector2(i.mouse)) <= self.t.qb_grab_radius
            if can_place and near_qb and not self.placing:
                self.placing = True
            elif not self.placing:
                self._dragging_aim = True
        if not i.mouse_held:
            self._dragging_aim = False
        if self._dragging_aim and i.mouse is not None:
            self._aim_at(Vector2(i.mouse))

        if self.placing:
            self._move(self.qb_player, i, dt)
            spot, self.qb_ok = self._standing_spot(self.qb_player, self.qb_lo, self.qb_hi)
            if self.qb_ok:
                self.qb_spot = spot
            if (i.z_pressed or i.button_pressed) and self.qb_ok:
                self.placing = False
        else:
            if i.aim_stick is not None:  # controller: right stick points the throw
                self.aim_angle = math.degrees(math.atan2(i.aim_stick[1], i.aim_stick[0])) % 360
            self.aim_angle = (self.aim_angle - i.move_x * self.t.aim_rate * dt) % 360
            self.aim_power = self._clamp_power(self.aim_power + i.vertical * self.t.power_rate * dt)
            if i.z_pressed and can_place:
                self.placing = True
            elif i.button_pressed:
                self.offense_locked = True
        if i.x_pressed and self.qb_ok:  # X locks in from either step - only standing on a platform
            self.placing = False
            self.offense_locked = True

    def _update_defense(self, i: Intent, dt: float) -> None:
        if self.defense_locked:
            return
        self._move(self.def_player, i, dt)
        spot, self.def_ok = self._standing_spot(self.def_player, self.def_lo, self.def_hi)
        if self.def_ok:
            self.def_spot = spot
        if (i.z_pressed or i.x_pressed or i.button_pressed) and self.def_ok:
            self.defense_locked = True

    # ------------------------------------------------------------ helpers

    def _aim_at(self, target: Vector2) -> None:
        d = target - self.qb_center()
        if d.length_squared() < 1:
            return
        self.aim_angle = math.degrees(math.atan2(-d.y, d.x)) % 360
        frac = min(1.0, d.length() / self.t.aim_drag_radius)
        self.aim_power = self._clamp_power(self.t.power_min + frac * (self.t.power_max - self.t.power_min))

    def _clamp_power(self, p: float) -> float:
        return min(self.t.power_max, max(self.t.power_min, p))
