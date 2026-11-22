import pytest

from conftest import make_game, run

from ballbrawlla.input import Intent

LEFT_WALL_X = 32  # inner face of the generated left boundary


def test_player_falls_and_lands(settled):
    assert settled.player.state.name == "grounded"
    assert settled.player.box.bottom == 720 - 32


def test_run_speed_is_fixed(settled):
    run(settled, Intent(move_x=1), ticks=10)
    assert settled.player.vel.x == settled.t.run_speed


def test_jump_then_land(settled):
    run(settled, Intent(jump_pressed=True, vertical=1))
    assert settled.player.state.name == "airborne"
    assert settled.player.vel.y < 0
    run(settled, ticks=120)
    assert settled.player.state.name == "grounded"


def test_double_jump_consumes_air_jump(settled):
    run(settled, Intent(jump_pressed=True, vertical=1))
    run(settled, Intent(vertical=1), ticks=10)
    run(settled, Intent(jump_pressed=True, vertical=1))
    assert settled.player.jumps_left == 0
    assert settled.player.vel.y < 0


def test_crouch_and_slide(settled):
    p = settled.player
    run(settled, Intent(vertical=-1), ticks=2)
    assert p.state.name == "crouch" and p.h == settled.t.player_crouch_height
    run(settled, ticks=2)
    assert p.state.name == "grounded" and p.h == settled.t.player_height
    run(settled, Intent(move_x=1, vertical=-1), ticks=2)
    assert p.state.name == "slide"
    assert p.vel.x > settled.t.run_speed


def _cling_left(g):
    # Jump, drift left into the boundary wall and hold into it.
    run(g, Intent(jump_pressed=True, vertical=1))
    for _ in range(240):
        run(g, Intent(move_x=-1, vertical=1))
        if g.player.state.name == "wall_cling":
            return
    raise AssertionError("never clung to wall")


def test_wall_cling_slides_slowly_and_wall_jumps():
    g = make_game(player=(120, 650))
    run(g, ticks=60)
    _cling_left(g)
    p = g.player
    assert p.box.left == LEFT_WALL_X
    run(g, ticks=60)  # no input: slide down gradually
    assert p.state.name == "wall_cling"
    assert 0 < p.vel.y <= g.t.wall_slide_max_speed
    run(g, Intent(move_x=1))  # press away: wall jump
    assert p.state.name == "airborne"
    assert p.vel.x > 0 and p.vel.y < 0


def test_up_on_wall_climbs():
    g = make_game(player=(120, 650))
    run(g, ticks=60)
    _cling_left(g)
    run(g, Intent(jump_pressed=True, vertical=1))
    assert g.player.state.name == "wall_cling"
    assert g.player.vel.y < 0


def test_pickup_aim_and_throw():
    g = make_game(player=(200, 650), ball=(220, 650))
    run(g, ticks=60)
    p, b = g.player, g.ball
    run(g, Intent(z_pressed=True))
    assert b.held_by is p
    run(g, Intent(z_pressed=True))
    assert p.state.name == "aiming"
    x0 = p.box.x
    run(g, Intent(move_x=1, vertical=1), ticks=30)  # rotate + add power; player stays put
    assert p.box.x == x0
    assert p.aim_power > (g.t.power_min + g.t.power_max) / 2
    angle, power = p.aim_angle, p.aim_power
    run(g, Intent(x_pressed=True))
    assert b.held_by is None and p.held_ball is None
    assert p.state.name == "grounded"
    # The throw happened before this tick's ball gravity step, so speed ~= power.
    assert abs(b.vel.length() - power) < power * 0.05
    assert angle < 45  # right arrow rotated clockwise


def test_pickup_out_of_reach_does_nothing(settled):
    run(settled, Intent(z_pressed=True))
    assert settled.ball.held_by is None


def test_ball_bounces_and_settles():
    g = make_game(ball=(640, 200))
    b = g.ball
    peak_vy = []
    for _ in range(600):
        prev = b.vel.y
        run(g)
        if prev > 0 and b.vel.y < 0:
            peak_vy.append(prev)
    assert len(peak_vy) >= 2, "ball should bounce more than once"
    assert peak_vy[1] < peak_vy[0], "bounces lose energy"
    assert b.resting
    assert abs(b.pos.y - (720 - 32 - b.radius)) < 1


def test_wall_absorbs_most_of_the_balls_energy():
    from ballbrawlla.physics.vec import Vector2

    g = make_game(ball=(640, 400), ball_gravity=0)
    v0 = 1000.0
    g.ball.release(Vector2(1200, 400), Vector2(v0, 0))  # straight at the right wall
    for _ in range(60):
        run(g)
        if g.ball.vel.x < 0:
            break
    assert g.ball.vel.x < 0, "ball should bounce back off the wall"
    kept = g.ball.vel.length() / v0
    assert kept == pytest.approx(g.t.ball_restitution)
    assert kept <= 0.5  # most of the energy is gone (energy kept = kept**2)


def test_glancing_wall_hit_also_loses_speed_along_the_wall():
    from ballbrawlla.physics.vec import Vector2

    g = make_game(ball=(640, 400), ball_gravity=0)
    g.ball.release(Vector2(1200, 400), Vector2(600, -600))
    for _ in range(60):
        run(g)
        if g.ball.vel.x < 0:
            break
    assert g.ball.vel.y == pytest.approx(-600 * (1 - g.t.ball_bounce_friction))
