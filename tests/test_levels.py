"""Every field level: loads, fits the 100-yard field, has spawn spots, and every
standing surface is reachable from the floor (approximate jump envelope)."""

from collections import deque

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.main import LEVELS
from ballbrawlla.rules.down import defender_x_range, possession_start, qb_x_range
from ballbrawlla.rules.field import Field
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import level_from_dict, level_to_dict, load_level

FIELDS = sorted(p.stem for p in LEVELS.glob("field_*.json"))


def test_there_are_several_field_levels():
    assert len(FIELDS) >= 4


@pytest.fixture(params=FIELDS)
def field(request) -> Field:
    return Field(load_level(LEVELS / f"{request.param}.json"), Tuning())


def test_field_spans_100_yards_plus_end_zones(field):
    f = field
    assert f.yards_from_goal(Team.LEFT, f.goal_line_x(Team.RIGHT)) == pytest.approx(100)
    assert f.end_zone_px == pytest.approx(10 * f.yard_px)


def test_yard_px_survives_the_network_welcome(field):
    lv = field.level
    again = level_from_dict(level_to_dict(lv))
    assert again.yard_px == lv.yard_px
    assert Field(again, Tuning()).yard_px == field.yard_px


@pytest.mark.parametrize("team", list(Team))
def test_qb_and_defender_have_spawn_spots(field, team):
    t = Tuning()
    down = possession_start(team, t)
    for lo, hi in (qb_x_range(down, field), defender_x_range(down, field, t)):
        assert field.snap(field.level.ball_spawn, lo, hi) is not None


def _reachable(field: Field) -> tuple[set[int], list]:
    """BFS over standing surfaces. Up to ~140 px up: up to 260 px across.
    Up to ~240 px up (double jump): up to 140 px across. Down: up to 450 px across."""
    S = field.surfaces
    start = {i for i, s in enumerate(S) if s.y == field.floor_y}
    seen, q = set(start), deque(start)
    while q:
        a = S[q.popleft()]
        for j, b in enumerate(S):
            if j in seen:
                continue
            up = a.y - b.y
            gap = max(0.0, b.x0 - a.x1, a.x0 - b.x1)
            if (up <= 0 and gap <= 450) or (up <= 140 and gap <= 260) or (up <= 240 and gap <= 140):
                seen.add(j)
                q.append(j)
    return seen, S


def test_every_surface_is_reachable_from_the_floor(field):
    seen, S = _reachable(field)
    missing = [S[i] for i in range(len(S)) if i not in seen]
    assert not missing, f"{field.level.name}: unreachable surfaces {missing}"


def test_levels_are_symmetric(field):
    lv = field.level
    rects = sorted((p.rect.x, p.rect.y, p.rect.w, p.rect.h, p.platform_type) for p in lv.platforms)
    mirrored = sorted((lv.width - x - w, y, w, h, k) for x, y, w, h, k in rects)
    assert rects == mirrored


def test_spawn_points_are_not_inside_platforms(field):
    from ballbrawlla.physics.collision import circle_vs_aabb
    from ballbrawlla.physics.shapes import AABB

    t, lv = Tuning(), field.level
    for c in lv.player_spawns:
        box = AABB(c.x - t.player_width / 2, c.y - t.player_height / 2, t.player_width, t.player_height)
        assert not any(box.overlaps(r) for r in lv.solids + lv.thin), f"player spawn {c} overlaps"
    assert not any(circle_vs_aabb(lv.ball_spawn, t.ball_radius, r) for r in lv.solids), "ball spawn overlaps"
