"""Downs: what a down is, where its players may spawn, and what follows it.

Every down is played the same way (play call, then execution). The only thing
that differs between downs is how the QB's spawn is decided:

* ChooseInRegion - 1st down of a possession that starts from the offense's own
  end (match start, after a score, after a turnover on downs). The offense
  drags the QB anywhere in a region; the defense watches it live.
* FixedSpot - downs 2-4, and 1st down after an interception. The QB starts
  where the last play died.

So a Down is (number, offense, qb_spawn) and the rest of the game is shared.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ballbrawlla.config import Tuning
from ballbrawlla.rules.field import Field, Spot
from ballbrawlla.rules.teams import Team


@dataclass(frozen=True)
class ChooseInRegion:
    """Offense picks the QB spot; yards are from the offense's own goal line."""

    start_yards: float
    end_yards: float


@dataclass(frozen=True)
class FixedSpot:
    spot: Spot


SpawnRule = ChooseInRegion | FixedSpot


@dataclass(frozen=True)
class Down:
    number: int  # 1..downs_per_possession
    offense: Team
    qb_spawn: SpawnRule

    @property
    def defense(self) -> Team:
        return self.offense.other

    @property
    def offense_picks_spawn(self) -> bool:
        return isinstance(self.qb_spawn, ChooseInRegion)


def possession_start(offense: Team, t: Tuning) -> Down:
    """1st down from the offense's own end, QB placed by the offense."""
    return Down(1, offense, ChooseInRegion(t.qb_region_start_yards, t.qb_region_end_yards))


# ---------------------------------------------------------------- spawn ranges

def qb_x_range(down: Down, field: Field) -> tuple[float, float]:
    """Where the QB's center x may be. A fixed spot is never inside the
    offense's own end zone (it is pushed out to the goal line)."""
    if isinstance(down.qb_spawn, ChooseInRegion):
        r = down.qb_spawn
        return field.x_range(down.offense, r.start_yards, r.end_yards)
    x = down.qb_spawn.spot.x
    if field.in_end_zone(down.offense, x):
        x = field.goal_line_x(down.offense)
    return (x, x)


def qb_furthest_yards(down: Down, field: Field) -> float:
    """Furthest the QB can be from the offense's goal line on this down."""
    if isinstance(down.qb_spawn, ChooseInRegion):
        return down.qb_spawn.end_yards
    lo, _ = qb_x_range(down, field)
    return field.yards_from_goal(down.offense, lo)


def defender_min_yards(down: Down, field: Field, t: Tuning) -> float:
    """Closest (in yards from the offense's goal line) the Defender may spawn.

    At least `defender_gap_yards` past the furthest the QB could be, but the
    defense's own end zone is always allowed. Because this uses the QB's
    *furthest possible* spot, it doesn't change while the offense drags the QB
    on 1st down (with the defaults: the offense's 20-yard line)."""
    return min(qb_furthest_yards(down, field) + t.defender_gap_yards, t.field_yards)


def defender_x_range(down: Down, field: Field, t: Tuning) -> tuple[float, float]:
    far = t.field_yards + t.end_zone_yards  # the defense's back wall
    return field.x_range(down.offense, defender_min_yards(down, field, t), far)


# ---------------------------------------------------------------- results

class Outcome(str, Enum):
    TOUCHDOWN = "touchdown"                    # WR reached the defense's end zone
    TAGGED = "tagged"                          # Defender tagged the WR carrying the ball
    DEAD_BALL = "dead_ball"                    # ball landed and nobody picked it up in time
    INTERCEPTION_TAGGED = "interception_tagged"  # Defender caught it, then the WR tagged them
    PICK_SIX = "pick_six"                      # Defender caught it and reached the offense's end zone


@dataclass(frozen=True)
class PlayResult:
    outcome: Outcome
    spot: Spot | None = None  # where the next play starts from (None after a score)


def next_down(down: Down, result: PlayResult, t: Tuning) -> tuple[Down, Team | None]:
    """The down that follows `result`, and the team that scored (if any)."""
    o = result.outcome
    if o is Outcome.TOUCHDOWN:
        return possession_start(down.defense, t), down.offense
    if o is Outcome.PICK_SIX:
        # The team that was scored on gets the ball back.
        return possession_start(down.offense, t), down.defense
    if o is Outcome.INTERCEPTION_TAGGED:
        return Down(1, down.defense, FixedSpot(result.spot)), None
    # TAGGED or DEAD_BALL: same offense, next down - unless that was the last one.
    if down.number >= t.downs_per_possession:
        return possession_start(down.defense, t), None
    return Down(down.number + 1, down.offense, FixedSpot(result.spot)), None
