"""Crouching crawls instead of freezing, so a slide that ends under a low gap is never a trap."""

from conftest import make_game, run

from ballbrawlla.config import Tuning
from ballbrawlla.input import Intent

FLOOR_TOP = 688
# A 200 px wide slab with a 32 px gap above the floor: longer than a slide (about 150 px).
SLAB = (300, FLOOR_TOP - 32 - 24, 200, 24)


def _slid_into_slab(**tuning):
    g = make_game(platforms=[SLAB], player=(250, 650), **tuning)
    run(g, ticks=60)
    run(g, Intent(move_x=1, vertical=-1), ticks=2)
    assert g.player.state.name == "slide"
    for _ in range(100):
        run(g, Intent(move_x=1, vertical=-1))
        if g.player.state.name == "crouch":
            break
    p = g.player
    assert p.state.name == "crouch"
    assert SLAB[0] < p.center.x < SLAB[0] + SLAB[2]  # the slide ended under the slab
    return g


def test_default_crawl_speed():
    t = Tuning()
    assert t.crawl_speed == 110
    assert 0 < t.crawl_speed < t.run_speed


def test_crouched_player_crawls_at_crawl_speed():
    g = make_game()
    run(g, ticks=60)
    run(g, Intent(vertical=-1), ticks=2)
    p = g.player
    assert p.state.name == "crouch"
    x0 = p.center.x
    run(g, Intent(move_x=1, vertical=-1), ticks=120)  # one second
    assert p.state.name == "crouch"
    assert abs((p.center.x - x0) - g.t.crawl_speed) < 3
    assert p.facing == 1


def test_slide_that_ends_under_a_gap_can_crawl_out():
    g = _slid_into_slab()
    p = g.player
    for _ in range(600):
        run(g, Intent(move_x=1))  # Down released, still blocked from standing under the slab
        if p.center.x > SLAB[0] + SLAB[2] + 20:
            break
    assert p.center.x > SLAB[0] + SLAB[2] + 20  # out the far side
    run(g, Intent(), ticks=5)
    assert p.state.name == "grounded" and p.h == g.t.player_height


def test_can_crawl_back_out_the_way_it_came():
    g = _slid_into_slab()
    p = g.player
    for _ in range(900):
        run(g, Intent(move_x=-1))
        if p.center.x < SLAB[0] - 20:
            break
    assert p.center.x < SLAB[0] - 20
    run(g, Intent(), ticks=5)
    assert p.state.name == "grounded"


def test_crawl_speed_zero_keeps_the_old_frozen_crouch():
    g = _slid_into_slab(crawl_speed=0)
    p = g.player
    x0 = p.center.x
    run(g, Intent(move_x=1), ticks=240)
    assert p.state.name == "crouch" and abs(p.center.x - x0) < 1e-6


def test_crawling_player_still_cannot_stand_under_the_gap():
    g = _slid_into_slab()
    p = g.player
    run(g, Intent(), ticks=30)  # Down released, standing still under the slab
    assert p.state.name == "crouch" and p.h == g.t.player_crouch_height
