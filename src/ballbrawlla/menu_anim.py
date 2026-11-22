"""The animated backdrop of the menu: a scrolling field, and two players throwing a football back and forth.

Everything is drawn in code, so the game needs no image files. If you add your own ball frames as
assets/menu/football_*.png (any size, transparent background, in order), they replace the drawn ball.

`pose(t, width)` is a pure function of time, so the animation is easy to test and has no state to get out of
step. Each throw takes PERIOD seconds: wind-up, flight along an arc, catch, hold. Then the players swap roles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pygame

from ballbrawlla.paths import assets_dir

PERIOD = 3.6
WINDUP, FLIGHT, CATCH = 0.5, 1.8, 0.4            # seconds; the rest of PERIOD is the hold
TRAIL = 6                                         # ghost balls behind the real one
TRAIL_STEP = 0.028                                # seconds between ghosts
SCROLL_PX_PER_S = 18.0
STRIPE = 80                                       # px per field stripe

GRASS_A = (30, 104, 52)
GRASS_B = (34, 112, 56)
LINE = (44, 128, 70)
BLUE = (72, 140, 240)
RED = (232, 84, 84)
OUTLINE = (255, 255, 255)
BALL_BROWN = (140, 82, 40)
BALL_DARK = (96, 54, 26)
LACE = (240, 240, 240)

BALL_W, BALL_H = 66, 40
PLAYER_W, PLAYER_H = 36, 64
ARC_HEIGHT = 92


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    angle: float          # degrees, 0 = nose pointing right
    phase: str            # "windup" | "flight" | "catch" | "hold"
    direction: int        # +1: left player throws, -1: right player throws
    receiver_lift: float  # 0..1 how high the receiver is jumping
    thrower_lean: float   # -1..1 wind-up lean


def layout(width: int, ground: int) -> tuple[float, float, float]:
    """Left x, right x and ground y of the two players."""
    return width * 0.22, width * 0.78, float(ground)


def pose(t: float, width: int, ground: int = 300) -> Pose:
    left, right, gy = layout(width, ground)
    cycle = int(t // PERIOD)
    local = t - cycle * PERIOD
    direction = 1 if cycle % 2 == 0 else -1
    x0, x1 = (left, right) if direction == 1 else (right, left)
    hand = gy - PLAYER_H * 0.75
    lean = 0.0
    lift = 0.0
    if local < WINDUP:
        phase, x, y, angle = "windup", x0, hand, 20.0 * direction
        lean = math.sin(local / WINDUP * math.pi / 2)
    elif local < WINDUP + FLIGHT:
        phase = "flight"
        u = (local - WINDUP) / FLIGHT
        x = x0 + (x1 - x0) * u
        y = hand - 4 * ARC_HEIGHT * u * (1 - u)                      # a parabola from hand to hand
        dy_du = -4 * ARC_HEIGHT * (1 - 2 * u)
        angle = math.degrees(math.atan2(-dy_du, x1 - x0))            # nose follows the path
        lean = max(0.0, 1 - u * 6)
    elif local < WINDUP + FLIGHT + CATCH:
        phase = "catch"
        v = (local - WINDUP - FLIGHT) / CATCH
        lift = math.sin(v * math.pi)
        x, y, angle = x1, hand - 34 * lift, 70.0 * direction
    else:
        phase, x, y, angle = "hold", x1, hand, 70.0 * direction
    return Pose(x, y, angle, phase, direction, lift, lean)


def ball_trail(t: float, width: int, ground: int = 300) -> list[Pose]:
    """Poses a moment ago, newest first, only while the ball is in flight."""
    out = []
    for k in range(1, TRAIL + 1):
        p = pose(max(0.0, t - k * TRAIL_STEP), width, ground)
        if p.phase != "flight":
            break
        out.append(p)
    return out


# ---------------------------------------------------------------- drawing

def _draw_ball(size: tuple[int, int] = (BALL_W, BALL_H)) -> pygame.Surface:
    w, h = size
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, BALL_DARK, (0, 0, w, h))
    pygame.draw.ellipse(s, BALL_BROWN, (2, 2, w - 4, h - 5))
    pygame.draw.line(s, LACE, (w * 0.28, h * 0.5), (w * 0.72, h * 0.5), 2)       # lace
    for i in range(5):
        x = w * (0.34 + 0.08 * i)
        pygame.draw.line(s, LACE, (x, h * 0.34), (x, h * 0.62), 1)
    pygame.draw.arc(s, LACE, (w * 0.12, 3, w * 0.12, h - 8), math.pi * 0.5, math.pi * 1.5, 2)   # white stripes
    pygame.draw.arc(s, LACE, (w * 0.76, 3, w * 0.12, h - 8), -math.pi * 0.5, math.pi * 0.5, 2)
    return s


def load_ball_frames(folder: Path | None = None) -> list[pygame.Surface]:
    """Your own frames from assets/menu/football_*.png, scaled to the ball size; empty if there are none."""
    folder = folder if folder is not None else assets_dir() / "menu"
    frames = []
    for path in sorted(folder.glob("football_*.png")) if folder.is_dir() else []:
        try:
            img = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            continue                       # a bad image must not break the menu: fall back to the drawn ball
        frames.append(pygame.transform.smoothscale(img, (BALL_W, BALL_H)))
    return frames


class Backdrop:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size
        w, h = size
        self._field = pygame.Surface((w + 2 * STRIPE, h))
        for n in range(w // STRIPE + 3):
            pygame.draw.rect(self._field, GRASS_A if n % 2 == 0 else GRASS_B, (n * STRIPE, 0, STRIPE, h))
        for n in range(0, w // STRIPE + 3, 2):
            pygame.draw.line(self._field, LINE, (n * STRIPE, 0), (n * STRIPE, h), 2)
        self._frames = load_ball_frames()
        self._ball = _draw_ball()
        self._rot: dict[int, pygame.Surface] = {}

    def _rotated(self, angle: float, t: float, spiral: bool = False) -> pygame.Surface:
        """The ball turned to `angle`. In flight it also squashes and stretches as it spirals about its long axis."""
        key = int(round(angle / 6.0)) * 6
        if self._frames:
            base = self._frames[int(t * 14) % len(self._frames)]
        else:
            base = self._ball
        if spiral:
            squash = 0.8 + 0.2 * abs(math.cos(t * 16))
            base = pygame.transform.smoothscale(base, (base.get_width(), max(6, int(base.get_height() * squash))))
        elif not self._frames:
            if key not in self._rot:
                self._rot[key] = pygame.transform.rotate(base, key)
            return self._rot[key]
        return pygame.transform.rotate(base, key)

    def _player(self, surface: pygame.Surface, cx: float, gy: float, color, lift: float, lean: float,
                facing: int) -> None:
        w, h = PLAYER_W, PLAYER_H
        top = gy - h - lift * 34
        body = pygame.Rect(cx - w / 2 + lean * 3 * -facing, top, w, h)
        pygame.draw.ellipse(surface, (20, 72, 36), (cx - w * 0.7, gy - 5, w * 1.4, 10))    # shadow
        pygame.draw.rect(surface, color, body, border_radius=4)
        pygame.draw.rect(surface, OUTLINE, body, 2, border_radius=4)
        pygame.draw.circle(surface, (236, 208, 176), (body.centerx, body.y + 13), 10)         # head
        arm = (body.centerx + facing * 10, body.y + 26)
        reach = (arm[0] + facing * (12 + 8 * lean + 10 * lift), arm[1] - 8 - 16 * lift - 8 * lean)
        pygame.draw.line(surface, OUTLINE, arm, reach, 4)

    def draw(self, surface: pygame.Surface, t: float, with_players: bool) -> None:
        w, h = surface.get_size()
        if (w, h) != self.size:
            self.__init__((w, h))
        surface.blit(self._field, (-STRIPE - (t * SCROLL_PX_PER_S) % (2 * STRIPE), 0))
        if not with_players:
            return
        ground = 300
        left, right, gy = layout(w, ground)
        p = pose(t, w, ground)
        thrower_left = p.direction == 1
        self._player(surface, left, gy, BLUE, p.receiver_lift if not thrower_left else 0.0,
                     p.thrower_lean if thrower_left else 0.0, 1)
        self._player(surface, right, gy, RED, p.receiver_lift if thrower_left else 0.0,
                     0.0 if thrower_left else p.thrower_lean, -1)
        height = max(0.0, gy - PLAYER_H * 0.75 - p.y)
        shadow = pygame.Surface((BALL_W, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, max(30, 90 - int(height * 0.5))), shadow.get_rect())
        surface.blit(shadow, shadow.get_rect(center=(p.x, gy + 2)))
        for k, g in enumerate(ball_trail(t, w, ground)):
            ghost = self._rotated(g.angle, t - (k + 1) * TRAIL_STEP, spiral=True)
            ghost.set_alpha(max(10, 110 - k * 20))
            surface.blit(ghost, ghost.get_rect(center=(g.x, g.y)))
        ball = self._rotated(p.angle, t, spiral=p.phase == "flight")
        surface.blit(ball, ball.get_rect(center=(p.x, p.y)))
