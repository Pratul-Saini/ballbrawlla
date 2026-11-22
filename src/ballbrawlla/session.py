"""A match in progress: rules (rules/) + physics (game.Game) driven by humans' Intents.

Phase flow for every down:

    PLAY_CALL --both locked--> PRE_THROW --10 s, QB throws--> LIVE --play ends--> DEAD
        ^  |                                                                     |
        |  +--15 s timeout: restart same play call                             |
        +------------------- next down (or GAME_OVER) <--------------------------+

Humans: index 0 is Team.LEFT (Blue), index 1 is Team.RIGHT (Red). On offense a
human controls the WR (the QB is placed in the play call and throws by itself);
on defense they control the Defender. With one human (practice) the defense
never moves.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from enum import Enum

from ballbrawlla.config import Tuning
from ballbrawlla.entities.ball import Ball
from ballbrawlla.entities.player import Player
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.rules.down import Down, Outcome, PlayResult
from ballbrawlla.rules.field import Field, Spot
from ballbrawlla.rules.match import Match
from ballbrawlla.rules.play_call import CallMemory, PlayCall
from ballbrawlla.rules.teams import CAN_THROW, Role, Team
from ballbrawlla.world.level import Level


class Phase(str, Enum):
    WAITING = "waiting"      # network: not every human has joined yet
    PLAY_CALL = "play_call"
    PRE_THROW = "pre_throw"  # free running; QB holds the ball
    LIVE = "live"            # ball thrown: in the air, loose, or carried
    DEAD = "dead"            # play over; showing the result
    GAME_OVER = "game_over"


def ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


class Session:
    def __init__(self, level: Level, tuning: Tuning, humans: int = 1, seed: int | None = None) -> None:
        if humans not in (1, 2):
            raise ValueError("a session has 1 (practice) or 2 humans")
        self.level = level
        self.t = tuning
        self.field = Field(level, tuning)
        self.humans = humans
        self.practice = humans == 1
        self.team_of_human = [Team.LEFT, Team.RIGHT][:humans]
        self.connected = [True] + [False] * (humans - 1)
        self.rng = random.Random(seed)
        self.tick = 0
        self.new_match()

    # ------------------------------------------------------------ setup

    def human_of(self, team: Team) -> int | None:
        return self.team_of_human.index(team) if team in self.team_of_human else None

    def set_connected(self, pid: int, connected: bool) -> None:
        """A human joined or left. Either way a fresh match starts (or waits)."""
        self.connected[pid] = connected
        self.new_match()

    def new_match(self) -> None:
        self.match = Match.start(self.t, self.rng, practice=self.practice)
        self.memory = CallMemory()
        self.call: PlayCall | None = None
        self.game: Game | None = None
        self.qb: Player | None = None
        self.qb_spot: Spot | None = None
        self.result: PlayResult | None = None
        self.message = ""
        self.timer = 0.0
        self.loose_timer: float | None = None
        if all(self.connected):
            self._start_play_call()
        else:
            self.phase = Phase.WAITING

    @property
    def down(self) -> Down:
        return self.match.down

    # ------------------------------------------------------------ tick

    def step(self, intents: Sequence[Intent], dt: float) -> None:
        """One physics tick. `intents[i]` is human i's input."""
        intents = list(intents) + [Intent()] * (self.humans - len(intents))
        self.tick += 1
        off_i = self._intent_for(self.down.offense, intents)
        def_i = self._intent_for(self.down.defense, intents)

        if self.phase is Phase.PLAY_CALL:
            if self.call.update(off_i, def_i, dt):
                self._start_execution()
        elif self.phase in (Phase.PRE_THROW, Phase.LIVE):
            self._step_execution(off_i, def_i, dt)
        elif self.phase is Phase.DEAD:
            self.timer -= dt
            if self.timer <= 0:
                if self.match.winner is not None:
                    self.phase = Phase.GAME_OVER
                    s = self.match.score
                    self.message = (
                        f"{self.match.winner.display} wins {s[Team.LEFT]}-{s[Team.RIGHT]}"
                    )
                else:
                    self._start_play_call()

    def _intent_for(self, team: Team, intents: list[Intent]) -> Intent:
        pid = self.human_of(team)
        return intents[pid] if pid is not None else Intent()

    # ------------------------------------------------------------ phases

    def _start_play_call(self) -> None:
        self.phase = Phase.PLAY_CALL
        self.call = PlayCall(
            self.down,
            self.field,
            self.t,
            self.memory,
            defense_auto=self.human_of(self.down.defense) is None,
        )
        self.message = ""

    def _make_actor(self, spot: Spot, role: Role, team: Team, pid: int) -> Player:
        p = Player(spot.center(self.t.player_height), self.t, pid=pid)
        p.role = role
        p.team = team
        p.can_throw = CAN_THROW[role]
        p.facing = team.attack_dir
        return p

    def _start_execution(self) -> None:
        c = self.call
        d = self.down
        c.remember(self.memory)
        off, dfn = d.offense, d.defense

        qb = self._make_actor(c.qb_spot, Role.QB, off, pid=2)
        qb.aim_angle, qb.aim_power = c.aim_angle, c.aim_power

        # WR: next to the QB, toward the defense's end zone.
        wr_x = c.qb_spot.x + off.attack_dir * (self.t.player_width + 4)
        wr_spot = self.field.spawn_spot(Spot(wr_x, c.qb_spot.y), wr_x, wr_x)
        wr = self._make_actor(wr_spot, Role.WR, off, pid=0)
        df = self._make_actor(c.def_spot, Role.DEF, dfn, pid=1)
        df.facing = dfn.attack_dir

        game = Game(self.level, self.t, num_players=2)
        game.players = [wr, df]
        ball = Ball(qb.hand_pos(), self.t)
        ball.held_by = qb
        qb.held_ball = ball
        game.ball = ball
        game.ball_trail.clear()

        self.game, self.qb, self.qb_spot = game, qb, c.qb_spot
        self.loose_timer = None
        self.phase = Phase.PRE_THROW
        self.timer = self.t.pre_throw_seconds

    def _step_execution(self, off_i: Intent, def_i: Intent, dt: float) -> None:
        g = self.game
        wr, df = g.players
        g.step([off_i, def_i], dt)

        if self.phase is Phase.PRE_THROW:
            self.timer -= dt
            if self.timer <= 0:
                self.qb.throw()
                self.phase = Phase.LIVE
            return

        ball = g.ball
        carrier = ball.held_by
        if carrier is None:
            # "Landed" = the ball has stopped moving. Then 3 s to pick it up.
            if self.loose_timer is None:
                if ball.resting and ball.vel.length() < self.t.ball_stopped_speed:
                    self.loose_timer = self.t.loose_ball_seconds
            else:
                self.loose_timer -= dt
                if self.loose_timer <= 0:
                    self._end(PlayResult(Outcome.DEAD_BALL, self.qb_spot))
            return
        self.loose_timer = None

        is_wr = carrier is wr
        goal_team = self.down.defense if is_wr else self.down.offense
        if carrier.contacts.on_ground and self.field.in_end_zone(goal_team, carrier.center.x):
            self._end(PlayResult(Outcome.TOUCHDOWN if is_wr else Outcome.PICK_SIX))
            return

        tagger, tag_intent = (df, def_i) if is_wr else (wr, off_i)
        if tag_intent.z_pressed and tagger.center.distance_to(carrier.center) <= self.t.tag_radius:
            spot = Spot(carrier.last_ground.x, carrier.last_ground.y)
            self._end(PlayResult(Outcome.TAGGED if is_wr else Outcome.INTERCEPTION_TAGGED, spot))

    def _end(self, result: PlayResult) -> None:
        before = self.down
        self.result = result
        scorer = self.match.apply(result)
        self.message = describe(before, result, scorer, self.down)
        self.phase = Phase.DEAD
        self.timer = self.t.result_pause_seconds


def describe(before: Down, result: PlayResult, scorer: Team | None, after: Down) -> str:
    o = result.outcome
    if o is Outcome.TOUCHDOWN:
        return f"Touchdown {before.offense.display}!"
    if o is Outcome.PICK_SIX:
        return f"Pick six! {before.defense.display} scores"
    if o is Outcome.INTERCEPTION_TAGGED:
        return f"Interception! {after.offense.display} ball, 1st down"
    what = "Tagged" if o is Outcome.TAGGED else "Ball dead"
    if after.offense is before.offense:
        return f"{what} - {ordinal(after.number)} down"
    return f"{what} - turnover on downs, {after.offense.display} ball"
