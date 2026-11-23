"""Football field markings, drawn behind everything else. Shared by the match
renderer and the sandbox renderer so every field level looks the same.

- End zones tinted in the defending team's color, with the team name painted on the floor
- Goal lines (bright), the 50 (medium), every 10 yards (faint), every 5 yards (short ticks)
- Yard numbers painted just above the floor, and optionally pinned to a fixed
  screen height so they're readable when the floor is off screen
"""

from __future__ import annotations

import pygame

from ballbrawlla.physics.vec import Vector2
from ballbrawlla.rules.field import Field
from ballbrawlla.rules.teams import Team

TEAM_COLORS = {Team.LEFT: (80, 170, 255), Team.RIGHT: (255, 110, 110)}
# Football field: green turf with mowed stripes, white chalk lines, team-colored end zones.
GRASS_DARK = (30, 84, 45)
GRASS_LIGHT = (38, 98, 53)
YARD_LINE = (236, 240, 236)        # white chalk, every 10 yards
MIDFIELD_LINE = (255, 255, 255)    # the 50
GOAL_LINE = (255, 255, 255)
YARD_TICK = (210, 222, 210)        # short 5-yard ticks
LABEL = (236, 240, 236)
FLOOR_PAINT = (228, 234, 228)      # yard numbers / end-zone names painted on the turf
END_ZONE_ALPHA = 120               # team color over the turf in each end zone


class FieldMarkers:
    def __init__(self, field: Field) -> None:
        self.field = field
        self.small = pygame.font.Font(None, 18)
        self.paint = pygame.font.Font(None, 40)
        self._tint_cache: dict[tuple[Team, int], pygame.Surface] = {}
        self._label_cache: dict[tuple[str, bool], pygame.Surface] = {}

    def _tint(self, team: Team, height: int, width: int) -> pygame.Surface:
        key = (team, height, width)
        if key not in self._tint_cache:
            if len(self._tint_cache) > 16:
                self._tint_cache.clear()          # zooming makes many widths; keep it small
            surf = pygame.Surface((max(1, width), height), pygame.SRCALPHA)
            surf.fill((*TEAM_COLORS[team], END_ZONE_ALPHA))
            self._tint_cache[key] = surf
        return self._tint_cache[key]

    def _label(self, text: str, painted: bool) -> pygame.Surface:
        key = (text, painted)
        if key not in self._label_cache:
            font, color = (self.paint, FLOOR_PAINT) if painted else (self.small, LABEL)
            self._label_cache[key] = font.render(text, True, color)
        return self._label_cache[key]

    def draw(self, screen: pygame.Surface, camera: Vector2, pinned_label_y: float | None = None,
             zoom: float = 1.0) -> None:
        """`camera` is the world position of the screen's top-left; `zoom` the scale."""
        f = self.field
        t = f.t
        sw, sh = screen.get_size()
        cx, cy = camera.x, camera.y
        floor_sy = (f.floor_y - cy) * zoom
        ez_w = f.end_zone_px * zoom

        # Mowed turf: alternating light/dark bands every 10 yards, across the whole
        # field including both end zones.
        ez_yards = int(round(t.end_zone_yards))
        for yards in range(-ez_yards, int(t.field_yards) + ez_yards, 10):
            x0 = (f.x_at(Team.LEFT, yards) - cx) * zoom
            x1 = (f.x_at(Team.LEFT, yards + 10) - cx) * zoom
            if x1 < 0 or x0 > sw:
                continue
            band = GRASS_LIGHT if (yards // 10) % 2 == 0 else GRASS_DARK
            pygame.draw.rect(screen, band, (x0, 0, x1 - x0 + 1, sh))

        # End zones
        for team in Team:
            x0 = f.goal_line_x(team) - (f.end_zone_px if team is Team.LEFT else 0)
            sx = (x0 - cx) * zoom
            if sx + ez_w < 0 or sx > sw:
                continue
            screen.blit(self._tint(team, sh, round(ez_w)), (sx, 0))
            name = self._label(team.display.upper(), painted=True)
            screen.blit(name, (sx + (ez_w - name.get_width()) / 2, floor_sy - 70))

        # Lines every 5 yards
        for yards in range(0, int(t.field_yards) + 1, 5):
            sx = (f.x_at(Team.LEFT, yards) - cx) * zoom
            if sx < -60 or sx > sw + 60:
                continue
            if yards in (0, t.field_yards):
                pygame.draw.line(screen, GOAL_LINE, (sx, 0), (sx, sh), 2)
            elif yards * 2 == t.field_yards:
                pygame.draw.line(screen, MIDFIELD_LINE, (sx, 0), (sx, sh), 2)
            elif yards % 10 == 0:
                pygame.draw.line(screen, YARD_LINE, (sx, 0), (sx, sh), 1)
            else:  # 5-yard tick at the floor
                pygame.draw.line(screen, YARD_TICK, (sx, floor_sy - 14), (sx, floor_sy), 1)

            if yards % 10 == 0 and 0 < yards < t.field_yards:
                text = str(int(min(yards, t.field_yards - yards)))
                img = self._label(text, painted=True)
                screen.blit(img, (sx - img.get_width() / 2, floor_sy - 34))
                if pinned_label_y is not None:
                    img = self._label(text, painted=False)
                    screen.blit(img, (sx - img.get_width() / 2, pinned_label_y))
