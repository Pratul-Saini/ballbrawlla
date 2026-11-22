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


def test_online_match_is_coming_soon_and_launches_nothing():
    s = MenuState()
    goto(s, "PLAY")
    goto(s, "ONLINE")
    assert labels(s) == ["HOST A GAME", "JOIN A GAME", "ONLINE MATCH"]
    item = s.items()[2]
    assert item.soon and not item.enabled and item.hint == "coming soon"
    assert "neither of you hosts" in item.reason and "isn't built yet" in item.reason
    s.cursor = 2
    s.select()
    assert s.result is None and s.screen == "online"
    assert s.error == item.reason                       # the description is shown, not an error about the code


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
    goto(s, "JOIN A GAME")
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


def test_every_screen_draws():
    pygame.font.init()
    fonts = {k: pygame.font.Font(None, n) for k, n in (("big", 64), ("mid", 36), ("small", 24))}
    surface = pygame.Surface((1280, 720))
    s = MenuState()
    for path in (["PLAY"], ["PLAY", "ONLINE"], ["PLAY", "ONLINE", "JOIN A GAME"]):
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
    goto(s, "JOIN A GAME")
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
    goto(s, "JOIN A GAME")
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
