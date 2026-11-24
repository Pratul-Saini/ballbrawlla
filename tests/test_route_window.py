"""The no-throw version: a route window after the play call in which the WR carries the ball and
neither side may cross the line of scrimmage, then live play with nothing thrown."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import random
import threading
import time
from dataclasses import asdict

import pygame
import pytest
from conftest import make_game
from test_session import FAST, FLOOR, lock_in, make_session, place, step

from ballbrawlla.config import Tuning
from ballbrawlla.input import Intent
from ballbrawlla.net.client import Client
from ballbrawlla.net.host import Host
from ballbrawlla.net.protocol import PROTOCOL_VERSION
from ballbrawlla.net.view import make_view
from ballbrawlla.render.match_renderer import LOS_LINE, MatchRenderer
from ballbrawlla.rules.down import Down, FixedSpot
from ballbrawlla.rules.field import Spot
from ballbrawlla.rules.teams import Team
from ballbrawlla.session import Phase, Session
from ballbrawlla.world.level import level_to_dict, load_level

WINDOW = 1.0
TICKS = int(WINDOW * 120)
OFF_TUNING = dict(throw_enabled=False, route_window_seconds=WINDOW)


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


def route_session(offense=Team.LEFT, qb_x=None, platforms=(), humans=2, **tuning) -> Session:
    """A no-throw session. With qb_x the down is a FixedSpot down at that (possibly fractional) x."""
    s = make_session(humans=humans, platforms=platforms, **{**OFF_TUNING, **tuning})
    if qb_x is not None:
        s.match.down = Down(2, offense, FixedSpot(Spot(qb_x, FLOOR)))
        s._start_play_call()
    return s


def lock_defense(s: Session) -> None:
    step(s, dfn=Intent(z_pressed=True))


def start_window(s: Session) -> None:
    step(s, off=Intent(x_pressed=True), dfn=Intent(z_pressed=True))
    assert s.phase is Phase.PRE_THROW


def actors(s: Session):
    wr = s.game.players[0]
    df = s.game.players[1] if len(s.game.players) > 1 else None
    return wr, df


def check_los(s: Session, d: int, los: float, slack: float = 1.0) -> None:
    wr, df = actors(s)
    assert d * (wr.center.x - los) <= slack, (wr.center.x, los)
    if df is not None:
        assert d * (df.center.x - los) >= -slack, (df.center.x, los)
    for p in (wr, df):
        if p is not None:
            assert -1 <= p.center.y <= s.level.height + 1, p.center.y


# ---------------------------------------------------------------- defaults

def test_defaults_are_no_throw_with_a_five_second_window():
    t = Tuning()
    assert t.throw_enabled is False
    assert t.route_window_seconds == 5.0
    assert PROTOCOL_VERSION == 5


# ---------------------------------------------------------------- (i) the line holds

def _policy(kind, d, side, tick):
    """Intent for the WR (side 'wr', pushes toward the defense = +d) or Defender (pushes toward the offense = -d)."""
    toward = d if side == "wr" else -d
    if kind == "hold":
        return Intent(move_x=toward)
    if kind == "jump":
        return Intent(move_x=toward, vertical=1, jump_pressed=tick % 40 == 0, jump_held=True)
    if kind == "double":
        return Intent(move_x=toward, vertical=1, jump_pressed=tick % 20 == 0)
    if kind == "wall":   # run away from the line into the wall, then wall-jump back toward it
        if tick < 50:
            return Intent(move_x=-toward)
        return Intent(move_x=toward, vertical=1, jump_pressed=tick % 12 == 0)
    raise AssertionError(kind)


@pytest.mark.parametrize("offense", [Team.LEFT, Team.RIGHT])
@pytest.mark.parametrize("qb_x", [300.37, 512.5, 700.63])
@pytest.mark.parametrize("kind", ["hold", "jump", "double"])
def test_los_holds_under_push(offense, qb_x, kind):
    s = route_session(offense, qb_x)
    d = offense.attack_dir
    lock_defense(s)
    step(s, off=Intent(x_pressed=True))
    assert s.phase is Phase.PRE_THROW
    los = s.los_x
    assert los == s.call.qb_spot.x
    assert set(s.game.barriers) == {0, 1}
    for tick in range(TICKS - 2):
        step(s, off=_policy(kind, d, "wr", tick), dfn=_policy(kind, d, "df", tick))
        assert s.phase is Phase.PRE_THROW
        check_los(s, d, los)
    wr, df = actors(s)
    if kind == "hold":     # both pressed against the line
        assert abs(wr.center.x - los) < 2
        assert abs(df.center.x - los) < 2


@pytest.mark.parametrize("offense", [Team.LEFT, Team.RIGHT])
def test_los_holds_against_a_wall_kick(offense):
    d = offense.attack_dir
    qb_x = 512.5
    wall_x = qb_x - d * 150 - (20 if d > 0 else 0)          # a wall behind the WR, on the offense's side
    s = route_session(offense, qb_x, platforms=[(wall_x, 100, 20, FLOOR - 100)])
    lock_defense(s)
    step(s, off=Intent(x_pressed=True))
    los = s.los_x
    clung = 0
    for tick in range(TICKS - 2):
        step(s, off=_policy("wall", d, "wr", tick), dfn=_policy("hold", d, "df", tick))
        check_los(s, d, los)
        clung += actors(s)[0].state.name == "wall_cling"
    assert clung > 0     # the scenario really did cling to the wall


# ---------------------------------------------------------------- (ii) the line lifts

@pytest.mark.parametrize("offense", [Team.LEFT, Team.RIGHT])
def test_line_lifts_at_expiry_and_both_can_cross(offense):
    s = route_session(offense, 512.5)
    d = offense.attack_dir
    lock_defense(s)
    step(s, off=Intent(x_pressed=True))
    los = s.los_x
    step(s, off=Intent(move_x=d), dfn=Intent(move_x=-d), ticks=TICKS + 2)
    assert s.phase is Phase.LIVE
    assert s.los_x is None and s.game.barriers == {}
    step(s, off=Intent(move_x=d), dfn=Intent(move_x=-d), ticks=60)
    wr, df = actors(s)
    assert d * (wr.center.x - los) > 20
    assert d * (df.center.x - los) < -20
    assert s.game.ball.held_by is wr


# ---------------------------------------------------------------- (iii) no throw, no catch

def test_no_throw_and_no_catch_while_the_offense_mashes_buttons():
    s = route_session()
    lock_defense(s)
    step(s, off=Intent(x_pressed=True))
    assert s.phase is Phase.PRE_THROW
    wr, _ = actors(s)
    ball = s.game.ball
    assert ball.held_by is wr and wr.held_ball is ball and s.qb.held_ball is None
    for tick in range(TICKS + 3 * 120):
        mash = Intent(z_pressed=tick % 2 == 0, x_pressed=tick % 3 == 0, mouse=(300.0, 100.0),
                      mouse_held=True, mouse_pressed=tick % 5 == 0, button_pressed=tick % 7 == 0,
                      aim_stick=(0.7, 0.7), move_x=1 if tick % 90 < 45 else -1)
        step(s, off=mash)
        if s.phase is Phase.DEAD:
            break
        assert s.qb.held_ball is None
        assert s.game.ball.held_by is wr and wr.held_ball is s.game.ball      # never free, never re-caught
        assert wr.state.name != "aiming"
        assert wr.pickup_buffer == 0
    assert s.phase is Phase.LIVE


def test_player_throw_is_a_no_op_when_throwing_is_off():
    g = make_game(throw_enabled=False, ball_gravity=0)
    p, ball = g.players[0], g.ball
    ball.held_by, p.held_ball = p, ball
    p.throw()
    assert p.held_ball is ball and ball.held_by is p
    g2 = make_game(throw_enabled=True, ball_gravity=0)
    p2, b2 = g2.players[0], g2.ball
    b2.held_by, p2.held_ball = p2, b2
    p2.throw()
    assert p2.held_ball is None and b2.held_by is None


# ---------------------------------------------------------------- window length and repetition

def _tick_count_of_window(s: Session) -> int:
    n = 0
    while s.phase is Phase.PRE_THROW:
        step(s)
        n += 1
        assert n < TICKS + 10
    return n


def test_window_is_route_window_seconds_long_on_the_first_down_and_repeats():
    s = route_session()
    assert s.down.number == 1
    start_window(s)
    assert s.timer == pytest.approx(WINDOW, abs=0.01)
    assert set(s.game.barriers) == {0, 1} and s.los_x == s.call.qb_spot.x
    first_game = s.game
    assert abs(_tick_count_of_window(s) - TICKS) <= 1
    assert s.phase is Phase.LIVE and s.los_x is None and s.game.barriers == {}

    wr, df = actors(s)                                  # tag the WR: next down from the same spot
    tag_x = wr.center.x
    place(df, tag_x + 10)
    step(s, dfn=Intent(z_pressed=True))
    assert s.phase is Phase.DEAD and s.down.number == 2
    step(s, ticks=int(s.t.result_pause_seconds * 120) + 2)
    assert s.phase is Phase.PLAY_CALL and s.call.offense_locked      # fixed spot: nothing to decide
    lock_defense(s)
    assert s.phase is Phase.PRE_THROW
    assert s.game is not first_game
    assert s.timer == pytest.approx(WINDOW, abs=0.01)
    assert set(s.game.barriers) == {0, 1}
    assert s.los_x == s.call.qb_spot.x
    wr2, _ = actors(s)
    assert s.game.ball.held_by is wr2
    assert abs(_tick_count_of_window(s) - TICKS) <= 1


def test_new_match_gets_a_fresh_window():
    s = route_session()
    start_window(s)
    s.new_match()
    assert s.los_x is None
    start_window(s)
    assert s.los_x is not None and set(s.game.barriers) == {0, 1}


# ---------------------------------------------------------------- play call

def test_confirming_the_qb_spot_locks_the_offense_in_and_aim_input_is_ignored():
    s = route_session()
    c = s.call
    assert not c.offense_locked
    aim0 = (c.aim_angle, c.aim_power)
    step(s, off=Intent(mouse=(10.0, 10.0), mouse_held=True, mouse_pressed=True, aim_stick=(0.0, 1.0), move_x=0,
                       vertical=0), ticks=3)
    assert (c.aim_angle, c.aim_power) == aim0 and not c.offense_locked
    step(s, off=Intent(jump_pressed=True, vertical=1))        # in the air: cannot lock
    step(s, off=Intent(z_pressed=True))
    assert not c.qb_ok and not c.offense_locked
    step(s, ticks=240)                                         # land
    for intent in (Intent(z_pressed=True), Intent(x_pressed=True), Intent(button_pressed=True)):
        s2 = route_session()
        step(s2, ticks=3)
        step(s2, off=intent)
        assert s2.call.offense_locked and not s2.call.placing


def test_fixed_spot_down_starts_with_the_offense_locked_in():
    s = route_session(Team.RIGHT, 600.0)
    assert s.call.offense_locked
    lock_defense(s)
    assert s.phase is Phase.PRE_THROW


# ---------------------------------------------------------------- spawn guard

def test_illegal_spawn_runs_the_window_without_a_line():
    s = route_session(Team.LEFT, 400.0)
    assert s.call.offense_locked
    s.call._standing_spot = lambda p, lo, hi: (Spot(300.0, FLOOR), True)   # the offense's side of the line
    lock_defense(s)
    assert s.phase is Phase.PRE_THROW and s.game.players[1].center.x == 300.0
    assert s.los_x is None and s.game.barriers == {}
    assert make_view(s, 0)["los"] is None
    step(s, ticks=TICKS + 2)
    assert s.phase is Phase.LIVE


def test_wr_spawns_behind_the_qb_on_its_own_side():
    for offense in Team:
        s = route_session(offense, 500.0)
        lock_defense(s)
        step(s, off=Intent(x_pressed=True))
        wr, _ = actors(s)
        assert wr.center.x == pytest.approx(500.0 - offense.attack_dir * 28)


# ---------------------------------------------------------------- views

def test_views_agree_and_never_carry_aim():
    s = route_session()
    for v in (make_view(s, 0), make_view(s, 1), make_view(s, 0, local=True)):
        assert v["throwing"] is False and "aim" not in v["call"] and v["los"] is None
    start_window(s)
    views = [make_view(s, 0), make_view(s, 1), make_view(s, 0, local=True)]
    for v in views:
        assert v["phase"] == "pre_throw" and v["throwing"] is False
        assert v["los"] == pytest.approx(s.los_x, abs=0.01)
        assert v["timer"] == views[0]["timer"]
        assert "aim" not in v and "call" not in v
        assert v["ball"]["holder"] == "WR"
    step(s, ticks=TICKS + 2)
    assert s.phase is Phase.LIVE
    assert all(make_view(s, p)["los"] is None and "aim" not in make_view(s, p) for p in (0, 1))
    assert make_view(s, 0)["throwing"] is False


def test_legacy_views_still_carry_aim():
    s = make_session(throw_enabled=True)
    assert make_view(s, s.human_of(s.down.offense))["call"]["aim"]
    lock_in(s)
    v = make_view(s, s.human_of(s.down.offense))
    assert v["throwing"] is True and "aim" in v and v["los"] is None


def test_loopback_client_sees_the_line_and_cannot_cross_it():
    s = route_session(Team.LEFT, 400.0)
    host = Host({"level": level_to_dict(s.level), "tuning": asdict(s.t)}, max_players=2, port=0,
                bind="127.0.0.1")
    stop, joined = threading.Event(), []

    def serve():
        while not stop.is_set() and not joined:
            joined.extend(host.poll()[0])
            time.sleep(0.005)

    th = threading.Thread(target=serve)
    th.start()
    try:
        client = Client("127.0.0.1", host.port, timeout=2.0)
        stop.set()
        th.join()
        assert Tuning(**client.tuning_data).throw_enabled is False
        assert Tuning(**client.tuning_data).route_window_seconds == WINDOW

        lock_defense(s)
        step(s, off=Intent(x_pressed=True))
        d = s.down.offense.attack_dir
        snaps = []
        for _ in range(TICKS - 2):
            host.poll()
            client.send_intent(Intent(move_x=-d))                 # the joiner is the defender
            s.step([Intent(move_x=d), host.intent_for(1)], s.t.dt)
            host.send_to(1, make_view(s, 1))
            deadline = time.monotonic() + 0.05
            snap = None
            while snap is None and time.monotonic() < deadline:
                snap = client.latest_snapshot()
                time.sleep(0.0005)
            if snap is not None:
                snaps.append(snap)
        assert snaps
        for snap in snaps:
            assert snap["phase"] == "pre_throw" and snap["throwing"] is False and "aim" not in snap
            assert snap["los"] == pytest.approx(s.los_x, abs=0.01)
            mine = next(a for a in snap["actors"] if a["role"] == "DEF")
            assert d * (mine["x"] + mine["w"] / 2 - snap["los"]) >= -1
        client.close()
    finally:
        stop.set()
        host.close()


# ---------------------------------------------------------------- determinism

def _random_run(seed: int):
    s = route_session(seed=3)
    rng = random.Random(seed)
    lock_defense(s)
    step(s, off=Intent(x_pressed=True))

    def rnd():
        return Intent(move_x=rng.choice((-1, 0, 1, 1)), vertical=rng.choice((-1, 0, 1)),
                      jump_pressed=rng.random() < 0.1, z_pressed=rng.random() < 0.05)

    for _ in range(TICKS + 5 * 120):
        step(s, off=rnd(), dfn=rnd())
    return [(p.body.pos.x, p.body.pos.y) for p in s.game.players], s.phase, s.tick


def test_runs_are_deterministic():
    assert _random_run(11) == _random_run(11)


# ---------------------------------------------------------------- catch practice

def test_catch_practice_has_only_the_wr_barrier():
    from ballbrawlla.world.level import Level
    t = Tuning(**{**FAST, **OFF_TUNING})
    s = Session(Level(width=1024, height=400), t, humans=1, defender=False)
    step(s, off=Intent(x_pressed=True))
    assert s.phase is Phase.PRE_THROW and set(s.game.barriers) == {0}
    d = s.down.offense.attack_dir
    los = s.los_x
    assert los is not None
    for _ in range(TICKS - 2):
        step(s, off=Intent(move_x=d))
        assert d * (s.game.players[0].center.x - los) <= 1
    step(s, off=Intent(move_x=d), ticks=60)
    assert s.phase is Phase.LIVE and d * (s.game.players[0].center.x - los) > 20
    assert make_view(s, 0)["defender"] is False


# ---------------------------------------------------------------- real levels

@pytest.mark.parametrize("name", ["field_01", "field_09", "field_12", "field_14"])
@pytest.mark.parametrize("offense", [Team.LEFT, Team.RIGHT])
def test_los_holds_with_random_inputs_on_real_levels(name, offense):
    level = load_level(f"levels/{name}.json")
    t = Tuning(throw_enabled=False, route_window_seconds=2.0, result_pause_seconds=0.05)
    s = Session(level, t, humans=2, seed=4)
    d = offense.attack_dir
    s.match.down = Down(1, offense, s.down.qb_spawn)
    s._start_play_call()
    rng = random.Random(f"{name}-{int(offense)}")
    step(s, off=Intent(x_pressed=True), dfn=Intent(z_pressed=True))
    assert s.phase is Phase.PRE_THROW
    los = s.los_x
    assert los is not None, "the real-level spawns must be legal"
    for tick in range(int(2.0 * 120) - 2):
        def rnd(toward):
            return Intent(move_x=rng.choice((-toward, 0, toward, toward, toward)),
                          vertical=rng.choice((-1, 0, 1, 1)), jump_pressed=rng.random() < 0.15,
                          jump_held=rng.random() < 0.3)
        step(s, off=rnd(d), dfn=rnd(-d))
        if s.phase is not Phase.PRE_THROW:
            break
        check_los(s, d, los)


# ---------------------------------------------------------------- render

def test_renderer_draws_the_line_and_the_countdown():
    s = route_session()
    start_window(s)
    screen = pygame.Surface((1280, 720))
    r = MatchRenderer(screen, s.level, s.field, s.t)
    view = make_view(s, 0)
    big, real_font = [], r.countdown_font

    class SpyFont:
        def render(self, text, *a, **k):
            big.append(text)
            return real_font.render(text, *a, **k)

    r.countdown_font = SpyFont()
    r.draw(view, 60, 0.0)
    assert big == ["1"]                      # the big whole-second countdown (timer is just under 1.0)
    sx = round(r._w(view["los"], 0)[0])
    assert 0 < sx < 1280
    assert tuple(screen.get_at((sx, 700)))[:3] == LOS_LINE
    assert "ROUTE" in r._phase_hint(view) and "ROUTE" in r._state_hint(view)
    assert "THROW" not in r._phase_hint(view)
    hidden = dict(view, los=None)
    r.draw(hidden, 60, 0.0)
    assert tuple(screen.get_at((sx, 700)))[:3] != LOS_LINE
    assert "line" in r._phase_hint(make_view(s, 1)) and r.button_rect is None
    local = make_view(s, 0, local=True)
    assert "WR:" in r._phase_hint(local) and "DEF:" in r._phase_hint(local)


def test_renderer_play_call_has_no_aim_wording():
    s = route_session()
    r = MatchRenderer(pygame.Surface((1280, 720)), s.level, s.field, s.t)
    off = make_view(s, s.human_of(s.down.offense))
    r.draw(off, 60, 0.0)
    assert r.button_rect is not None
    step(s, ticks=3)
    off = make_view(s, s.human_of(s.down.offense))
    assert "aim" not in r._phase_hint(off).lower() and "throw" not in r._phase_hint(off).lower()
    assert r._button_label(off) in ("Confirm QB spot", "Move QB onto a platform")
