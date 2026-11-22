"""Keyboard + mouse + game controllers -> Intent.

The simulation never reads devices directly; it only sees an Intent. That keeps
player logic testable and makes a second player / AI a matter of producing
another Intent.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from ballbrawlla.gamepad import Gamepads, PadEdges, PadHeld
from ballbrawlla.physics.vec import Vector2


@dataclass
class Intent:
    move_x: int = 0          # -1 left, 0, +1 right (held)
    vertical: int = 0        # +1 up, 0, -1 down (held)
    jump_pressed: bool = False  # Up pressed this tick
    z_pressed: bool = False     # pick up / tag / confirm spot / enter or cancel aim
    x_pressed: bool = False     # throw / lock in the play call
    # Mouse (play call). Position is in world coordinates.
    mouse: tuple[float, float] | None = None
    mouse_held: bool = False      # left button down (and not started on the HUD button)
    mouse_pressed: bool = False   # left button went down this tick (not on the HUD button)
    button_pressed: bool = False  # the on-screen play-call button was clicked
    # Controller extras
    jump_held: bool = False       # jump button held (Cross); keeps a jump full height like holding Up
    aim_stick: tuple[float, float] | None = None  # right stick direction (y up) when pushed

    @property
    def up_held(self) -> bool:
        return self.vertical > 0 or self.jump_held

    @property
    def down_held(self) -> bool:
        return self.vertical < 0


KEY_LEFT = pygame.K_LEFT
KEY_RIGHT = pygame.K_RIGHT
KEY_UP = pygame.K_UP
KEY_DOWN = pygame.K_DOWN
KEY_GRAB_AIM = pygame.K_z
KEY_THROW = pygame.K_x


class KeyboardInput:
    """Collects key/mouse/controller press edges between physics ticks so none
    are dropped. Any controller plugged into this machine drives the same player."""

    def __init__(self, gamepads: bool = True) -> None:
        self.gamepads = Gamepads() if gamepads else None
        self._pressed: set[int] = set()
        self._mouse_pressed = False
        self._button_pressed = False
        self._hold_on_button = False  # a press that began on the HUD button isn't a drag

    def handle_event(
        self, event: pygame.event.Event, button_hit: Callable[[tuple[int, int]], bool] | None = None
    ) -> str | None:
        """Returns "restart" or "debug" when a controller menu button is pressed."""
        if self.gamepads is not None:
            action = self.gamepads.handle_event(event)
            if action is not None:
                return action
        if event.type == pygame.KEYDOWN:
            self._pressed.add(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if button_hit is not None and button_hit(event.pos):
                self._button_pressed = True
                self._hold_on_button = True
            else:
                self._mouse_pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._hold_on_button = False
        return None

    def consume(self, camera: Vector2 | None = None) -> Intent:
        """`camera` is the world position of the screen's top-left corner."""
        held = pygame.key.get_pressed()
        mouse = None
        if pygame.mouse.get_focused():
            mx, my = pygame.mouse.get_pos()
            off = camera if camera is not None else Vector2()
            mouse = (mx + off.x, my + off.y)
        pad, edges = PadHeld(), PadEdges()
        if self.gamepads is not None:
            pad, edges = self.gamepads.held(), self.gamepads.consume_edges()
        key_x = int(held[KEY_RIGHT]) - int(held[KEY_LEFT])
        key_v = int(held[KEY_UP]) - int(held[KEY_DOWN])
        intent = Intent(
            move_x=key_x or pad.move_x,
            vertical=key_v or pad.vertical,
            jump_pressed=KEY_UP in self._pressed or edges.jump,
            z_pressed=KEY_GRAB_AIM in self._pressed or edges.grab,
            x_pressed=KEY_THROW in self._pressed or edges.throw,
            jump_held=pad.jump_held,
            aim_stick=pad.aim_stick,
            mouse=mouse,
            mouse_held=pygame.mouse.get_pressed()[0] and not self._hold_on_button,
            mouse_pressed=self._mouse_pressed,
            button_pressed=self._button_pressed,
        )
        self._pressed.clear()
        self._mouse_pressed = self._button_pressed = False
        return intent
