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
    practice: bool = False  # single player: the human is always on offense
    human: Team = Team.LEFT  # practice only: the team the human plays; swaps after a touchdown

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
        if self.practice:
            if scorer is not None:
                self.human = nxt.offense                     # touchdown: you swap sides and attack the other end zone
            elif nxt.offense is not self.human:
                nxt = possession_start(self.human, self.t)   # turnover on downs: you keep the ball
        self.down = nxt
        return scorer
