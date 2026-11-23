extends Node3D
## A third-person follow camera. Yaw is player-controlled (mouse / right stick); it trails the target.
## Movement and aiming are taken relative to its yaw. Horizontal yaw=0 looks toward +X (the attack
## direction for the offense).

const Cfg = preload("res://scripts/config.gd")

var yaw := 0.0                  # radians
var pitch := 0.32              # radians, a gentle downward tilt for the view
var distance := 10.0
var height := 4.0
var _target := Vector3.ZERO
var cam: Camera3D

func setup() -> void:
	cam = Camera3D.new()
	cam.fov = 72.0
	cam.current = true
	add_child(cam)

func add_yaw(d: float) -> void:
	yaw += d

func forward_flat() -> Vector3:
	return Vector3(cos(yaw), 0.0, sin(yaw))

func right_flat() -> Vector3:
	return Vector3(-sin(yaw), 0.0, cos(yaw))

# A throw direction: look heading (yaw) plus a chosen pitch in degrees.
static func aim_direction(yaw_rad: float, pitch_deg: float) -> Vector3:
	var p := deg_to_rad(pitch_deg)
	return Vector3(cos(yaw_rad) * cos(p), sin(p), sin(yaw_rad) * cos(p)).normalized()

func update(delta: float, target: Vector3) -> void:
	_target = _target.lerp(target, clampf(delta * 10.0, 0.0, 1.0)) if _target != Vector3.ZERO else target
	var fwd := forward_flat()
	var pos := _target - fwd * distance + Vector3(0, height, 0)
	cam.global_position = pos
	cam.look_at(_target + Vector3(0, 1.2, 0), Vector3.UP)
