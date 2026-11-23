"""Draws a match from a view dict (net/view.py), so the host's screen and a
client's screen go through exactly the same code and the same hidden-info rules.

World is larger than the window: a camera follows what you control, and a
minimap across the top shows the whole field. In local play (two players on one
screen, view["local"]) the camera zooms out to keep both players in frame and
both sides' choices are shown.
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
from ballbrawlla.render.field_markers import TEAM_COLORS, FieldMarkers
from ballbrawlla.rules.field import Field
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import Level

QB_REGION = (255, 220, 90)
SPOT_OK = (120, 230, 140)      # play call: where the player would be placed
SPOT_BAD = (240, 90, 90)       # play call: not on a platform in the zone
BANNER = (255, 240, 180)
DIM = (150, 155, 170)
BUTTON = (60, 120, 80)
BUTTON_EDGE = (150, 230, 170)
BUTTON_OFF = (60, 62, 70)          # nothing to confirm yet (not on a platform)
BUTTON_OFF_EDGE = (110, 114, 126)
MINIMAP_H = 40
HUD_H = MINIMAP_H + 54  # dark band behind the minimap and the two HUD text lines
AIM_RING_RADIUS = 60

PLAY_CALL = "play_call"


def _team_color(team: int, alpha: int | None = None):
    c = TEAM_COLORS[Team(team)]
    return c if alpha is None else (*c, alpha)


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


MIN_ZOOM = 0.4          # local play: how far the shared camera may zoom out
FRAME_MARGIN = (260, 200)  # world px kept around the players when framing them


class Camera:
    """`pos` is the world position of the screen's top-left corner; `zoom` is the
    scale (1 = one world px per screen px, 0.5 = twice as much world on screen)."""

    def __init__(self, viewport: tuple[int, int]) -> None:
        self.vw, self.vh = viewport
        self.pos = Vector2()
        self.zoom = 1.0
        self._placed = False

    @property
    def world_size(self) -> tuple[float, float]:
        return self.vw / self.zoom, self.vh / self.zoom

    def _place(self, center: Vector2, level: Level, dt: float, zoom: float) -> None:
        if not self._placed:
            self.zoom = zoom
        else:
            self.zoom += (zoom - self.zoom) * min(1.0, dt * 4)
        ww, wh = self.world_size

        def clamp(c: float, view: float, size: float) -> float:
            if size <= view:
                return (size - view) / 2          # level smaller than the view: center it
            return min(max(c - view / 2, 0), size - view)

        desired = Vector2(clamp(center.x, ww, level.width), clamp(center.y, wh, level.height))
        if not self._placed:
            self.pos, self._placed = desired, True
        else:
            self.pos += (desired - self.pos) * min(1.0, dt * 8)

    def follow(self, target: Vector2, level: Level, dt: float) -> None:
        """Keep `target` centred at normal scale."""
        self._place(target, level, dt, 1.0)

    def frame(self, points: list[Vector2], level: Level, dt: float, top_inset: float = 0) -> None:
        """Keep every point on screen, zooming out (down to MIN_ZOOM) if needed.
        `top_inset` is screen px covered by the HUD at the top."""
        mx, my = FRAME_MARGIN
        xs, ys = [p.x for p in points], [p.y for p in points]
        bw = max(xs) - min(xs) + 2 * mx
        bh = max(ys) - min(ys) + 2 * my
        zoom = max(MIN_ZOOM, min(1.0, self.vw / bw, (self.vh - top_inset) / bh))
        center = Vector2((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2 - top_inset / (2 * zoom))
        self._place(center, level, dt, zoom)


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
        self._invite_font: pygame.font.Font | None = None
        self.debug = False
        self.button_rect: pygame.Rect | None = None
        self.markers = FieldMarkers(field)
        self._hud_band: pygame.Surface | None = None
        self.hud_h = HUD_H
        # Names shown in hints for the "grab" (Z) and "lock in" (X) actions.
        self.key_names = {"grab": "Z / Square", "lock": "X / Circle", "restart": "R"}
        self.show_controls = True   # F3: key instructions in the hints and the bottom line

    # ------------------------------------------------------------ input helper

    def button_hit(self, pos: tuple[int, int]) -> bool:
        return self.button_rect is not None and self.button_rect.collidepoint(pos)

    # ------------------------------------------------------------ helpers

    def _w(self, x: float, y: float) -> tuple[float, float]:
        z = self.camera.zoom
        return ((x - self.camera.pos.x) * z, (y - self.camera.pos.y) * z)

    def _wrect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        sx, sy = self._w(x, y)
        z = self.camera.zoom
        return pygame.Rect(round(sx), round(sy), max(1, round(w * z)), max(1, round(h * z)))

    def _band(self, x0: float, x1: float, color_rgba) -> None:
        z = self.camera.zoom
        sx0, _ = self._w(x0, 0)
        sx1, _ = self._w(x1, 0)
        w = max(2, int(sx1 - sx0 + self.t.player_width * z))
        surf = pygame.Surface((w, self.screen.get_height()), pygame.SRCALPHA)
        surf.fill(color_rgba)
        self.screen.blit(surf, (sx0 - self.t.player_width * z / 2, 0))

    def _text(self, text: str, pos, color=TEXT, font=None, center=False) -> None:
        img = (font or self.font).render(text, True, color)
        x, y = pos
        if center:
            x -= img.get_width() / 2
        self.screen.blit(img, (x, y))

    # ------------------------------------------------------------ main

    def draw(self, view: dict, fps: float, dt: float, status: str = "", controls: str = "",
             invite: dict | None = None) -> None:
        """`status` (e.g. network state) is always shown; `controls` (the key list)
        only while show_controls is on. `invite`: the host's invite panel, shown while waiting for the other
        player: {"code": "KQ7M-3XPA" or None while it's being worked out, "lines": [(label, text, state)],
        "copied": bool, "test": bool (offer N: open a test window)}."""
        if view.get("local"):
            self.camera.frame(self._focus_points(view), self.level, dt, top_inset=self.hud_h)
        else:
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
        self._draw_hud(view, fps, status, controls)
        if invite and phase == "waiting":
            self._draw_invite(invite)

    def _wrapped(self, text: str, width: int) -> list[str]:
        lines, line = [], ""
        for word in text.split():
            if line and self.font.size(f"{line} {word}")[0] > width:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        return lines + [line] if line else lines

    def _draw_invite(self, invite: dict) -> None:
        """The host's waiting panel: the code to share, and who can join (same Wi-Fi / internet)."""
        colors = {"ready": SPOT_OK, "checking": BANNER, "unavailable": (255, 170, 160)}
        vw, vh = self.screen.get_size()
        w = min(760, vw - 40)
        label_w = 120
        body = []
        for label, text, state in invite["lines"]:
            wrapped = self._wrapped(text, w - 60 - label_w)
            body.append((label, wrapped, colors.get(state, DIM)))
        line_h = self.font.get_linesize()
        h = 150 + sum(len(b[1]) for b in body) * line_h + len(body) * 6 + (30 if invite.get("test") else 0)
        box = pygame.Rect(0, 0, w, h)
        box.center = (vw // 2, vh // 2)
        pygame.draw.rect(self.screen, (16, 17, 22), box, border_radius=10)
        pygame.draw.rect(self.screen, BANNER, box, 2, border_radius=10)
        self._text("Waiting for the other player. Send them this invite code:", (box.centerx, box.y + 14), DIM,
                   center=True)
        if self._invite_font is None:
            self._invite_font = pygame.font.Font(None, 84)
        code = invite.get("code")
        if code:
            self._text(code, (box.centerx, box.y + 40), BANNER, self._invite_font, center=True)
            hint = "copied!" if invite.get("copied") else "Ctrl+C copies it. They pick JOIN GAME and type it."
        else:
            self._text("getting your code...", (box.centerx, box.y + 56), DIM, center=True)
            hint = ""
        self._text(hint, (box.centerx, box.y + 104), DIM, center=True)
        y = box.y + 136
        for label, wrapped, color in body:
            self._text(f"{label}:", (box.x + 30, y), DIM)
            for k, line in enumerate(wrapped):
                self._text(line, (box.x + 30 + label_w, y + k * line_h), color)
            y += len(wrapped) * line_h + 6
        if invite.get("test"):
            self._text("No second player handy? N opens a second window on this computer that joins.",
                       (box.centerx, box.bottom - 28), DIM, center=True)

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

    def _focus_points(self, view: dict) -> list[Vector2]:
        """Local play: what both players need to see (their spawn picks during the
        play call; both runners - and a ball in flight - during the play)."""
        h = self.t.player_height
        pts: list[Vector2] = []
        call = view.get("call")
        if call is not None:
            pts.append(Vector2(call["qb"][0], call["qb"][1] - h / 2))
            if "def" in call:
                pts.append(Vector2(call["def"][0], call["def"][1] - h / 2))
        for a in view.get("actors", ()):
            if a["role"] != "QB":
                pts.append(Vector2(a["x"] + a["w"] / 2, a["y"] + a["h"] / 2))
        ball = view.get("ball")
        if ball is not None and view["phase"] == "live" and ball["holder"] is None:
            pts.append(Vector2(ball["x"], ball["y"]))
        return pts or [Vector2(self.level.width / 2, self.level.height / 2)]

    def _is_mine(self, view: dict, team: int, role: str) -> bool:
        """Highlight the runner(s) the people at this screen control."""
        return role != "QB" and (view.get("local") or team == view["team"])

    # ------------------------------------------------------------ world

    def _draw_field(self) -> None:
        self.markers.draw(self.screen, self.camera.pos, pinned_label_y=self.hud_h + 4, zoom=self.camera.zoom)

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

    def _draw_figure(self, x: float, feet_y: float, team: int, label: str, outline_only=False, me=False,
                     h: float | None = None):
        w, h = self.t.player_width, (h or self.t.player_height)
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
        ring = max(24, AIM_RING_RADIUS * self.camera.zoom)
        pygame.draw.circle(self.screen, AIM_RING, c, ring, 1)
        frac = (power - t.power_min) / max(1e-6, t.power_max - t.power_min)
        pygame.draw.line(self.screen, AIM_LINE, c, c + d * (ring * (0.3 + 0.7 * frac)), 3)
        vel = d * power
        for i in range(1, 22):
            tt = i * 0.05
            pt = center + vel * tt + Vector2(0, 0.5 * t.ball_gravity * tt * tt)   # world
            pygame.draw.circle(self.screen, TRAJ, self._w(pt.x, pt.y), 2)

    # ------------------------------------------------------------ phases

    def _draw_play_call(self, view: dict) -> None:
        call = view["call"]
        off = view["offense"]
        dfn = 1 - off
        h = self.t.player_height
        local = bool(view.get("local"))
        me_off = local or view["side"] == "offense"
        me_def = local or view["side"] == "defense"

        if call["picks"] and not call["off_locked"]:
            self._band(*call["qb_range"], (*QB_REGION, 30))
        if me_def and not call["def_locked"]:
            self._band(*call["def_range"], _team_color(dfn, 30))

        qb = call["qb"]
        placing = call["placing"] and not call["off_locked"]
        self._draw_figure(qb[0], qb[1], off, "QB", me=placing and me_off, h=call.get("qb_h"))
        if placing:
            self._draw_spot_marker(call["qb_ok"], qb, call.get("qb_h"))
        if "def" in call:
            self._draw_figure(call["def"][0], call["def"][1], dfn, "DEF", outline_only=call["def_locked"], me=True,
                              h=call.get("def_h"))
            if not call["def_locked"]:
                self._draw_spot_marker(call["def_ok"], call["def"], call.get("def_h"))
        if "aim" in call and not call["placing"]:
            self._draw_aim(Vector2(qb[0], qb[1] - (call.get("qb_h") or h) / 2), *call["aim"])

    def _draw_spot_marker(self, ok: bool, feet, h: float | None) -> None:
        """Green bar under the player if it's standing somewhere it can lock in;
        otherwise a red box (jumping, clinging, or outside its zone)."""
        w, h = self.t.player_width, (h or self.t.player_height)
        if ok:
            bar = self._wrect(feet[0] - w, feet[1] - 2, 2 * w, 4)
            pygame.draw.rect(self.screen, SPOT_OK, bar)
        else:
            box = self._wrect(feet[0] - w / 2, feet[1] - h, w, h)
            pygame.draw.rect(self.screen, SPOT_BAD, box.inflate(6, 6), 2)
            self._text("not on a platform in your zone", (box.centerx, box.bottom + 4), SPOT_BAD, self.small,
                       center=True)

    def _draw_actors(self, view: dict) -> None:
        z = self.camera.zoom
        for a in view["actors"]:
            feet_x = a["x"] + a["w"] / 2
            me = self._is_mine(view, a["team"], a["role"])
            self._draw_figure(feet_x, a["y"] + a["h"], a["team"], a["role"], me=me)
            if me:
                pygame.draw.circle(
                    self.screen, (90, 200, 120), self._w(feet_x, a["y"] + a["h"] / 2),
                    max(4, self.t.tag_radius * z), 1,
                )
        if "aim" in view:
            qb = view["actors"][0]
            self._draw_aim(Vector2(qb["x"] + qb["w"] / 2, qb["y"] + qb["h"] / 2), *view["aim"])
        b = view["ball"]
        pygame.draw.circle(self.screen, BALL, self._w(b["x"], b["y"]), max(3, self.t.ball_radius * z))

    # ------------------------------------------------------------ HUD

    def _draw_minimap(self, view: dict) -> None:
        vw = self.screen.get_width()
        x0, y0, w, h = 40, 6, vw - 80, MINIMAP_H
        sx, sy = w / self.level.width, h / self.level.height
        pygame.draw.rect(self.screen, (16, 17, 22), (x0, y0, w, h))
        ez_w = self.field.end_zone_px
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
        ww, wh = cam.world_size
        pygame.draw.rect(self.screen, (200, 200, 200),
                         (x0 + cam.pos.x * sx, y0 + cam.pos.y * sy, ww * sx, wh * sy), 1)

    def _draw_hud(self, view: dict, fps: float, status: str, controls: str = "") -> None:
        vw, vh = self.screen.get_size()
        local = bool(view.get("local"))
        me, off = Team(view["team"]), Team(view["offense"])
        if local and view["phase"] == PLAY_CALL and self.show_controls:
            hints = [f"{off.display} (offense): " + self._phase_hint(view, "offense"),
                     f"{off.other.display} (defense): " + self._phase_hint(view, "defense", head=False)]
        else:
            hints = [h for h in [self._phase_hint(view)] if h]
        self.hud_h = MINIMAP_H + 34 + 20 * max(1, len(hints))
        if self._hud_band is None or self._hud_band.get_size() != (vw, self.hud_h):
            self._hud_band = pygame.Surface((vw, self.hud_h), pygame.SRCALPHA)
            self._hud_band.fill((16, 17, 22, 200))
        self.screen.blit(self._hud_band, (0, 0))
        self._draw_minimap(view)
        score = view["score"]
        top = MINIMAP_H + 12
        line = f"Blue {score[0]} - {score[1]} Red   |   {_ordinal(view['down'])} down, {off.display} on offense"
        if local:
            line += "   |   local 2-player"
        else:
            line += f"   |   You: {me.display} ({view['side']})"
        if view["practice"]:
            line += "   |   practice" if view.get("defender", True) else "   |   catch practice"
        self._text(line, (40, top))

        for i, hint in enumerate(hints):
            self._text(hint, (40, top + 20 + 20 * i), DIM)
        bottom = [status] + ([controls] if self.show_controls else ["F3: show controls"])
        bottom = "   |   ".join(b for b in bottom if b)
        if bottom:
            self._text(bottom, (40, vh - 26), DIM)

        msg = view.get("message")
        if msg and view["phase"] in ("dead", "game_over"):
            self._text(msg, (vw / 2, vh / 2 - 60), BANNER, self.big, center=True)
            if view["phase"] == "game_over":
                who = "Press" if local else "Host: press"
                self._text(f"{who} {self.key_names['restart']} for a new match", (vw / 2, vh / 2 - 20), DIM,
                           center=True)

        self.button_rect = None
        label = self._button_label(view)
        if label:
            enabled = not label.startswith("Move ")
            rect = pygame.Rect(0, 0, 240, 40)
            rect.topright = (vw - 24, self.hud_h + 12)   # top-right under the HUD, clear of the players
            pygame.draw.rect(self.screen, BUTTON if enabled else BUTTON_OFF, rect, border_radius=6)
            pygame.draw.rect(self.screen, BUTTON_EDGE if enabled else BUTTON_OFF_EDGE, rect, 2, border_radius=6)
            self._text(label, (rect.centerx, rect.y + 12), TEXT if enabled else DIM, center=True)
            self.button_rect = rect

        if self.debug:
            self._draw_debug(view, fps)

    def _button_label(self, view: dict) -> str | None:
        call = view.get("call")
        if view["phase"] != PLAY_CALL or call is None:
            return None
        if view.get("local") or view["side"] == "offense":   # local: the mouse belongs to the offense
            if call["off_locked"]:
                return None
            if call["placing"]:
                return "Confirm QB spot" if call["qb_ok"] else "Move QB onto a platform"
            return "Lock in throw"
        if call["def_locked"]:
            return None
        return "Lock in Defender" if call.get("def_ok", True) else "Move onto a platform"

    def _phase_hint(self, view: dict, side: str | None = None, head: bool = True) -> str:
        """The phase line. With show_controls off, only the game state (timers,
        locks, who has the ball) - no key instructions."""
        phase, timer = view["phase"], view.get("timer")
        side = side or view["side"]
        grab, lock = self.key_names["grab"], self.key_names["lock"]
        if phase == "waiting":
            return "Waiting for the other player to join..."
        if not self.show_controls:
            return self._state_hint(view)
        if phase == PLAY_CALL:
            call = view["call"]
            mine_locked = call["off_locked"] if side == "offense" else call["def_locked"]
            prefix = self._state_hint(view) + "   " if head else ""
            if mine_locked:
                return prefix + "Locked in - waiting for the other side"
            if side == "defense":
                return prefix + f"Run the Defender to a platform in your zone - {grab} / button: lock in"
            if call["placing"]:
                return prefix + f"Run the QB to a platform in the yellow zone - {grab} / button: confirm - {lock}: lock in"
            back = f" - {grab} / click QB: move it" if call["picks"] else ""
            return prefix + f"Aim (mouse, right stick or keys) - {lock} / button: lock in" + back
        if phase == "pre_throw":
            if not view.get("defender", True):
                return f"THROW IN {timer:4.1f}s - get open"
            return f"THROW IN {timer:4.1f}s - get open (WR) / get in position (DEF)"
        if phase == "live":
            holder = view["ball"]["holder"]
            if holder is None:
                return (f"LOOSE BALL - dead in {timer:3.1f}s, {grab} to pick up" if timer is not None
                        else f"Ball in the air - {grab} to catch")
            if holder == "WR":
                if not view.get("defender", True):
                    return "You have the ball: run to the end zone"
                return f"WR has the ball: run to the end zone / DEF: {grab} to tag"
            return f"INTERCEPTION: DEF runs the other way / WR: {grab} to tag"
        return ""

    def _state_hint(self, view: dict) -> str:
        phase, timer = view["phase"], view.get("timer")
        if phase == PLAY_CALL:
            call = view["call"]
            locks = f"offense {'locked' if call['off_locked'] else '...'}"
            if view.get("defender", True):
                locks += f", defense {'locked' if call['def_locked'] else '...'}"
            restarted = "  (play call restarted)" if call["restarts"] else ""
            return f"PLAY CALL {timer:4.1f}s   [{locks}]{restarted}"
        if phase == "pre_throw":
            return f"THROW IN {timer:4.1f}s"
        if phase == "live":
            holder = view["ball"]["holder"]
            if holder is None:
                return f"LOOSE BALL - dead in {timer:3.1f}s" if timer is not None else "Ball in the air"
            return "WR has the ball" if holder == "WR" else "INTERCEPTION: DEF has the ball"
        return ""

    def _draw_debug(self, view: dict, fps: float) -> None:
        lines = [f"fps {fps:5.1f}  tick {view['tick']}  phase {view['phase']}"]
        for a in view.get("actors", ()):
            if self._is_mine(view, a["team"], a["role"]):
                flags = "".join(ch if on else "." for ch, on in zip("GCLR", a["c"]))
                lines.append(f"{a['role']} {a['s']:<10} vel ({a['vx']:7.1f}, {a['vy']:7.1f}) contacts {flags}")
        for i, line in enumerate(lines):
            self._text(line, (40, self.screen.get_height() - 70 + i * 18), DIM)
