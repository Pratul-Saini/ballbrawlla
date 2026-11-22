import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.main import LEVELS
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.render.match_renderer import Camera
from ballbrawlla.render.renderer import BG, PLATFORM, Renderer
from ballbrawlla.world.level import Level, Platform, load_level


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    yield
    pygame.quit()


def _draw(camera):
    level = Level(width=2000, height=720, platforms=[Platform(AABB(1500, 300, 100, 40))],
                  player_spawns=[Vector2(200, 650)], ball_spawn=Vector2(1000, 650))
    surf = pygame.Surface((1280, 720))
    r = Renderer(surf)
    r.debug = False
    r.draw(Game(level, Tuning(), 1), 60.0, camera=camera)
    return surf


def test_camera_offset_moves_the_world_on_screen():
    surf = _draw(Vector2(1000, 0))
    assert tuple(surf.get_at((550, 320)))[:3] == PLATFORM  # world x 1550 -> screen x 550
    surf = _draw(None)  # default: no offset, platform is off screen
    assert tuple(surf.get_at((550, 320)))[:3] == BG


def test_camera_follows_player_and_stays_inside_the_big_field():
    level = load_level(LEVELS / "field_01.json")
    cam = Camera((1280, 720))
    cam.follow(Vector2(1472, 900), level, 1.0)
    assert cam.pos.x == pytest.approx(1472 - 640)
    cam.follow(Vector2(10, 900), level, 1.0)
    assert cam.pos.x == 0
    cam.follow(Vector2(level.width, 900), level, 1.0)
    assert cam.pos.x == level.width - 1280 and cam.pos.y == level.height - 720
