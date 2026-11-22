from conftest import make_game, run

from ballbrawlla.input import Intent

FLOOR_TOP = 688
THIN_TOP = 600
THIN = (150, THIN_TOP, 200, 20)


def test_player_falls_onto_thin_platform():
    g = make_game(thin=[THIN], player=(200, 500))
    run(g, ticks=90)
    p = g.player
    assert p.state.name == "grounded"
    assert p.box.bottom == THIN_TOP
    assert p.vel.y == 0
    assert p.contacts.on_ground


def test_jump_up_through_thin_platform_and_land_on_top():
    g = make_game(thin=[THIN], player=(200, 650))
    run(g, ticks=60)
    assert g.player.box.bottom == FLOOR_TOP
    run(g, Intent(jump_pressed=True, vertical=1))
    min_bottom = g.player.box.bottom
    for _ in range(60):  # hold Up so the jump is not cut short
        run(g, Intent(vertical=1))
        assert not g.player.contacts.on_ceiling
        min_bottom = min(min_bottom, g.player.box.bottom)
    assert min_bottom < THIN_TOP  # apex cleared the platform top
    for _ in range(120):
        run(g)
        assert not g.player.contacts.on_ceiling
    p = g.player
    assert p.state.name == "grounded"
    assert p.box.bottom == THIN_TOP


def test_airborne_beside_thin_side_never_clings():
    g = make_game(thin=[(300, 200, 100, 300)], player=(250, 280))
    max_right = 0
    for _ in range(40):
        run(g, Intent(move_x=1, vertical=1))
        p = g.player
        assert p.state.name != "wall_cling"
        assert not (p.contacts.wall_left or p.contacts.wall_right)
        max_right = max(max_right, p.box.right)
    assert max_right > 300  # moved into / through the thin platform


def test_airborne_beside_solid_side_wall_clings():
    g = make_game(platforms=[(300, 200, 100, 300)], player=(250, 280))
    for _ in range(120):
        run(g, Intent(move_x=1, vertical=1))
        if g.player.state.name == "wall_cling":
            break
    assert g.player.state.name == "wall_cling"
    assert g.player.contacts.wall_right


# --- stand-up checks -------------------------------------------------------

OVERHEAD = (120, 640, 780, 10)  # overlaps a full-height box on the floor, not a crouched one


def _crouched_under(overhead_kind):
    kwargs = {"thin": [OVERHEAD]} if overhead_kind == "thin" else {"platforms": [OVERHEAD]}
    g = make_game(player=(50, 650), **kwargs)
    run(g, ticks=60)
    assert g.player.box.bottom == FLOOR_TOP
    return g


def _slide_in(g):
    run(g, Intent(move_x=1, vertical=-1))
    assert g.player.state.name == "slide"


def _crouch_in(g):
    _slide_in(g)
    for _ in range(100):
        run(g, Intent(vertical=-1))
        if g.player.state.name == "crouch":
            break
    p = g.player
    assert p.state.name == "crouch" and p.h == g.t.player_crouch_height
    assert p.box.left >= 120 and p.box.right <= 900  # fully under the overhead


def _ticks_while_sliding(g, intent):
    for _ in range(100):
        run(g, intent)
        if g.player.state.name != "slide":
            return
    raise AssertionError("slide never ended")


def test_crouch_release_under_thin_stands_up():
    g = _crouched_under("thin")
    _crouch_in(g)
    run(g, Intent())
    p = g.player
    assert p.state.name == "grounded"
    assert p.h == g.t.player_height
    assert p.box.bottom == FLOOR_TOP


def test_crouch_release_under_solid_stays_crouched():
    g = _crouched_under("solid")
    _crouch_in(g)
    run(g, Intent(), ticks=5)
    p = g.player
    assert p.state.name == "crouch"
    assert p.h == g.t.player_crouch_height
    assert p.box.bottom == FLOOR_TOP


def test_slide_end_under_thin_stands_up():
    g = _crouched_under("thin")
    _slide_in(g)
    _ticks_while_sliding(g, Intent(move_x=1))
    p = g.player
    assert p.state.name == "grounded"
    assert p.h == g.t.player_height
    assert p.box.bottom == FLOOR_TOP


def test_slide_end_under_solid_stays_crouched():
    g = _crouched_under("solid")
    _slide_in(g)
    _ticks_while_sliding(g, Intent(move_x=1))
    p = g.player
    assert p.state.name == "crouch"
    assert p.h == g.t.player_crouch_height
    assert p.box.bottom == FLOOR_TOP


def test_jump_from_crouch_under_thin_stands_and_jumps():
    g = _crouched_under("thin")
    _crouch_in(g)
    run(g, Intent(jump_pressed=True, vertical=1))
    p = g.player
    assert p.state.name == "airborne"
    assert p.h == g.t.player_height
    assert p.vel.y < 0
    assert FLOOR_TOP - 10 < p.box.bottom < FLOOR_TOP  # left the floor by one tick of motion


def test_jump_from_crouch_under_solid_is_ignored():
    g = _crouched_under("solid")
    _crouch_in(g)
    run(g, Intent(jump_pressed=True, vertical=-1))
    p = g.player
    assert p.state.name == "crouch"
    assert p.h == g.t.player_crouch_height
    assert p.box.bottom == FLOOR_TOP
    assert p.vel.y >= 0


def _slide_until_under(g):
    _slide_in(g)
    run(g, Intent(move_x=1), ticks=30)
    p = g.player
    assert p.state.name == "slide" and p.box.left >= 120


def test_jump_from_slide_under_thin_stands_and_jumps():
    g = _crouched_under("thin")
    _slide_until_under(g)
    run(g, Intent(jump_pressed=True, move_x=1, vertical=1))
    p = g.player
    assert p.state.name == "airborne"
    assert p.h == g.t.player_height
    assert p.vel.y < 0


def test_jump_from_slide_under_solid_is_ignored():
    g = _crouched_under("solid")
    _slide_until_under(g)
    run(g, Intent(jump_pressed=True, move_x=1, vertical=1))
    p = g.player
    assert p.state.name == "slide"
    assert p.h == g.t.player_crouch_height
    assert p.box.bottom == FLOOR_TOP
