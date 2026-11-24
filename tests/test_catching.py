import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from dataclasses import asdict

import pygame
import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.input import Intent
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.render.renderer import REACH, Renderer
from tests.conftest import make_game, run


@pytest.fixture(scope="module")
def _pygame():
    pygame.init()
    yield
    pygame.quit()


def test_default_pickup_radius():
    t = Tuning()
    assert t.pickup_radius == 55
    assert t.pickup_buffer_time == 0.1
    assert t.pickup_grace_time == 0.1
    assert t.pickup_buffer_ticks == 12
    assert t.pickup_grace_ticks == 12


def test_new_tuning_fields_survive_welcome():
    data = asdict(Tuning(pickup_radius=60))
    assert Tuning(**data) == Tuning(pickup_radius=60)
    assert "pickup_buffer_time" in data and "pickup_grace_time" in data
    assert not any(k.endswith("_ticks") for k in data)


def test_reach_circle_uses_pickup_radius(_pygame, monkeypatch):
    g = make_game(pickup_radius=77, ball_gravity=0)
    run(g, ticks=60)
    p = g.players[0]
    g.ball.release(Vector2(p.center), Vector2())
    run(g)  # lets the player see the ball
    assert p.ball_in_reach()

    calls = []
    real = pygame.draw.circle

    def spy(surface, color, center, radius, *args, **kwargs):
        calls.append((tuple(color), radius))
        return real(surface, color, center, radius, *args, **kwargs)

    monkeypatch.setattr(pygame.draw, "circle", spy)
    renderer = Renderer(pygame.Surface((1280, 720)))
    renderer.debug = False
    renderer.draw(g, 60.0)
    assert (REACH, 77) in calls


# ---------------------------------------------------------------- helpers


def _put_ball_on(g, p, offset=(0, 0)):
    g.ball.release(Vector2(p.center) + Vector2(offset), Vector2())


def _holding_game(**tuning):
    """Player on the floor next to a left wall, already holding the ball."""
    g = make_game(player=(120, 650), ball_gravity=0, **tuning)
    run(g, ticks=60)
    p = g.players[0]
    _put_ball_on(g, p)
    run(g, Intent(z_pressed=True))
    assert p.held_ball is g.ball
    return g, p


def _cling_left(g):
    run(g, Intent(jump_pressed=True, vertical=1))
    for _ in range(240):
        run(g, Intent(move_x=-1, vertical=1))
        if g.players[0].state.name == "wall_cling":
            return
    raise AssertionError("never clung to wall")


# ---------------------------------------------------------------- Property 1


# Property 1 -- Validates: Requirements 1.1, 1.8, 7.1
def test_z_on_landing_tick_catches():
    g = make_game(player=(200, 300), ball_gravity=0)
    p = g.players[0]
    for _ in range(300):
        run(g)
        if p.contacts.on_ground and p.state.name == "airborne":
            break
    else:
        raise AssertionError("never reached the landing tick")
    _put_ball_on(g, p)
    run(g, Intent(z_pressed=True))  # Airborne -> Grounded on this tick
    assert p.state.name == "grounded"
    assert p.held_ball is g.ball and g.ball.held_by is p


# Property 1 -- Validates: Requirements 1.2, 1.8, 7.1
def test_z_on_leaving_ground_tick_catches():
    g = make_game(platforms=[(0, 500, 400, 40)], player=(300, 470), ball_gravity=0)
    p = g.players[0]
    run(g, ticks=60)
    assert p.state.name == "grounded" and p.contacts.on_ground
    for _ in range(300):
        run(g, Intent(move_x=1))
        if p.state.name == "grounded" and not p.contacts.on_ground:
            break
    else:
        raise AssertionError("never walked off the ledge")
    _put_ball_on(g, p)
    run(g, Intent(move_x=1, z_pressed=True))  # Grounded -> Airborne on this tick
    assert p.state.name == "airborne"
    assert p.held_ball is g.ball


# Property 1 -- Validates: Requirements 1.3, 1.8, 7.1
def test_z_on_wall_cling_entry_tick_catches():
    g = make_game(player=(120, 650), ball_gravity=0)
    p = g.players[0]
    run(g, ticks=60)
    run(g, Intent(jump_pressed=True, vertical=1))
    for _ in range(240):
        run(g, Intent(move_x=-1, vertical=1))
        if p.contacts.wall_left and p.state.name == "airborne":
            break
    else:
        raise AssertionError("never touched the wall while airborne")
    _put_ball_on(g, p)
    run(g, Intent(move_x=-1, vertical=1, z_pressed=True))  # Airborne -> WallCling
    assert p.state.name == "wall_cling"
    assert p.held_ball is g.ball


# Property 1 -- Validates: Requirements 1.4, 1.8
def test_z_while_sliding_catches():
    g = make_game(ball_gravity=0)
    run(g, ticks=60)
    p = g.players[0]
    slide = Intent(move_x=1, vertical=-1)
    run(g, slide, ticks=2)
    assert p.state.name == "slide"
    _put_ball_on(g, p)
    run(g, Intent(move_x=1, vertical=-1, z_pressed=True))
    assert p.held_ball is g.ball


# ---------------------------------------------------------------- Property 2


# Property 2 -- Validates: Requirements 1.5, 1.7
def test_z_cancels_aim_without_pickup():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(z_pressed=True))
    assert p.state.name == "aiming"
    run(g, Intent(z_pressed=True))
    assert p.state.name == "grounded"
    assert p.held_ball is g.ball
    assert not p.pickup_requested
    assert p.pickup_buffer == 0


# Property 2 -- Validates: Requirements 1.6, 1.8
def test_z_while_holding_in_airborne_files_no_request():
    g, p = _holding_game()
    run(g, Intent(jump_pressed=True, vertical=1))
    assert p.state.name == "airborne"
    run(g, Intent(z_pressed=True))
    assert p.state.name == "airborne"
    assert p.held_ball is g.ball and not p.pickup_requested and p.pickup_buffer == 0


# Property 2 -- Validates: Requirements 1.6, 1.8
def test_z_while_holding_in_wall_cling_files_no_request():
    g, p = _holding_game()
    _cling_left(g)
    run(g, Intent(z_pressed=True))
    assert p.state.name == "wall_cling"
    assert p.held_ball is g.ball and not p.pickup_requested and p.pickup_buffer == 0


# Property 2 -- Validates: Requirements 1.7, 6.1
def test_z_while_holding_on_ground_enters_aiming():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(z_pressed=True))
    assert p.state.name == "aiming" and p.held_ball is g.ball


# Property 2 -- Validates: Requirements 1.7, 6.1
def test_z_while_holding_in_crouch_enters_aiming():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(vertical=-1), ticks=2)
    assert p.state.name == "crouch"
    run(g, Intent(vertical=-1, z_pressed=True))
    assert p.state.name == "aiming" and p.held_ball is g.ball


# Property 2 -- Validates: Requirements 1.7
def test_z_while_holding_does_nothing_when_throw_disabled():
    g, p = _holding_game(throw_enabled=False)
    run(g, Intent(z_pressed=True))
    assert p.state.name == "grounded"
    assert p.held_ball is g.ball and not p.pickup_requested
    run(g, Intent(vertical=-1), ticks=2)
    assert p.state.name == "crouch"
    run(g, Intent(vertical=-1, z_pressed=True))
    assert p.state.name == "crouch" and p.held_ball is g.ball


# ---------------------------------------------------------------- early-press buffer helpers

_BALL_VX = -300.0  # px/s toward the player: 2.5 px per tick at 120 Hz


def _approach_game(**tuning):
    """Settled player at x=200 and a Free ball released 400 px to its right, flying at it."""
    g = make_game(ball_gravity=0, **tuning)
    run(g, ticks=60)
    p = g.players[0]
    g.ball.release(Vector2(p.center.x + 400, p.center.y), Vector2(_BALL_VX, 0))
    return g, p


def _arrival_step(**tuning) -> int:
    """1-indexed tick at which a Z press would first see the ball in reach (dry run)."""
    g, p = _approach_game(**tuning)
    n = 0
    while p.center.distance_to(g.ball.pos) > g.t.pickup_radius:
        run(g)
        n += 1
        assert n < 1000
    return n + 1


def _play(presses, total, **tuning):
    """Z pressed on the given 1-indexed ticks; run `total` ticks. Returns (game, player)."""
    g, p = _approach_game(**tuning)
    for s in range(1, total + 1):
        run(g, Intent(z_pressed=s in presses))
    return g, p


# ---------------------------------------------------------------- Property 3


# Property 3 -- Validates: Requirements 2.2, 2.4, 7.2
def test_early_press_within_buffer_catches():
    a = _arrival_step()
    g, p = _play({a - 11}, a + 2)
    assert p.held_ball is g.ball and g.ball.held_by is p


# Property 3 -- Validates: Requirements 2.5, 7.2
def test_early_press_beyond_buffer_misses():
    a = _arrival_step()
    g, p = _play({a - 13}, a + 30)
    assert p.held_ball is None and g.ball.held_by is None
    assert g.ball.pos.x < p.center.x  # ball flew on past the player


# Property 3 -- Validates: Requirements 2.3
def test_second_press_restarts_buffer():
    a = _arrival_step()
    first = a - 13  # alone, its window would end on tick a - 1
    g, p = _play({first}, a + 2)
    assert p.held_ball is None
    g, p = _play({first, first + 11}, a + 2)
    assert p.held_ball is g.ball


# Property 3 -- Validates: Requirements 2.9
def test_buffer_disabled_with_zero_time():
    a = _arrival_step(pickup_buffer_time=0)
    g, p = _play({a - 3}, a + 2, pickup_buffer_time=0)
    assert p.held_ball is None and p.pickup_buffer == 0


# Property 3 -- Validates: Requirements 2.10, 2.11
def test_buffer_does_not_take_ball_held_by_other_but_catches_when_free():
    g = make_game(players=[(200, 650), (900, 650)], ball_gravity=0)
    run(g, ticks=60)
    p0, p1 = g.players
    _put_ball_on(g, p1)
    run(g, [Intent(), Intent(z_pressed=True)])
    assert p1.held_ball is g.ball
    run(g, [Intent(z_pressed=True), Intent()])  # P0 presses, ball is held by P1
    assert p0.held_ball is None and p0.pickup_buffer > 0
    run(g, ticks=3)
    assert g.ball.held_by is p1 and p0.held_ball is None
    # P1 "throws" the ball into P0's reach, inside P0's window
    p1.held_ball = None
    g.ball.release(Vector2(p0.center), Vector2())
    run(g)
    assert p0.held_ball is g.ball and g.ball.held_by is p0


# ---------------------------------------------------------------- Property 4


# Property 4 -- Validates: Requirements 2.6
def test_buffer_cleared_after_catch():
    a = _arrival_step()
    g, p = _play({a - 5}, a + 1)
    assert p.held_ball is g.ball
    assert p.pickup_buffer == 0


# Property 4 -- Validates: Requirements 2.7, 2.8
def test_buffer_zero_when_entering_aiming_and_while_holding():
    g, p = _holding_game(throw_enabled=True)
    p.pickup_buffer = 5
    run(g, Intent(z_pressed=True))
    assert p.state.name == "aiming"
    assert p.pickup_buffer == 0
    run(g, ticks=3)
    assert p.pickup_buffer == 0


# Property 4 -- Validates: Requirements 2.12
def test_buffer_cleared_after_reset_player():
    a = _arrival_step()
    g, p = _play({a - 8}, a - 4)
    assert p.pickup_buffer > 0
    g.reset_player(0)
    assert g.players[0].pickup_buffer == 0


# Property 4 -- Validates: Requirements 4.5
def test_grant_clears_every_other_players_buffer():
    g = make_game(players=[(200, 650), (900, 650)], ball_gravity=0)
    run(g, ticks=60)
    p0, p1 = g.players
    g.ball.release(Vector2(p0.center.x + 400, p0.center.y), Vector2(_BALL_VX, 0))
    run(g, ticks=_arrival_step() - 9)  # both presses land a few ticks before arrival
    run(g, [Intent(z_pressed=True), Intent(z_pressed=True)])
    assert p0.pickup_buffer > 0 and p1.pickup_buffer > 0
    for _ in range(300):
        run(g)
        if g.ball.held_by is not None:
            break
    assert g.ball.held_by is p0
    assert p0.pickup_buffer == 0 and p1.pickup_buffer == 0


# ---------------------------------------------------------------- late-press grace helpers

_FLY_VX = -600.0  # px/s: 5 px per tick at 120 Hz, so leaving reach is quickly "well beyond"


def _fly_past_game(**tuning):
    """Settled player at x=200; a Free ball released 400 px to the right flies through it."""
    g = make_game(ball_gravity=0, **tuning)
    run(g, ticks=60)
    p = g.players[0]
    g.ball.release(Vector2(p.center.x + 400, p.center.y), Vector2(_FLY_VX, 0))
    return g, p


def _leave_step(**tuning) -> int:
    """1-indexed tick at whose end the ball is first out of reach after having been in reach."""
    g, p = _fly_past_game(**tuning)
    r = g.t.pickup_radius
    was_in = False
    for n in range(1, 1000):
        run(g)
        d = p.center.distance_to(g.ball.pos)
        if d <= r:
            was_in = True
        elif was_in:
            return n
    raise AssertionError("ball never left reach")


def _late_press(delay, **tuning):
    """Idle until `delay` ticks after the ball left reach, then press Z on that tick."""
    leave = _leave_step(**tuning)
    g, p = _fly_past_game(**tuning)
    run(g, ticks=leave + delay - 1)
    far = p.center.distance_to(g.ball.pos)
    run(g, Intent(z_pressed=True))
    return g, p, far


# ---------------------------------------------------------------- Property 5


# Property 5 -- Validates: Requirements 3.3, 3.5, 7.3
def test_late_press_within_grace_catches():
    g_ticks = Tuning().pickup_grace_ticks - 1
    assert g_ticks == 11
    g, p, far = _late_press(g_ticks)
    assert far > g.t.pickup_radius  # plain In_Reach would miss
    assert p.held_ball is g.ball and g.ball.held_by is p


# Property 5 -- Validates: Requirements 3.3, 7.3
def test_late_press_beyond_grace_misses():
    g, p, far = _late_press(Tuning().pickup_grace_ticks + 2)
    assert far > g.t.pickup_radius
    assert p.held_ball is None and g.ball.held_by is None


# Property 5 -- Validates: Requirements 3.10
def test_grace_zero_equals_plain_in_reach():
    g, p, _ = _late_press(2, pickup_grace_time=0)
    assert p.held_ball is None and g.ball.held_by is None
    assert len(g.ball_trail) <= 1
    run(g, ticks=20)
    assert len(g.ball_trail) <= 1


# Property 5 -- Validates: Requirements 3.3
def test_trail_length_settles_at_grace_ticks_plus_one():
    g = make_game(ball_gravity=0)
    run(g, ticks=100)
    assert g.ball.held_by is None
    assert len(g.ball_trail) == g.t.pickup_grace_ticks + 1 == 13


# Property 5 -- Validates: Requirements 3.2, 3.3
def test_trail_newest_entry_is_current_ball_position():
    g, p = _fly_past_game()
    for _ in range(30):
        run(g)
        assert g.ball_trail[-1] == g.ball.pos
    # entries are copies, not aliases of the ball's position
    assert g.ball_trail[-2] != g.ball.pos


# ---------------------------------------------------------------- Property 6


# Property 6 -- Validates: Requirements 3.2, 3.12
def test_trail_empty_while_held_and_after_grant():
    g = make_game(ball_gravity=0)
    run(g, ticks=60)
    p = g.players[0]
    _put_ball_on(g, p)
    run(g, ticks=5)
    assert len(g.ball_trail) > 0
    run(g, Intent(z_pressed=True))
    assert p.held_ball is g.ball
    assert len(g.ball_trail) == 0
    run(g, ticks=10)
    assert len(g.ball_trail) == 0


# Property 6 -- Validates: Requirements 3.4
def test_trail_empty_after_reset_and_reset_player():
    g = make_game(ball_gravity=0)
    run(g, ticks=30)
    assert len(g.ball_trail) > 0
    g.reset()
    assert len(g.ball_trail) == 0
    run(g, ticks=30)
    assert len(g.ball_trail) > 0
    g.reset_player(0)
    assert len(g.ball_trail) == 0


# Property 6 -- Validates: Requirements 3.4, 3.11
def test_trail_after_throw_has_only_post_throw_positions():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(z_pressed=True))
    assert p.state.name == "aiming"
    assert len(g.ball_trail) == 0
    run(g, Intent(x_pressed=True))
    assert g.ball.held_by is None and p.held_ball is None
    assert len(g.ball_trail) == 1
    first = Vector2(g.ball_trail[0])
    assert first == g.ball.pos
    run(g, ticks=3)
    assert len(g.ball_trail) == 4
    assert g.ball_trail[0] == first
    assert g.ball_trail[-1] == g.ball.pos


# Property 6 -- Validates: Requirements 3.9
def test_z_while_ball_held_by_other_ignores_close_trail():
    g = make_game(players=[(200, 650), (900, 650)], ball_gravity=0)
    run(g, ticks=60)
    p0, p1 = g.players
    _put_ball_on(g, p0)
    run(g, ticks=4)
    assert len(g.ball_trail) > 0 and p0.ball_in_reach()
    # P1 takes the ball on the same tick P0 presses Z
    p1.held_ball = g.ball
    g.ball.held_by = p1
    run(g, [Intent(z_pressed=True), Intent()])
    assert not p0.pickup_requested
    assert g.ball.held_by is p1 and p0.held_ball is None
    assert len(g.ball_trail) == 0
    run(g, [Intent(z_pressed=True), Intent()], ticks=5)
    assert g.ball.held_by is p1 and p0.held_ball is None


# ---------------------------------------------------------------- Property 7

BOTH_Z = [Intent(z_pressed=True), Intent(z_pressed=True)]


def _two_players(x0, x1):
    g = make_game(players=[(x0, 650), (x1, 650)], ball=(640, 670), ball_gravity=0)
    run(g, ticks=60)
    return g


def _assert_winner_keeps_ball(g, winner, loser):
    for i in range(30):
        run(g, [Intent(z_pressed=i % 2 == 0), Intent(z_pressed=i % 2 == 0)])
        assert g.ball.held_by is winner
        assert loser.held_ball is None


# Property 7 -- Validates: Requirements 4.1, 4.2, 4.6, 4.7, 7.5
def test_nearer_requester_wins_and_loser_stays_empty():
    g = _two_players(610, 655)  # P0 is 30 px away, P1 is 15 px away
    p0, p1 = g.players
    run(g, BOTH_Z)
    holders = [p for p in g.players if p.held_ball is g.ball]
    assert holders == [p1] and g.ball.held_by is p1
    assert p0.pickup_buffer == 0 and not p0.pickup_requested
    assert len(g.ball_trail) == 0
    _assert_winner_keeps_ball(g, p1, p0)


# Property 7 -- Validates: Requirements 4.3, 4.4, 7.5
def test_equal_distance_requesters_lowest_pid_wins():
    g = _two_players(610, 670)  # ball exactly midway
    p0, p1 = g.players
    assert p0.center.distance_to(g.ball.pos) == p1.center.distance_to(g.ball.pos)
    run(g, BOTH_Z)
    holders = [p for p in g.players if p.held_ball is g.ball]
    assert holders == [p0] and g.ball.held_by is p0
    assert p1.pickup_buffer == 0
    _assert_winner_keeps_ball(g, p0, p1)


# Property 7 -- Validates: Requirements 4.6, 7.4
def test_stale_buffer_and_trail_do_not_steal_after_catch():
    g = _two_players(610, 655)
    p0, p1 = g.players
    # Ball is in reach of both, P0 armed a buffer earlier is impossible while in reach,
    # so force a stale buffer on the loser and a populated trail.
    assert len(g.ball_trail) > 0
    p0.pickup_buffer = g.t.pickup_buffer_ticks
    run(g, [Intent(), Intent(z_pressed=True)])
    assert g.ball.held_by is p1
    assert p0.pickup_buffer == 0 and len(g.ball_trail) == 0
    for _ in range(30):
        run(g)
        assert g.ball.held_by is p1 and p0.held_ball is None


# ---------------------------------------------------------------- no instant re-grab


# no instant re-grab -- Validates: Requirements 2.7, 2.8, 3.4
def test_no_instant_regrab_after_throw():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(z_pressed=True))
    assert p.state.name == "aiming" and p.pickup_buffer == 0
    run(g, Intent(x_pressed=True))
    assert p.held_ball is None and g.ball.held_by is None
    for _ in range(30):
        run(g)
        assert p.held_ball is None and g.ball.held_by is None


# no instant re-grab -- Validates: Requirements 2.7, 2.8
def test_z_while_holding_leaves_no_stale_buffer():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(z_pressed=True))  # holding: enters Aiming, no buffer
    assert p.pickup_buffer == 0
    run(g, Intent(x_pressed=True))
    assert g.ball.held_by is None and p.pickup_buffer == 0
    run(g, ticks=30)
    assert p.held_ball is None


# no instant re-grab -- Validates: Requirements 3.4
def test_new_z_press_catches_freshly_thrown_ball():
    g, p = _holding_game(throw_enabled=True)
    run(g, Intent(z_pressed=True))
    run(g, Intent(x_pressed=True))
    assert g.ball.held_by is None
    run(g, Intent(z_pressed=True))
    assert p.held_ball is g.ball and g.ball.held_by is p


# ---------------------------------------------------------------- host-side delayed Z

from ballbrawlla.net.host import RemoteInput  # noqa: E402

_DELAY = 4  # ticks: ~30 ms round trip at 120 Hz


def _delayed_z_scenario(pid, deliver, **tuning):
    """Ball flies at 1400 px/s through player `pid` (standing at x=640); the client's Z is
    pressed when the ball is about to leave reach and reaches the host _DELAY ticks later.
    `deliver(intents_slot_pid)` returns the Intent list for the delivery tick.
    Returns (game, player, distance at delivery tick)."""
    direction = 1 if pid == 1 else -1
    positions = [(200, 650), (640, 650)] if pid == 1 else [(640, 650), (200, 650)]

    def setup():
        g = make_game(players=positions, ball_gravity=0, **tuning)
        run(g, ticks=60)
        p = g.players[pid]
        start = Vector2(p.center.x - 300 * direction, p.center.y)
        g.ball.release(start, Vector2(1400.0 * direction, 0))
        return g, p

    # dry run: last tick at whose end the ball is still within reach
    g, p = setup()
    last_in = None
    for n in range(1, 200):
        run(g)
        if p.center.distance_to(g.ball.pos) <= g.t.pickup_radius:
            last_in = n
        elif last_in is not None:
            break
    assert last_in is not None

    g, p = setup()
    run(g, ticks=last_in)  # the moment the client would have pressed Z
    run(g, ticks=_DELAY - 1)
    far = p.center.distance_to(g.ball.pos)
    run(g, deliver(pid))
    return g, p, far


def _z_intents(pid):
    return [Intent(z_pressed=i == pid) for i in range(2)]


def _remote_intents(pid):
    r = RemoteInput()
    r.feed({"t": "in", "mx": 0, "v": 0, "z": 1})
    intents = [Intent(), Intent()]
    intents[pid] = r.consume()
    assert not r.consume().z_pressed
    return intents


# Property 5 -- Validates: Requirements 3.8, 7.6
def test_host_delayed_z_catches_fast_ball():
    g, p, far = _delayed_z_scenario(1, _z_intents)
    assert far > g.t.pickup_radius  # plain In_Reach would miss
    assert p.held_ball is g.ball and g.ball.held_by is p

    g, p, far = _delayed_z_scenario(1, _z_intents, pickup_grace_time=0)
    assert far > g.t.pickup_radius
    assert p.held_ball is None and g.ball.held_by is None


# Property 5 -- Validates: Requirements 3.7, 3.8, 7.6
def test_remote_input_delayed_z():
    g, p, far = _delayed_z_scenario(1, _remote_intents)
    assert far > g.t.pickup_radius
    assert p.held_ball is g.ball and g.ball.held_by is p

    g, p, _ = _delayed_z_scenario(1, _remote_intents, pickup_grace_time=0)
    assert p.held_ball is None


# Property 5 -- Validates: Requirements 3.7
def test_remote_input_z_edge_latches_until_consumed():
    r = RemoteInput()
    r.feed({"t": "in", "mx": 0, "v": 0, "z": 1})
    r.feed({"t": "in", "mx": 0, "v": 0, "z": 0})  # later message must not erase the press

    def latched(pid):
        first = r.consume()
        assert first.z_pressed and not r.consume().z_pressed
        intents = [Intent(), Intent()]
        intents[pid] = first
        return intents

    g, p, far = _delayed_z_scenario(1, latched)
    assert far > g.t.pickup_radius
    assert p.held_ball is g.ball


# Property 5 -- Validates: Requirements 3.7, 3.8
def test_host_local_player_gets_same_late_press_result_as_joiner():
    g1, p1, far1 = _delayed_z_scenario(1, _z_intents)
    g0, p0, far0 = _delayed_z_scenario(0, _z_intents)
    assert far0 == pytest.approx(far1) and far0 > g0.t.pickup_radius
    assert p0.held_ball is g0.ball and g0.ball.held_by is p0
    assert p1.held_ball is g1.ball
    g0, p0, _ = _delayed_z_scenario(0, _z_intents, pickup_grace_time=0)
    assert p0.held_ball is None
