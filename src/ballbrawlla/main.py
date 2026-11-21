"""Entry point: window + fixed-timestep loop. Physics runs at Tuning.physics_hz
regardless of frame rate.

    ballbrawlla                     single player
    ballbrawlla --host              host a LAN game (you are P1)
    ballbrawlla --join 192.168.x.y  join a LAN game
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
from ballbrawlla.net.snapshot import apply_snapshot, make_snapshot
from ballbrawlla.render.renderer import Renderer
from ballbrawlla.world.level import Level, level_from_dict, level_to_dict, load_level

DEFAULT_LEVEL = Path(__file__).resolve().parents[2] / "levels" / "arena_01.json"
MAX_FRAME_TIME = 0.25  # avoid a spiral of death after a stall


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ballbrawlla")
    parser.add_argument("--level", type=Path, default=DEFAULT_LEVEL)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true", help="host a local network game")
    mode.add_argument("--join", metavar="ADDRESS", help="join a host at this IP address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    pygame.init()
    try:
        if args.join:
            run_client(args.join, args.port)
        else:
            run_local(load_level(args.level), host=args.host, port=args.port)
    finally:
        pygame.quit()


def _open_window(level: Level, title: str) -> pygame.Surface:
    screen = pygame.display.set_mode(
        (int(level.width), int(level.height)), pygame.SCALED | pygame.RESIZABLE
    )
    pygame.display.set_caption(title)
    return screen


def run_local(level: Level, host: bool = False, port: int = DEFAULT_PORT) -> None:
    """Single player, or the hosting player (who also runs the simulation)."""
    num_players = TUNING.max_players if host else 1
    game = Game(level, TUNING, num_players)

    server: Host | None = None
    if host:
        server = Host(
            welcome={"level": level_to_dict(level), "tuning": asdict(TUNING)},
            max_players=num_players,
            port=port,
        )
        for p in game.players[1:]:
            p.connected = False
        address = f"{lan_ip()}:{server.port}"
        print(f"Hosting on {address} - others join with: ballbrawlla --join {lan_ip()}")

    screen = _open_window(level, "ballbrawlla (host)" if host else "ballbrawlla")
    renderer = Renderer(screen)
    inputs = KeyboardInput()
    clock = pygame.time.Clock()
    dt = TUNING.dt
    accumulator = 0.0
    tick = 0

    try:
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

            if server:
                joined, left = server.poll()
                for pid in joined:
                    game.reset_player(pid, connected=True)
                for pid in left:
                    game.reset_player(pid, connected=False)

            stepped = False
            while accumulator >= dt:
                intents = [inputs.consume()]
                if server:
                    intents += [server.intent_for(pid) for pid in range(1, num_players)]
                game.step(intents, dt)
                accumulator -= dt
                tick += 1
                stepped = True

            status = ""
            if server:
                if stepped:
                    server.broadcast(make_snapshot(game, tick))
                status = f"hosting on {address}   players {1 + len(server.clients)}/{num_players}"

            renderer.draw(game, clock.get_fps(), local_id=0, status=status)
            pygame.display.flip()
    finally:
        if server:
            server.close()


def run_client(address: str, port: int = DEFAULT_PORT) -> None:
    """Sends keyboard Intents to the host and draws the snapshots it sends back."""
    print(f"Connecting to {address}:{port} ...")
    try:
        client = Client(address, port)
    except ConnectionError as e:
        print(f"Could not join: {e}", file=sys.stderr)
        return

    level = level_from_dict(client.level_data)
    tuning = Tuning(**client.tuning_data)
    game = Game(level, tuning, tuning.max_players)

    screen = _open_window(level, f"ballbrawlla (P{client.pid + 1})")
    renderer = Renderer(screen)
    inputs = KeyboardInput()
    clock = pygame.time.Clock()
    dt = tuning.dt
    accumulator = 0.0

    try:
        running = True
        while running:
            accumulator += min(clock.tick(240) / 1000.0, MAX_FRAME_TIME)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_F1:
                        renderer.debug = not renderer.debug
                inputs.handle_event(event)

            # Send input at the simulation rate so press edges line up with host ticks.
            while accumulator >= dt:
                client.send_intent(inputs.consume())
                accumulator -= dt

            snap = client.latest_snapshot()
            if snap is not None:
                apply_snapshot(game, snap)

            status = f"connected to {address}:{port}"
            if client.closed:
                status = "disconnected from host - press Esc to quit"
            renderer.draw(game, clock.get_fps(), local_id=client.pid, status=status)
            pygame.display.flip()
    finally:
        client.close()


if __name__ == "__main__":
    run()
