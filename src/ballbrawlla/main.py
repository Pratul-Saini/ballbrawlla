"""Window + fixed-timestep loop. Physics runs at Tuning.physics_hz regardless of frame rate."""

import argparse
from pathlib import Path

import pygame

from ballbrawlla.config import TUNING
from ballbrawlla.game import Game
from ballbrawlla.input import KeyboardInput
from ballbrawlla.render.renderer import Renderer
from ballbrawlla.world.level import load_level

DEFAULT_LEVEL = Path(__file__).resolve().parents[2] / "levels" / "arena_01.json"
MAX_FRAME_TIME = 0.25  # avoid a spiral of death after a stall


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ballbrawlla")
    parser.add_argument("--level", type=Path, default=DEFAULT_LEVEL)
    args = parser.parse_args(argv)

    pygame.init()
    level = load_level(args.level)
    screen = pygame.display.set_mode((int(level.width), int(level.height)), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("ballbrawlla")

    game = Game(level, TUNING)
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
            game.step(inputs.consume(), dt)
            accumulator -= dt

        renderer.draw(game, clock.get_fps())
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run()
