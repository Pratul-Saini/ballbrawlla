"""Collision detection and response.

- Player: AABB moved one axis at a time and pushed out of solids (classic platformer).
- Ball: circle vs AABB, reflected about the contact normal with restitution.
"""

import math
from dataclasses import dataclass
from typing import Iterable

from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2

_EPS = 1e-9


# ---------------------------------------------------------------- player (AABB)

@dataclass
class Contacts:
    """Which sides of a box are touching a solid (within 1px)."""

    on_ground: bool = False
    on_ceiling: bool = False
    wall_left: bool = False
    wall_right: bool = False


ABOVE_TOP_TOL = 1e-6  # px; tolerance for "mover bottom is at/above a thin top"

MAX_AABB_STEP = 8.0  # px; keep below the thinnest platform to prevent tunnelling


def _near_box(rects, box: AABB, margin: float) -> list:
    """The rects that can touch `box` once it is grown by `margin` on every side (cheap float compares only)."""
    x0, x1, y0, y1 = box.x - margin, box.x + box.w + margin, box.y - margin, box.y + box.h + margin
    return [r for r in rects if r.x < x1 and r.x + r.w > x0 and r.y < y1 and r.y + r.h > y0]


def move_aabb(
    box: AABB,
    vel: Vector2,
    dt: float,
    solids: Iterable[AABB],
    thin: Iterable[AABB] = (),
) -> AABB:
    """Move `box` by vel*dt, resolving X then Y. Zeroes the velocity component
    on any axis that hits a solid (mutates `vel`). Returns the new box.
    `thin` platforms only stop downward motion that started at/above their top.
    Large moves are split into sub-steps of at most MAX_AABB_STEP px."""
    travel = max(abs(vel.x), abs(vel.y)) * dt
    steps = max(1, math.ceil(travel / MAX_AABB_STEP))
    # Broad phase: only platforms within this move's reach (a collision only ever stops the box sooner).
    reach = max(abs(vel.x), abs(vel.y)) * dt + 2
    solids = _near_box(solids, box, reach)
    thin = _near_box(thin, box, reach)
    for _ in range(steps):
        box = _move_aabb_step(box, vel, dt / steps, solids, thin)
    return box


def _move_aabb_step(
    box: AABB, vel: Vector2, dt: float, solids: list[AABB], thin: list[AABB] = ()
) -> AABB:
    box = box.shifted(vel.x * dt, 0)
    for s in solids:
        if box.overlaps(s):
            if vel.x > 0:
                box.x = s.left - box.w
            elif vel.x < 0:
                box.x = s.right
            vel.x = 0

    vy = vel.y
    prev_bottom = box.bottom
    box = box.shifted(0, vel.y * dt)
    for s in solids:
        if box.overlaps(s):
            if vel.y > 0:
                box.y = s.top - box.h
            elif vel.y < 0:
                box.y = s.bottom
            vel.y = 0

    if vy > 0:
        for t in thin:
            if box.overlaps(t) and prev_bottom <= t.top + ABOVE_TOP_TOL:
                box.y = t.top - box.h
                vel.y = 0

    return box


def probe_contacts(
    box: AABB, solids: Iterable[AABB], thin: Iterable[AABB] = ()
) -> Contacts:
    """Detect touching solids by nudging the box 1px in each direction.
    Thin platforms only count for `on_ground`, when the box bottom rests on
    the top edge (within ABOVE_TOP_TOL) and overlaps it horizontally."""
    solids = _near_box(solids, box, 2)
    thin = _near_box(thin, box, 2)

    def touching(dx: float, dy: float) -> bool:
        probe = box.shifted(dx, dy)
        return any(probe.overlaps(s) for s in solids)

    return Contacts(
        on_ground=touching(0, 1) or any(
            abs(box.bottom - t.top) <= ABOVE_TOP_TOL
            and box.left < t.right
            and box.right > t.left
            for t in thin
        ),
        on_ceiling=touching(0, -1),
        wall_left=touching(-1, 0),
        wall_right=touching(1, 0),
    )


def box_is_free(box: AABB, solids: Iterable[AABB]) -> bool:
    return not any(box.overlaps(s) for s in solids)


# ---------------------------------------------------------------- ball (circle)

@dataclass
class CircleContact:
    normal: Vector2  # unit vector pointing out of the solid, toward the circle
    depth: float     # penetration distance along the normal


def circle_vs_aabb(center: Vector2, radius: float, box: AABB) -> CircleContact | None:
    closest = Vector2(
        min(max(center.x, box.left), box.right),
        min(max(center.y, box.top), box.bottom),
    )
    d = center - closest
    dist_sq = d.length_squared()
    if dist_sq >= radius * radius:
        return None

    if dist_sq > _EPS:
        dist = math.sqrt(dist_sq)
        return CircleContact(d / dist, radius - dist)

    # Center is inside the box: push out along the shallowest axis.
    options = [
        (center.x - box.left, Vector2(-1, 0)),
        (box.right - center.x, Vector2(1, 0)),
        (center.y - box.top, Vector2(0, -1)),
        (box.bottom - center.y, Vector2(0, 1)),
    ]
    pen, normal = min(options, key=lambda o: o[0])
    return CircleContact(normal, pen + radius)


def bounce(
    vel: Vector2,
    normal: Vector2,
    restitution: float,
    friction: float,
    rest_speed: float,
) -> Vector2:
    """Reflect velocity about `normal`: v' = v_t*(1-friction) - e*v_n.

    Impacts slower than `rest_speed` kill the normal component instead of
    bouncing, so a ball settles rather than jittering forever."""
    vn = vel.dot(normal)
    if vn >= 0:  # already separating
        return Vector2(vel)
    v_normal = normal * vn
    v_tangent = vel - v_normal
    if -vn < rest_speed:
        return v_tangent
    return v_tangent * (1 - friction) - v_normal * restitution
