"""Match: score, current down, and the winner."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ballbrawlla.config import Tuning
from ballbrawlla.rules.down import Down, PlayResult, next_down, possession_start
from ballbrawlla.rules.teams import Team


@dataclass
class Match:
    t: Tuning
    down: Down
    score: dict[Team, int] = field(default_factory=lambda: {Team.LEFT: 0, Team.RIGHT: 0})
    winner: Team | None = None
    practice: bool = False  # single player: Team.LEFT is always on offense

    @classmethod
    def start(cls, t: Tuning, rng: random.Random | None = None, practice: bool = False) -> "Match":
        """Coin flip for the first offense (practice: always Team.LEFT)."""
        first = Team.LEFT if practice else (rng or random).choice([Team.LEFT, Team.RIGHT])
        return cls(t=t, down=possession_start(first, t), practice=practice)

    def apply(self, result: PlayResult) -> Team | None:
        """Advance past a finished play. Returns the scoring team, if any."""
        nxt, scorer = next_down(self.down, result, self.t)
        if scorer is not None:
            self.score[scorer] += 1
            if self.score[scorer] >= self.t.touchdowns_to_win:
                self.winner = scorer
        if self.practice and nxt.offense is not Team.LEFT:
            nxt = possession_start(Team.LEFT, self.t)
        self.down = nxt
        return scorer
