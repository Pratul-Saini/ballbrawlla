"""You can't re-cling to the wall you just left."""

import pytest
from conftest import make_game, run

from ballbrawlla.input import Intent

R, L = 1, -1


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
    run(g, Intent(move_x=L, vertical=1))                     # wall-jump away...
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
        run(g, Intent(move_x=direction, vertical=1))          # wall-jump across
        for _ in range(60):
            run(g, Intent(move_x=direction, vertical=1))
            if g.player.state.name == "wall_cling":
                break
        sides.append(g.player.state.name)
        direction = -direction
    assert sides == ["wall_cling"] * 4                        # A, B, A, B
