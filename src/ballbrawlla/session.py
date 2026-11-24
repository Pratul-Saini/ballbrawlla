"""A match in progress: rules (rules/) + physics (game.Game) driven by humans' Intents.

Phase flow for every down:

    PLAY_CALL --both locked--> PRE_THROW --timer--> LIVE --play ends--> DEAD
        ^  |                                                              |
        |  +--15 s timeout: restart same play call                       |
        +------------------- next down (or GAME_OVER) <-------------------+

PRE_THROW is the route window. With Tuning.throw_enabled False (the default) it lasts
route_window_seconds, the WR already carries the ball, and neither the WR nor the Defender
may cross the line of scrimmage until the timer ends; then LIVE starts with nothing thrown.
With throw_enabled True it lasts pre_throw_seconds, the QB holds the ball and throws at zero.

Humans: index 0 is Team.LEFT (Blue), index 1 is Team.RIGHT (Red). On offense a
human controls the WR (the QB is placed in the play call and, with throwing on,
throws by itself); on defense they control the Defender. With one human (practice) the defense
never moves (or, with defender=False for catch practice, there is no defender), and after
a touchdown the human swaps to the other team and attacks the other end zone.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from enum import Enum

from ballbrawlla.config import Tuning
from ballbrawlla.entities.ball import Ball
from ballbrawlla.entities.player import Player
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.rules.down import Down, Outcome, PlayResult
from ballbrawlla.rules.field import Field, Spot
from ballbrawlla.rules.match import Match
from ballbrawlla.rules.play_call import CallMemory, PlayCall
from ballbrawlla.rules.teams import CAN_THROW, Role, Team
from ballbrawlla.world.level import Level


class Phase(str, Enum):
    WAITING = "waiting"      # network: not every human has joined yet
    PLAY_CALL = "play_call"
    PRE_THROW = "pre_throw"  # the route window: free running behind the line of scrimmage (QB holds the ball if throwing)
    LIVE = "live"            # ball thrown: in the air, loose, or carried
    DEAD = "dead"            # play over; showing the result
    GAME_OVER = "game_over"


def ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


class Session:
    def __init__(self, level: Level, tuning: Tuning, humans: int = 1, seed: int | None = None,
                 defender: bool = True) -> None:
        if humans not in (1, 2):
            raise ValueError("a session has 1 (practice) or 2 humans")
        self.level = level
        self.t = tuning
        self.field = Field(level, tuning)
        self.humans = humans
        self.practice = humans == 1
        # Catch practice: no defender at all. One human only; a 2-human game always has a defender.
        self.defender = defender or humans == 2
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
        self._follow_human_team()
        self.memory = CallMemory()
        self.call: PlayCall | None = None
        self.game: Game | None = None
        self.qb: Player | None = None
        self.qb_spot: Spot | None = None
        self.result: PlayResult | None = None
        self.message = ""
        self.timer = 0.0
        self.loose_timer: float | None = None
        self.los_x: float | None = None     # line of scrimmage x while the route window locks both sides
        if all(self.connected):
            self._start_play_call()
        else:
            self.phase = Phase.WAITING

    def _follow_human_team(self) -> None:
        """Practice: the human plays whichever team the match says (it swaps after a touchdown)."""
        if self.practice:
            self.team_of_human = [self.match.human]

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

        throwing = self.t.throw_enabled
        if throwing:
            # WR: next to the QB, toward the defense's end zone.
            wr_x = c.qb_spot.x + off.attack_dir * (self.t.player_width + 4)
            wr_spot = self.field.spawn_spot(Spot(wr_x, c.qb_spot.y), wr_x, wr_x)
        else:
            wr_spot = self._route_wr_spot(c.qb_spot, off)
        wr = self._make_actor(wr_spot, Role.WR, off, pid=0)
        actors = [wr]
        if self.defender:
            df = self._make_actor(c.def_spot, Role.DEF, dfn, pid=1)
            df.facing = dfn.attack_dir
            actors.append(df)

        game = Game(self.level, self.t, num_players=len(actors))
        game.players = actors
        holder = qb if throwing else wr
        ball = Ball(holder.hand_pos(), self.t)
        ball.held_by = holder
        holder.held_ball = ball
        game.ball = ball
        game.ball_trail.clear()

        self.game, self.qb, self.qb_spot = game, qb, c.qb_spot
        self.loose_timer = None
        self.phase = Phase.PRE_THROW
        if throwing:
            self.timer = self.t.pre_throw_seconds
        else:
            self.timer = self.t.route_window_seconds
            self._lock_line_of_scrimmage(c.qb_spot.x, off, actors)

    def _route_wr_spot(self, qb_spot: Spot, off: Team) -> Spot:
        """No-throw WR spawn: 28 px behind the QB (toward the offense's own end zone), always on its side of the line."""
        wr_x = qb_spot.x - off.attack_dir * (self.t.player_width + 4)
        if off.attack_dir > 0:
            lo, hi = self.field.inner_left, qb_spot.x
        else:
            lo, hi = qb_spot.x, self.field.inner_right
        return self.field.snap(Spot(wr_x, qb_spot.y), lo, hi) or qb_spot

    def _lock_line_of_scrimmage(self, los: float, off: Team, actors: list[Player]) -> None:
        """Wall the WR (and Defender) off from the far side of the line for the route window.

        Each gets one full-height solid whose face is half a player width past the line, so their
        centers can reach it but not cross. Edges are whole pixels (plus a hair) so a fractional
        edge can never leave a 1-ulp overlap, which the Y pass would resolve by teleporting."""
        w = self.t.player_width
        big = float(self.level.width)
        tall = self.level.height + 2 * big
        d = off.attack_dir
        ahead = AABB(float(math.ceil(los + w / 2 + 1e-6)), -big, big, tall)        # right of the line
        behind = AABB(float(math.floor(los - w / 2 - 1e-6)) - big, -big, big, tall)  # left of the line
        barriers = {0: ahead if d > 0 else behind}
        if len(actors) > 1:
            barriers[1] = behind if d > 0 else ahead
        if any(actors[i].box.overlaps(b) for i, b in barriers.items()):
            return          # illegal spawn (see Field.spawn_spot): run the window without a line
        self.game.barriers = barriers
        self.los_x = los

    def _step_execution(self, off_i: Intent, def_i: Intent, dt: float) -> None:
        g = self.game
        wr = g.players[0]
        df = g.players[1] if len(g.players) > 1 else None      # None in catch practice
        g.step([off_i, def_i], dt)

        if self.phase is Phase.PRE_THROW:
            self.timer -= dt
            if self.timer <= 0:
                if self.t.throw_enabled:
                    self.qb.throw()
                else:
                    g.barriers.clear()
                    self.los_x = None
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
        if tagger is not None and tag_intent.z_pressed and tagger.center.distance_to(carrier.center) <= self.t.tag_radius:
            spot = Spot(carrier.last_ground.x, carrier.last_ground.y)
            self._end(PlayResult(Outcome.TAGGED if is_wr else Outcome.INTERCEPTION_TAGGED, spot))

    def _end(self, result: PlayResult) -> None:
        before = self.down
        self.result = result
        scorer = self.match.apply(result)
        self._follow_human_team()
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
