"""Keyboard -> Intent.

The simulation never reads keys directly; it only sees an Intent. That keeps
player logic testable and makes a second player / AI a matter of producing
another Intent.
"""

from dataclasses import dataclass

import pygame


@dataclass
class Intent:
    move_x: int = 0          # -1 left, 0, +1 right (held)
    vertical: int = 0        # +1 up, 0, -1 down (held)
    jump_pressed: bool = False  # Up pressed this tick
    z_pressed: bool = False     # pick up / enter aim / cancel aim
    x_pressed: bool = False     # throw

    @property
    def up_held(self) -> bool:
        return self.vertical > 0

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
    """Collects key-press edges between physics ticks so none are dropped."""

    def __init__(self) -> None:
        self._pressed: set[int] = set()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._pressed.add(event.key)

    def consume(self) -> Intent:
        held = pygame.key.get_pressed()
        intent = Intent(
            move_x=int(held[KEY_RIGHT]) - int(held[KEY_LEFT]),
            vertical=int(held[KEY_UP]) - int(held[KEY_DOWN]),
            jump_pressed=KEY_UP in self._pressed,
            z_pressed=KEY_GRAB_AIM in self._pressed,
            x_pressed=KEY_THROW in self._pressed,
        )
        self._pressed.clear()
        return intent
