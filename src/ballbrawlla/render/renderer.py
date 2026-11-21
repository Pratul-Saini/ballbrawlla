"""Draws the game state with primitive shapes. Reads state, never mutates it."""

import pygame

from ballbrawlla.game import Game
from ballbrawlla.physics.vec import Vector2

BG = (24, 26, 32)
BOUND = (70, 74, 86)
PLATFORM = (120, 128, 148)
BALL = (235, 140, 50)
AIM_RING = (80, 90, 110)
AIM_LINE = (255, 230, 120)
TRAJ = (255, 230, 120)
TEXT = (220, 220, 220)
REACH = (90, 200, 120)

STATE_COLORS = {
    "grounded": (80, 170, 255),
    "airborne": (120, 200, 255),
    "wall_cling": (200, 120, 255),
    "crouch": (60, 130, 210),
    "slide": (60, 220, 200),
    "aiming": (255, 200, 80),
}

AIM_RING_RADIUS = 60


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = pygame.font.Font(None, 22)
        self.debug = True

    def draw(self, game: Game, fps: float) -> None:
        s = self.screen
        s.fill(BG)

        for plat in game.level.platforms:
            color = BOUND if plat.kind == "bound" else PLATFORM
            r = plat.rect
            pygame.draw.rect(s, color, pygame.Rect(r.x, r.y, r.w, r.h))

        p = game.player
        b = game.ball

        if p.state.name == "aiming":
            self._draw_aim(game)

        box = p.box
        pygame.draw.rect(
            s, STATE_COLORS.get(p.state.name, (200, 200, 200)),
            pygame.Rect(round(box.x), round(box.y), round(box.w), round(box.h)),
        )
        # Facing marker (eye).
        eye = Vector2(box.center.x + p.facing * box.w * 0.25, box.y + 10)
        pygame.draw.circle(s, BG, eye, 3)

        if p.ball_in_reach():
            pygame.draw.circle(s, REACH, p.center, p.t.pickup_radius, 1)

        pygame.draw.circle(s, BALL, b.pos, b.radius)

        if self.debug:
            self._draw_debug(game, fps)

    def _draw_aim(self, game: Game) -> None:
        p, t = game.player, game.t
        c = p.center
        d = p.aim_direction()
        pygame.draw.circle(self.screen, AIM_RING, c, AIM_RING_RADIUS, 1)
        frac = (p.aim_power - t.power_min) / max(1e-6, t.power_max - t.power_min)
        tip = c + d * (AIM_RING_RADIUS * (0.3 + 0.7 * frac))
        pygame.draw.line(self.screen, AIM_LINE, c, tip, 3)

        # Predicted arc (ignores collisions) to help tune throw feel.
        vel = d * p.aim_power
        for i in range(1, 16):
            tt = i * 0.05
            pt = c + vel * tt + Vector2(0, 0.5 * t.ball_gravity * tt * tt)
            pygame.draw.circle(self.screen, TRAJ, pt, 2)

    def _draw_debug(self, game: Game, fps: float) -> None:
        p, b = game.player, game.ball
        c = p.contacts
        flags = "".join(
            ch if on else "."
            for ch, on in (("G", c.on_ground), ("C", c.on_ceiling), ("L", c.wall_left), ("R", c.wall_right))
        )
        lines = [
            f"{game.level.name}   fps {fps:5.1f}",
            f"state {p.state.name:<10} contacts {flags}  jumps {p.jumps_left}",
            f"player vel ({p.vel.x:7.1f}, {p.vel.y:7.1f})",
            f"ball   vel ({b.vel.x:7.1f}, {b.vel.y:7.1f})  {'held' if b.held_by else 'rest' if b.resting else 'free'}",
        ]
        if p.state.name == "aiming":
            lines.append(f"aim {p.aim_angle:5.1f} deg   power {p.aim_power:6.1f}")
        lines.append("arrows move/jump/down  Z grab/aim/cancel  X throw  R reset  F1 debug  Esc quit")
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (40, 40 + i * 18))
