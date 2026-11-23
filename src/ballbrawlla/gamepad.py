"""PS5 DualSense (and any other SDL game controller) -> Intent fields.

Uses SDL's game-controller API, which maps every supported pad to the same
layout (A = bottom face button, X = left, ...), so a DualSense, DualShock 4 or
Xbox pad all work. Every pad plugged into this machine controls the local
player, alongside the keyboard and mouse. Pads can be plugged in at any time.

    DualSense            Action                          Keyboard
    ---------            ------                          --------
    Left stick / D-pad   run, crouch/slide (down),       arrows
                         move the spawn cursor,
                         aim angle / power (when aiming)
    Cross                jump                            Up
    Square               catch / pick up / tag,          Z
                         confirm QB spot
    Circle               slide, or cancel a slide;       (hold Down to slide)
                         throw (sandbox) / lock in       X
    R1 or R2             throw (sandbox) / lock in        X
    Right stick          point the aim (play call and    mouse
                         sandbox aiming)
    Options              new match (practice/host)       R
    Create or touchpad   debug overlay                   F1
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

MOVE_DEADZONE = 0.35    # left stick: fraction of full tilt before it counts as left/right
VERTICAL_DEADZONE = 0.5  # higher, so running on a slight diagonal doesn't crouch
AIM_DEADZONE = 0.5      # right stick must be pushed this far to point the aim
TRIGGER_THRESHOLD = 0.5  # R2 pulled this far counts as a press
AXIS_MAX = 32767

BUTTON_TOUCHPAD = 20  # SDL_CONTROLLER_BUTTON_TOUCHPAD (not exposed by name in pygame-ce)

JUMP_BUTTONS = {pygame.CONTROLLER_BUTTON_A}                          # Cross
GRAB_BUTTONS = {pygame.CONTROLLER_BUTTON_X}                          # Square
THROW_BUTTONS = {pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER}  # Circle, R1
SLIDE_BUTTONS = {pygame.CONTROLLER_BUTTON_B}                         # Circle: slide (and cancel a slide)
RESTART_BUTTONS = {pygame.CONTROLLER_BUTTON_START}                   # Options
DEBUG_BUTTONS = {pygame.CONTROLLER_BUTTON_BACK, BUTTON_TOUCHPAD}     # Create, touchpad


@dataclass
class PadHeld:
    """Held (not edge) state of one pad, or combined over every connected pad."""

    move_x: int = 0
    vertical: int = 0      # +1 up, -1 down
    jump_held: bool = False
    aim_stick: tuple[float, float] | None = None  # (x, y) with y pointing up, or None


@dataclass
class PadEdges:
    jump: bool = False
    grab: bool = False
    throw: bool = False
    slide: bool = False


def _axis(pad, axis: int) -> float:
    return max(-1.0, min(1.0, pad.get_axis(axis) / AXIS_MAX))


class Gamepads:
    def __init__(self) -> None:
        self.pads: dict[int, object] = {}      # instance id -> pad, in the order they connected
        self._edges: dict[int, PadEdges] = {}
        self._r2_down: dict[int, bool] = {}
        self.available = False
        try:
            from pygame._sdl2 import controller

            controller.init()
            self._controller = controller
            self.available = True
            for i in range(controller.get_count()):
                self._open(i)
        except Exception:  # no controller support in this SDL build: keyboard/mouse only
            self._controller = None

    def _open(self, index: int) -> None:
        if self._controller is None or not self._controller.is_controller(index):
            return
        pad = self._controller.Controller(index)
        self.pads[pad.as_joystick().get_instance_id()] = pad

    @property
    def names(self) -> list[str]:
        return [getattr(p, "name", "controller") for p in self.pads.values()]

    # ------------------------------------------------------------ events

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Track pads and button presses. Returns "restart" or "debug" for menu buttons."""
        if event.type == pygame.CONTROLLERDEVICEADDED:
            self._open(event.device_index)
        elif event.type == pygame.CONTROLLERDEVICEREMOVED:
            pad = self.pads.pop(event.instance_id, None)
            self._r2_down.pop(event.instance_id, None)
            self._edges.pop(event.instance_id, None)
            if pad is not None and hasattr(pad, "quit"):
                pad.quit()
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            b = event.button
            edges = self._edges.setdefault(event.instance_id, PadEdges())
            if b in JUMP_BUTTONS:
                edges.jump = True
            elif b in GRAB_BUTTONS:
                edges.grab = True
            elif b in THROW_BUTTONS:
                edges.throw = True
            elif b in RESTART_BUTTONS:
                return "restart"
            elif b in DEBUG_BUTTONS:
                return "debug"
            if b in SLIDE_BUTTONS:        # Circle also starts/cancels a slide (its throw role is unused mid-run)
                edges.slide = True
        elif event.type == pygame.CONTROLLERAXISMOTION and event.axis == pygame.CONTROLLER_AXIS_TRIGGERRIGHT:
            down = event.value / AXIS_MAX >= TRIGGER_THRESHOLD
            if down and not self._r2_down.get(event.instance_id, False):
                self._edges.setdefault(event.instance_id, PadEdges()).throw = True
            self._r2_down[event.instance_id] = down
        return None

    def _ids(self, slot: int | None) -> list[int]:
        """All pads (slot None), or just the slot-th pad to have connected."""
        ids = list(self.pads)
        return ids if slot is None else ids[slot:slot + 1]

    def consume_edges(self, slot: int | None = None) -> PadEdges:
        """Button presses since the last call, for every pad or for one slot."""
        out = PadEdges()
        for pid in (list(self._edges) if slot is None else self._ids(slot)):
            e = self._edges.pop(pid, None)
            if e is not None:
                out.jump |= e.jump
                out.grab |= e.grab
                out.throw |= e.throw
                out.slide |= e.slide
        return out

    # ------------------------------------------------------------ held state

    def held(self, slot: int | None = None) -> PadHeld:
        """Held state for every pad combined, or for the slot-th pad to connect
        (local play: slot 0 is Blue's pad, slot 1 is Red's)."""
        out = PadHeld()
        best_aim = 0.0
        for pad in (self.pads[i] for i in self._ids(slot)):
            lx = _axis(pad, pygame.CONTROLLER_AXIS_LEFTX)
            ly = -_axis(pad, pygame.CONTROLLER_AXIS_LEFTY)  # SDL: down is positive
            mx = (lx >= MOVE_DEADZONE) - (lx <= -MOVE_DEADZONE)
            mx += pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT) - pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
            vy = (ly >= VERTICAL_DEADZONE) - (ly <= -VERTICAL_DEADZONE)
            vy += pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_UP) - pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN)
            out.move_x = out.move_x or max(-1, min(1, mx))
            out.vertical = out.vertical or max(-1, min(1, vy))
            out.jump_held = out.jump_held or any(pad.get_button(b) for b in JUMP_BUTTONS)

            rx = _axis(pad, pygame.CONTROLLER_AXIS_RIGHTX)
            ry = -_axis(pad, pygame.CONTROLLER_AXIS_RIGHTY)
            mag = math.hypot(rx, ry)
            if mag >= AIM_DEADZONE and mag > best_aim:
                best_aim, out.aim_stick = mag, (rx, ry)
        return out
