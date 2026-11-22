"""Ball vs thin (one-way) platforms. Validates: Requirements 7.1-7.6, 8.3."""

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.entities.ball import Ball
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2

R = Tuning().ball_radius
DT = Tuning().dt


def mk(pos, vel, **tuning) -> Ball:
    b = Ball(Vector2(pos), Tuning(**tuning))
    b.release(Vector2(pos), Vector2(vel))
    return b


def state(b: Ball):
    return (b.pos.x, b.pos.y, b.vel.x, b.vel.y, b.resting)


def assert_same(a: Ball, b: Ball):
    assert state(a) == pytest.approx(state(b), abs=1e-6)


def test_thin_landing_matches_solid_floor():
    plat = AABB(400, 500, 200, 20)
    thin = mk((500, 470), (100, 300))
    solid = mk((500, 470), (100, 300))
    bounced = False
    for _ in range(60):
        thin.update(DT, [], [plat])
        solid.update(DT, [plat], [])
        assert_same(thin, solid)
        bounced = bounced or thin.vel.y < 0
    assert bounced


def test_slow_landing_rests_and_rolls():
    plat = AABB(400, 500, 200, 20)
    b = mk((450, plat.top - R - 0.05), (100, 0))
    for _ in range(5):
        b.update(DT, [], [plat])
    assert b.resting
    assert b.vel.y == 0
    assert b.pos.y + R == pytest.approx(plat.top, abs=1e-6)
    vx = b.vel.x
    b.update(DT, [], [plat])
    assert b.resting and 0 < b.vel.x < vx


def test_corner_landing_snaps_to_top():
    plat = AABB(400, 500, 200, 20)
    b = mk((398, plat.top - R - 2), (0, 300))
    b.update(DT, [], [plat])
    assert b.pos.y == pytest.approx(plat.top - R, abs=1e-6)
    assert b.pos.x == pytest.approx(398)
    assert b.vel.y <= 0


def test_rising_ball_passes_through():
    plat = AABB(400, 500, 200, 20)
    a = mk((500, 540), (0, -500))
    b = mk((500, 540), (0, -500))
    for _ in range(30):
        a.update(DT, [], [plat])
        b.update(DT, [], [])
        assert_same(a, b)
    assert a.pos.y < plat.top


def test_ball_below_top_moving_down_passes_through():
    plat = AABB(400, 500, 200, 20)
    a = mk((500, 530), (0, 200))
    b = mk((500, 530), (0, 200))
    for _ in range(20):
        a.update(DT, [], [plat])
        b.update(DT, [], [])
        assert_same(a, b)
    assert a.pos.y > 530


def test_zero_vertical_velocity_passes_through_thin_side():
    plat = AABB(400, 500, 200, 20)
    b = mk((380, 510), (200, 0), ball_gravity=0)
    for _ in range(240):
        b.update(DT, [], [plat])
    assert b.pos.y == 510
    assert b.vel.x == 200
    assert b.pos.x > plat.right


@pytest.mark.parametrize("h", [1, 20])
@pytest.mark.parametrize("vel", [(0, 1400), (990, 990)])
def test_power_max_never_passes_below_top(h, vel):
    plat = AABB(400, 500, 200, h)
    start_x = 500 if vel[0] == 0 else 420
    b = mk((start_x, plat.top - 100), vel)
    bounced = False
    for _ in range(120):
        b.update(DT, [], [plat])
        if plat.left <= b.pos.x <= plat.right:
            assert b.pos.y <= plat.top - R + 1e-6
        if b.vel.y < 0:
            bounced = True
    assert bounced


@pytest.mark.parametrize(
    "pos,vel,check",
    [
        ((500, 540), (0, -300), lambda b: b.vel.y > 0),  # from below
        ((380, 510), (300, 0), lambda b: b.vel.x < 0),  # from the left
        ((620, 510), (-300, 0), lambda b: b.vel.x > 0),  # from the right
        ((500, 470), (0, 300), lambda b: b.vel.y < 0),  # from above
    ],
)
def test_solid_bounces_ball_from_every_side(pos, vel, check):
    plat = AABB(400, 500, 200, 20)
    b = mk(pos, vel, ball_gravity=0)
    for _ in range(30):
        b.update(DT, [plat], [])
    assert check(b)
