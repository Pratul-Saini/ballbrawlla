"""Draws the game state with primitive shapes. Reads state, never mutates it."""

import pygame

from ballbrawlla.entities.player import Player
from ballbrawlla.game import Game
from ballbrawlla.physics.vec import Vector2

BG = (24, 26, 32)
BOUND = (70, 74, 86)
PLATFORM = (120, 128, 148)
THIN_FILL = (84, 140, 160)
THIN_EDGE = (190, 235, 245)
THIN_EDGE_HEIGHT = 3
BALL = (235, 140, 50)
AIM_RING = (80, 90, 110)
AIM_LINE = (255, 230, 120)
TRAJ = (255, 230, 120)
TEXT = (220, 220, 220)
STATUS = (150, 220, 160)
REACH = (90, 200, 120)

PLAYER_COLORS = [(80, 170, 255), (255, 110, 110), (110, 220, 120), (240, 210, 90)]

AIM_RING_RADIUS = 60


def _dim(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(c // 3 for c in color)


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = pygame.font.Font(None, 22)
        self.small = pygame.font.Font(None, 18)
        self.debug = True

    def draw(self, game: Game, fps: float, local_id: int = 0, status: str = "") -> None:
        s = self.screen
        s.fill(BG)

        for plat in game.level.platforms:
            r = plat.rect
            if plat.kind == "bound":
                pygame.draw.rect(s, BOUND, pygame.Rect(r.x, r.y, r.w, r.h))
            elif plat.is_thin:
                pygame.draw.rect(s, THIN_FILL, pygame.Rect(r.x, r.y, r.w, r.h))
                pygame.draw.rect(
                    s, THIN_EDGE, pygame.Rect(r.x, r.y, r.w, min(THIN_EDGE_HEIGHT, r.h))
                )
            else:
                pygame.draw.rect(s, PLATFORM, pygame.Rect(r.x, r.y, r.w, r.h))

        for p in game.players:
            if p.connected and p.state.name == "aiming":
                self._draw_aim(game, p)
        for p in game.players:
            self._draw_player(game, p, is_local=p.pid == local_id)

        b = game.ball
        pygame.draw.circle(s, BALL, b.pos, b.radius)

        if self.debug:
            self._draw_debug(game, fps, game.players[local_id], status)
        elif status:
            s.blit(self.font.render(status, True, STATUS), (40, 40))

    def _draw_player(self, game: Game, p: Player, is_local: bool) -> None:
        s = self.screen
        color = PLAYER_COLORS[p.pid % len(PLAYER_COLORS)]
        box = p.box
        rect = pygame.Rect(round(box.x), round(box.y), round(box.w), round(box.h))
        if not p.connected:
            pygame.draw.rect(s, _dim(color), rect, 1)
            return
        pygame.draw.rect(s, color, rect)
        eye = Vector2(box.center.x + p.facing * box.w * 0.25, box.y + 10)
        pygame.draw.circle(s, BG, eye, 3)

        label = f"P{p.pid + 1}" + (f" {p.state.name}" if self.debug else "")
        img = self.small.render(label, True, color)
        s.blit(img, (box.center.x - img.get_width() / 2, box.y - 16))

        if is_local and p.ball_in_reach():
            pygame.draw.circle(s, REACH, p.center, p.t.pickup_radius, 1)

    def _draw_aim(self, game: Game, p: Player) -> None:
        t = game.t
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

    def _draw_debug(self, game: Game, fps: float, p: Player, status: str) -> None:
        b = game.ball
        c = p.contacts
        flags = "".join(
            ch if on else "."
            for ch, on in (("G", c.on_ground), ("C", c.on_ceiling), ("L", c.wall_left), ("R", c.wall_right))
        )
        holder = f"held by P{b.held_by.pid + 1}" if b.held_by else "rest" if b.resting else "free"
        lines = [
            f"{game.level.name}   fps {fps:5.1f}   you are P{p.pid + 1}",
            f"state {p.state.name:<10} contacts {flags}  jumps {p.jumps_left}",
            f"player vel ({p.vel.x:7.1f}, {p.vel.y:7.1f})",
            f"ball   vel ({b.vel.x:7.1f}, {b.vel.y:7.1f})  {holder}",
        ]
        if p.state.name == "aiming":
            lines.append(f"aim {p.aim_angle:5.1f} deg   power {p.aim_power:6.1f}")
        lines.append("arrows move/jump/down  Z grab/aim/cancel  X throw  R reset  F1 debug  Esc quit")
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (40, 40 + i * 18))
        if status:
            self.screen.blit(self.font.render(status, True, STATUS), (40, 40 + len(lines) * 18))
