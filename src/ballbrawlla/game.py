"""Simulation root: owns the level, players and ball and advances them one tick.

No rendering, windowing or networking here, so tests (and the network host)
can drive it directly with one Intent per player.
"""

from collections import deque
from collections.abc import Sequence

from ballbrawlla.config import Tuning
from ballbrawlla.entities.ball import Ball
from ballbrawlla.entities.player import Player
from ballbrawlla.input import Intent
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.world.level import Level


class Game:
    def __init__(self, level: Level, tuning: Tuning, num_players: int = 1) -> None:
        self.level = level
        self.t = tuning
        self.num_players = num_players
        self.players: list[Player] = []
        # Recent Free-ball centers (newest last); empty while the ball is Held.
        self.ball_trail: deque[Vector2] = deque(maxlen=tuning.pickup_grace_ticks + 1)
        self.reset()

    @property
    def player(self) -> Player:
        """The first player (convenience for single-player and tests)."""
        return self.players[0]

    def _spawn(self, pid: int) -> Player:
        return Player(self.level.spawn_for(pid), self.t, pid=pid)

    def reset(self) -> None:
        connected = [p.connected for p in self.players] or [True] * self.num_players
        self.players = [self._spawn(i) for i in range(self.num_players)]
        for p, c in zip(self.players, connected):
            p.connected = c
        self.ball = Ball(self.level.ball_spawn, self.t)
        self.ball_trail.clear()

    def reset_player(self, pid: int, connected: bool = True) -> None:
        """Respawn one player (e.g. on join/leave), dropping the ball if they held it."""
        old = self.players[pid]
        if self.ball.held_by is old:
            self.ball.release(old.center, Vector2())
        self.ball_trail.clear()
        self.players[pid] = self._spawn(pid)
        self.players[pid].connected = connected

    def step(self, intents: Sequence[Intent], dt: float) -> None:
        for p, intent in zip(self.players, intents):
            if p.connected:
                p.update(
                    intent,
                    dt,
                    self.level.solids,
                    self.ball,
                    thin=self.level.thin,
                    ball_trail=self.ball_trail,
                )
        self._resolve_pickups()
        self.ball.update(dt, self.level.solids, thin=self.level.thin)
        if self.ball.held_by is None:
            self.ball_trail.append(Vector2(self.ball.pos))
        else:
            self.ball_trail.clear()

    def _resolve_pickups(self) -> None:
        """Players only *request* a pickup during their update; if several ask on
        the same tick, the one closest to the ball gets it."""
        requesters = [p for p in self.players if p.pickup_requested and p.ball_in_grace_reach()]
        for p in self.players:
            p.pickup_requested = False
        if not requesters:
            return
        winner = min(requesters, key=lambda p: (p.pickup_distance(), p.pid))
        winner.held_ball = self.ball
        self.ball.held_by = winner
        for p in self.players:
            p.pickup_buffer = 0
        self.ball_trail.clear()
