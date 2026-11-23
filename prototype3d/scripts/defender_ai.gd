extends RefCounted
## A deliberately simple chaser: steer toward a target point, and jump to climb toward it or to get off
## a wall. It produces the same Intent a human would, so the sim doesn't know the difference. This is a
## prototype stand-in for the second human; a future agent can replace it with split-screen 2-player.

const Intent = preload("res://scripts/intent.gd")

var _jump_cd := 0.0

func decide(defender, target: Vector3, delta: float):
	_jump_cd = maxf(0.0, _jump_cd - delta)
	var i = Intent.new()
	var to: Vector3 = target - defender.global_position
	var flat := Vector3(to.x, 0.0, to.z)
	if flat.length() > 0.6:
		var dir := flat.normalized()
		i.move = Vector2(dir.x, dir.z)
		i.move_world = dir                      # AI steers in world space directly
	if defender._on_floor and _jump_cd <= 0.0 and ((to.y > 2.0 and flat.length() < 25.0) or defender._on_wall):
		i.jump_pressed = true
		i.jump_held = true
		_jump_cd = 0.6
	return i
