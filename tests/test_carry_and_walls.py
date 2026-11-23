"""Ball carriers are slower on the ground; you can't re-cling to the wall you just left."""

import pytest
from conftest import make_game, run

from ballbrawlla.input import Intent

R, L = 1, -1


def give_ball(g, p):
    g.ball.held_by, p.held_ball = p, g.ball


# ---------------------------------------------------------------- carrying the ball

def test_carrier_runs_and_slides_slower_but_jumps_the_same():
    g = make_game(players=[(200, 650), (200, 600)], ball_gravity=0)
    run(g, ticks=60)
    free, carrier = g.players
    give_ball(g, carrier)
    m = g.t.carry_speed_multiplier
    assert 0.75 <= m < 1.0                       # slower, not a snail
    run(g, [Intent(move_x=R), Intent(move_x=R)], ticks=5)
    assert free.vel.x == pytest.approx(g.t.run_speed)
    assert carrier.vel.x == pytest.approx(g.t.run_speed * m)
    assert carrier.slide_speed == pytest.approx(g.t.slide_speed * m)
    assert carrier.crawl_speed == pytest.approx(g.t.crawl_speed * m)
    assert carrier.air_speed == free.air_speed == g.t.air_speed   # jumping is how you escape


def test_defender_wins_a_flat_race_against_the_carrier():
    g = make_game(players=[(100, 650), (100, 600)], ball_gravity=0)
    run(g, ticks=60)
    defender, carrier = g.players
    give_ball(g, carrier)
    run(g, [Intent(move_x=R), Intent(move_x=R)], ticks=120)     # one second
    gap = defender.center.x - carrier.center.x
    assert gap == pytest.approx(g.t.run_speed * (1 - g.t.carry_speed_multiplier), rel=0.05)


def test_without_the_ball_full_speed_returns():
    g = make_game(players=[(200, 650)], ball_gravity=0)
    run(g, ticks=60)
    p = g.player
    give_ball(g, p)
    g.ball.held_by, p.held_ball = None, None
    run(g, Intent(move_x=R), ticks=5)
    assert p.vel.x == pytest.approx(g.t.run_speed)


# ---------------------------------------------------------------- one cling per wall

WALL = (600, 100, 24, 588)          # floor-to-high wall, left face at x=600


def cling_right(g, ticks=30):
    """Jump and push right until clinging (or give up)."""
    run(g, Intent(move_x=R, vertical=1, jump_pressed=True))
    for _ in range(ticks):
        run(g, Intent(move_x=R, vertical=1))
        if g.player.state.name == "wall_cling":
            return True
    return False


def test_cannot_cling_to_the_same_wall_twice_in_a_row():
    g = make_game(platforms=[WALL], player=(560, 650))
    run(g, ticks=30)
    assert cling_right(g)
    run(g, Intent(move_x=L, vertical=1, jump_pressed=True))  # wall-jump away...
    states = []
    for _ in range(90):                                       # ...and steer straight back into it
        run(g, Intent(move_x=R, vertical=1))
        states.append(g.player.state.name)
    assert "wall_cling" not in states
    assert g.player.box.right == pytest.approx(600)           # it did get back to the wall


def test_landing_lets_you_grab_the_same_wall_again():
    g = make_game(platforms=[WALL], player=(560, 650))
    run(g, ticks=30)
    assert cling_right(g)
    run(g, Intent(), ticks=180)                               # slide down and land
    assert g.player.state.name == "grounded"
    assert cling_right(g)


def test_alternating_between_two_walls_is_allowed():
    a, b = (500, 100, 24, 588), (640, 100, 24, 588)           # a chimney, 116 px wide
    g = make_game(platforms=[a, b], player=(580, 650))
    run(g, ticks=30)
    assert cling_right(g)                                     # wall B
    sides = []
    direction = L
    for _ in range(4):
        run(g, Intent(move_x=direction, vertical=1, jump_pressed=True))  # wall-jump across
        for _ in range(60):
            run(g, Intent(move_x=direction, vertical=1))
            if g.player.state.name == "wall_cling":
                break
        sides.append(g.player.state.name)
        direction = -direction
    assert sides == ["wall_cling"] * 4                        # A, B, A, B
