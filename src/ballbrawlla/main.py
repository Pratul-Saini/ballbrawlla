"""Entry point: window + fixed-timestep loop. Physics runs at Tuning.physics_hz
regardless of frame rate.

    ballbrawlla                     practice: you on offense vs a defender that stands still
    ballbrawlla --host              host a 2-player LAN match (you are Blue)
    ballbrawlla --join 192.168.x.y  join a LAN match (you are Red)
    ballbrawlla --sandbox           free play in the small arena (physics tuning, no rules)
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import pygame

from ballbrawlla.config import TUNING, Tuning
from ballbrawlla.game import Game
from ballbrawlla.input import KeyboardInput
from ballbrawlla.net.client import Client
from ballbrawlla.net.host import Host
from ballbrawlla.net.protocol import DEFAULT_PORT, lan_ip
from ballbrawlla.net.view import make_view
from ballbrawlla.render.match_renderer import MatchRenderer
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
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    pygame.init()
    try:
        if args.join:
            run_client(args.join, args.port)
        elif args.sandbox:
            run_sandbox(load_level(args.level or SANDBOX_LEVEL))
        else:
            run_match(load_level(args.level or DEFAULT_LEVEL), host=args.host, port=args.port)
    finally:
        pygame.quit()


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
    clock = pygame.time.Clock()
    dt = TUNING.dt
    accumulator = 0.0

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
            accumulator += frame_dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        session.new_match()
                    elif event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                inputs.handle_event(event, renderer.button_hit)

            if server:
                joined, left = server.poll()
                for pid in joined:
                    session.set_connected(pid, True)
                for pid in left:
                    session.set_connected(pid, False)

            stepped = False
            while accumulator >= dt:
                intents = [inputs.consume(renderer.camera.pos)]
                if server:
                    intents.append(server.intent_for(1))
                session.step(intents, dt)
                accumulator -= dt
                stepped = True

            if server and stepped:
                for pid in server.clients:
                    server.send_to(pid, make_view(session, pid))

            status = f"hosting on {address}" if server else "R: restart   F1: debug   Esc: quit"
            renderer.draw(make_view(session, 0), clock.get_fps(), frame_dt, status)
            pygame.display.flip()
    finally:
        if server:
            server.close()


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

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
            accumulator += frame_dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                inputs.handle_event(event, renderer.button_hit)

            # Send input at the simulation rate so press edges line up with host ticks.
            while accumulator >= dt:
                client.send_intent(inputs.consume(renderer.camera.pos))
                accumulator -= dt

            latest = client.latest_snapshot()
            if latest is not None:
                view = latest

            status = f"connected to {address}:{port}"
            if client.closed:
                status = "disconnected from host - press Esc to quit"
            if view is not None:
                renderer.draw(view, clock.get_fps(), frame_dt, status)
            pygame.display.flip()
    finally:
        client.close()


def run_sandbox(level: Level) -> None:
    """The original free-play arena: one player, a ball, no rules."""
    game = Game(level, TUNING, 1)
    screen = _open_window("ballbrawlla (sandbox)", (int(level.width), int(level.height)))
    renderer = Renderer(screen)
    inputs = KeyboardInput()
    clock = pygame.time.Clock()
    dt = TUNING.dt
    accumulator = 0.0
    running = True
    while running:
        accumulator += min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_F1:
                    renderer.debug = not renderer.debug
            inputs.handle_event(event)
        while accumulator >= dt:
            game.step([inputs.consume()], dt)
            accumulator -= dt
        renderer.draw(game, clock.get_fps())
        pygame.display.flip()


if __name__ == "__main__":
    run()
