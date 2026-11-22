"""Menu logic without a window, plus command-line launch failures as subprocesses."""

import os
import subprocess
import sys

import pygame
import pytest

from ballbrawlla.menu import MenuState, draw, handle_event

ENV = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}


def press(state, key, unicode=""):
    handle_event(state, pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode), [])


def labels(state):
    return [i.label.split(":")[0] for i in state.items()]


def goto(state, label):
    state.cursor = labels(state).index(label)
    state.select()


def test_main_and_play_menus():
    s = MenuState()
    assert labels(s) == ["PLAY", "QUIT"]
    goto(s, "PLAY")
    assert labels(s) == ["FREE PLAY", "TWO PLAYERS", "ONLINE"]
    goto(s, "FREE PLAY")
    assert labels(s) == ["EXPLORE", "CATCH PRACTICE"]


def test_free_play_lists_every_level_and_launches_one():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    goto(s, "EXPLORE")
    assert s.screen == "level" and s.result is None
    keys = [i.key for i in s.shown_levels()]
    assert "arena_01" in keys and len(keys) == 15
    s.cursor = keys.index("field_05")
    s.select()
    assert s.result.mode == "sandbox" and s.result.level.stem == "field_05"


def test_free_play_can_launch_the_arena():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    goto(s, "EXPLORE")
    s.cursor = [i.key for i in s.shown_levels()].index("arena_01")
    s.select()
    assert s.result.mode == "sandbox" and s.result.level.stem == "arena_01"


def test_two_players_only_lists_football_fields():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "TWO PLAYERS")
    keys = [i.key for i in s.shown_levels()]
    assert "arena_01" not in keys and len(keys) == 14
    s.cursor = keys.index("field_09")
    s.select()
    assert s.result.mode == "local" and s.result.level.stem == "field_09"


@pytest.fixture
def relay_env(monkeypatch):
    from ballbrawlla.net import invite
    monkeypatch.setattr(invite, "DEFAULT_RELAY", "")
    monkeypatch.setenv(invite.RELAY_ENV, "relay.example.com")
    # These tests are about the relay, not the game port: a real game running on this machine (port 50555 in
    # use) must not grey out "Host online game" and fail them.
    from ballbrawlla import launch, menu
    monkeypatch.setattr(launch, "check_port", lambda port: None)
    monkeypatch.setattr(menu, "check_port", lambda port: None)
    return monkeypatch


def test_online_screen_lists_invite_and_lan_options(relay_env):
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    assert labels(s) == ["HOST ONLINE GAME", "JOIN WITH CODE", "HOST ON THIS NETWORK", "JOIN ON THIS NETWORK"]
    goto(s, "HOST ONLINE GAME")
    assert s.screen == "level" and s.mode == "host_online"
    assert "football" not in " ".join(i.reason or "" for i in s.items())    # the picker only shows fields
    s.select()
    assert s.result.mode == "host_online"


def test_online_options_are_greyed_without_a_relay(monkeypatch):
    from ballbrawlla.net import invite
    monkeypatch.setattr(invite, "DEFAULT_RELAY", "")
    monkeypatch.delenv(invite.RELAY_ENV, raising=False)
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    host, join = s.items()[:2]
    assert not host.enabled and not join.enabled and "No relay server" in join.reason
    s.cursor = 1
    s.select()
    assert s.screen == "online" and "No relay server" in s.error


def test_join_with_code_types_pastes_and_connects(relay_env):
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    goto(s, "JOIN WITH CODE")
    assert s.screen == "code" and s.editing and not s.items()[1].enabled
    for ch in "kq7-m3":
        press(s, ord(ch), ch)
    assert s.code == "KQ7M3" and labels(s)[0] == "CODE" and not s.items()[1].enabled
    press(s, ord("x"), "x")
    assert "KQ7-M3X" in s.items()[0].label and s.items()[1].enabled
    s.paste("Join my game! Code: ab2-cd3")                 # a whole pasted message still finds the code
    assert s.code == "AB2CD3"
    press(s, pygame.K_BACKSPACE)
    assert s.code == "AB2CD"
    s.paste("ab2cd4")
    press(s, pygame.K_RETURN)                               # Enter on the code row moves to CONNECT
    s.select()
    assert s.result.mode == "join_code" and s.result.code == "AB2CD4"


def test_broken_level_is_greyed_in_the_picker(tmp_path):
    from ballbrawlla.launch import inspect_level
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    s = MenuState(levels=[inspect_level(bad)])
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    goto(s, "EXPLORE")
    assert not s.items()[0].enabled
    s.select()
    assert s.error and s.result is None


def test_escape_from_level_picker_returns_to_the_free_play_screen():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    goto(s, "EXPLORE")
    press(s, pygame.K_ESCAPE)
    assert s.screen == "freeplay"


def test_join_needs_an_address():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    goto(s, "JOIN ON THIS NETWORK")
    s.close()                       # no network listener needed for this test
    assert s.items()[0].action == "none" and s.editing                     # starts on the address row
    assert not s.items()[2].enabled                                         # CONNECT needs an address
    for ch in "10.0.0.7":
        press(s, ord(ch), ch)
    assert s.address == "10.0.0.7" and s.items()[2].enabled
    press(s, pygame.K_BACKSPACE)
    assert s.address == "10.0.0."
    s.cursor = 2
    s.select()
    assert s.result.mode == "join" and s.result.address == "10.0.0."


def test_escape_goes_back_then_quits():
    s = MenuState()
    goto(s, "PLAY")
    press(s, pygame.K_ESCAPE)
    assert s.screen == "main" and not s.quit
    press(s, pygame.K_ESCAPE)
    assert s.quit


def test_every_screen_draws(relay_env):
    pygame.font.init()
    fonts = {k: pygame.font.Font(None, n) for k, n in (("big", 64), ("mid", 36), ("small", 24))}
    surface = pygame.Surface((1280, 720))
    s = MenuState()
    for path in (["PLAY"], ["PLAY", "ONLINE"], ["PLAY", "ONLINE", "JOIN ON THIS NETWORK"],
                 ["PLAY", "ONLINE", "JOIN WITH CODE"]):
        s = MenuState()
        for label in path:
            goto(s, label)
        draw(surface, s, fonts)
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    goto(s, "EXPLORE")
    for n in range(len(s.shown_levels())):
        s.cursor = n
        draw(surface, s, fonts)


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "ballbrawlla", *args], env=ENV, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("args,needle", [
    (["--level", "field_99"], "not found"),
    (["--level", "arena_01"], "football field"),
    (["--local", "--level", "arena_01"], "football field"),
    (["--join", "127.0.0.1", "--port", "80"], "isn't valid"),
])
def test_cli_failures_are_one_line_with_status_2(args, needle):
    r = run_cli(*args)
    assert r.returncode == 2 and needle in r.stderr and "Traceback" not in r.stderr


def test_pause_menu_flow():
    from ballbrawlla.pause import PauseMenu
    ev = lambda key: pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")
    p = PauseMenu()
    assert not p.handle(ev(pygame.K_LEFT)) and not p.freezes     # closed: game gets the key
    assert p.handle(ev(pygame.K_ESCAPE)) and p.freezes           # opens and freezes
    assert p.handle(ev(pygame.K_LEFT))                           # open: game gets nothing
    p.handle(ev(pygame.K_DOWN))
    p.handle(ev(pygame.K_RETURN))                                # CONTROLS
    assert p.page == "controls"
    p.handle(ev(pygame.K_a))
    assert p.page == "menu"
    p.handle(ev(pygame.K_ESCAPE))
    assert not p.open                                            # Esc resumes
    p.handle(ev(pygame.K_ESCAPE))
    p.handle(ev(pygame.K_UP))                                    # wraps to MAIN MENU
    p.handle(ev(pygame.K_RETURN))
    assert p.result == "menu"


def test_network_pause_does_not_freeze():
    from ballbrawlla.pause import PauseMenu
    p = PauseMenu(pauses=False)
    p.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    assert p.open and not p.freezes


def test_pause_draws():
    from ballbrawlla.pause import PauseMenu
    pygame.font.init()
    p = PauseMenu()
    p.open = True
    surface = pygame.Surface((1280, 720))
    p.draw(surface)
    p.page = "controls"
    p.draw(surface)


def _join_screen(monkeypatch):
    import socket as _socket
    from ballbrawlla import menu as menu_mod
    from ballbrawlla.net.discovery import Beacon, Finder
    probe = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    monkeypatch.setattr(menu_mod, "Finder", lambda: Finder(port))
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    goto(s, "JOIN ON THIS NETWORK")
    return s, lambda name, level, tcp: Beacon(name, level, tcp, discovery_port=port)


def test_join_lists_found_games_and_connects(monkeypatch):
    import time
    s, make_beacon = _join_screen(monkeypatch)
    assert s.items()[0].action == "none" and s.cursor == 1 and s.editing       # waiting; typing still works
    beacon = make_beacon("Kris's game", "Field 05", 50611)
    try:
        beacon.tick(now=1.0)
        for _ in range(50):
            s.update()
            if s.games:
                break
            time.sleep(0.02)
        assert [i.label for i in s.items()][0] == "Kris's game" and len(s.games) == 1
        assert s.cursor == 1 and s.editing                                      # cursor stayed on the address row
        shown = s.games[0].address        # this machine's LAN address, or loopback when offline
        s.cursor = 0
        s.select()
        assert s.result.mode == "join" and s.result.port == 50611 and s.result.address == shown
    finally:
        beacon.close()
        s.close()


def test_leaving_join_closes_the_listener(monkeypatch):
    s, _ = _join_screen(monkeypatch)
    finder = s.finder
    assert finder.available
    s.back()
    assert finder.sock is None and s.finder is None


def test_join_without_discovery_says_so(monkeypatch):
    from ballbrawlla import menu as menu_mod

    class Dead:
        available = False
        def poll(self): return []
        def close(self): pass
    monkeypatch.setattr(menu_mod, "Finder", Dead)
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    goto(s, "JOIN ON THIS NETWORK")
    assert "automatically" in s.items()[0].label


def test_mouse_click_selects_a_row():
    pygame.font.init()
    fonts = {k: pygame.font.Font(None, n) for k, n in (("big", 64), ("mid", 36), ("small", 24))}
    surface = pygame.Surface((1280, 720))
    s = MenuState()
    rects = draw(surface, s, fonts)
    handle_event(s, pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rects[0].center, button=1), rects)
    assert s.screen == "play"
    rects = draw(surface, s, fonts)
    handle_event(s, pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1), rects)   # empty space
    assert s.screen == "play"


@pytest.mark.parametrize("button", [pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_X])
def test_cross_and_square_select_and_dpad_moves(button):
    s = MenuState()
    ev = lambda b: pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=b, instance_id=0)
    handle_event(s, ev(pygame.CONTROLLER_BUTTON_DPAD_DOWN), [])
    assert s.cursor == 1
    handle_event(s, ev(pygame.CONTROLLER_BUTTON_DPAD_UP), [])
    handle_event(s, ev(button), [])
    assert s.screen == "play"
    handle_event(s, ev(pygame.CONTROLLER_BUTTON_B), [])       # Circle goes back
    assert s.screen == "main"


def test_pad_works_in_pause_menu():
    from ballbrawlla.pause import PauseMenu
    p = PauseMenu()
    p.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    ev = lambda b: pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=b, instance_id=0)
    p.handle(ev(pygame.CONTROLLER_BUTTON_DPAD_DOWN))
    p.handle(ev(pygame.CONTROLLER_BUTTON_X))
    assert p.page == "controls"


def test_closing_the_window_in_a_game_quits_the_whole_app(monkeypatch):
    """The red close button must end the program, not drop back to the menu."""
    from ballbrawlla import main
    pygame.init()
    monkeypatch.setattr(main, "_app_quit", False)
    menus = []
    sandbox = main.LEVELS / "arena_01.json"

    def fake_menu(screen, state, names, pads):
        menus.append(1)
        return main.Launch("sandbox", sandbox)

    monkeypatch.setattr(main, "run_menu", fake_menu)
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    main.run_launcher()
    assert menus == [1]            # the menu was not shown a second time


def test_escape_menu_returns_to_launcher_but_close_does_not(monkeypatch):
    from ballbrawlla import main
    pygame.init()
    monkeypatch.setattr(main, "_app_quit", False)
    calls = []

    def fake_menu(screen, state, names, pads):
        calls.append(1)
        if len(calls) == 1:
            for key in (pygame.K_ESCAPE, pygame.K_UP, pygame.K_RETURN):    # pause > MAIN MENU
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
            return main.Launch("sandbox", main.LEVELS / "arena_01.json")
        return None                                                          # second time: quit from the menu

    monkeypatch.setattr(main, "run_menu", fake_menu)
    pygame.event.clear()
    main.run_launcher()
    assert len(calls) == 2         # went back to the menu after "Main menu"


def test_catch_practice_lists_football_fields_and_launches():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    goto(s, "CATCH PRACTICE")
    keys = [i.key for i in s.shown_levels()]
    assert "arena_01" not in keys and len(keys) == 14
    s.cursor = keys.index("field_05")
    s.select()
    assert s.result.mode == "catch" and s.result.level.stem == "field_05"


def test_escape_from_free_play_screen_goes_back_to_play():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "FREE PLAY")
    press(s, pygame.K_ESCAPE)
    assert s.screen == "play"


def test_animation_is_a_pure_function_of_time_and_loops():
    from ballbrawlla.menu_anim import PERIOD, pose
    a, b = pose(1.1, 1280), pose(1.1, 1280)
    assert a == b
    assert pose(0.1, 1280).phase == "windup" and pose(1.0, 1280).phase == "flight"
    assert pose(PERIOD - 0.1, 1280).phase == "hold"
    assert pose(0.5, 1280).direction == 1 and pose(PERIOD + 0.5, 1280).direction == -1     # players swap


def test_ball_flies_from_one_player_to_the_other_along_an_arc():
    from ballbrawlla.menu_anim import FLIGHT, WINDUP, layout, pose
    left, right, _ = layout(1280, 300)
    start, mid, end = (pose(WINDUP + FLIGHT * u, 1280) for u in (0.01, 0.5, 0.99))
    assert start.x == pytest.approx(left, abs=20) and end.x == pytest.approx(right, abs=20)
    assert mid.y < start.y and mid.y < end.y                       # the middle of the flight is the highest point
    back = pose(3.6 + WINDUP + FLIGHT * 0.99, 1280)
    assert back.x == pytest.approx(left, abs=20)                  # and the next throw goes the other way


def test_bad_sprite_files_do_not_break_the_menu(tmp_path):
    from ballbrawlla.menu_anim import load_ball_frames
    pygame.display.set_mode((10, 10))
    (tmp_path / "football_1.png").write_bytes(b"not an image")
    assert load_ball_frames(tmp_path) == []                       # falls back to the drawn ball
    img = pygame.Surface((8, 8), pygame.SRCALPHA)
    pygame.image.save(img, str(tmp_path / "football_2.png"))
    assert len(load_ball_frames(tmp_path)) == 1


def test_menu_draws_with_animation_at_several_times():
    pygame.font.init()
    fonts = {k: pygame.font.Font(None, n) for k, n in (("big", 64), ("mid", 36), ("small", 24))}
    surface = pygame.Surface((1280, 720))
    s = MenuState()
    for t in (0.0, 0.7, 1.5, 2.6, 3.4, 5.9):
        draw(surface, s, fonts, t=t)
