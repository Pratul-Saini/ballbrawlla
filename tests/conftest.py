import os

os.environ.setdefault("BALLBRAWLLA_MUSIC", "off")   # tests must never play (or load) the real song

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.world.level import Level, Platform


def make_game(platforms=(), player=(200, 650), ball=(600, 650), players=None, thin=(), **tuning) -> Game:
    """`players` is a list of spawn centers; defaults to a single player at `player`.
    `thin` is a list of (x, y, w, h) one-way platforms, added after the solid `platforms`."""
    spawns = players or [player]
    level = Level(
        width=1280,
        height=720,
        platforms=[Platform(AABB(*p)) for p in platforms]
        + [Platform(AABB(*p), platform_type="thin") for p in thin],
        player_spawns=[Vector2(s) for s in spawns],
        ball_spawn=Vector2(ball),
    )
    return Game(level, Tuning(**tuning), num_players=len(spawns))


def run(game: Game, intent: Intent | list[Intent] | None = None, ticks: int = 1) -> None:
    """Step the game. A single Intent drives player 0; others idle."""
    if intent is None or isinstance(intent, Intent):
        intents = [intent or Intent()] + [Intent()] * (game.num_players - 1)
    else:
        intents = intent
    for _ in range(ticks):
        game.step(intents, game.t.dt)


@pytest.fixture
def settled():
    """Player standing on the floor, ball resting far away."""
    g = make_game()
    run(g, ticks=60)
    return g
