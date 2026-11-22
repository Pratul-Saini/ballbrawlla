"""Local two-player play (--local): one screen, nothing hidden, a camera that
keeps both players in view, and two keyboard layouts / controllers."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from collections import defaultdict

import pygame
import pytest
from test_session import make_session, step

from ballbrawlla.input import BLUE_KEYS, RED_KEYS, Intent, KeyboardInput
from ballbrawlla.net.view import make_view
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.render.match_renderer import MIN_ZOOM, Camera, MatchRenderer
from ballbrawlla.world.level import Level


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


# ---------------------------------------------------------------- view

def test_local_view_shows_both_sides_choices():
    s = make_session()
    v = make_view(s, 0, local=True)
    assert v["local"] and "aim" in v["call"] and "def" in v["call"]
    step(s, off=Intent(x_pressed=True), dfn=Intent(z_pressed=True))   # both lock in
    assert "aim" in make_view(s, 0, local=True)                        # the throw, before it happens
    assert ("aim" in make_view(s, s.human_of(s.down.defense))) is False  # network play still hides it


# ---------------------------------------------------------------- camera

LEVEL = Level(width=7000, height=2400)


def _inside(cam: Camera, p: Vector2) -> bool:
    ww, wh = cam.world_size
    return cam.pos.x <= p.x <= cam.pos.x + ww and cam.pos.y <= p.y <= cam.pos.y + wh


def test_camera_stays_at_full_size_when_players_are_close():
    cam = Camera((1280, 720))
    cam.frame([Vector2(3000, 1500), Vector2(3300, 1600)], LEVEL, 1.0)
    assert cam.zoom == pytest.approx(1.0)


def test_camera_zooms_out_to_keep_both_players_in_view():
    cam = Camera((1280, 720))
    pts = [Vector2(2000, 1500), Vector2(4200, 1200)]
    cam.frame(pts, LEVEL, 1.0)
    assert MIN_ZOOM < cam.zoom < 1
    assert all(_inside(cam, p) for p in pts)


def test_camera_never_zooms_out_past_the_limit():
    cam = Camera((1280, 720))
    cam.frame([Vector2(100, 1500), Vector2(6900, 1500)], LEVEL, 1.0)
    assert cam.zoom == pytest.approx(MIN_ZOOM)


# ---------------------------------------------------------------- input

def _hold(monkeypatch, *keys):
    held = defaultdict(int, {k: 1 for k in keys})
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: held)


def test_blue_and_red_have_separate_keys(monkeypatch):
    blue = KeyboardInput(gamepads=False, keys=BLUE_KEYS)
    red = KeyboardInput(gamepads=False, keys=RED_KEYS)
    _hold(monkeypatch, pygame.K_d, pygame.K_LEFT)
    for k in (pygame.K_f, pygame.K_SLASH, pygame.K_w):
        ev = pygame.event.Event(pygame.KEYDOWN, key=k)
        blue.handle_event(ev)
        red.handle_event(ev)
    b, r = blue.consume(use_mouse=False), red.consume(use_mouse=False)
    assert (b.move_x, r.move_x) == (1, -1)
    assert b.z_pressed and not b.x_pressed and b.jump_pressed      # F, and W jumps for Blue
    assert r.x_pressed and not r.z_pressed and not r.jump_pressed  # slash; W means nothing to Red


def test_only_the_player_given_the_mouse_gets_it(monkeypatch):
    _hold(monkeypatch)
    monkeypatch.setattr(pygame.mouse, "get_focused", lambda: True)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (640, 360))
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda num_buttons=3: (1, 0, 0))
    a = KeyboardInput(gamepads=False, keys=BLUE_KEYS)
    b = KeyboardInput(gamepads=False, keys=RED_KEYS)
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(640, 360))
    a.handle_event(click)
    b.handle_event(click)
    with_mouse = a.consume(Vector2(1000, 500), zoom=0.5, use_mouse=True)
    without = b.consume(Vector2(1000, 500), zoom=0.5, use_mouse=False)
    assert with_mouse.mouse == (1000 + 640 / 0.5, 500 + 360 / 0.5)   # screen -> world at half zoom
    assert with_mouse.mouse_pressed and with_mouse.mouse_held
    assert without.mouse is None and not without.mouse_pressed and not without.mouse_held


# ---------------------------------------------------------------- rendering

def test_local_screen_draws_both_hints_and_the_offense_button():
    s = make_session()
    screen = pygame.Surface((1280, 720))
    r = MatchRenderer(screen, s.level, s.field, s.t)
    r.draw(make_view(s, s.human_of(s.down.defense), local=True), 60, 1 / 60)
    assert r.hud_h > MatchRenderer(screen, s.level, s.field, s.t).hud_h   # two hint lines
    assert r.button_rect is not None                                     # the offense's button
    step(s, off=Intent(x_pressed=True), dfn=Intent(z_pressed=True))
    r.draw(make_view(s, 0, local=True), 60, 1 / 60)                      # execution, framed

