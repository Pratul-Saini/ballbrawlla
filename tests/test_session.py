"""A match driven through Session.step: play call, execution, and play endings."""

import json

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.input import Intent
from ballbrawlla.net.view import make_view
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.rules.down import ChooseInRegion, FixedSpot, Outcome
from ballbrawlla.rules.field import Spot
from ballbrawlla.rules.teams import Team
from ballbrawlla.session import Phase, Session
from ballbrawlla.world.level import Level, Platform

FLOOR = 400 - 32
FAST = dict(yard_px=8, pre_throw_seconds=0.05, result_pause_seconds=0.05, throw_enabled=True)


def make_session(humans=2, seed=1, platforms=(), **tuning) -> Session:
    t = Tuning(**{**FAST, **tuning})
    level = Level(width=1024, height=400, platforms=[Platform(AABB(*p)) for p in platforms])
    s = Session(level, t, humans=humans, seed=seed)
    if humans == 2:
        s.set_connected(1, True)
    return s


def step(s: Session, off: Intent | None = None, dfn: Intent | None = None, ticks: int = 1):
    for _ in range(ticks):
        intents = [Intent() for _ in range(s.humans)]
        for team, it in ((s.down.offense, off), (s.down.defense, dfn)):
            pid = s.human_of(team)
            if it is not None and pid is not None:
                intents[pid] = it
        s.step(intents, s.t.dt)


def lock_in(s: Session):
    step(s, off=Intent(x_pressed=True), dfn=Intent(z_pressed=True))


def to_live(s: Session):
    lock_in(s)
    assert s.phase is Phase.PRE_THROW
    step(s, ticks=int(s.t.pre_throw_seconds * s.t.physics_hz) + 2)
    assert s.phase is Phase.LIVE


def give_ball(s: Session, actor):
    ball = s.game.ball
    ball.held_by, actor.held_ball = actor, ball


def place(actor, x, feet_y=FLOOR):
    actor.body.pos.update(x - actor.w / 2, feet_y - actor.h)
    actor.last_ground = Vector2(x, feet_y)


# ---------------------------------------------------------------- setup / play call

def test_network_match_waits_for_second_player():
    t = Tuning(**FAST)
    s = Session(Level(width=1024, height=400), t, humans=2)
    assert s.phase is Phase.WAITING
    s.set_connected(1, True)
    assert s.phase is Phase.PLAY_CALL and s.down.number == 1
    assert isinstance(s.down.qb_spawn, ChooseInRegion)


def test_qb_is_run_into_place_and_only_confirms_standing_in_its_zone():
    s = make_session()
    c = s.call
    off = s.down.offense
    fwd = off.attack_dir
    step(s, off=Intent(jump_pressed=True, vertical=1))           # jump in place
    step(s, off=Intent(vertical=1), ticks=5)
    assert c.qb_player.state.name == "airborne" and not c.qb_ok
    step(s, off=Intent(z_pressed=True, x_pressed=True, vertical=1))
    assert c.placing and not c.offense_locked                    # can't confirm mid-air
    step(s, ticks=60)                                             # land
    assert c.qb_ok
    step(s, off=Intent(move_x=fwd), ticks=30)                     # run past the 10-yard line
    assert s.field.yards_from_goal(off, c.qb_player.center.x) > s.t.qb_region_end_yards
    assert not c.qb_ok
    step(s, off=Intent(z_pressed=True))
    assert c.placing                                              # can't confirm outside the zone
    step(s, off=Intent(move_x=-fwd), ticks=20)                    # back into the zone
    assert c.qb_ok
    step(s, off=Intent(z_pressed=True))
    assert not c.placing                                          # confirmed where it stands
    assert (c.qb_spot.x, c.qb_spot.y) == pytest.approx((c.qb_player.center.x, FLOOR))
    x = c.qb_player.center.x
    step(s, off=Intent(move_x=fwd), ticks=20)                     # now the arrows aim, the QB stays put
    assert c.qb_player.center.x == pytest.approx(x)
def test_confirm_then_aim_with_mouse_then_lock():
    s = make_session()
    c = s.call
    step(s, off=Intent(button_pressed=True))  # confirm QB spot
    assert not c.placing and not c.offense_locked
    qb = c.qb_center()
    target = qb + Vector2(0, -s.t.aim_drag_radius)  # straight up, full distance
    step(s, off=Intent(mouse=tuple(target), mouse_pressed=True, mouse_held=True))
    assert c.aim_angle == pytest.approx(90) and c.aim_power == pytest.approx(s.t.power_max)
    step(s, off=Intent(button_pressed=True))
    assert c.offense_locked


def test_clicking_qb_while_aiming_goes_back_to_placing():
    s = make_session()
    c = s.call
    step(s, off=Intent(z_pressed=True))
    assert not c.placing
    step(s, off=Intent(mouse=tuple(c.qb_center()), mouse_pressed=True, mouse_held=True))
    assert c.placing


def test_defender_is_run_into_place_and_cannot_lock_in_its_forbidden_zone():
    s = make_session()
    off = s.down.offense
    c = s.call
    toward_offense = -off.attack_dir
    step(s, dfn=Intent(move_x=toward_offense), ticks=60)          # run inside the 20-yard line
    assert s.field.yards_from_goal(off, c.def_player.center.x) < 20
    assert not c.def_ok
    step(s, dfn=Intent(z_pressed=True))
    assert not c.defense_locked
    step(s, dfn=Intent(move_x=-toward_offense), ticks=70)         # back out past the 20
    assert c.def_ok
    step(s, dfn=Intent(z_pressed=True))
    assert c.defense_locked
    assert s.field.yards_from_goal(off, c.def_spot.x) >= 20
    assert c.def_spot.x == pytest.approx(c.def_player.center.x)
def test_execution_starts_as_soon_as_both_lock():
    s = make_session()
    step(s, off=Intent(x_pressed=True))
    assert s.phase is Phase.PLAY_CALL and s.call.offense_locked
    step(s, dfn=Intent(z_pressed=True))
    assert s.phase is Phase.PRE_THROW


def test_play_call_timeout_restarts_same_down_keeping_choices():
    s = make_session(play_call_seconds=0.1)
    step(s, off=Intent(move_x=s.down.offense.attack_dir), ticks=3)  # nudge the QB
    spot, down = s.call.qb_spot, s.down
    step(s, ticks=13)
    assert s.phase is Phase.PLAY_CALL and s.down == down
    assert s.call.restarts == 1 and s.call.qb_spot == spot
    assert s.call.timer > 0


def test_last_inputs_are_the_next_defaults():
    s = make_session()
    step(s, off=Intent(move_x=-1), ticks=3)                    # nudge the QB, staying in its zone
    step(s, off=Intent(z_pressed=True))
    step(s, off=Intent(move_x=1), ticks=20)  # rotate aim
    angle = s.call.aim_angle
    to_live(s)
    wr, _ = s.game.players
    give_ball(s, wr)
    place(wr, s.field.x_at(s.down.offense, 30))
    step(s, dfn=Intent())  # no tag; force a tag below
    _, df = s.game.players
    place(df, wr.center.x)
    step(s, dfn=Intent(z_pressed=True), ticks=1)
    step(s, ticks=10)
    assert s.phase is Phase.PLAY_CALL and s.down.number == 2
    assert s.call.aim_angle == pytest.approx(angle)


# ---------------------------------------------------------------- execution

def test_wr_spawns_next_to_qb_toward_the_defense():
    s = make_session()
    lock_in(s)
    wr, df = s.game.players
    dir_ = s.down.offense.attack_dir
    assert (wr.center.x - s.qb.center.x) * dir_ > 0
    assert abs(wr.center.x - s.qb.center.x) < 2 * s.t.player_width
    assert df.center.x == pytest.approx(s.call.def_spot.x)


def test_qb_throws_automatically_with_locked_aim():
    s = make_session()
    step(s, off=Intent(z_pressed=True))
    aim = (s.call.aim_angle, s.call.aim_power)
    lock_in(s)
    assert s.game.ball.held_by is s.qb
    step(s, ticks=int(s.t.pre_throw_seconds * s.t.physics_hz) + 2)
    assert s.phase is Phase.LIVE and s.game.ball.held_by is None
    assert s.game.ball.vel.length() == pytest.approx(aim[1], rel=0.05)


def test_qb_cannot_be_tagged_and_nobody_can_take_the_ball_from_it():
    s = make_session(pre_throw_seconds=1)
    lock_in(s)
    _, df = s.game.players
    place(df, s.qb.center.x)
    step(s, dfn=Intent(z_pressed=True), ticks=3)
    assert s.phase is Phase.PRE_THROW and s.game.ball.held_by is s.qb


def test_wr_cannot_throw():
    s = make_session()
    to_live(s)
    wr, _ = s.game.players
    give_ball(s, wr)
    step(s, ticks=5)
    step(s, off=Intent(z_pressed=True), ticks=2)
    assert wr.state.name != "aiming" and wr.held_ball is s.game.ball


def test_ball_dead_3s_after_it_stops_and_next_down_is_from_same_spot():
    s = make_session(loose_ball_seconds=0.5)
    lock_in(s)
    qb_spot = s.qb_spot
    step(s, ticks=int(s.t.pre_throw_seconds * s.t.physics_hz) + 2)
    stopped_at = None
    for i in range(3000):
        step(s)
        if stopped_at is None and s.loose_timer is not None:
            stopped_at = i
            assert s.game.ball.vel.length() < s.t.ball_stopped_speed
        if s.phase is Phase.DEAD:
            break
    assert stopped_at is not None and s.result.outcome is Outcome.DEAD_BALL
    assert (i - stopped_at) / s.t.physics_hz == pytest.approx(0.5, abs=0.02)
    assert s.down.number == 2 and s.down.qb_spawn == FixedSpot(qb_spot)


def test_picking_up_a_landed_ball_keeps_the_play_alive():
    s = make_session(loose_ball_seconds=0.5)
    to_live(s)
    ball = s.game.ball
    for _ in range(3000):
        step(s)
        if s.loose_timer is not None:
            break
    wr, _ = s.game.players
    place(wr, ball.pos.x, FLOOR)
    step(s, off=Intent(z_pressed=True), ticks=2)
    assert ball.held_by is wr and s.loose_timer is None
    step(s, ticks=int(0.6 * s.t.physics_hz))
    assert s.phase is Phase.LIVE


def test_tagged_wr_next_down_from_last_platform_touched():
    s = make_session()
    to_live(s)
    wr, df = s.game.players
    give_ball(s, wr)
    off = s.down.offense
    x = s.field.x_at(off, 40)
    place(wr, x)
    wr.body.pos.y -= 60  # mid-air now; last platform touched is still (x, FLOOR)
    place(df, x, FLOOR)
    df.body.pos.y = wr.body.pos.y
    step(s, dfn=Intent(z_pressed=True))
    assert s.phase is Phase.DEAD and s.result.outcome is Outcome.TAGGED
    assert s.down.number == 2 and s.down.offense is off
    assert s.down.qb_spawn.spot.x == pytest.approx(x, abs=s.t.run_speed * s.t.dt * 2)
    assert s.down.qb_spawn.spot.y == FLOOR
    step(s, ticks=10)
    assert s.phase is Phase.PLAY_CALL and s.call.qb_spot.x == pytest.approx(s.down.qb_spawn.spot.x)
    assert not s.call.placing  # downs 2-4: offense only aims


def test_tag_needs_to_be_in_range():
    s = make_session()
    to_live(s)
    wr, df = s.game.players
    give_ball(s, wr)
    place(wr, s.field.x_at(s.down.offense, 40))
    place(df, s.field.x_at(s.down.offense, 60))
    step(s, dfn=Intent(z_pressed=True))
    assert s.phase is Phase.LIVE


def test_touchdown_needs_wr_standing_in_end_zone_then_possession_switches():
    s = make_session()
    off = s.down.offense
    to_live(s)
    wr, _ = s.game.players
    give_ball(s, wr)
    place(wr, s.field.x_at(off, 105), FLOOR - 80)  # above the end zone, in the air
    step(s)
    assert s.phase is Phase.LIVE
    for _ in range(120):
        step(s)
        if s.phase is Phase.DEAD:
            break
    assert s.result.outcome is Outcome.TOUCHDOWN
    assert s.match.score[off] == 1
    assert s.down.offense is off.other and s.down.offense_picks_spawn and s.down.number == 1
    assert "Touchdown" in s.message


def test_interception_then_wr_tag_gives_defense_the_ball_at_tag_spot():
    s = make_session()
    off = s.down.offense
    to_live(s)
    wr, df = s.game.players
    give_ball(s, df)
    x = s.field.x_at(off, 35)
    place(df, x)
    place(wr, x)
    step(s, off=Intent(z_pressed=True))
    assert s.result.outcome is Outcome.INTERCEPTION_TAGGED
    assert s.down.offense is off.other and s.down.number == 1
    assert isinstance(s.down.qb_spawn, FixedSpot)


def test_pick_six():
    s = make_session()
    off = s.down.offense
    to_live(s)
    _, df = s.game.players
    give_ball(s, df)
    place(df, s.field.x_at(off, -5))  # in the offense's own end zone, standing
    step(s)
    assert s.result.outcome is Outcome.PICK_SIX
    assert s.match.score[off.other] == 1 and s.down.offense is off


def test_four_failed_downs_turn_the_ball_over():
    s = make_session()
    off = s.down.offense
    for n in range(1, 5):
        assert s.down.number == n and s.down.offense is off
        to_live(s)
        wr, df = s.game.players
        give_ball(s, wr)
        place(df, wr.center.x)
        step(s, dfn=Intent(z_pressed=True))
        assert s.result.outcome is Outcome.TAGGED
        message = s.message
        step(s, ticks=10)
    assert s.down.offense is off.other and s.down.number == 1 and s.down.offense_picks_spawn
    assert "turnover on downs" in message


def test_first_to_five_ends_the_match():
    s = make_session(touchdowns_to_win=2)
    for _ in range(4):
        if s.phase is Phase.GAME_OVER:
            break
        off = s.down.offense
        to_live(s)
        wr, _ = s.game.players
        give_ball(s, wr)
        place(wr, s.field.x_at(off, 105))
        step(s)
        step(s, ticks=10)
    assert s.phase is Phase.GAME_OVER and s.match.winner is not None
    assert s.message.startswith(f"{s.match.winner.display} wins 2-")


# ---------------------------------------------------------------- practice

def test_practice_defense_is_auto_locked_and_never_moves():
    s = make_session(humans=1)
    assert s.down.offense is Team.LEFT and s.call.defense_locked
    lock_in(s)
    _, df = s.game.players
    step(s, ticks=30)
    x = df.center.x
    step(s, ticks=30)
    assert df.center.x == pytest.approx(x)


def make_catch_session(**tuning) -> Session:
    t = Tuning(**{**FAST, **tuning})
    return Session(Level(width=1024, height=400), t, humans=1, defender=False)


def score_touchdown(s: Session):
    """Run one play to a touchdown, carrying the ball into the end zone the human is attacking."""
    off = s.down.offense
    lock_in(s)
    step(s, ticks=int(s.t.pre_throw_seconds * s.t.physics_hz) + 2)
    wr = s.game.players[0]
    give_ball(s, wr)
    place(wr, s.field.x_at(off, 105), FLOOR - 80)
    for _ in range(200):
        step(s)
        if s.phase is Phase.DEAD:
            return
    raise AssertionError("no touchdown")


def test_catch_practice_has_no_defender():
    s = make_catch_session()
    assert s.defender is False
    lock_in(s)
    assert len(s.game.players) == 1 and s.game.players[0].role.name == "WR"
    v = make_view(s, 0)
    assert [a["role"] for a in v["actors"]] == ["QB", "WR"] and v["defender"] is False
    json.dumps(v)


def test_normal_practice_still_has_its_defender_and_two_humans_always_do():
    assert make_session(humans=1).defender is True
    assert Session(Level(width=1024, height=400), Tuning(**FAST), humans=2, defender=False).defender is True


def test_catch_practice_touchdown_swaps_you_to_the_other_side_and_end_zone():
    s = make_catch_session()
    first = s.down.offense
    assert s.team_of_human == [first] == [Team.LEFT]
    score_touchdown(s)
    assert s.match.score[first] == 1 and s.result.outcome is Outcome.TOUCHDOWN
    step(s, ticks=int(s.t.result_pause_seconds * s.t.physics_hz) + 3)       # on to the next play
    assert s.phase is Phase.PLAY_CALL
    assert s.down.offense is first.other and s.team_of_human == [first.other]   # you are the other team now
    assert s.down.number == 1
    assert s.human_of(s.down.offense) == 0                                      # and you are still on offense
    assert first.other.attack_dir == -first.attack_dir                          # heading the other way
    score_touchdown(s)                                                          # and you can score going back
    assert s.match.score[first.other] == 1


# ---------------------------------------------------------------- views / hidden info

def test_views_hide_the_other_sides_secrets():
    s = make_session()
    off_pid, def_pid = s.human_of(s.down.offense), s.human_of(s.down.defense)
    ov, dv = make_view(s, off_pid), make_view(s, def_pid)
    assert "aim" in ov["call"] and not {"def", "def_spot", "def_ok"} & set(ov["call"])
    assert "def" in dv["call"] and "aim" not in dv["call"]
    assert ov["call"]["qb"] == dv["call"]["qb"]  # QB placement is visible live to both
    lock_in(s)
    ov, dv = make_view(s, off_pid), make_view(s, def_pid)
    assert "aim" in ov and "aim" not in dv
    json.dumps(ov), json.dumps(dv)


def test_qb_can_confirm_standing_on_a_platform_edge():
    s = make_session(humans=1, platforms=[(140, FLOOR - 60, 30, 60)])   # a block inside the QB zone
    c = s.call
    p = c.qb_player
    step(s, off=Intent(move_x=1, vertical=1, jump_pressed=True))
    for _ in range(120):
        step(s, off=Intent(move_x=1 if p.center.x < 150 else 0, vertical=1))
    assert p.box.bottom == pytest.approx(FLOOR - 60)                    # on top of the block
    for _ in range(60):                                                 # edge out until barely on it
        if p.center.x >= 178:
            break
        step(s, off=Intent(move_x=1))
    step(s, ticks=5)
    assert p.contacts.on_ground and p.center.x > 170                     # center past the block's edge
    assert c.qb_ok
    step(s, off=Intent(z_pressed=True))
    assert not c.placing and (c.qb_spot.x, c.qb_spot.y) == pytest.approx((170, FLOOR - 60))
