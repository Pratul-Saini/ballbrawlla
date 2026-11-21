"""Collision shapes. The player is an AABB, the ball is a circle, platforms are AABBs."""

from dataclasses import dataclass

from ballbrawlla.physics.vec import Vector2


@dataclass
class AABB:
    """Axis-aligned box; (x, y) is the top-left corner, y-down."""

    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def center(self) -> Vector2:
        return Vector2(self.x + self.w / 2, self.y + self.h / 2)

    def overlaps(self, other: "AABB") -> bool:
        """Strict overlap: boxes that merely touch edges do not overlap."""
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )

    def shifted(self, dx: float, dy: float) -> "AABB":
        return AABB(self.x + dx, self.y + dy, self.w, self.h)


@dataclass
class Circle:
    center: Vector2
    radius: float
