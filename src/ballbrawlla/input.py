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


@dataclass(frozen=True)
class KeyBindings:
    left: int
    right: int
    up: int
    down: int
    grab: int    # catch / pick up / tag / confirm (the "Z" action)
    throw: int   # throw / lock in (the "X" action)
    label: str = ""


# One player per machine (practice, host, join, sandbox)
DEFAULT_KEYS = KeyBindings(pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                           pygame.K_z, pygame.K_x, "arrows, Z, X")
# Two players on one keyboard (--local)
BLUE_KEYS = KeyBindings(pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s,
                        pygame.K_f, pygame.K_g, "WASD, F, G")
RED_KEYS = KeyBindings(pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                       pygame.K_PERIOD, pygame.K_SLASH, "arrows, period, slash")

KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN = (DEFAULT_KEYS.left, DEFAULT_KEYS.right,
                                         DEFAULT_KEYS.up, DEFAULT_KEYS.down)
KEY_GRAB_AIM, KEY_THROW = DEFAULT_KEYS.grab, DEFAULT_KEYS.throw


class KeyboardInput:
    """Collects key/mouse/controller press edges between physics ticks so none
    are dropped. Any controller plugged into this machine drives the same player."""

    def __init__(
        self,
        gamepads: bool = True,
        keys: KeyBindings = DEFAULT_KEYS,
        shared_pads: Gamepads | None = None,
        pad_slot: int | None = None,
    ) -> None:
        """One player's input. By default this owns every controller on the machine.
        For local play, pass `shared_pads` (whose events the caller handles once)
        and the `pad_slot` this player uses (0 = first controller to connect)."""
        self.keys = keys
        self._owns_pads = shared_pads is None and gamepads
        self.gamepads = shared_pads if shared_pads is not None else (Gamepads() if gamepads else None)
        self.pad_slot = pad_slot
        self._pressed: set[int] = set()
        self._mouse_pressed = False
        self._button_pressed = False
        self._hold_on_button = False  # a press that began on the HUD button isn't a drag

    def handle_event(
        self, event: pygame.event.Event, button_hit: Callable[[tuple[int, int]], bool] | None = None
    ) -> str | None:
        """Returns "restart" or "debug" when a controller menu button is pressed."""
        if self.gamepads is not None and self._owns_pads:
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

    def consume(self, camera: Vector2 | None = None, zoom: float = 1.0, use_mouse: bool = True) -> Intent:
        """`camera` is the world position of the screen's top-left corner and `zoom`
        the camera scale. `use_mouse=False` leaves the mouse to the other player."""
        k = self.keys
        held = pygame.key.get_pressed()
        mouse = None
        if use_mouse and pygame.mouse.get_focused():
            mx, my = pygame.mouse.get_pos()
            off = camera if camera is not None else Vector2()
            mouse = (mx / zoom + off.x, my / zoom + off.y)
        pad, edges = PadHeld(), PadEdges()
        if self.gamepads is not None:
            pad, edges = self.gamepads.held(self.pad_slot), self.gamepads.consume_edges(self.pad_slot)
        key_x = int(held[k.right]) - int(held[k.left])
        key_v = int(held[k.up]) - int(held[k.down])
        intent = Intent(
            move_x=key_x or pad.move_x,
            vertical=key_v or pad.vertical,
            jump_pressed=k.up in self._pressed or edges.jump,
            z_pressed=k.grab in self._pressed or edges.grab,
            x_pressed=k.throw in self._pressed or edges.throw,
            jump_held=pad.jump_held,
            aim_stick=pad.aim_stick,
            mouse=mouse,
            mouse_held=use_mouse and bool(pygame.mouse.get_pressed()[0]) and not self._hold_on_button,
            mouse_pressed=use_mouse and self._mouse_pressed,
            button_pressed=use_mouse and self._button_pressed,
        )
        self._pressed.clear()
        self._mouse_pressed = self._button_pressed = False
        return intent
