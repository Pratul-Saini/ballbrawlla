extends RefCounted
## Point-mass kinematics (src/ballbrawlla/physics/body.py). Position, velocity and gravity as plain 64-bit floats.

var px: float = 0.0
var py: float = 0.0
var vx: float = 0.0
var vy: float = 0.0
var gravity: float = 0.0

func _init(x: float = 0.0, y: float = 0.0, g: float = 0.0) -> void:
	px = x
	py = y
	gravity = g

## Semi-implicit Euler, step 1: update velocity from gravity.
func integrate_velocity(dt: float, gravity_scale: float = 1.0) -> void:
	vy += (gravity * gravity_scale) * dt
