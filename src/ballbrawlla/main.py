"""Entry point: window + fixed-timestep loop. Physics runs at Tuning.physics_hz
regardless of frame rate.

    ballbrawlla                     open the menu
    ballbrawlla --level field_01    practice: you on offense vs a defender that stands still
    ballbrawlla --host              host a 2-player LAN match (you are Blue)
    ballbrawlla --join 192.168.x.y  join a LAN match (you are Red)
    ballbrawlla --host --online     host an internet match: prints an invite code (needs a relay server)
    ballbrawlla --join-code KQ7-M3X join an internet match with the host's invite code
    ballbrawlla --local             two players on one screen (Blue: WASD + F/G, Red: arrows + . and /)
    ballbrawlla --sandbox           free play in the small arena (physics tuning, no rules)
    ballbrawlla --sandbox --level field_01   free play on the big match field
"""

import argparse
import os
import socket
import sys
from dataclasses import asdict
from pathlib import Path

import pygame

from ballbrawlla import diag
from ballbrawlla.config import TUNING, Tuning
from ballbrawlla.game import Game
from ballbrawlla.gamepad import Gamepads
from ballbrawlla.input import BLUE_KEYS, RED_KEYS, KeyboardInput
from ballbrawlla.launch import LaunchError, check_launch, read_level, resolve_level
from ballbrawlla.menu import Launch, MenuState, run_menu
from ballbrawlla.net.client import Client
from ballbrawlla.net.discovery import Beacon
from ballbrawlla.net.host import Host
from ballbrawlla.net.invite import RELAY_ENV, RelayRoom, format_code, relay_address
from ballbrawlla.net.protocol import DEFAULT_PORT, lan_ip
from ballbrawlla.net.view import make_view
from ballbrawlla.notes import SessionNotes
from ballbrawlla.paths import is_frozen, levels_dir, user_data_dir
from ballbrawlla.version import __version__
from ballbrawlla.pause import LOCAL, PauseMenu
from ballbrawlla.render.match_renderer import Camera, MatchRenderer
from ballbrawlla.render.renderer import Renderer
from ballbrawlla.rules.field import Field
from ballbrawlla.session import Session
from ballbrawlla.world.level import Level, level_from_dict, level_to_dict

LEVELS = levels_dir()
DEFAULT_LEVEL = LEVELS / "field_01.json"
SANDBOX_LEVEL = LEVELS / "arena_01.json"
WINDOW = (1280, 720)
MAX_FRAME_TIME = 0.25  # avoid a spiral of death after a stall


_app_quit = False


def _quit_app() -> None:
    """The window's close button (or Cmd-Q) was used inside a game: end the whole program, not just the game."""
    global _app_quit
    _app_quit = True
    diag.log.info("window closed: quitting the app")


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ballbrawlla")
    parser.add_argument("--level", type=Path, default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true", help="host a local network match")
    mode.add_argument("--join", metavar="ADDRESS", help="join a host at this IP address")
    mode.add_argument("--join-code", metavar="CODE", help="join an internet match with an invite code")
    mode.add_argument("--sandbox", action="store_true", help="free play, no rules")
    mode.add_argument("--local", action="store_true", help="two players on one screen")
    mode.add_argument("--catch", action="store_true", help="catch practice: football rules, no defender")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--online", action="store_true",
                        help="with --host: also open the game on the relay server and get an invite code")
    parser.add_argument("--relay", metavar="HOST[:PORT]",
                        help=f"relay server for invite codes (default: ${RELAY_ENV}, else the built-in one)")
    args = parser.parse_args(argv)
    if args.online and not args.host:
        parser.error("--online goes with --host (to join, use --join-code CODE)")
    if args.relay:
        os.environ[RELAY_ENV] = args.relay        # every later relay_address() call sees it, menu included
    if args.join_code:
        mode = "join_code"
    elif args.join:
        mode = "join"
    elif args.sandbox:
        mode = "sandbox"
    elif args.local:
        mode = "local"
    elif args.host:
        mode = "host_online" if args.online else "host"
    elif args.catch:
        mode = "catch"
    elif args.level is not None:
        mode = "practice"
    else:
        mode = None                      # no flags at all: open the menu

    log_path = diag.setup()
    if log_path:
        print(f"log: {log_path}", file=sys.stderr)
    if os.environ.get("SDL_VIDEODRIVER", "").lower() in ("dummy", "offscreen"):
        msg = ("SDL_VIDEODRIVER is set to '%s', so no window will appear. "
               "Run `unset SDL_VIDEODRIVER SDL_AUDIODRIVER` and start again." % os.environ["SDL_VIDEODRIVER"])
        diag.log.warning(msg)
        print(f"ballbrawlla: WARNING: {msg}", file=sys.stderr)
    # macOS: deliver the click that focuses the window (otherwise the first click is lost), and keep
    # controller input flowing even when the window isn't the focused one.
    os.environ.setdefault("SDL_MOUSE_FOCUS_CLICKTHROUGH", "1")
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    pygame.init()
    diag.describe_pygame()
    try:
        if mode is None:
            run_launcher()
            return
        level = resolve_level(args.level) if args.level else (SANDBOX_LEVEL if mode == "sandbox" else DEFAULT_LEVEL)
        try:
            start(Launch(mode, level, args.port, args.join or "", args.join_code or ""))
        except (LaunchError, ConnectionError) as e:
            diag.log.warning("launch refused: %s", e)
            print(f"ballbrawlla: {e}", file=sys.stderr)
            raise SystemExit(2) from None
    except SystemExit:
        raise
    except BaseException:
        diag.log.exception("run() failed")
        raise
    finally:
        diag.log.info("exit")
        pygame.quit()


def start(choice: Launch) -> None:
    """Check that the launch can work, then run it. Raises LaunchError or ConnectionError with a readable message."""
    diag.log.info("launch requested: %s", choice)
    why = check_launch(choice.mode, choice.level, choice.port, choice.address, choice.code)
    if why:
        diag.log.warning("launch refused: %s", why)
        raise LaunchError(why)
    diag.where(choice.mode)
    if choice.mode == "join":
        run_client(choice.address, choice.port)
        return
    if choice.mode == "join_code":
        run_client(code=choice.code)
        return
    level = read_level(choice.level)
    if choice.mode == "sandbox":
        run_sandbox(level)
    elif choice.mode == "local":
        run_couch(level)
    else:
        run_match(level, host=choice.mode in ("host", "host_online"), port=choice.port,
                  defender=choice.mode != "catch", online=choice.mode == "host_online")


def run_launcher() -> None:
    """Menu -> game -> menu, until the player quits from the menu."""
    state = MenuState()
    pads = Gamepads()
    diag.log.info("game version %s, controller support: %s, frozen: %s, levels: %s, writable: %s",
                  __version__, pads.available, is_frozen(), LEVELS, user_data_dir())
    while True:
        screen = _open_window("Gridiron Scramble", WINDOW)
        choice = run_menu(screen, state, pads.names, pads)
        if choice is None:
            return
        try:
            start(choice)
        except (LaunchError, ConnectionError, OSError) as e:
            diag.log.warning("launch failed, back to menu: %s", e)
            state.error = str(e)
        diag.where("menu")
        if _app_quit:
            return
        

def _match_context(view_fn) -> str:
    """One line describing the match, for the notes header."""
    v = view_fn()
    if v is None:
        return ""
    from ballbrawlla.rules.teams import Team
    from ballbrawlla.session import ordinal
    s = v["score"]
    return (f"Blue {s[0]} - {s[1]} Red, {ordinal(v['down'])} down, {Team(v['offense']).display} on offense, "
            f"phase {v['phase']}")


def _level_label(level: Level) -> str:
    return level.name


def _pad_status(inputs: KeyboardInput) -> str:
    pads = inputs.gamepads.names if inputs.gamepads is not None else []
    return f"   |   controller: {', '.join(pads)}" if pads else ""


def _open_window(title: str, size: tuple[int, int] = WINDOW) -> pygame.Surface:
    screen = pygame.display.set_mode(size, pygame.SCALED | pygame.RESIZABLE, display=_display_index())
    pygame.display.set_caption(title)
    diag.describe_window(title, "SCALED|RESIZABLE")
    return screen


def _display_index() -> int:
    """Which monitor to open on: the main one (0) unless BALLBRAWLLA_DISPLAY says otherwise.
    Without this, macOS can put the window on a second monitor that you aren't looking at."""
    try:
        wanted = int(os.environ.get("BALLBRAWLLA_DISPLAY", "0"))
    except ValueError:
        wanted = 0
    count = len(pygame.display.get_desktop_sizes())
    return wanted if 0 <= wanted < count else 0


def _copy(text: str) -> bool:
    try:
        pygame.scrap.put_text(text)
        return True
    except (pygame.error, AttributeError):
        return False


def run_match(level: Level, host: bool = False, port: int = DEFAULT_PORT, defender: bool = True,
              online: bool = False) -> None:
    """Practice (1 human, optionally with no defender) or the hosting player (who also runs the simulation).
    `online` also opens the game on the relay server, so a player on another network can join with a code."""
    session = Session(level, TUNING, humans=2 if host else 1, defender=defender)

    server: Host | None = None
    beacon: Beacon | None = None
    room: RelayRoom | None = None
    address = ""
    if host:
        if online:
            relay = relay_address()
            print(f"Opening an online game on the relay server {relay[0]}:{relay[1]} ...")
            room = RelayRoom(relay)                     # raises ConnectionError with a readable message
            print(f"Invite code: {room.display_code} - the other player joins with: "
                  f"ballbrawlla --join-code {room.display_code}")
        try:
            server = Host(
                welcome={"level": level_to_dict(level), "tuning": asdict(TUNING)},
                max_players=2,
                port=port,
                room=room,
            )
        except OSError:
            if room is not None:
                room.close()
            raise
        address = f"{lan_ip()}:{server.port}"
        beacon = Beacon(f"{socket.gethostname().split('.')[0]}'s game", level.name, server.port)
        print(f"Hosting on {address} - the other player joins with: ballbrawlla --join {lan_ip()}")

    screen = _open_window(("ballbrawlla (online host, Blue)" if online else "ballbrawlla (host, Blue)") if host
                          else "ballbrawlla (practice)")
    renderer = MatchRenderer(screen, level, session.field, TUNING)
    inputs = KeyboardInput()
    notes = SessionNotes(("host_online" if online else "host") if host else "practice", _level_label(level),
                         context=lambda: _match_context(lambda: make_view(session, 0)))
    clock = pygame.time.Clock()
    pause = PauseMenu(pauses=not host)
    dt = TUNING.dt
    accumulator = 0.0
    copied_at = -10.0

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
            diag.beat()
            accumulator += frame_dt

            for event in pygame.event.get():
                diag.event(event)
                if notes.handle(event):
                    continue
                if pause.handle(event, screen.get_size()):
                    continue
                if event.type == pygame.QUIT:
                    running = False
                    _quit_app()
                elif event.type == pygame.KEYDOWN:
                    if (room is not None and event.key == pygame.K_c
                            and event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                        if _copy(room.display_code):
                            copied_at = pygame.time.get_ticks() / 1000.0
                        continue
                    if event.key == pygame.K_r:
                        session.new_match()
                    elif event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                    elif event.key == pygame.K_F3:
                        renderer.show_controls = not renderer.show_controls
                action = inputs.handle_event(event, renderer.button_hit)
                if action == "restart":
                    session.new_match()
                elif action == "debug":
                    renderer.debug = not renderer.debug

            if server:
                if beacon:
                    beacon.tick(open_seat=len(server.clients) < server.max_players - 1)
                joined, left = server.poll()
                for pid in joined:
                    session.set_connected(pid, True)
                for pid in left:
                    session.set_connected(pid, False)

            stepped = False
            if notes.is_open and not server:
                accumulator = 0.0                 # practice pauses while you write notes
            if pause.result:
                running = False
            if pause.freezes:
                accumulator = 0.0
            while accumulator >= dt:
                intents = [notes.gate(inputs.consume(renderer.camera.pos))]
                if server:
                    intents.append(server.intent_for(1))
                session.step(intents, dt)
                accumulator -= dt
                stepped = True

            if server and stepped:
                for pid in server.clients:
                    server.send_to(pid, make_view(session, pid))

            status = f"hosting on {address}" if server else ""
            invite = None
            if room is not None:
                if room.lost:
                    status = f"relay connection lost - nobody new can join   |   LAN {address}"
                else:
                    copied = pygame.time.get_ticks() / 1000.0 - copied_at < 2.0
                    status = (f"invite code {room.display_code} ({'copied!' if copied else 'Ctrl+C: copy'})"
                              f"   |   LAN {address}")
                    invite = room.display_code
            controls = ("R / Options: restart   F1: debug   F2: notes   F3: hide controls   Esc: menu"
                        + _pad_status(inputs))
            renderer.draw(make_view(session, 0), clock.get_fps(), frame_dt, status, controls, invite=invite)
            pause.draw(screen)
            notes.draw(screen)
            pygame.display.flip()
    finally:
        notes.save()
        if beacon:
            beacon.close()
        if server:
            server.close()


def run_couch(level: Level) -> None:
    """Two players on one screen and one machine. Nothing is hidden; the camera
    zooms out to keep both players in view. Blue uses W A S D + F (catch / tag /
    confirm) + G (lock in); Red uses the arrows + . and /. The first controller to
    connect is Blue's, the second Red's. During the play call the mouse belongs to
    whichever side is on offense. F5 (or Options) starts a new match - not R,
    which sits next to Blue's keys."""
    session = Session(level, TUNING, humans=2)
    session.set_connected(1, True)

    screen = _open_window("ballbrawlla (local 2-player)")
    renderer = MatchRenderer(screen, level, session.field, TUNING)
    renderer.key_names = {"grab": "F / . / Square", "lock": "G / slash / Circle", "restart": "F5"}
    pads = Gamepads()
    players = [KeyboardInput(keys=BLUE_KEYS, shared_pads=pads, pad_slot=0),
               KeyboardInput(keys=RED_KEYS, shared_pads=pads, pad_slot=1)]
    notes = SessionNotes("local", _level_label(level),
                         context=lambda: _match_context(lambda: make_view(session, 0, local=True)))
    clock = pygame.time.Clock()
    pause = PauseMenu(controls=LOCAL)
    dt = TUNING.dt
    accumulator = 0.0

    running = True
    while running:
        frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
        diag.beat()
        accumulator += frame_dt

        for event in pygame.event.get():
            diag.event(event)
            if notes.handle(event):
                continue
            if pause.handle(event, screen.get_size()):
                continue
            if event.type == pygame.QUIT:
                running = False
                _quit_app()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F5:
                    session.new_match()
                elif event.key == pygame.K_F1:
                    renderer.debug = not renderer.debug
                elif event.key == pygame.K_F3:
                    renderer.show_controls = not renderer.show_controls
            action = pads.handle_event(event)
            if action == "restart":
                session.new_match()
            elif action == "debug":
                renderer.debug = not renderer.debug
            for inp in players:
                inp.handle_event(event, renderer.button_hit)

        if notes.is_open:
            accumulator = 0.0                     # local play pauses while you write notes
        if pause.result:
            running = False
        if pause.freezes:
            accumulator = 0.0
        while accumulator >= dt:
            offense = session.human_of(session.down.offense)
            cam = renderer.camera
            intents = [inp.consume(cam.pos, cam.zoom, use_mouse=(pid == offense))
                       for pid, inp in enumerate(players)]
            session.step(intents, dt)
            accumulator -= dt

        names = pads.names
        controls = (f"Blue: {BLUE_KEYS.label}   Red: {RED_KEYS.label}   |   "
                    + (f"controllers: {', '.join(names)}   |   " if names else "")
                    + "F5: new match   F1: debug   F2: notes   F3: hide controls   Esc: menu")
        renderer.draw(make_view(session, 0, local=True), clock.get_fps(), frame_dt, "", controls)
        pause.draw(screen)
        notes.draw(screen)
        pygame.display.flip()
    notes.save()


def run_client(address: str = "", port: int = DEFAULT_PORT, code: str = "") -> None:
    """Sends input to the host and draws the view it sends back. With `code`, joins through the relay server."""
    if code:
        relay = relay_address()
        where = f"invite code {format_code(code)}"
        print(f"Joining {where} via the relay server {relay[0]}:{relay[1]} ...")
        client = Client.via_code(relay, code)          # its errors already name the code
    else:
        where = f"{address}:{port}"
        print(f"Connecting to {where} ...")
        try:
            client = Client(address, port)
        except ConnectionError as e:
            raise ConnectionError(f"Could not join {where}. {e}") from e

    level = level_from_dict(client.level_data)
    tuning = Tuning(**client.tuning_data)
    screen = _open_window("ballbrawlla (Red)")
    renderer = MatchRenderer(screen, level, Field(level, tuning), tuning)
    inputs = KeyboardInput()
    clock = pygame.time.Clock()
    pause = PauseMenu(pauses=False)
    dt = tuning.dt
    accumulator = 0.0
    view: dict | None = None
    notes = SessionNotes("join_code" if code else "join", _level_label(level), context=lambda: _match_context(lambda: view))

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
            diag.beat()
            accumulator += frame_dt

            for event in pygame.event.get():
                diag.event(event)
                if notes.handle(event):
                    continue
                if pause.handle(event, screen.get_size()):
                    continue
                if event.type == pygame.QUIT:
                    running = False
                    _quit_app()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                    elif event.key == pygame.K_F3:
                        renderer.show_controls = not renderer.show_controls
                if inputs.handle_event(event, renderer.button_hit) == "debug":
                    renderer.debug = not renderer.debug

            # Send input at the simulation rate so press edges line up with host ticks.
            if pause.result:
                running = False
            if pause.freezes:
                accumulator = 0.0
            while accumulator >= dt:
                client.send_intent(notes.gate(inputs.consume(renderer.camera.pos)))
                accumulator -= dt

            latest = client.latest_snapshot()
            if latest is not None:
                view = latest

            status = f"connected via {where}" if code else f"connected to {where}"
            if client.closed:
                status = "disconnected from host - press Esc to quit"
            controls = "F1: debug   F2: notes   F3: hide controls   Esc: menu" + _pad_status(inputs)
            if view is not None:
                renderer.draw(view, clock.get_fps(), frame_dt, status, controls)
            pause.draw(screen)
            notes.draw(screen)
            pygame.display.flip()
    finally:
        notes.save()
        client.close()


def run_sandbox(level: Level) -> None:
    """Free play: one player, a ball, no rules. Levels bigger than the window
    get a camera that follows the player."""
    game = Game(level, TUNING, 1)
    size = (min(int(level.width), WINDOW[0]), min(int(level.height), WINDOW[1]))
    screen = _open_window(f"ballbrawlla (sandbox: {level.name})", size)
    try:
        field = Field(level, TUNING)  # field levels get yard lines and end zones
    except ValueError:
        field = None                  # e.g. the small arena: not a football field
    renderer = Renderer(screen, field)
    camera = Camera(size)
    inputs = KeyboardInput()
    notes = SessionNotes("sandbox", _level_label(level))
    clock = pygame.time.Clock()
    pause = PauseMenu()
    dt = TUNING.dt
    accumulator = 0.0
    running = True
    while running:
        frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
        diag.beat()
        accumulator += frame_dt
        for event in pygame.event.get():
            diag.event(event)
            if notes.handle(event):
                continue
            if pause.handle(event, screen.get_size()):
                continue
            if event.type == pygame.QUIT:
                running = False
                _quit_app()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_F1:
                    renderer.debug = not renderer.debug
                elif event.key == pygame.K_F3:
                    renderer.show_controls = not renderer.show_controls
            action = inputs.handle_event(event)
            if action == "restart":
                game.reset()
            elif action == "debug":
                renderer.debug = not renderer.debug
        if notes.is_open:
            accumulator = 0.0                     # the sandbox pauses while you write notes
        if pause.result:
            running = False
        if pause.freezes:
            accumulator = 0.0
        while accumulator >= dt:
            game.step([inputs.consume()], dt)
            accumulator -= dt
        camera.follow(game.player.center, level, frame_dt)
        renderer.draw(game, clock.get_fps(), camera=camera.pos)
        pause.draw(screen)
        notes.draw(screen)
        pygame.display.flip()
    notes.save()


if __name__ == "__main__":
    run()
