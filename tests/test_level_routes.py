"""The lane mechanics the new fields are designed around, run with the real
physics: each route must work with the intended move and fail without it."""

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.main import LEVELS
from ballbrawlla.world.level import load_level

T = Tuning()


def start(level: str, x: float, feet_y: float) -> Game:
    g = Game(load_level(LEVELS / f"{level}.json"), T, 1)
    p = g.player
    p.body.pos.update(x - p.w / 2, feet_y - p.h)
    g.ball.body.pos.update(10_000, 0)  # out of the way
    g.ball.held_by = None
    for _ in range(20):
        g.step([Intent()], T.dt)
    assert p.contacts.on_ground and p.box.bottom == pytest.approx(feet_y)
    return g


def play(g: Game, *program) -> None:
    for intent, ticks in program:
        for _ in range(ticks):
            g.step([intent], T.dt)


def feet(g: Game) -> tuple[float, float]:
    p = g.player
    return p.center.x, p.box.bottom


R, L = 1, -1


def leap(g: Game, direction: int, double_after: int | None = None, hold: int = 999) -> None:
    """Jump holding Up, and `direction` for the first `hold` ticks, optionally
    double-jumping after N ticks; let go of everything as soon as the player lands."""
    p = g.player
    g.step([Intent(move_x=direction, vertical=1, jump_pressed=True)], T.dt)
    for tick in range(1, 240):
        d = direction if tick < hold else 0
        g.step([Intent(move_x=d, vertical=1, jump_pressed=tick == double_after)], T.dt)
        if tick > 3 and p.state.name == "grounded":
            break
    play(g, (Intent(), 20))


def yd(y: float) -> float:
    """x of a yard line on the 44 px/yard lane fields (field_06-07)."""
    return 472 + 44 * y


def hop_up_wall(g: Game, direction: int, hops: int = 10) -> None:
    """The old way up a wall: jump into it and keep pressing Up (now a single hop)."""
    play(g, (Intent(move_x=direction, jump_pressed=True, vertical=1), 1), (Intent(move_x=direction, vertical=1), 12))
    for _ in range(hops):
        play(g, (Intent(move_x=direction, jump_pressed=True, vertical=1), 1), (Intent(move_x=direction, vertical=1), 14))
    play(g, (Intent(move_x=direction, vertical=1), 40), (Intent(), 40))


def chimney(g: Game, first: int, rise: int = 0) -> None:
    """Jump straight up for `rise` ticks, lean toward `first`, then wall-jump (Up + away)
    from every wall and hold toward the next one, until standing somewhere."""
    p = g.player
    play(g, (Intent(vertical=1, jump_pressed=True), 1), (Intent(vertical=1), rise))
    d = first
    for tick in range(1500):
        if p.state.name == "wall_cling":
            d = -p.state.side
            g.step([Intent(move_x=d, vertical=1, jump_pressed=True)], T.dt)
        else:
            g.step([Intent(move_x=d, vertical=1)], T.dt)
            if tick > 10 and p.state.name == "grounded":
                break
    play(g, (Intent(), 20))


# Every chimney: (level, start x, start feet y, lean, rise, an upper surface at or above this y)
CHIMNEYS = [
    ("field_06", 1793, 1428, L, 6, 1138),    # wall shaft, girder at the 27 -> top lane
    ("field_07", 758, 1768, R, 6, 1508),     # trunks at the 5-8, ground -> branches
    ("field_07", 1506, 1768, R, 0, 1528),    # trunks at the 22-25, ground -> branches
    ("field_07", 1616, 1528, L, 0, 1228),    # trunks on the branch at the 25-30 -> upper branches
    ("field_07", 2320, 1518, L, 0, 1248),    # trunks on the branch at the 41-46 -> upper branches
    ("field_09", 1400, 1968, L, 0, 1488),    # opening at the 13, courtyard -> ramparts
    ("field_09", 2132, 1518, R, 0, 1038),    # opening at the 26, ramparts -> battlements
    ("field_10", 1685, 2168, R, 0, 1648),    # opening at the 17, floor -> walkways
    ("field_10", 2857, 1618, R, 0, 1128),    # opening at the 38, walkways -> surface
    ("field_11", 1320, 1808, L, 0, 1248),    # masts at the 10-12.5, deck -> gantries
    ("field_11", 2210, 1808, L, 0, 1288),    # masts at the 24.5-27, deck -> gantries
]


@pytest.mark.parametrize("level,x,y,first,rise,up_to", CHIMNEYS)
def test_chimney_wall_jumps_up_a_lane(level, x, y, first, rise, up_to):
    g = start(level, x, y)
    chimney(g, first, rise)
    assert feet(g)[1] <= up_to
    g = start(level, x, y)
    leap(g, 0, double_after=30)                   # a double jump alone falls short
    assert feet(g)[1] > up_to


# ---------------------------------------------------------------- Scaffold (field_06)

def test_scaffold_ladder_takes_two_jumps_from_ground_to_girders():
    g = start("field_06", 1210, 1668)            # under the step ledge at the 16
    leap(g, 0)
    assert feet(g)[1] == pytest.approx(1528)
    leap(g, R)
    assert feet(g)[1] == pytest.approx(1388)     # girder at the 18-24


def test_scaffold_girders_are_solid_from_below():
    g = start("field_06", 1400, 1668)            # under the girder at the 18-24
    leap(g, 0, double_after=30)
    assert feet(g)[1] == pytest.approx(1668)     # bonks its underside


def test_scaffold_wall_shaft_climbs_to_the_top_lane():
    g = start("field_06", 1793, 1428)            # girder at the 27-31, in the shaft
    chimney(g, L, 6)
    assert feet(g)[1] == pytest.approx(1138)     # top lane at the 31-38


def test_one_wall_alone_cannot_be_climbed():
    g = start("field_06", 1700, 1428)            # girder at the 27-31, the shaft's post to the right
    hop_up_wall(g, R)
    assert feet(g)[1] == pytest.approx(1428)     # one hop, slide down, back on the girder


def test_scaffold_crown_over_midfield():
    g = start("field_06", 2440, 1108)            # top lane at the 42-47, under the step
    leap(g, 0)
    assert feet(g)[1] == pytest.approx(968)
    leap(g, R)
    assert feet(g)[1] == pytest.approx(830)      # the crown


# ---------------------------------------------------------------- Canopy (field_07)

def test_canopy_twig_then_branch():
    g = start("field_07", 1120, 1768)            # under the twig at the 14
    leap(g, 0)
    assert feet(g)[1] == pytest.approx(1628)
    leap(g, L)
    assert feet(g)[1] == pytest.approx(1508)     # branch at the 8-13


def test_canopy_branches_are_one_way_from_below():
    g = start("field_07", 1700, 1768)            # under the branch at the 25-30 (240 px up)
    leap(g, 0)
    assert feet(g)[1] == pytest.approx(1768)
    g = start("field_07", 1700, 1768)
    leap(g, 0, double_after=40)
    assert feet(g)[1] == pytest.approx(1528)     # jumped up through it and landed on top


def test_canopy_trunk_climbs_to_the_upper_branches():
    g = start("field_07", 1616, 1528)            # branch at the 25-30, between two trunks
    chimney(g, L)
    assert feet(g)[1] == pytest.approx(1178)     # upper branch at the 29-35


# ---------------------------------------------------------------- Undercity (field_08)

def test_undercity_buildings_block_the_street():
    g = start("field_08", 530, 1660)
    play(g, (Intent(move_x=R), 60))
    x, y = feet(g)
    assert y == pytest.approx(1660) and x < 560


def test_undercity_subway_route_under_a_building():
    g = start("field_08", 1100, 1768)            # in the subway, turnstile ahead at 1176..1206
    play(g, (Intent(move_x=R), 60))
    assert feet(g)[0] < 1176                     # can't walk through the turnstile
    play(g, (Intent(move_x=R, vertical=-1), 30), (Intent(move_x=R), 1))
    for _ in range(200):
        play(g, (Intent(move_x=R), 1))
        if feet(g)[0] >= 1440:
            break
    assert feet(g)[1] == pytest.approx(1768)     # still in the subway, under the stairwell
    leap(g, R)
    x, y = feet(g)
    assert y == pytest.approx(1660) and x > 1528  # up through the stairwell onto the street


def test_undercity_fire_escape_to_a_tall_roof():
    g = start("field_08", 1050, 1660)            # street, at the foot of the tall building at the 14
    leap(g, 0)
    assert feet(g)[1] == pytest.approx(1520)
    leap(g, L, hold=19)                          # a short tap: the flights zig-zag
    assert feet(g)[1] == pytest.approx(1380)
    leap(g, R)
    assert feet(g)[1] == pytest.approx(1240)     # the roof


# ---------------------------------------------------------------- three-lane maps (field_09-10)

def steer_leap(g: Game, target_x: float) -> None:
    """Jump holding Up, steering toward target_x, and stop when landed."""
    p = g.player
    for tick in range(240):
        dx = target_x - p.center.x
        d = 0 if abs(dx) < 4 else (1 if dx > 0 else -1)
        g.step([Intent(move_x=d, vertical=1, jump_pressed=tick == 0)], T.dt)
        if tick > 3 and p.state.name == "grounded":
            break
    play(g, (Intent(), 20))


def climb_stair(g: Game, xs: list[float], ys: list[float]) -> None:
    for x, y in zip(xs, ys):
        steer_leap(g, x)
        assert feet(g)[1] == pytest.approx(y), f"missed the step at ({x}, {y})"


def test_fortress_stair_from_courtyard_to_ramparts():
    # Opening at the 4: steps at x 862/938 (alternating), 120 px apart; rampart ends at x 816.
    g = start("field_09", 862, 1968)
    climb_stair(g, [862, 938, 862, 790], [1848, 1728, 1608, 1488])


def test_fortress_ramparts_are_solid_from_below():
    g = start("field_09", 1600, 1968)            # under the rampart at the 16-21
    leap(g, 0, double_after=30)
    assert feet(g)[1] == pytest.approx(1968)


def test_fortress_wall_climb_from_courtyard_to_ramparts():
    g = start("field_09", 1400, 1968)            # in the chimney at the 13
    chimney(g, L)
    assert feet(g)[1] == pytest.approx(1458)     # rampart at the 7-13


def test_fortress_lanes_switch_at_different_yard_lines():
    from ballbrawlla.rules.field import Field
    from ballbrawlla.rules.teams import Team
    from ballbrawlla.world.level import load_level

    lv = load_level(LEVELS / "field_09.json")
    f = Field(lv, T)
    mid_gaps, top_gaps = set(), set()
    for y, gaps in ((1488, mid_gaps), (1008, top_gaps)):
        xs = sorted((p.rect.left, p.rect.right) for p in lv.platforms
                    if p.kind == "platform" and abs(p.rect.top - y) <= 40 and p.rect.w > 150)
        for (_, r), (l2, _) in zip(xs, xs[1:]):
            if l2 - r > 60 and f.goal_line_x(Team.LEFT) < r < f.goal_line_x(Team.RIGHT):
                gaps.add(round(f.yards_from_goal(Team.LEFT, r)))
    assert len(mid_gaps) >= 5 and len(top_gaps) >= 4
    assert mid_gaps != top_gaps                  # switch points are staggered, not stacked


def test_harbor_mast_climb_from_deck_to_gantry():
    g = start("field_11", 1320, 1808)            # deck at the 6-15, between the masts at the 10-12.5
    chimney(g, L)
    assert feet(g)[1] == pytest.approx(1208)     # gantry at the 12.5-17


def test_mineshaft_stair_from_floor_to_walkway():
    # Opening at the 2 (58 px/yd): steps 130 px apart up to the walkway ending at the 2.
    yd9 = lambda y: 612 + 58 * y
    w = round(0.35 * 3 * 58)
    a, b = yd9(2 + 0.3) + w / 2, yd9(2 + 1.65) + w / 2
    g = start("field_10", a, 2168)
    climb_stair(g, [a, b, a, yd9(2) - 20], [2038, 1908, 1778, 1648])
