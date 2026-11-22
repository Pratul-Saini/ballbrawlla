"""Entry point: window + fixed-timestep loop. Physics runs at Tuning.physics_hz
regardless of frame rate.

    ballbrawlla                     practice: you on offense vs a defender that stands still
    ballbrawlla --host              host a 2-player LAN match (you are Blue)
    ballbrawlla --join 192.168.x.y  join a LAN match (you are Red)
    ballbrawlla --local             two players on one screen (Blue: WASD + F/G, Red: arrows + . and /)
    ballbrawlla --sandbox           free play in the small arena (physics tuning, no rules)
    ballbrawlla --sandbox --level field_01   free play on the big match field
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import pygame

from ballbrawlla.config import TUNING, Tuning
from ballbrawlla.game import Game
from ballbrawlla.gamepad import Gamepads
from ballbrawlla.input import BLUE_KEYS, RED_KEYS, KeyboardInput
from ballbrawlla.net.client import Client
from ballbrawlla.net.host import Host
from ballbrawlla.net.protocol import DEFAULT_PORT, lan_ip
from ballbrawlla.net.view import make_view
from ballbrawlla.notes import SessionNotes
from ballbrawlla.render.match_renderer import Camera, MatchRenderer
from ballbrawlla.render.renderer import Renderer
from ballbrawlla.rules.field import Field
from ballbrawlla.session import Session
from ballbrawlla.world.level import Level, level_from_dict, level_to_dict, load_level

LEVELS = Path(__file__).resolve().parents[2] / "levels"
DEFAULT_LEVEL = LEVELS / "field_01.json"
SANDBOX_LEVEL = LEVELS / "arena_01.json"
WINDOW = (1280, 720)
MAX_FRAME_TIME = 0.25  # avoid a spiral of death after a stall


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ballbrawlla")
    parser.add_argument("--level", type=Path, default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true", help="host a local network match")
    mode.add_argument("--join", metavar="ADDRESS", help="join a host at this IP address")
    mode.add_argument("--sandbox", action="store_true", help="free play, no rules")
    mode.add_argument("--local", action="store_true", help="two players on one screen")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if args.level is not None and not args.level.exists():
        named = LEVELS / f"{args.level.stem}.json"  # allow --level field_01
        if named.exists():
            args.level = named

    pygame.init()
    try:
        if args.join:
            run_client(args.join, args.port)
        elif args.sandbox:
            run_sandbox(load_level(args.level or SANDBOX_LEVEL))
        elif args.local:
            run_couch(load_level(args.level or DEFAULT_LEVEL))
        else:
            run_match(load_level(args.level or DEFAULT_LEVEL), host=args.host, port=args.port)
    finally:
        pygame.quit()


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
    screen = pygame.display.set_mode(size, pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption(title)
    return screen


def run_match(level: Level, host: bool = False, port: int = DEFAULT_PORT) -> None:
    """Practice (1 human) or the hosting player (who also runs the simulation)."""
    session = Session(level, TUNING, humans=2 if host else 1)

    server: Host | None = None
    address = ""
    if host:
        server = Host(
            welcome={"level": level_to_dict(level), "tuning": asdict(TUNING)},
            max_players=2,
            port=port,
        )
        address = f"{lan_ip()}:{server.port}"
        print(f"Hosting on {address} - the other player joins with: ballbrawlla --join {lan_ip()}")

    screen = _open_window("ballbrawlla (host, Blue)" if host else "ballbrawlla (practice)")
    renderer = MatchRenderer(screen, level, session.field, TUNING)
    inputs = KeyboardInput()
    notes = SessionNotes("host" if host else "practice", _level_label(level),
                         context=lambda: _match_context(lambda: make_view(session, 0)))
    clock = pygame.time.Clock()
    dt = TUNING.dt
    accumulator = 0.0

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
            accumulator += frame_dt

            for event in pygame.event.get():
                if notes.handle(event):
                    continue
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        session.new_match()
                    elif event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                action = inputs.handle_event(event, renderer.button_hit)
                if action == "restart":
                    session.new_match()
                elif action == "debug":
                    renderer.debug = not renderer.debug

            if server:
                joined, left = server.poll()
                for pid in joined:
                    session.set_connected(pid, True)
                for pid in left:
                    session.set_connected(pid, False)

            stepped = False
            if notes.is_open and not server:
                accumulator = 0.0                 # practice pauses while you write notes
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

            status = f"hosting on {address}" if server else "R / Options: restart   F1: debug   Esc: quit"
            status += "   F2: notes" + _pad_status(inputs)
            renderer.draw(make_view(session, 0), clock.get_fps(), frame_dt, status)
            notes.draw(screen)
            pygame.display.flip()
    finally:
        notes.save()
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
    dt = TUNING.dt
    accumulator = 0.0

    running = True
    while running:
        frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
        accumulator += frame_dt

        for event in pygame.event.get():
            if notes.handle(event):
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F5:
                    session.new_match()
                elif event.key == pygame.K_F1:
                    renderer.debug = not renderer.debug
            action = pads.handle_event(event)
            if action == "restart":
                session.new_match()
            elif action == "debug":
                renderer.debug = not renderer.debug
            for inp in players:
                inp.handle_event(event, renderer.button_hit)

        if notes.is_open:
            accumulator = 0.0                     # local play pauses while you write notes
        while accumulator >= dt:
            offense = session.human_of(session.down.offense)
            cam = renderer.camera
            intents = [inp.consume(cam.pos, cam.zoom, use_mouse=(pid == offense))
                       for pid, inp in enumerate(players)]
            session.step(intents, dt)
            accumulator -= dt

        names = pads.names
        status = (f"Blue: {BLUE_KEYS.label}   Red: {RED_KEYS.label}   |   "
                  + (f"controllers: {', '.join(names)}   |   " if names else "")
                  + "F5: new match   F1: debug   F2: notes   Esc: quit")
        renderer.draw(make_view(session, 0, local=True), clock.get_fps(), frame_dt, status)
        notes.draw(screen)
        pygame.display.flip()
    notes.save()


def run_client(address: str, port: int = DEFAULT_PORT) -> None:
    """Sends input to the host and draws the view it sends back."""
    print(f"Connecting to {address}:{port} ...")
    try:
        client = Client(address, port)
    except ConnectionError as e:
        print(f"Could not join: {e}", file=sys.stderr)
        return

    level = level_from_dict(client.level_data)
    tuning = Tuning(**client.tuning_data)
    screen = _open_window("ballbrawlla (Red)")
    renderer = MatchRenderer(screen, level, Field(level, tuning), tuning)
    inputs = KeyboardInput()
    clock = pygame.time.Clock()
    dt = tuning.dt
    accumulator = 0.0
    view: dict | None = None
    notes = SessionNotes("join", _level_label(level), context=lambda: _match_context(lambda: view))

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
            accumulator += frame_dt

            for event in pygame.event.get():
                if notes.handle(event):
                    continue
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                if inputs.handle_event(event, renderer.button_hit) == "debug":
                    renderer.debug = not renderer.debug

            # Send input at the simulation rate so press edges line up with host ticks.
            while accumulator >= dt:
                client.send_intent(notes.gate(inputs.consume(renderer.camera.pos)))
                accumulator -= dt

            latest = client.latest_snapshot()
            if latest is not None:
                view = latest

            status = f"connected to {address}:{port}"
            if client.closed:
                status = "disconnected from host - press Esc to quit"
            status += "   F2: notes" + _pad_status(inputs)
            if view is not None:
                renderer.draw(view, clock.get_fps(), frame_dt, status)
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
    dt = TUNING.dt
    accumulator = 0.0
    running = True
    while running:
        frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
        accumulator += frame_dt
        for event in pygame.event.get():
            if notes.handle(event):
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_F1:
                    renderer.debug = not renderer.debug
            action = inputs.handle_event(event)
            if action == "restart":
                game.reset()
            elif action == "debug":
                renderer.debug = not renderer.debug
        if notes.is_open:
            accumulator = 0.0                     # the sandbox pauses while you write notes
        while accumulator >= dt:
            game.step([inputs.consume()], dt)
            accumulator -= dt
        camera.follow(game.player.center, level, frame_dt)
        renderer.draw(game, clock.get_fps(), camera=camera.pos)
        notes.draw(screen)
        pygame.display.flip()
    notes.save()


if __name__ == "__main__":
    run()
