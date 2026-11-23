extends CharacterBody3D
## A kinematic sphere (not a rigid body). Gravity + reflect-and-settle bounces off the arena, ported
## from the 2-D ball. It passes through players; pickups are decided by distance in main.gd.

const Cfg = preload("res://scripts/config.gd")

var vel := Vector3.ZERO
var held_by = null                      # a player node, or null when loose
var resting := false
var _mesh: MeshInstance3D

func setup() -> void:
	collision_layer = 0
	collision_mask = 1                  # arena only
	var col := CollisionShape3D.new()
	var s := SphereShape3D.new()
	s.radius = Cfg.BALL_RADIUS
	col.shape = s
	add_child(col)
	_mesh = MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = Cfg.BALL_RADIUS
	sm.height = Cfg.BALL_RADIUS * 2.0
	_mesh.mesh = sm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.92, 0.55, 0.2)
	_mesh.material_override = mat
	add_child(_mesh)

func throw(from: Vector3, v: Vector3) -> void:
	held_by = null
	resting = false
	global_position = from
	vel = v

func carry(pos: Vector3) -> void:
	# main calls this while the ball is held, to pin it to the carrier's hand.
	global_position = pos
	vel = Vector3.ZERO
	resting = false

func step(delta: float) -> void:
	if held_by != null:
		return
	vel.y -= Cfg.BALL_GRAVITY * delta
	var hit := false
	var sub := 4
	var sdt := delta / sub
	for _i in sub:
		var c := move_and_collide(vel * sdt)
		if c != null:
			vel = _bounce(vel, c.get_normal())
			hit = true
	if hit and vel.length() < Cfg.BALL_STOPPED:
		vel = Vector3.ZERO
		resting = true
	elif vel.length() >= Cfg.BALL_STOPPED:
		resting = false

func _bounce(v: Vector3, n: Vector3) -> Vector3:
	var into := v.dot(n)
	if into >= 0.0:
		return v                        # already moving away
	var v_n := n * into                 # normal part (points into the surface)
	var v_t := v - v_n                  # tangential part
	if absf(into) < Cfg.BALL_REST_SPEED:
		return v_t                      # gentle hit: drop the normal part, settle
	return v_t * (1.0 - Cfg.BALL_FRICTION) - v_n * Cfg.BALL_RESTITUTION
