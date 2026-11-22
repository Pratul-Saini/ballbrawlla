"""Player state machine.

    Grounded --Up--> Airborne --touch wall + press into it--> WallCling
       |  ^             ^  |                                     |
  Down |  | release     |  +--land--> Grounded       press away / lose wall
       v  |             +--------------------------------------+
    Crouch / Slide

    Grounded/Crouch --Z (holding ball)--> Aiming --X throw / Z cancel--> Grounded

Each state's update() runs *before* physics for the tick. It sets velocity and
returns a new State to transition to, or None to stay.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ballbrawlla.input import Intent

if TYPE_CHECKING:
    from ballbrawlla.entities.player import Player


class State:
    name = "state"
    wants_full_height = True  # player stands back up when possible
    allows_pickup = True  # False: Z means something else in this state

    def enter(self, p: Player) -> None:
        pass

    def exit(self, p: Player) -> None:
        pass

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        raise NotImplementedError

    def gravity_scale(self, p: Player) -> float:
        return 1.0

    def max_fall_speed(self, p: Player) -> float:
        return p.t.player_max_fall_speed


def _jump(p: Player, speed: float) -> None:
    p.vel.y = -speed
    p.jump_cut_ready = True


def _face(p: Player, move_x: int) -> None:
    if move_x:
        p.facing = move_x


def _grab_or_aim(p: Player, intent: Intent) -> State | None:
    """Z on the ground while holding the ball: aim. Pickups are handled in Player.update."""
    if intent.z_pressed and p.held_ball is not None and p.t.throw_enabled and p.can_throw:
        return Aiming()
    return None


class Grounded(State):
    name = "grounded"

    def enter(self, p: Player) -> None:
        p.jumps_left = p.t.air_jumps
        p.control_lock = 0.0

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        if not p.contacts.on_ground:
            return Airborne()
        p.vel.x = intent.move_x * p.t.run_speed
        _face(p, intent.move_x)

        if (nxt := _grab_or_aim(p, intent)) is not None:
            return nxt
        if intent.jump_pressed:
            _jump(p, p.t.jump_speed)
            return Airborne()
        if intent.down_held:
            return Slide() if intent.move_x and p.t.slide_enabled else Crouch()
        return None


class Airborne(State):
    name = "airborne"

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        if p.contacts.on_ground and p.vel.y >= 0:
            return Grounded()

        if p.control_lock > 0:
            p.control_lock -= dt
        else:
            p.vel.x = intent.move_x * p.t.air_speed
            _face(p, intent.move_x)

        # Press into a wall to stick to it.
        if p.contacts.wall_left and intent.move_x < 0:
            return WallCling(-1)
        if p.contacts.wall_right and intent.move_x > 0:
            return WallCling(1)

        if intent.jump_pressed and p.jumps_left > 0:
            p.jumps_left -= 1
            _jump(p, p.t.double_jump_speed)
        elif p.jump_cut_ready and p.vel.y < 0 and not intent.up_held:
            p.vel.y *= p.t.jump_cut_multiplier  # short hop on early release
            p.jump_cut_ready = False
        if p.vel.y >= 0:
            p.jump_cut_ready = False
        return None


class WallCling(State):
    name = "wall_cling"

    def __init__(self, side: int) -> None:
        self.side = side  # -1 wall on the left, +1 wall on the right

    def enter(self, p: Player) -> None:
        p.vel.update(0, 0)  # stick
        p.jumps_left = p.t.air_jumps
        p.jump_cut_ready = False
        p.facing = -self.side  # face away from the wall

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        if p.contacts.on_ground:
            return Grounded()
        touching = p.contacts.wall_left if self.side < 0 else p.contacts.wall_right
        if not touching:
            return Airborne()

        p.vel.x = 0
        if intent.move_x == -self.side:  # press away: wall jump
            p.vel.update(-self.side * p.t.wall_jump_x, -p.t.wall_jump_y)
            p.control_lock = p.t.wall_jump_control_lock
            p.facing = -self.side
            return Airborne()
        if intent.jump_pressed:  # hop up the wall
            _jump(p, p.t.wall_climb_speed)
            p.jump_cut_ready = False
        if intent.move_x == self.side and p.t.wall_hold_sticks and p.vel.y > 0:
            p.vel.y = 0
        return None

    def gravity_scale(self, p: Player) -> float:
        # Rising: full gravity. Falling: wall friction.
        return 1.0 if p.vel.y < 0 else p.t.wall_gravity_scale

    def max_fall_speed(self, p: Player) -> float:
        return p.t.wall_slide_max_speed


class Crouch(State):
    name = "crouch"
    wants_full_height = False

    def enter(self, p: Player) -> None:
        p.set_height(p.t.player_crouch_height)
        p.vel.x = 0

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        if not p.contacts.on_ground:
            return Airborne()
        p.vel.x = 0
        _face(p, intent.move_x)
        if (nxt := _grab_or_aim(p, intent)) is not None:
            return nxt
        if intent.jump_pressed and p.can_stand():
            _jump(p, p.t.jump_speed)
            return Airborne()
        if not intent.down_held and p.can_stand():
            return Grounded()
        return None


class Slide(State):
    name = "slide"
    wants_full_height = False

    def enter(self, p: Player) -> None:
        p.set_height(p.t.player_crouch_height)
        p.vel.x = p.facing * p.t.slide_speed
        self.timer = p.t.slide_duration

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        if not p.contacts.on_ground:
            return Airborne()
        self.timer -= dt
        p.vel.x *= max(0.0, 1 - p.t.slide_friction * dt)
        if intent.jump_pressed and p.can_stand():
            _jump(p, p.t.jump_speed)
            return Airborne()
        if self.timer <= 0 or abs(p.vel.x) < p.t.run_speed * 0.3:
            if intent.down_held or not p.can_stand():
                return Crouch()
            return Grounded()
        return None


class Aiming(State):
    """Fixed in place. Left/right rotates the aim (full circle), up/down sets power."""

    name = "aiming"
    allows_pickup = False

    def enter(self, p: Player) -> None:
        p.vel.update(0, 0)
        p.pickup_buffer = 0
        p.aim_angle = 45.0 if p.facing > 0 else 135.0
        p.aim_power = (p.t.power_min + p.t.power_max) / 2

    def update(self, p: Player, intent: Intent, dt: float) -> State | None:
        p.vel.x = 0
        if not p.contacts.on_ground:
            return Airborne()
        # Right = clockwise, left = counter-clockwise.
        if intent.aim_stick is not None:  # controller: right stick points the throw
            p.aim_angle = math.degrees(math.atan2(intent.aim_stick[1], intent.aim_stick[0])) % 360
        p.aim_angle = (p.aim_angle - intent.move_x * p.t.aim_rate * dt) % 360
        p.aim_power = min(
            p.t.power_max,
            max(p.t.power_min, p.aim_power + intent.vertical * p.t.power_rate * dt),
        )
        if intent.x_pressed:
            p.throw()
            return Grounded()
        if intent.z_pressed:
            return Grounded()
        return None
