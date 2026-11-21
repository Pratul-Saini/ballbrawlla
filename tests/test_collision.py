from ballbrawlla.physics.collision import bounce, circle_vs_aabb, move_aabb, probe_contacts
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2

FLOOR = AABB(0, 100, 200, 20)


def test_circle_above_floor_contacts_with_up_normal():
    c = circle_vs_aabb(Vector2(50, 95), 10, FLOOR)
    assert c is not None
    assert c.normal == Vector2(0, -1)
    assert abs(c.depth - 5) < 1e-9


def test_circle_clear_of_floor_has_no_contact():
    assert circle_vs_aabb(Vector2(50, 80), 10, FLOOR) is None


def test_circle_center_inside_box_pushes_out_shallowest_side():
    c = circle_vs_aabb(Vector2(50, 102), 5, FLOOR)
    assert c.normal == Vector2(0, -1)
    assert abs(c.depth - 7) < 1e-9


def test_bounce_reflects_normal_with_restitution():
    v = bounce(Vector2(100, 400), Vector2(0, -1), restitution=0.5, friction=0.0, rest_speed=10)
    assert v == Vector2(100, -200)


def test_bounce_elastic_conserves_speed():
    v0 = Vector2(300, 400)
    v = bounce(v0, Vector2(0, -1), restitution=1.0, friction=0.0, rest_speed=0)
    assert abs(v.length() - v0.length()) < 1e-9


def test_bounce_slow_impact_comes_to_rest():
    v = bounce(Vector2(50, 5), Vector2(0, -1), restitution=0.8, friction=0.1, rest_speed=10)
    assert v == Vector2(50, 0)


def test_bounce_ignores_separating_velocity():
    assert bounce(Vector2(0, -50), Vector2(0, -1), 0.8, 0.1, 10) == Vector2(0, -50)


def test_move_aabb_lands_on_floor():
    vel = Vector2(0, 600)
    box = move_aabb(AABB(10, 70, 10, 20), vel, 0.1, [FLOOR])
    assert box.bottom == FLOOR.top
    assert vel.y == 0
    c = probe_contacts(box, [FLOOR])
    assert c.on_ground and not c.wall_left and not c.wall_right
