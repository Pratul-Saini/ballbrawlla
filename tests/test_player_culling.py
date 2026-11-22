"""move_aabb and probe_contacts only test the platforms near the box. That must change nothing about the result."""

import math
import random

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.main import LEVELS
from ballbrawlla.physics.collision import (
    ABOVE_TOP_TOL,
    MAX_AABB_STEP,
    Contacts,
    _move_aabb_step,
    move_aabb,
    probe_contacts,
)
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.world.level import load_level

T = Tuning()


def reference_move(box, vel, dt, solids, thin):
    """move_aabb as it was before culling: every platform, every sub-step."""
    travel = max(abs(vel.x), abs(vel.y)) * dt
    steps = max(1, math.ceil(travel / MAX_AABB_STEP))
    for _ in range(steps):
        box = _move_aabb_step(box, vel, dt / steps, list(solids), list(thin))
    return box


def reference_probe(box, solids, thin):
    def touching(dx, dy):
        probe = box.shifted(dx, dy)
        return any(probe.overlaps(s) for s in solids)

    return Contacts(
        on_ground=touching(0, 1) or any(
            abs(box.bottom - t.top) <= ABOVE_TOP_TOL and box.left < t.right and box.right > t.left for t in thin
        ),
        on_ceiling=touching(0, -1),
        wall_left=touching(-1, 0),
        wall_right=touching(1, 0),
    )


@pytest.mark.parametrize("level", ["field_01", "field_05", "field_12", "field_14"])
def test_culled_move_and_probe_match_testing_every_platform(level):
    lv = load_level(LEVELS / f"{level}.json")
    rng = random.Random(level)
    checked = 0
    for _ in range(1500):
        # start near real geometry half the time, anywhere the other half, so touching cases come up
        if rng.random() < 0.5:
            r = rng.choice(lv.solids + lv.thin)
            x = rng.uniform(r.x - 40, r.x + r.w + 12)
            y = rng.choice([r.y - 48, r.y + r.h, r.y - 30, r.y + 4])
        else:
            x = rng.uniform(lv.wall_thickness, lv.width - lv.wall_thickness - 28)
            y = rng.uniform(lv.wall_thickness, lv.height - lv.wall_thickness - 48)
        box = AABB(x, y, 28, rng.choice([48, 30]))
        if any(box.overlaps(s) for s in lv.solids):
            continue  # a player is never inside a solid at the start of a move
        v1 = Vector2(rng.choice([0, 320, -320, 560, -560, 100]), rng.choice([0, 820, -820, 1200, -200, 300]))
        v2 = Vector2(v1)
        a = move_aabb(AABB(box.x, box.y, box.w, box.h), v1, T.dt, lv.solids, lv.thin)
        b = reference_move(AABB(box.x, box.y, box.w, box.h), v2, T.dt, lv.solids, lv.thin)
        assert (a.x, a.y, a.w, a.h) == (b.x, b.y, b.w, b.h) and (v1.x, v1.y) == (v2.x, v2.y)
        assert probe_contacts(a, lv.solids, lv.thin) == reference_probe(a, lv.solids, lv.thin)
        checked += 1
    assert checked > 800
