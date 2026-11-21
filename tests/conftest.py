import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.world.level import Level, Platform


def make_game(platforms=(), player=(200, 650), ball=(600, 650), **tuning) -> Game:
    level = Level(
        width=1280,
        height=720,
        platforms=[Platform(AABB(*p)) for p in platforms],
        player_spawn=Vector2(player),
        ball_spawn=Vector2(ball),
    )
    return Game(level, Tuning(**tuning))


def run(game: Game, intent: Intent | None = None, ticks: int = 1) -> None:
    intent = intent or Intent()
    for _ in range(ticks):
        game.step(intent, game.t.dt)


@pytest.fixture
def settled():
    """Player standing on the floor, ball resting far away."""
    g = make_game()
    run(g, ticks=60)
    return g
