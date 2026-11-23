extends CharacterBody3D
## A kinematic character (NOT a rigid body), ported from the 2-D state machine. It collides only with
## the arena; players and the ball pass through it. main.gd calls step(intent, delta) every physics tick.
##
## States: GROUNDED -> AIRBORNE -> WALLCLING, plus SLIDE. A wall cling buys ONE jump (hop / wall-jump /
## air-jump-after-drop), and you can't re-grab the same wall until you land or touch a different one.

const Cfg = preload("res://scripts/config.gd")

enum { GROUNDED, AIRBORNE, WALLCLING, SLIDE }

var team := 0
var role := "WR"
var has_ball := false
var facing := Vector3(1, 0, 0)          # horizontal heading; drives the slide and where a held ball sits

var state := AIRBORNE
var jumps_left := Cfg.AIR_JUMPS
var jump_cut_ready := false
var control_lock := 0.0                 # s of no air steering after a wall jump
var last_wall_normal := Vector3.ZERO    # the wall last clung to (cleared on landing)
var slide_timer := 0.0

var _on_floor := false
var _on_wall := false
var _wall_normal := Vector3.ZERO
var _height := Cfg.PLAYER_HEIGHT
var _col: CollisionShape3D
var _mesh: MeshInstance3D
var _eye: MeshInstance3D

func setup(p_team: int, p_role: String, color: Color) -> void:
	team = p_team
	role = p_role
	facing = Vector3(float(1 if team == 0 else -1), 0, 0)
	collision_layer = 2                 # players on layer 2
	collision_mask = 1                  # collide with the arena only (layer 1)
	floor_max_angle = deg_to_rad(50.0)
	floor_snap_length = 0.4
	_col = CollisionShape3D.new()
	var caps := CapsuleShape3D.new()
	caps.radius = Cfg.PLAYER_RADIUS
	caps.height = Cfg.PLAYER_HEIGHT
	_col.shape = caps
	add_child(_col)
	_mesh = MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = Cfg.PLAYER_RADIUS
	cm.height = Cfg.PLAYER_HEIGHT
	_mesh.mesh = cm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	_mesh.material_override = mat
	add_child(_mesh)
	_eye = MeshInstance3D.new()           # a nub so you can read which way it faces
	var em := BoxMesh.new()
	em.size = Vector3(0.25, 0.25, 0.25)
	_eye.mesh = em
	var emat := StandardMaterial3D.new()
	emat.albedo_color = Color(0.05, 0.05, 0.08)
	_eye.material_override = emat
	add_child(_eye)

# ------------------------------------------------------------ helpers

func run_speed() -> float:
	return Cfg.RUN_SPEED * (Cfg.CARRY_MULT if has_ball else 1.0)

func slide_speed() -> float:
	return Cfg.SLIDE_SPEED * (Cfg.CARRY_MULT if has_ball else 1.0)

func feet_y() -> float:
	return global_position.y - _height / 2.0

func place_feet(x: float, y: float, z: float) -> void:
	global_position = Vector3(x, y + _height / 2.0, z)
	velocity = Vector3.ZERO
	state = AIRBORNE
	jumps_left = Cfg.AIR_JUMPS

func center() -> Vector3:
	return global_position

func _set_height(h: float) -> void:
	var feet := feet_y()
	_height = h
	(_col.shape as CapsuleShape3D).height = h
	(_mesh.mesh as CapsuleMesh).height = h
	global_position.y = feet + h / 2.0

# ------------------------------------------------------------ tick

func step(intent, delta: float) -> void:
	control_lock = max(0.0, control_lock - delta)
	match state:
		GROUNDED: _grounded(intent)
		AIRBORNE: _airborne(intent)
		WALLCLING: _wallcling(intent)
		SLIDE: _slide(intent, delta)
	_gravity_and_move(delta)
	_eye.position = facing * (Cfg.PLAYER_RADIUS + 0.15) + Vector3(0, _height * 0.2, 0)

func _grounded(intent) -> void:
	if not _on_floor:
		state = AIRBORNE
		return
	jumps_left = Cfg.AIR_JUMPS
	last_wall_normal = Vector3.ZERO
	control_lock = 0.0
	var dir: Vector3 = intent.move_world
	velocity.x = dir.x * run_speed()
	velocity.z = dir.z * run_speed()
	if dir.length() > 0.05:
		facing = dir.normalized()
	if intent.jump_pressed:
		_jump(Cfg.JUMP_SPEED)
		state = AIRBORNE
	elif intent.slide_pressed:
		_enter_slide()

func _airborne(intent) -> void:
	if _on_floor and velocity.y <= 0.1:
		state = GROUNDED
		return
	if control_lock <= 0.0:
		var dir: Vector3 = intent.move_world
		velocity.x = dir.x * Cfg.AIR_SPEED
		velocity.z = dir.z * Cfg.AIR_SPEED
		if dir.length() > 0.05:
			facing = dir.normalized()
	if _on_wall:
		var n := _wall_normal                       # points away from the wall
		var pressing: bool = intent.move_world.dot(-n) > 0.1
		var reclimb_ok: bool = last_wall_normal == Vector3.ZERO or n.dot(last_wall_normal) < 0.9
		if pressing and reclimb_ok and velocity.y < Cfg.JUMP_SPEED * 0.6:
			_enter_wallcling(n)
			return
	if intent.jump_pressed and jumps_left > 0:
		jumps_left -= 1
		_jump(Cfg.DOUBLE_JUMP_SPEED)                # replaces vertical velocity
	elif jump_cut_ready and velocity.y > 0 and not intent.jump_held:
		velocity.y *= Cfg.JUMP_CUT
		jump_cut_ready = false
	if velocity.y <= 0:
		jump_cut_ready = false

func _enter_wallcling(n: Vector3) -> void:
	state = WALLCLING
	last_wall_normal = n
	velocity = Vector3.ZERO
	jumps_left = Cfg.WALL_JUMPS
	jump_cut_ready = false
	var away := Vector3(n.x, 0, n.z)
	if away.length() > 0.01:
		facing = away.normalized()

func _wallcling(intent) -> void:
	if _on_floor:
		state = GROUNDED
		return
	if not _on_wall:
		state = AIRBORNE
		return
	var n := _wall_normal
	var away := Vector3(n.x, 0, n.z).normalized()
	var push_in: float = intent.move_world.dot(n)   # > 0 : pressing away from the wall
	# keep gently pressing into the wall so the kinematic body still reports the contact
	velocity.x = -n.x * 3.0
	velocity.z = -n.z * 3.0
	if push_in > 0.1 and intent.jump_pressed and jumps_left > 0:     # wall jump: away + up
		velocity = away * Cfg.WALL_JUMP_AWAY + Vector3.UP * Cfg.WALL_JUMP_UP
		control_lock = Cfg.WALL_CONTROL_LOCK
		jumps_left = 0
		facing = away
		state = AIRBORNE
	elif push_in > 0.3:                                              # drop off (keep the jump)
		velocity = away * Cfg.WALL_DROP_AWAY
		state = AIRBORNE
	elif intent.jump_pressed and jumps_left > 0:                     # hop straight up, once
		jumps_left -= 1
		velocity.y = Cfg.WALL_HOP_UP

func _enter_slide() -> void:
	state = SLIDE
	slide_timer = Cfg.SLIDE_DURATION
	_set_height(Cfg.PLAYER_CROUCH_HEIGHT)
	velocity.x = facing.x * slide_speed()
	velocity.z = facing.z * slide_speed()

func _end_slide(next_state: int) -> void:
	_set_height(Cfg.PLAYER_HEIGHT)
	state = next_state

func _slide(intent, delta: float) -> void:
	if not _on_floor:
		_end_slide(AIRBORNE)
		return
	slide_timer -= delta
	var decay: float = max(0.0, 1.0 - Cfg.SLIDE_FRICTION * delta)
	velocity.x *= decay
	velocity.z *= decay
	if intent.slide_pressed:                                         # Circle again cancels back to running
		_end_slide(GROUNDED)
		return
	if intent.jump_pressed:
		_set_height(Cfg.PLAYER_HEIGHT)
		_jump(Cfg.JUMP_SPEED)
		state = AIRBORNE
		return
	var speed := Vector2(velocity.x, velocity.z).length()
	if slide_timer <= 0.0 or speed < run_speed() * 0.3:
		_end_slide(GROUNDED)

func _jump(speed: float) -> void:
	velocity.y = speed
	jump_cut_ready = true

func _gravity_and_move(delta: float) -> void:
	var scale := 1.0
	var fall_cap := Cfg.MAX_FALL
	if state == WALLCLING:
		scale = 1.0 if velocity.y > 0.0 else Cfg.WALL_GRAVITY_SCALE
		fall_cap = Cfg.WALL_SLIDE_MAX
	velocity.y -= Cfg.GRAVITY * scale * delta
	if velocity.y < -fall_cap:
		velocity.y = -fall_cap
	move_and_slide()
	_on_floor = is_on_floor()
	_on_wall = is_on_wall()
	_wall_normal = get_wall_normal() if _on_wall else Vector3.ZERO
