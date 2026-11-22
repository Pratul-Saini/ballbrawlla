"""Ball.update only tests the platforms near it. That must change nothing about the result."""

import copy
import math
import random

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.entities import ball as ball_mod
from ballbrawlla.entities.ball import Ball
from ballbrawlla.main import LEVELS
from ballbrawlla.physics.collision import ABOVE_TOP_TOL, bounce, circle_vs_aabb
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.world.level import load_level

T = Tuning()


def reference_update(ball: Ball, dt, solids, thin):
    """Ball.update exactly as it was before culling: every platform, every sub-step."""
    ball.body.integrate_velocity(dt)
    travel = ball.body.vel.length() * dt
    steps = max(1, math.ceil(travel / (ball.radius * 0.5)))
    sub_dt = dt / steps
    ball.resting = False
    for _ in range(steps):
        prev_bottom = ball.body.pos.y + ball.radius
        vy = ball.body.vel.y
        ball.body.pos += ball.body.vel * sub_dt
        for s in solids:
            c = circle_vs_aabb(ball.body.pos, ball.radius, s)
            if c is None:
                continue
            ball.body.pos += c.normal * c.depth
            ball.body.vel = bounce(ball.body.vel, c.normal, T.ball_restitution, T.ball_bounce_friction, T.ball_rest_speed)
            if c.normal.y < -0.7:
                ball.resting = abs(ball.body.vel.y) < 1e-6
        if vy > 0:
            for t in thin:
                if prev_bottom <= t.top + ABOVE_TOP_TOL and circle_vs_aabb(ball.body.pos, ball.radius, t) is not None:
                    ball.body.pos.y = t.top - ball.radius
                    ball.body.vel = bounce(ball.body.vel, Vector2(0, -1), T.ball_restitution, T.ball_bounce_friction, T.ball_rest_speed)
                    ball.resting = abs(ball.body.vel.y) < 1e-6
    if ball.resting:
        ball.body.vel.x *= max(0.0, 1 - T.ball_rolling_drag * dt)


@pytest.mark.parametrize("level", ["field_01", "field_05", "field_12", "field_14"])
def test_culling_gives_identical_results_to_testing_every_platform(level):
    lv = load_level(LEVELS / f"{level}.json")
    rng = random.Random(level)
    for trial in range(6):
        x = rng.uniform(lv.wall_thickness + 20, lv.width - lv.wall_thickness - 20)
        y = rng.uniform(lv.wall_thickness + 20, lv.height - lv.wall_thickness - 60)
        speed = rng.choice([0, 300, 900, 1400])
        ang = rng.uniform(0, 2 * math.pi)
        a = Ball(Vector2(x, y), T)
        a.release(Vector2(x, y), Vector2(math.cos(ang) * speed, math.sin(ang) * speed))
        b = copy.deepcopy(a)
        for tick in range(600):
            a.update(T.dt, lv.solids, lv.thin)
            reference_update(b, T.dt, lv.solids, lv.thin)
            assert (a.pos.x, a.pos.y, a.vel.x, a.vel.y, a.resting) == (b.pos.x, b.pos.y, b.vel.x, b.vel.y, b.resting), \
                f"{level} trial {trial} tick {tick}: culled ball diverged"


def test_a_ball_far_from_everything_tests_almost_no_platforms(monkeypatch):
    lv = load_level(LEVELS / "field_05.json")
    calls = []
    real = ball_mod.circle_vs_aabb
    monkeypatch.setattr(ball_mod, "circle_vs_aabb", lambda *args: (calls.append(1), real(*args))[1])
    b = Ball(Vector2(100_000, 0), T)  # the way the skill-route tests park it
    for _ in range(120):
        b.update(T.dt, lv.solids, lv.thin)
    assert len(lv.solids) + len(lv.thin) >= 90
    assert len(calls) == 0


def test_a_ball_in_the_middle_of_the_level_tests_only_its_neighbours(monkeypatch):
    lv = load_level(LEVELS / "field_05.json")
    calls = []
    real = ball_mod.circle_vs_aabb
    monkeypatch.setattr(ball_mod, "circle_vs_aabb", lambda *args: (calls.append(1), real(*args))[1])
    b = Ball(Vector2(2900, 1500), T)
    b.update(T.dt, lv.solids, lv.thin)
    total = len(lv.solids) + len(lv.thin)
    assert len(calls) < total / 5, f"tested {len(calls)} of {total} platforms"
