import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.render.renderer import BG, BOUND, PLATFORM, THIN_EDGE, THIN_FILL, Renderer
from ballbrawlla.world.level import THIN, Level, Platform

THICK = (400, 300, 200, 20)  # thin, 20 px tall
FLAT = (700, 300, 100, 2)  # thin, 2 px tall
SOLID = (400, 450, 200, 40)


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def surface():
    level = Level(
        width=1280,
        height=720,
        platforms=[
            Platform(AABB(*THICK), platform_type=THIN),
            Platform(AABB(*FLAT), platform_type=THIN),
            Platform(AABB(*SOLID)),
        ],
        player_spawns=[Vector2(200, 650)],
        ball_spawn=Vector2(1000, 650),
    )
    game = Game(level, Tuning(), num_players=1)
    surf = pygame.Surface((1280, 720))
    renderer = Renderer(surf)
    renderer.debug = False
    renderer.draw(game, 60.0)
    return surf


def px(surf, x, y):
    return tuple(surf.get_at((x, y)))[:3]


def test_thin_interior_is_fill(surface):
    x, y, w, h = THICK
    assert px(surface, x + w // 2, y + 10) == THIN_FILL
    assert px(surface, x + w // 2, y + h - 1) == THIN_FILL


def test_thin_top_three_rows_are_edge(surface):
    x, y, w, _ = THICK
    for row in range(3):
        assert px(surface, x + 5, y + row) == THIN_EDGE
        assert px(surface, x + w - 1, y + row) == THIN_EDGE
    assert px(surface, x + 5, y + 3) == THIN_FILL


def test_two_px_thin_platform_is_all_edge(surface):
    x, y, w, h = FLAT
    for row in range(h):
        assert px(surface, x + w // 2, y + row) == THIN_EDGE
    assert px(surface, x + w // 2, y + h) == BG


def test_solid_interior_and_no_strip(surface):
    x, y, w, h = SOLID
    assert px(surface, x + w // 2, y + h // 2) == PLATFORM
    for row in range(3):
        assert px(surface, x + w // 2, y + row) == PLATFORM


def test_boundary_color(surface):
    assert px(surface, 640, 719) == BOUND  # floor
    assert px(surface, 640, 0) == BOUND  # ceiling


def test_thin_colors_are_distinct():
    others = {PLATFORM, BOUND, BG}
    assert THIN_FILL != THIN_EDGE
    assert THIN_FILL not in others
    assert THIN_EDGE not in others
