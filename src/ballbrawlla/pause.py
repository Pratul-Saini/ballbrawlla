"""In-game pause menu: Resume, Controls, Main menu. Esc opens and closes it.

`PauseMenu.handle(event)` returns True when it used the event, so the game loop skips it. While `open`, the
loop should stop stepping the simulation (`pauses` says whether this mode can: network games keep running,
because freezing the host would freeze the other player).
"""

from __future__ import annotations

import pygame

from ballbrawlla.menu import DIM, FG, PANEL

ITEMS = ("RESUME", "CONTROLS", "MAIN MENU")

COMMON = [
    "Move: left / right arrows, left stick       Jump: Up arrow, Cross",
    "Crouch, slide: Down arrow, down on stick    Catch, tag, confirm: Z, Square",
    "Throw, lock in: X, Circle, R1               Aim: mouse, right stick",
    "R / Options: restart   F1: debug   F2: notes   F3: hide controls   Esc: this menu",
]
LOCAL = [
    "Blue: WASD + F (catch, tag, confirm) + G (lock in)",
    "Red: arrows + . (catch, tag, confirm) + / (lock in)",
    "Controllers: first pad is Blue, second is Red",
    "F5: new match   F1: debug   F2: notes   F3: hide controls   Esc: this menu",
]


class PauseMenu:
    def __init__(self, controls: list[str] | None = None, pauses: bool = True) -> None:
        self.controls = controls or COMMON
        self.pauses = pauses
        self.open = False
        self.page = "menu"          # "menu" or "controls"
        self.cursor = 0
        self._hint: pygame.Surface | None = None
        self.result: str | None = None   # "menu" when the player asked for the main menu

    @property
    def freezes(self) -> bool:
        return self.open and self.pauses

    def _rects(self, size: tuple[int, int]) -> list[pygame.Rect]:
        w, h = size
        return [pygame.Rect(w // 2 - 160, h // 2 - 70 + k * 52, 320, 44) for k in range(len(ITEMS))]

    def _choose(self) -> None:
        if self.page == "controls":
            self.page = "menu"
        elif ITEMS[self.cursor] == "RESUME":
            self.open = False
        elif ITEMS[self.cursor] == "CONTROLS":
            self.page = "controls"
        else:
            self.result = "menu"
            self.open = False

    def _close_or_back(self) -> None:
        if self.page == "controls":
            self.page = "menu"
        else:
            self.open = False

    def handle(self, event: pygame.event.Event, size: tuple[int, int] = (1280, 720)) -> bool:
        if not self.open:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.open, self.page, self.cursor = True, "menu", 0
                return True
            return False
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if self.page == "controls":
                self.page = "menu"
            elif event.key == pygame.K_ESCAPE:
                self._close_or_back()
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.cursor = (self.cursor - 1) % len(ITEMS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.cursor = (self.cursor + 1) % len(ITEMS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._choose()
        elif event.type == pygame.MOUSEMOTION and self.page == "menu":
            for k, r in enumerate(self._rects(size)):
                if r.collidepoint(event.pos):
                    self.cursor = k
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.page == "controls":
                self.page = "menu"
            else:
                for k, r in enumerate(self._rects(size)):
                    if r.collidepoint(event.pos):
                        self.cursor = k
                        self._choose()
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            b = event.button
            if b == pygame.CONTROLLER_BUTTON_DPAD_UP:
                self.cursor = (self.cursor - 1) % len(ITEMS)
            elif b == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
                self.cursor = (self.cursor + 1) % len(ITEMS)
            elif b in (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_X):
                self._choose()
            elif b in (pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_START):
                self._close_or_back()
        return True      # while open, the game sees no input

    def draw_hint(self, surface: pygame.Surface) -> None:
        """A small "Esc: menu" badge in the bottom-right corner, on the same line as the status text, drawn over everything else and taking no input."""
        if self._hint is None:
            img = pygame.font.Font(None, 20).render("Esc: menu", True, (255, 255, 255))
            badge = pygame.Surface((img.get_width() + 14, img.get_height() + 6), pygame.SRCALPHA)
            pygame.draw.rect(badge, (0, 0, 0, 120), badge.get_rect(), border_radius=5)
            badge.blit(img, (7, 3))
            self._hint = badge
        surface.blit(self._hint, (surface.get_width() - self._hint.get_width() - 12, surface.get_height() - self._hint.get_height() - 12))

    def draw(self, surface: pygame.Surface) -> None:
        if not self.open:
            self.draw_hint(surface)
            return
        w, h = surface.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, (0, 0))
        big, mid, small = pygame.font.Font(None, 56), pygame.font.Font(None, 36), pygame.font.Font(None, 26)

        def text(font, s, color, **pos):
            img = font.render(s, True, color)
            surface.blit(img, img.get_rect(**pos))

        if self.page == "controls":
            box = pygame.Rect(0, 0, 900, 120 + 36 * len(self.controls))
            box.center = (w // 2, h // 2)
            pygame.draw.rect(surface, PANEL, box, border_radius=8)
            pygame.draw.rect(surface, FG, box, 2, border_radius=8)
            text(big, "CONTROLS", FG, midtop=(w // 2, box.y + 16))
            for k, line in enumerate(self.controls):
                text(small, line, FG, midtop=(w // 2, box.y + 80 + 36 * k))
            text(small, "any key or click to go back", DIM, midbottom=(w // 2, box.bottom - 10))
            return
        text(big, "PAUSED" if self.pauses else "MENU (game keeps running)", FG, midtop=(w // 2, h // 2 - 170))
        for k, (label, r) in enumerate(zip(ITEMS, self._rects((w, h)))):
            if k == self.cursor:
                pygame.draw.rect(surface, PANEL, r, border_radius=6)
                pygame.draw.rect(surface, FG, r, 2, border_radius=6)
            text(mid, label, FG, center=r.center)
