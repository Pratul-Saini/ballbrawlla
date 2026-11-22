"""Pure rules: field geometry, spawn ranges, and what follows each kind of play."""

import random

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.rules.down import (
    ChooseInRegion,
    Down,
    FixedSpot,
    Outcome,
    PlayResult,
    defender_min_yards,
    defender_x_range,
    next_down,
    possession_start,
    qb_x_range,
)
from ballbrawlla.rules.field import Field, Spot
from ballbrawlla.rules.match import Match
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import Level, Platform, load_level

T = Tuning(yard_px=8)  # 120 yards * 8 px = 960 px between the walls
FLOOR = 400 - 32


def small_field(platforms=()) -> Field:
    level = Level(width=1024, height=400, platforms=[Platform(AABB(*p)) for p in platforms])
    return Field(level, T)


# ---------------------------------------------------------------- field

def test_yard_lines_and_end_zones():
    f = small_field()
    assert f.goal_line_x(Team.LEFT) == 112 and f.goal_line_x(Team.RIGHT) == 912
    assert f.x_at(Team.LEFT, 50) == f.x_at(Team.RIGHT, 50) == 512
    assert f.x_at(Team.RIGHT, 10) == 832
    assert f.in_end_zone(Team.LEFT, 100) and not f.in_end_zone(Team.LEFT, 112)
    assert f.in_end_zone(Team.RIGHT, 950) and not f.in_end_zone(Team.RIGHT, 500)
    assert f.yards_from_goal(Team.RIGHT, 832) == pytest.approx(10)


def test_field_rejects_wrong_level_width():
    with pytest.raises(ValueError, match="inner width"):
        Field(Level(width=1280, height=400), T)


def test_real_field_level_matches_default_tuning():
    f = Field(load_level("levels/field_01.json"), Tuning())
    assert f.goal_line_x(Team.LEFT) == 272 and f.goal_line_x(Team.RIGHT) == 2672
    assert len(f.surfaces) > 20


def test_snap_stays_in_range_on_a_platform_top_and_avoids_obstacles():
    f = small_field(platforms=[(300, FLOOR - 60, 40, 60)])  # block on the floor
    s = f.snap(Vector2(0, 0), 150, 250)
    assert s == Spot(150, FLOOR)
    s = f.snap(Vector2(320, FLOOR - 70), 0, 1024)  # pointing just above the block: on top of it
    assert s.y == FLOOR - 60 and 300 <= s.x <= 340
    s = f.snap(Vector2(320, FLOOR + 50), 0, 1024)  # below it: next to it on the floor
    assert s.y == FLOOR and (s.x <= 300 - T.player_width / 2 or s.x >= 340 + T.player_width / 2)


# ---------------------------------------------------------------- spawn ranges

def test_first_down_qb_region_is_goal_line_to_10_yard_line():
    f = small_field()
    assert qb_x_range(possession_start(Team.LEFT, T), f) == (112, 192)
    assert qb_x_range(possession_start(Team.RIGHT, T), f) == (832, 912)


def test_first_down_defender_is_at_offense_20_or_deeper():
    f = small_field()
    d = possession_start(Team.LEFT, T)
    assert defender_min_yards(d, f, T) == 20
    assert defender_x_range(d, f, T) == (f.x_at(Team.LEFT, 20), 992)
    d = possession_start(Team.RIGHT, T)
    assert defender_x_range(d, f, T) == (32, f.x_at(Team.RIGHT, 20))


def test_later_downs_defender_10_yards_past_qb_but_end_zone_always_allowed():
    f = small_field()
    d = Down(2, Team.LEFT, FixedSpot(Spot(f.x_at(Team.LEFT, 50), FLOOR)))
    assert defender_min_yards(d, f, T) == pytest.approx(60)
    d = Down(3, Team.LEFT, FixedSpot(Spot(f.x_at(Team.LEFT, 95), FLOOR)))
    assert defender_min_yards(d, f, T) == 100  # only the end zone is left
    lo, hi = defender_x_range(d, f, T)
    assert lo == f.goal_line_x(Team.RIGHT) and hi == 992


def test_fixed_spot_inside_own_end_zone_is_pushed_to_goal_line():
    f = small_field()
    d = Down(2, Team.LEFT, FixedSpot(Spot(60, FLOOR)))
    assert qb_x_range(d, f) == (112, 112)


# ---------------------------------------------------------------- next down

def _fixed(n, team=Team.LEFT, x=400.0):
    return Down(n, team, FixedSpot(Spot(x, FLOOR)))


SPOT = Spot(450, FLOOR)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_tag_or_dead_ball_before_4th_down_is_next_down_from_spot(n):
    for outcome in (Outcome.TAGGED, Outcome.DEAD_BALL):
        nxt, scorer = next_down(_fixed(n), PlayResult(outcome, SPOT), T)
        assert nxt == Down(n + 1, Team.LEFT, FixedSpot(SPOT)) and scorer is None


def test_4th_down_failure_is_turnover_with_spawn_pick():
    for outcome in (Outcome.TAGGED, Outcome.DEAD_BALL):
        nxt, scorer = next_down(_fixed(4), PlayResult(outcome, SPOT), T)
        assert nxt == possession_start(Team.RIGHT, T) and scorer is None
        assert isinstance(nxt.qb_spawn, ChooseInRegion)


def test_touchdown_scores_and_gives_other_team_the_ball():
    nxt, scorer = next_down(_fixed(3), PlayResult(Outcome.TOUCHDOWN), T)
    assert scorer is Team.LEFT and nxt == possession_start(Team.RIGHT, T)


def test_pick_six_scores_for_defense_and_offense_gets_ball_back():
    nxt, scorer = next_down(_fixed(2), PlayResult(Outcome.PICK_SIX), T)
    assert scorer is Team.RIGHT and nxt == possession_start(Team.LEFT, T)


def test_interception_tagged_is_new_1st_down_at_tag_spot():
    nxt, scorer = next_down(_fixed(2), PlayResult(Outcome.INTERCEPTION_TAGGED, SPOT), T)
    assert scorer is None and nxt == Down(1, Team.RIGHT, FixedSpot(SPOT))
    assert not nxt.offense_picks_spawn


# ---------------------------------------------------------------- match

def test_coin_flip_can_go_either_way():
    firsts = {Match.start(T, random.Random(seed)).down.offense for seed in range(20)}
    assert firsts == {Team.LEFT, Team.RIGHT}


def test_first_to_five_touchdowns_wins():
    m = Match(t=T, down=possession_start(Team.LEFT, T))
    for i in range(4):
        m.down = possession_start(Team.LEFT, T)
        m.apply(PlayResult(Outcome.TOUCHDOWN))
        assert m.winner is None
    m.down = possession_start(Team.LEFT, T)
    m.apply(PlayResult(Outcome.TOUCHDOWN))
    assert m.winner is Team.LEFT and m.score[Team.LEFT] == 5


def test_practice_swaps_sides_after_a_touchdown():
    m = Match.start(T, practice=True)
    assert m.human is Team.LEFT and m.down.offense is Team.LEFT
    m.apply(PlayResult(Outcome.TOUCHDOWN))
    assert m.human is Team.RIGHT and m.down.offense is Team.RIGHT      # now attacking the other end zone
    m.apply(PlayResult(Outcome.TOUCHDOWN))
    assert m.human is Team.LEFT and m.down.offense is Team.LEFT        # and back again


def test_practice_keeps_the_ball_after_a_failed_play():
    m = Match.start(T, practice=True)
    m.apply(PlayResult(Outcome.TOUCHDOWN))                              # human is Red now
    for _ in range(T.downs_per_possession + 1):
        m.apply(PlayResult(Outcome.DEAD_BALL, SPOT))
        assert m.down.offense is Team.RIGHT and m.human is Team.RIGHT
