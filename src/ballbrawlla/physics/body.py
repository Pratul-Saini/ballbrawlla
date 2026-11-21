"""Point-mass kinematics: position, velocity, acceleration."""

from dataclasses import dataclass, field

from ballbrawlla.physics.vec import Vector2


@dataclass
class Body:
    pos: Vector2
    vel: Vector2 = field(default_factory=Vector2)
    acc: Vector2 = field(default_factory=Vector2)  # extra acceleration on top of gravity
    gravity: float = 0.0

    def integrate_velocity(self, dt: float, gravity_scale: float = 1.0) -> None:
        """Semi-implicit Euler, step 1: update velocity from gravity + acc."""
        self.vel.x += self.acc.x * dt
        self.vel.y += (self.gravity * gravity_scale + self.acc.y) * dt
