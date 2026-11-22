"""Collision tests for thin (one-way) platforms vs solids."""

from ballbrawlla.physics.collision import move_aabb, probe_contacts
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2

DT = 1 / 120
MAX_FALL = 1200.0
THIN = AABB(0, 100, 200, 20)  # top edge at y=100
SOLID = AABB(0, 100, 200, 20)


def _same(a: AABB, b: AABB) -> bool:
    return (a.x, a.y, a.w, a.h) == (b.x, b.y, b.w, b.h)


# ------------------------------------------------- landing from above (4.1-4.4)

def test_lands_on_thin_top_at_normal_speed():
    vel = Vector2(30, 600)  # 5 px per tick
    box = move_aabb(AABB(10, 68, 10, 30), vel, DT, [], [THIN])  # bottom 98 -> 103
    assert box.bottom == THIN.top
    assert vel.y == 0
    assert box.x == 10 + 30 * DT
    assert vel.x == 30


def test_lands_on_thin_top_at_max_fall_speed():
    vel = Vector2(0, MAX_FALL)  # 10 px per tick
    box = move_aabb(AABB(10, 65, 10, 30), vel, DT, [], [THIN])  # bottom 95 -> 105
    assert box.bottom == THIN.top
    assert vel.y == 0
    assert box.x == 10 and vel.x == 0


def test_lands_when_starting_exactly_on_top_edge():
    vel = Vector2(0, 300)
    box = move_aabb(AABB(10, 70, 10, 30), vel, DT, [], [THIN])  # bottom == 100
    assert box.bottom == THIN.top
    assert vel.y == 0


def test_on_ground_when_resting_on_thin_top():
    c = probe_contacts(AABB(10, 70, 10, 30), [], [THIN])
    assert c.on_ground


def test_on_ground_cleared_beside_thin():
    c = probe_contacts(AABB(210, 70, 10, 30), [], [THIN])  # same height, no overlap
    assert not c.on_ground


def test_on_ground_false_when_hovering_above_thin():
    assert not probe_contacts(AABB(10, 60, 10, 30), [], [THIN]).on_ground


# ------------------------------------------- passes through otherwise (5.1-5.3)

def test_moving_up_passes_through_thin():
    start = AABB(10, 110, 10, 30)
    v1, v2 = Vector2(0, -600), Vector2(0, -600)
    with_thin = move_aabb(start, v1, DT, [], [THIN])
    without = move_aabb(start, v2, DT, [], [])
    assert _same(with_thin, without)
    assert v1 == v2


def test_moving_sideways_passes_through_thin():
    start = AABB(-5, 90, 10, 30)  # overlaps thin vertically, bottom below top
    v1, v2 = Vector2(600, 0), Vector2(600, 0)
    with_thin = move_aabb(start, v1, DT, [], [THIN])
    without = move_aabb(start, v2, DT, [], [])
    assert _same(with_thin, without)
    assert v1 == v2


def test_already_below_top_moving_down_passes_through():
    start = AABB(10, 95, 10, 30)  # bottom 125 > top + tol
    v1, v2 = Vector2(0, 600), Vector2(0, 600)
    with_thin = move_aabb(start, v1, DT, [], [THIN])
    without = move_aabb(start, v2, DT, [], [])
    assert _same(with_thin, without)
    assert v1 == v2


def test_ceiling_and_wall_flags_false_near_thin():
    for box in (
        AABB(10, 120, 10, 20),   # directly under thin
        AABB(-10, 100, 10, 20),  # left of thin, touching its left edge
        AABB(200, 100, 10, 20),  # right of thin, touching its right edge
        AABB(10, 105, 10, 10),   # inside thin
    ):
        c = probe_contacts(box, [], [THIN])
        assert not (c.on_ceiling or c.wall_left or c.wall_right)


# ----------------------------------------- solids unchanged and win (8.1, 8.4)

def test_solid_blocks_from_above():
    vel = Vector2(0, 600)
    box = move_aabb(AABB(10, 68, 10, 30), vel, DT, [SOLID])
    assert box.bottom == SOLID.top and vel.y == 0


def test_solid_blocks_from_below_and_sets_on_ceiling():
    vel = Vector2(0, -600)
    box = move_aabb(AABB(10, 122, 10, 30), vel, DT, [SOLID])
    assert box.top == SOLID.bottom and vel.y == 0
    assert probe_contacts(box, [SOLID]).on_ceiling


def test_solid_blocks_from_left_and_right():
    v = Vector2(600, 0)
    box = move_aabb(AABB(-12, 100, 10, 20), v, DT, [SOLID])
    assert box.right == SOLID.left and v.x == 0
    assert probe_contacts(box, [SOLID]).wall_right

    v = Vector2(-600, 0)
    box = move_aabb(AABB(202, 100, 10, 20), v, DT, [SOLID])
    assert box.left == SOLID.right and v.x == 0
    assert probe_contacts(box, [SOLID]).wall_left


def test_thin_and_solid_in_one_step_resolves_to_solid():
    thin = AABB(0, 102, 200, 5)
    vel = Vector2(0, MAX_FALL)
    box = move_aabb(AABB(10, 68, 10, 30), vel, DT, [SOLID], [thin])  # bottom 98 -> 108
    assert box.bottom == SOLID.top
    assert vel.y == 0


def test_solid_still_blocks_sideways_while_overlapping_thin():
    thin = AABB(0, 90, 200, 20)
    solid = AABB(50, 90, 20, 20)
    vel = Vector2(600, 0)
    box = move_aabb(AABB(38, 95, 10, 10), vel, DT, [solid], [thin])  # inside thin
    assert box.right <= solid.left + 1e-9
    assert vel.x == 0


def test_solid_still_blocks_upward_while_overlapping_thin():
    thin = AABB(0, 100, 200, 40)
    solid = AABB(0, 90, 200, 20)
    vel = Vector2(0, -600)
    box = move_aabb(AABB(10, 113, 10, 20), vel, DT, [solid], [thin])
    assert box.top == solid.bottom and vel.y == 0
