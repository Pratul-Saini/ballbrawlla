"""Draws a match from a view dict (net/view.py), so the host's screen and a
client's screen go through exactly the same code and the same hidden-info rules.

World is larger than the window: a camera follows what you control, and a
minimap across the top shows the whole field.
"""

from __future__ import annotations

import math

import pygame

from ballbrawlla.config import Tuning
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.render.renderer import (
    AIM_LINE,
    AIM_RING,
    BALL,
    BG,
    BOUND,
    PLATFORM,
    TEXT,
    THIN_EDGE,
    THIN_EDGE_HEIGHT,
    THIN_FILL,
    TRAJ,
)
from ballbrawlla.rules.field import Field
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import Level

TEAM_COLORS = {Team.LEFT: (80, 170, 255), Team.RIGHT: (255, 110, 110)}
QB_REGION = (255, 220, 90)
YARD_LINE = (44, 48, 58)
GOAL_LINE = (200, 200, 210)
BANNER = (255, 240, 180)
DIM = (150, 155, 170)
BUTTON = (60, 120, 80)
BUTTON_EDGE = (150, 230, 170)
MINIMAP_H = 40
AIM_RING_RADIUS = 60

PLAY_CALL = "play_call"


def _team_color(team: int, alpha: int | None = None):
    c = TEAM_COLORS[Team(team)]
    return c if alpha is None else (*c, alpha)


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


class Camera:
    def __init__(self, viewport: tuple[int, int]) -> None:
        self.vw, self.vh = viewport
        self.pos = Vector2()
        self._placed = False

    def follow(self, target: Vector2, level: Level, dt: float) -> None:
        desired = Vector2(target.x - self.vw / 2, target.y - self.vh / 2)
        desired.x = min(max(desired.x, 0), max(0, level.width - self.vw))
        desired.y = min(max(desired.y, 0), max(0, level.height - self.vh))
        if not self._placed:
            self.pos, self._placed = desired, True
        else:
            self.pos += (desired - self.pos) * min(1.0, dt * 8)


class MatchRenderer:
    def __init__(self, screen: pygame.Surface, level: Level, field: Field, tuning: Tuning) -> None:
        self.screen = screen
        self.level = level
        self.field = field
        self.t = tuning
        self.camera = Camera(screen.get_size())
        self.font = pygame.font.Font(None, 22)
        self.small = pygame.font.Font(None, 18)
        self.big = pygame.font.Font(None, 44)
        self.debug = False
        self.button_rect: pygame.Rect | None = None

    # ------------------------------------------------------------ input helper

    def button_hit(self, pos: tuple[int, int]) -> bool:
        return self.button_rect is not None and self.button_rect.collidepoint(pos)

    # ------------------------------------------------------------ helpers

    def _w(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.camera.pos.x, y - self.camera.pos.y)

    def _wrect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        sx, sy = self._w(x, y)
        return pygame.Rect(round(sx), round(sy), round(w), round(h))

    def _band(self, x0: float, x1: float, color_rgba) -> None:
        sx0, _ = self._w(x0, 0)
        sx1, _ = self._w(x1, 0)
        w = max(2, int(sx1 - sx0) + self.t.player_width)
        surf = pygame.Surface((w, self.screen.get_height()), pygame.SRCALPHA)
        surf.fill(color_rgba)
        self.screen.blit(surf, (sx0 - self.t.player_width / 2, 0))

    def _text(self, text: str, pos, color=TEXT, font=None, center=False) -> None:
        img = (font or self.font).render(text, True, color)
        x, y = pos
        if center:
            x -= img.get_width() / 2
        self.screen.blit(img, (x, y))

    # ------------------------------------------------------------ main

    def draw(self, view: dict, fps: float, dt: float, status: str = "") -> None:
        self.camera.follow(self._camera_target(view), self.level, dt)
        s = self.screen
        s.fill(BG)
        self._draw_field()
        self._draw_platforms()

        phase = view["phase"]
        if phase == PLAY_CALL:
            self._draw_play_call(view)
        if "actors" in view:
            self._draw_actors(view)
        self._draw_hud(view, fps, status)

    def _camera_target(self, view: dict) -> Vector2:
        h = self.t.player_height
        call = view.get("call")
        if call is not None:
            spot = call["def"] if view["side"] == "defense" and "def" in call else call["qb"]
            return Vector2(spot[0], spot[1] - h / 2)
        for a in view.get("actors", ()):
            if a["team"] == view["team"] and a["role"] != "QB":
                return Vector2(a["x"] + a["w"] / 2, a["y"] + a["h"] / 2)
        return Vector2(self.level.width / 2, self.level.height / 2)

    # ------------------------------------------------------------ world

    def _draw_field(self) -> None:
        f, lv = self.field, self.level
        ez_w = self.t.end_zone_yards * self.field.yard_px
        for team in Team:
            x0 = f.goal_line_x(team) - (ez_w if team is Team.LEFT else 0)
            surf = pygame.Surface((ez_w, lv.height), pygame.SRCALPHA)
            surf.fill(_team_color(team, 28))
            self.screen.blit(surf, self._w(x0, 0))
        step = 10
        for yards in range(0, int(self.t.field_yards) + 1, step):
            x = f.x_at(Team.LEFT, yards)
            color = GOAL_LINE if yards in (0, self.t.field_yards) else YARD_LINE
            sx, _ = self._w(x, 0)
            pygame.draw.line(self.screen, color, (sx, 0), (sx, self.screen.get_height()), 1)
            label = int(min(yards, self.t.field_yards - yards))
            if 0 < yards < self.t.field_yards:  # pinned just under the HUD text
                self._text(str(label), (sx, MINIMAP_H + 52), DIM, self.small, center=True)

    def _draw_platforms(self) -> None:
        for plat in self.level.platforms:
            r = plat.rect
            rect = self._wrect(r.x, r.y, r.w, r.h)
            if plat.kind == "bound":
                pygame.draw.rect(self.screen, BOUND, rect)
            elif plat.is_thin:
                pygame.draw.rect(self.screen, THIN_FILL, rect)
                pygame.draw.rect(self.screen, THIN_EDGE, (rect.x, rect.y, rect.w, min(THIN_EDGE_HEIGHT, rect.h)))
            else:
                pygame.draw.rect(self.screen, PLATFORM, rect)

    def _draw_figure(self, x: float, feet_y: float, team: int, label: str, outline_only=False, me=False):
        w, h = self.t.player_width, self.t.player_height
        rect = self._wrect(x - w / 2, feet_y - h, w, h)
        color = _team_color(team)
        if outline_only:
            pygame.draw.rect(self.screen, color, rect, 2)
        else:
            pygame.draw.rect(self.screen, color, rect)
        if me:
            pygame.draw.rect(self.screen, (255, 255, 255), rect.inflate(4, 4), 1)
        self._text(label, (rect.centerx, rect.y - 16), color, self.small, center=True)

    def _draw_aim(self, center: Vector2, angle: float, power: float) -> None:
        t = self.t
        c = Vector2(self._w(center.x, center.y))
        a = math.radians(angle)
        d = Vector2(math.cos(a), -math.sin(a))
        pygame.draw.circle(self.screen, AIM_RING, c, AIM_RING_RADIUS, 1)
        frac = (power - t.power_min) / max(1e-6, t.power_max - t.power_min)
        pygame.draw.line(self.screen, AIM_LINE, c, c + d * (AIM_RING_RADIUS * (0.3 + 0.7 * frac)), 3)
        vel = d * power
        for i in range(1, 22):
            tt = i * 0.05
            pt = c + vel * tt + Vector2(0, 0.5 * t.ball_gravity * tt * tt)
            pygame.draw.circle(self.screen, TRAJ, pt, 2)

    # ------------------------------------------------------------ phases

    def _draw_play_call(self, view: dict) -> None:
        call = view["call"]
        off = view["offense"]
        dfn = 1 - off
        h = self.t.player_height
        me_off = view["side"] == "offense"

        if call["picks"] and not call["off_locked"]:
            self._band(*call["qb_range"], (*QB_REGION, 30))
        if not me_off and not call["def_locked"]:
            self._band(*call["def_range"], _team_color(dfn, 30))

        qb = call["qb"]
        self._draw_figure(qb[0], qb[1], off, "QB", outline_only=call["placing"] and me_off)
        if "def" in call:
            self._draw_figure(call["def"][0], call["def"][1], dfn, "DEF", outline_only=not call["def_locked"], me=True)
        if "aim" in call and not call["placing"]:
            self._draw_aim(Vector2(qb[0], qb[1] - h / 2), *call["aim"])

    def _draw_actors(self, view: dict) -> None:
        for a in view["actors"]:
            feet_x = a["x"] + a["w"] / 2
            me = a["team"] == view["team"] and a["role"] != "QB"
            self._draw_figure(feet_x, a["y"] + a["h"], a["team"], a["role"], me=me)
            if me:
                pygame.draw.circle(
                    self.screen, (90, 200, 120), self._w(feet_x, a["y"] + a["h"] / 2), self.t.tag_radius, 1
                )
        if "aim" in view:
            qb = view["actors"][0]
            self._draw_aim(Vector2(qb["x"] + qb["w"] / 2, qb["y"] + qb["h"] / 2), *view["aim"])
        b = view["ball"]
        pygame.draw.circle(self.screen, BALL, self._w(b["x"], b["y"]), self.t.ball_radius)

    # ------------------------------------------------------------ HUD

    def _draw_minimap(self, view: dict) -> None:
        vw = self.screen.get_width()
        x0, y0, w, h = 40, 6, vw - 80, MINIMAP_H
        sx, sy = w / self.level.width, h / self.level.height
        pygame.draw.rect(self.screen, (16, 17, 22), (x0, y0, w, h))
        ez_w = self.t.end_zone_yards * self.field.yard_px
        for team in Team:
            gx = self.field.goal_line_x(team) - (ez_w if team is Team.LEFT else 0)
            pygame.draw.rect(self.screen, tuple(c // 3 for c in _team_color(team)),
                             (x0 + gx * sx, y0, ez_w * sx, h))
        for plat in self.level.platforms:
            if plat.kind == "bound":
                continue
            r = plat.rect
            pygame.draw.rect(self.screen, DIM, (x0 + r.x * sx, y0 + r.y * sy, max(1, r.w * sx), max(1, r.h * sy)))

        def dot(x, y, color, rad=3):
            pygame.draw.circle(self.screen, color, (x0 + x * sx, y0 + y * sy), rad)

        call = view.get("call")
        if call is not None:
            dot(call["qb"][0], call["qb"][1] - 20, _team_color(view["offense"]))
            if "def" in call:
                dot(call["def"][0], call["def"][1] - 20, _team_color(1 - view["offense"]))
        for a in view.get("actors", ()):
            dot(a["x"] + a["w"] / 2, a["y"] + a["h"] / 2, _team_color(a["team"]))
        if "ball" in view:
            dot(view["ball"]["x"], view["ball"]["y"], BALL, 2)
        cam = self.camera
        pygame.draw.rect(self.screen, (200, 200, 200),
                         (x0 + cam.pos.x * sx, y0 + cam.pos.y * sy, cam.vw * sx, cam.vh * sy), 1)

    def _draw_hud(self, view: dict, fps: float, status: str) -> None:
        vw, vh = self.screen.get_size()
        self._draw_minimap(view)
        me, off = Team(view["team"]), Team(view["offense"])
        score = view["score"]
        top = MINIMAP_H + 12
        line = (
            f"Blue {score[0]} - {score[1]} Red   |   {_ordinal(view['down'])} down, "
            f"{off.display} on offense   |   You: {me.display} ({view['side']})"
        )
        if view["practice"]:
            line += "   |   practice"
        self._text(line, (40, top))

        hint = self._phase_hint(view)
        if hint:
            self._text(hint, (40, top + 20), DIM)
        if status:
            self._text(status, (40, vh - 26), DIM)

        msg = view.get("message")
        if msg and view["phase"] in ("dead", "game_over"):
            self._text(msg, (vw / 2, vh / 2 - 60), BANNER, self.big, center=True)
            if view["phase"] == "game_over":
                self._text("Host: press R for a new match", (vw / 2, vh / 2 - 20), DIM, center=True)

        self.button_rect = None
        label = self._button_label(view)
        if label:
            rect = pygame.Rect(0, 0, 240, 40)
            rect.midbottom = (vw // 2, vh - 36)
            pygame.draw.rect(self.screen, BUTTON, rect, border_radius=6)
            pygame.draw.rect(self.screen, BUTTON_EDGE, rect, 2, border_radius=6)
            self._text(label, (rect.centerx, rect.y + 12), TEXT, center=True)
            self.button_rect = rect

        if self.debug:
            self._draw_debug(view, fps)

    def _button_label(self, view: dict) -> str | None:
        call = view.get("call")
        if view["phase"] != PLAY_CALL or call is None:
            return None
        if view["side"] == "offense":
            if call["off_locked"]:
                return None
            return "Confirm QB spot" if call["placing"] else "Lock in throw"
        return None if call["def_locked"] else "Lock in Defender"

    def _phase_hint(self, view: dict) -> str:
        phase, timer = view["phase"], view.get("timer")
        if phase == "waiting":
            return "Waiting for the other player to join..."
        if phase == PLAY_CALL:
            call = view["call"]
            mine_locked = call["off_locked"] if view["side"] == "offense" else call["def_locked"]
            locks = (f"offense {'locked' if call['off_locked'] else '...'}, "
                     f"defense {'locked' if call['def_locked'] else '...'}")
            restarted = "  (play call restarted)" if call["restarts"] else ""
            head = f"PLAY CALL {timer:4.1f}s   [{locks}]{restarted}   "
            if mine_locked:
                return head + "Locked in - waiting for the other side"
            if view["side"] == "defense":
                return head + "Drag the Defender (or arrows) inside your zone - Z / button: lock in"
            if call["placing"]:
                return head + "Drag the QB (or arrows) in the yellow zone - Z / button: confirm - X: lock in"
            back = " - click QB / Z: move QB" if call["picks"] else ""
            return head + "Hold mouse and point to aim (farther = more power), or arrows - X / button: lock in" + back
        if phase == "pre_throw":
            return f"THROW IN {timer:4.1f}s - get open (WR) / get in position (DEF)"
        if phase == "live":
            holder = view["ball"]["holder"]
            if holder is None:
                return f"LOOSE BALL - dead in {timer:3.1f}s, Z to pick up" if timer is not None else "Ball in the air - Z to catch"
            if holder == "WR":
                return "WR has the ball: run to the end zone / DEF: Z to tag"
            return "INTERCEPTION: DEF runs the other way / WR: Z to tag"
        return ""

    def _draw_debug(self, view: dict, fps: float) -> None:
        lines = [f"fps {fps:5.1f}  tick {view['tick']}  phase {view['phase']}"]
        for a in view.get("actors", ()):
            if a["team"] == view["team"] and a["role"] != "QB":
                flags = "".join(ch if on else "." for ch, on in zip("GCLR", a["c"]))
                lines.append(f"{a['role']} {a['s']:<10} vel ({a['vx']:7.1f}, {a['vy']:7.1f}) contacts {flags}")
        for i, line in enumerate(lines):
            self._text(line, (40, self.screen.get_height() - 70 + i * 18), DIM)
