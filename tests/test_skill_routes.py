"""Skill routes on the skill maps (field_12-13), run with the real physics.

For each skill element we sweep the input timing tick by tick and measure the
success window (120 ticks = 1 s). A skill route must be possible (window >= 3
ticks) but demanding (<= 14 ticks), and the beginner version must fail."""

import copy

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.main import LEVELS
from ballbrawlla.world.level import load_level

T = Tuning()
GEOM = {  # yard px, floor, middle lane, top lane
    "field_12": (56, 1968, 1488, 1008),
    "field_13": (58, 2168, 1648, 1128),
    "field_14": (60, 2368, 1808, 1248),
}
_levels = {}


def geom(level):
    YD, F, MID, TOP = GEOM[level]
    return YD, F, MID, TOP, (lambda y: 32 + 10 * YD + y * YD)


def start(level: str, x: float, feet_y: float) -> Game:
    if level not in _levels:
        _levels[level] = load_level(LEVELS / f"{level}.json")
    g = Game(_levels[level], T, 1)
    p = g.player
    p.body.pos.update(x - p.w / 2, feet_y - p.h)
    g.ball.body.pos.update(100_000, 0)
    for _ in range(10):
        g.step([Intent()], T.dt)
    assert p.contacts.on_ground and p.box.bottom == pytest.approx(feet_y), "bad start spot"
    return g


def step(g, intent, n=1):
    for _ in range(n):
        g.step([intent], T.dt)


# ---------------------------------------------------------------- kick hatch

_climbed = {}


def at_column_top(level, edge_yd, facing, D) -> Game:
    """Jump up beside the hatch column, cling to it and climb to the ceiling."""
    key = (level, edge_yd, facing, D)
    if key in _climbed:
        return copy.deepcopy(_climbed[key])
    YD, F, MID, TOP, yd = geom(level)
    face = yd(edge_yd) - D if facing > 0 else yd(edge_yd) + D
    g = start(level, face + facing * 14, MID)
    p = g.player
    step(g, Intent(vertical=1, jump_pressed=True))
    step(g, Intent(vertical=1), 20)                                # up past the column's bottom
    step(g, Intent(move_x=-facing, vertical=1), 10)               # then lean into it
    for i in range(900):
        step(g, Intent(move_x=-facing, vertical=1, jump_pressed=(i % 12 == 0)))
        if p.state.name == "wall_cling" and p.box.top - (TOP + 24) < 2 and abs(p.vel.y) < 1:
            break
    assert p.state.name == "wall_cling", "never got to the top of the column"
    step(g, Intent(move_x=-facing))
    _climbed[key] = g
    return copy.deepcopy(g)


def kick(level, edge_yd, facing, D, t_dj):
    """From the top of the hatch column, wall-jump toward the opening and double-jump
    `t_dj` ticks later (None = no double jump). True if it ends on the top lane."""
    YD, F, MID, TOP, yd = geom(level)
    g = at_column_top(level, edge_yd, facing, D)
    p = g.player
    step(g, Intent(move_x=facing, vertical=1))                     # wall jump
    for t in range(1, 240):
        step(g, Intent(move_x=facing, vertical=1, jump_pressed=(t == t_dj)))
        if t > 5 and p.state.name == "grounded":
            break
    return p.box.bottom == pytest.approx(TOP)


HATCHES = [("field_12", 9, 1, 60), ("field_13", 36, 1, 60), ("field_13", 21, 1, 40),
           ("field_14", 25, 1, 60), ("field_14", 46, -1, 40)]


@pytest.mark.parametrize("level,edge,facing,D", HATCHES)
def test_kick_hatch_is_a_skill_jump(level, edge, facing, D):
    window = [t for t in range(1, 60) if kick(level, edge, facing, D, t)]
    assert 3 <= len(window) <= 14, f"double-jump window {window}"
    assert window == list(range(window[0], window[-1] + 1)), "window should be one block"
    assert not kick(level, edge, facing, D, None), "should need the double jump"


# ---------------------------------------------------------------- vault

def vault(level, a_yd, start_x, t_dj):
    """Run right from start_x, jump, double-jump after t_dj ticks onto the balcony
    in front of the vault at a_yd, slide through. True if out the other side."""
    YD, F, MID, TOP, yd = geom(level)
    x1 = yd(a_yd + 4)
    g = start(level, start_x, MID)
    p = g.player
    step(g, Intent(move_x=1, vertical=1, jump_pressed=True))
    x0 = yd(a_yd)
    for t in range(1, 360):
        down = (t > (t_dj or 0) and p.vel.y > 0) or p.state.name in ("slide", "crouch")
        step(g, Intent(move_x=1, vertical=-1 if down else 1, jump_pressed=(t == t_dj)))
        if p.center.x > x1 + 60:
            return True
        if t > 5 and p.state.name == "grounded" and p.center.x < x0 and p.box.bottom == pytest.approx(MID):
            return False                      # came back down on the near side
        if p.state.name == "wall_cling" and p.vel.y > 0 and p.box.bottom > MID - 200:
            return False                      # missed the balcony, sliding down the face
    return False


VAULTS = [("field_12", 33, 27), ("field_13", 4, -3), ("field_14", 36, 29)]


@pytest.mark.parametrize("level,a,seg", VAULTS)
def test_vault_balcony_is_a_skill_jump(level, a, seg):
    YD, F, MID, TOP, yd = geom(level)
    pad_left = yd(a) - 56
    lo, hi = max(int(pad_left) - 320, int(yd(seg)) + 14), int(pad_left) - 40
    # coarse sweep for take-off spots that work at all, then a fine sweep around the best
    hits = {sx: sum(vault(level, a, sx, t) for t in range(15, 65, 3)) for sx in range(lo, hi, 18)}
    assert any(hits.values()), "no take-off spot works"
    center = max(hits, key=hits.get)
    best = []
    for start_x in range(max(lo, center - 18), min(hi, center + 19), 3):
        window = [t for t in range(15, 65) if vault(level, a, start_x, t)]
        best = max(best, window, key=len)
        assert not vault(level, a, start_x, None), "a single jump should never make it"
    assert 3 <= len(best) <= 14, f"best double-jump window {best}"


@pytest.mark.parametrize("level,a,seg", VAULTS)
def test_nothing_within_a_single_jump_of_a_vault_balcony(level, a, seg):
    """No stair step, perch or block may sit within a single jump below either
    balcony - that would let anyone skip the double jump."""
    from ballbrawlla.rules.field import Field

    YD, F, MID, TOP, yd = geom(level)
    f = Field(load_level(LEVELS / f"{level}.json"), T)
    pad_y = MID - 220
    pads = [(yd(a) - 56, yd(a)), (yd(a + 4), yd(a + 4) + 56)]
    for s in f.surfaces:
        if s.y <= pad_y or s.y >= MID:          # the tunnel/balconies themselves, or the lane floor
            continue
        for x0, x1 in pads:
            gap = max(0.0, x0 - s.x1, s.x0 - x1)
            assert not (s.y - pad_y <= 150 and gap <= 280), f"{s} is a stepping stone to the balcony at {x0}"


@pytest.mark.parametrize("level,a,seg", VAULTS)
def test_vault_face_cannot_be_climbed_onto_the_balcony(level, a, seg):
    YD, F, MID, TOP, yd = geom(level)
    g = start(level, yd(a) - 13, MID)
    p = g.player
    step(g, Intent(vertical=1, jump_pressed=True))
    for i in range(400):
        step(g, Intent(move_x=1, vertical=1, jump_pressed=(i % 12 == 0)))
    step(g, Intent(move_x=1), 60)
    assert p.box.bottom > MID - 220 + 1   # never stood on the balcony
    assert p.center.x < yd(a)             # still on the near side


# ---------------------------------------------------------------- slide gauntlet

GAUNTLET = [(40, 120, 30, 80), (40, 120, 50, 160), (40, 120, 40, 0)]


def gauntlet(level, a_yd, hop_for):
    """Run the gauntlet starting at a_yd. hop_for(pit) -> ticks to hold Up on the hop.
    True if through to the far side still on the middle lane."""
    YD, F, MID, TOP, yd = geom(level)
    x = yd(a_yd)
    beams, pits = [], []
    for run_up, beam, exit_, pit in GAUNTLET:
        beams.append((x + run_up, x + run_up + beam))
        pits.append(pit)
        x += run_up + beam + exit_ + pit
    end = x
    g = start(level, yd(a_yd) - 60, MID)
    p = g.player
    i, hop_left = 0, 0
    for tick in range(1200):
        if i < len(beams) and p.center.x > beams[i][1] + 13:
            hold = hop_for(pits[i])
            i += 1
            if hold:
                step(g, Intent(move_x=1, vertical=1, jump_pressed=True))
                hop_left = hold
                continue
        if hop_left > 0:
            hop_left -= 1
            step(g, Intent(move_x=1, vertical=1))
            continue
        nxt = beams[i][0] if i < len(beams) else 1e9
        before_beam = nxt - 120 < p.center.x < nxt
        under = i < len(beams) and nxt <= p.center.x <= beams[i][1] + 13
        down = before_beam or under or (p.state.name == "airborne" and p.vel.y > 0)
        step(g, Intent(move_x=1, vertical=-1 if down else 0))
        if p.center.x > end + 40 or p.box.bottom > MID + 30:
            break
    step(g, Intent(), 90)
    ok = p.center.x > end + 40 and p.box.bottom == pytest.approx(MID)
    return tick if ok else None


@pytest.mark.parametrize("level,a", [("field_12", 12), ("field_14", 8)])
def test_gauntlet_rewards_reading_each_pit(level, a):
    expert = gauntlet(level, a, lambda pit: 0 if not pit else (4 if pit < 120 else 30))  # short hop, full jump
    sloppy = gauntlet(level, a, lambda pit: 30 if pit else 0)                       # full jump every time
    assert expert is not None, "expert line should work"
    assert sloppy is None or sloppy - expert >= 12, "reading the pits should be clearly faster"
    assert gauntlet(level, a, lambda pit: 0) is None, "without hopping you fall into a pit"


def test_gauntlet_beams_block_anyone_who_does_not_slide():
    YD, F, MID, TOP, yd = geom("field_12")
    g = start("field_12", yd(12) - 60, MID)
    step(g, Intent(move_x=1), 120)
    assert g.player.center.x < yd(12) + 40       # stopped at the first beam
