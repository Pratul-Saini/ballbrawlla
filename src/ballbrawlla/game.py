"""Simulation root: owns the level, player and ball and advances them one tick.

No rendering or windowing here, so tests can drive it directly.
"""

from ballbrawlla.config import Tuning
from ballbrawlla.entities.ball import Ball
from ballbrawlla.entities.player import Player
from ballbrawlla.input import Intent
from ballbrawlla.world.level import Level


class Game:
    def __init__(self, level: Level, tuning: Tuning) -> None:
        self.level = level
        self.t = tuning
        self.reset()

    def reset(self) -> None:
        self.player = Player(self.level.player_spawn, self.t)
        self.ball = Ball(self.level.ball_spawn, self.t)

    def step(self, intent: Intent, dt: float) -> None:
        self.player.update(intent, dt, self.level.solids, self.ball)
        self.ball.update(dt, self.level.solids)
