extends Node3D
## The prototype's "session": it builds the world, runs the down loop (place the QB, aim the throw,
## free run, snap, catch/tag/score), keeps the score, and drives the camera and HUD.
##
## Single human = offense (place the QB, aim, then run the WR); a simple AI = defense. This mirrors the
## 2-D "practice" mode. Everything is kinematic and deterministic-friendly. See README.md for controls.

const Cfg = preload("res://scripts/config.gd")
const Arena = preload("res://scripts/arena.gd")
const Levels = preload("res://scripts/levels.gd")
const PlayerScript = preload("res://scripts/player.gd")
const BallScript = preload("res://scripts/ball.gd")
const CameraRig = preload("res://scripts/camera_rig.gd")
const HudScript = preload("res://scripts/hud.gd")
const DefenderAi = preload("res://scripts/defender_ai.gd")
const Intent = preload("res://scripts/intent.gd")

enum { PLACE_QB, AIM, PRE_THROW, LIVE, DEAD, GAME_OVER }

var phase := PLACE_QB
var timer := 0.0
var loose_timer := -1.0
var score := [0, 0]
var down_num := 1
var qb_spot := Vector3.ZERO
var last_spot := Vector3.ZERO
var result_msg := ""
var _pending := {}

var aim_yaw := 0.0
var aim_pitch := 25.0
var aim_power := (Cfg.POWER_MIN + Cfg.POWER_MAX) / 2.0

var level_index := 0
var _arena: Arena
var _world: Node3D
var qb
var wr
var defender
var ball
var cam
var hud
var ai

# input edge tracking + accumulators
var _prev := {"jump": false, "slide": false, "catch": false, "throw": false}
var _mouse_dx := 0.0
var _mouse_dy := 0.0
var _wheel := 0.0
var _lmb := false
var _restart_req := false
var _cycle_req := false
var _arc_dots: Array = []

# dev aid: set P3D_AUTO=1 to drive the loop with no human (for headless smoke tests). Off in normal play.
var _auto := false
var _phase_ticks := 0
var _last_phase := -1

const OFFENSE := 0
const DEFENSE := 1

func _ready() -> void:
	_build_lighting()
	_build_actors()
	_build_level(level_index)
	for _i in 28:
		var d := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.18
		sm.height = 0.36
		d.mesh = sm
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(1.0, 0.95, 0.4)
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		d.material_override = m
		d.visible = false
		add_child(d)
		_arc_dots.append(d)
	_auto = OS.get_environment("P3D_AUTO") != ""
	_shot_path = OS.get_environment("P3D_SHOT")
	if not _auto and _shot_path == "":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	new_match()

# dev aid: P3D_SHOT=<path> saves one screenshot after a few frames, then quits (visual smoke test).
var _shot_path := ""
var _shot_frame := 0

func _process(_delta: float) -> void:
	if _shot_path == "":
		return
	_shot_frame += 1
	var at := int(OS.get_environment("P3D_SHOT_FRAME")) if OS.get_environment("P3D_SHOT_FRAME") != "" else 60
	if _shot_frame == at:
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		img.save_png(_shot_path)
		get_tree().quit()

func _build_lighting() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.52, 0.7, 0.95)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.72, 0.76, 0.82)
	env.ambient_light_energy = 0.6
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -50, 0)
	sun.shadow_enabled = true
	sun.light_energy = 1.1
	add_child(sun)

func _build_actors() -> void:
	qb = _make_player(OFFENSE, "QB", Color(0.55, 0.78, 1.0))
	wr = _make_player(OFFENSE, "WR", Color(0.3, 0.6, 1.0))
	defender = _make_player(DEFENSE, "DEF", Color(1.0, 0.42, 0.42))
	ball = BallScript.new()
	ball.set_script(BallScript)
	add_child(ball)
	ball.setup()
	cam = CameraRig.new()
	cam.set_script(CameraRig)
	add_child(cam)
	cam.setup()
	hud = HudScript.new()
	add_child(hud)
	hud.setup()
	ai = DefenderAi.new()

func _make_player(team: int, role: String, color: Color):
	var p := CharacterBody3D.new()
	p.set_script(PlayerScript)
	add_child(p)
	p.setup(team, role, color)
	return p

func _build_level(index: int) -> void:
	if _world != null:
		_world.queue_free()
	_world = Node3D.new()
	add_child(_world)
	_arena = Arena.new()
	var levels := Levels.all()
	_arena.build(_world, levels[index % levels.size()])

# ------------------------------------------------------------ match / downs

func new_match() -> void:
	score = [0, 0]
	down_num = 1
	_begin_place()

func _begin_place() -> void:
	phase = PLACE_QB
	timer = Cfg.PLAY_CALL_SECONDS
	var ax := Arena.attack_dir(OFFENSE)
	var spot: Vector3 = last_spot if down_num > 1 else Vector3(Arena.goal_line_x(OFFENSE) + ax * 5.0, 0.0, 0.0)
	qb_spot = spot
	qb.place_feet(spot.x, spot.y + 2.0, spot.z)   # a little above so it drops onto the surface
	qb.has_ball = false
	cam.yaw = 0.0 if ax > 0 else PI
	wr.visible = false
	defender.visible = false
	ball.visible = false
	qb.visible = true

func _begin_aim() -> void:
	phase = AIM
	aim_yaw = cam.yaw
	aim_pitch = 25.0
	aim_power = (Cfg.POWER_MIN + Cfg.POWER_MAX) / 2.0
	ball.visible = true
	ball.held_by = qb
	qb.has_ball = true

func _begin_pre_throw() -> void:
	phase = PRE_THROW
	timer = Cfg.PRE_THROW_SECONDS
	var ax := Arena.attack_dir(OFFENSE)
	wr.place_feet(qb_spot.x + ax * 1.8, qb_spot.y + 0.5, qb_spot.z)
	wr.has_ball = false
	wr.visible = true
	var dx: float = clampf(qb_spot.x + ax * (Cfg.DEFENDER_GAP_YARDS + 6.0), -Cfg.HALF_LENGTH + 2.0, Cfg.HALF_LENGTH - 2.0)
	defender.place_feet(dx, 2.0, 0.0)
	defender.visible = true
	_hide_arc()

func _do_throw() -> void:
	phase = LIVE
	loose_timer = -1.0
	var dir := CameraRig.aim_direction(aim_yaw, aim_pitch)
	qb.facing = Vector3(cos(aim_yaw), 0, sin(aim_yaw))
	ball.throw(_hand_of(qb), dir * aim_power)
	qb.has_ball = false

func _end_play(msg: String, kind: String, spot = null) -> void:
	result_msg = msg
	_pending = {"kind": kind, "spot": spot}
	phase = DEAD
	timer = Cfg.RESULT_SECONDS

func _apply_pending() -> void:
	if score[OFFENSE] >= Cfg.POINTS_TO_WIN or score[DEFENSE] >= Cfg.POINTS_TO_WIN:
		phase = GAME_OVER
		result_msg = ("You win %d-%d!" if score[OFFENSE] > score[DEFENSE] else "Defense wins %d-%d") % [score[OFFENSE], score[DEFENSE]]
		return
	var k: String = _pending.get("kind", "dead")
	match k:
		"touchdown", "pick_six", "int_tackle":
			down_num = 1
		"tackle":
			if down_num >= Cfg.DOWNS_PER_POSSESSION:
				down_num = 1
			else:
				down_num += 1
				last_spot = _pending.get("spot", qb_spot)
		_:  # dead ball
			if down_num >= Cfg.DOWNS_PER_POSSESSION:
				down_num = 1
			else:
				down_num += 1
				last_spot = qb_spot
	_begin_place()

# ------------------------------------------------------------ main tick

func _physics_process(delta: float) -> void:
	if _restart_req:
		_restart_req = false
		new_match()
	if _cycle_req:
		_cycle_req = false
		level_index += 1
		_build_level(level_index)
		new_match()
	if phase != _last_phase:
		_last_phase = phase
		_phase_ticks = 0
		if _auto:
			print("phase=", phase, " down=", down_num, " score=", score, " msg=", result_msg)
	else:
		_phase_ticks += 1
	_apply_look(delta)
	var human = _human_intent()
	if _auto:
		human = _auto_intent()
	match phase:
		PLACE_QB: _tick_place(human, delta)
		AIM: _tick_aim(human, delta)
		PRE_THROW: _tick_pre_throw(human, delta)
		LIVE: _tick_live(human, delta)
		DEAD:
			timer -= delta
			if timer <= 0.0:
				_apply_pending()
		GAME_OVER:
			pass
	cam.update(delta, _active_center())
	_draw_hud()
	_mouse_dx = 0.0
	_mouse_dy = 0.0
	_wheel = 0.0
	_lmb = false

func _tick_place(human, delta: float) -> void:
	timer -= delta
	qb.step(human, delta)
	var x: float = qb.global_position.x
	var in_zone: bool = (x <= 0.0 and x >= Arena.goal_line_x(OFFENSE)) if Arena.attack_dir(OFFENSE) > 0 else (x >= 0.0 and x <= Arena.goal_line_x(OFFENSE))
	var valid: bool = qb._on_floor and in_zone
	if (human.catch_pressed and valid) or timer <= 0.0:
		if not valid:
			qb.place_feet(Arena.goal_line_x(OFFENSE) + Arena.attack_dir(OFFENSE) * 5.0, 0.0, 0.0)
		qb_spot = Vector3(qb.global_position.x, qb.feet_y(), qb.global_position.z)
		_begin_aim()

func _tick_aim(human, delta: float) -> void:
	aim_yaw = cam.yaw
	aim_pitch = clampf(aim_pitch - _mouse_dy * 0.12 + _stick_pitch() * 60.0 * delta, Cfg.AIM_PITCH_MIN, Cfg.AIM_PITCH_MAX)
	aim_power = clampf(aim_power + _wheel * 3.0 + _trigger_power() * Cfg.POWER_RATE * delta, Cfg.POWER_MIN, Cfg.POWER_MAX)
	qb.facing = Vector3(cos(aim_yaw), 0, sin(aim_yaw))
	ball.carry(_hand_of(qb))
	_show_arc(_hand_of(qb), CameraRig.aim_direction(aim_yaw, aim_pitch) * aim_power)
	if human.throw_pressed:
		_begin_pre_throw()

func _tick_pre_throw(human, delta: float) -> void:
	timer -= delta
	wr.step(human, delta)
	defender.step(ai.decide(defender, wr.global_position, delta), delta)
	_clamp_safe_zone()
	ball.carry(_hand_of(qb))
	if timer <= 0.0 or human.throw_pressed:
		_do_throw()

func _tick_live(human, delta: float) -> void:
	wr.step(human, delta)
	defender.step(ai.decide(defender, _defender_target(), delta), delta)
	ball.step(delta)
	_resolve_pickup()
	if ball.held_by != null:
		ball.carry(_hand_of(ball.held_by))
	_check_live_end(delta)

# ------------------------------------------------------------ live helpers

func _resolve_pickup() -> void:
	if ball.held_by != null:
		return
	var best = null
	var best_d := Cfg.PICKUP_RADIUS
	for p in [wr, defender]:
		var d: float = p.center().distance_to(ball.global_position)
		if d <= best_d:
			best_d = d
			best = p
	if best != null:
		ball.held_by = best
		best.has_ball = true
		ball.resting = false
		loose_timer = -1.0

func _defender_target() -> Vector3:
	var carrier = ball.held_by
	if carrier == defender:
		return Vector3(Arena.goal_line_x(OFFENSE) - Arena.attack_dir(OFFENSE) * 6.0, 0, defender.global_position.z)
	if carrier == wr:
		return wr.global_position
	return ball.global_position     # loose: go for it (intercept / recover)

func _check_live_end(delta: float) -> void:
	var carrier = ball.held_by
	if carrier == null:
		if ball.resting:
			if loose_timer < 0.0:
				loose_timer = Cfg.LOOSE_BALL_SECONDS
			else:
				loose_timer -= delta
				if loose_timer <= 0.0:
					_end_play("Ball dead", "dead")
		return
	if carrier == wr:
		if wr._on_floor and Arena.in_end_zone(DEFENSE, wr.global_position.x):
			score[OFFENSE] += 1
			_end_play("Touchdown!", "touchdown")
		elif defender.center().distance_to(wr.center()) <= Cfg.TAG_RADIUS:
			_end_play("Tackled", "tackle", Vector3(wr.global_position.x, wr.feet_y(), wr.global_position.z))
	elif carrier == defender:
		if defender._on_floor and Arena.in_end_zone(OFFENSE, defender.global_position.x):
			score[DEFENSE] += 1
			_end_play("Pick six! Defense scores", "pick_six")
		elif wr.center().distance_to(defender.center()) <= Cfg.TAG_RADIUS:
			_end_play("Interception stopped", "int_tackle")

func _clamp_safe_zone() -> void:
	# The Defender can't cross the QB's yard line until the throw.
	var ax := Arena.attack_dir(OFFENSE)
	if ax > 0 and defender.global_position.x < qb_spot.x:
		defender.global_position.x = qb_spot.x
		if defender.velocity.x < 0: defender.velocity.x = 0.0
	elif ax < 0 and defender.global_position.x > qb_spot.x:
		defender.global_position.x = qb_spot.x
		if defender.velocity.x > 0: defender.velocity.x = 0.0

func _hand_of(p) -> Vector3:
	return p.center() + p.facing * (Cfg.PLAYER_RADIUS + 0.35) + Vector3(0, p._height * 0.2, 0)

func _active_center() -> Vector3:
	match phase:
		PLACE_QB, AIM: return qb.center()
		_: return wr.center() if wr.visible else qb.center()

# ------------------------------------------------------------ input

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_mouse_dx += event.relative.x
		_mouse_dy += event.relative.y
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			_wheel += 1.0
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_wheel -= 1.0
		elif event.button_index == MOUSE_BUTTON_LEFT:
			_lmb = true
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_ESCAPE:
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED else Input.MOUSE_MODE_CAPTURED
			KEY_R:
				_restart_req = true
			KEY_L:
				_cycle_req = true

func _apply_look(delta: float) -> void:
	cam.add_yaw(-_mouse_dx * 0.004)
	var rx := Input.get_joy_axis(0, JOY_AXIS_RIGHT_X)
	if absf(rx) > 0.2:
		cam.add_yaw(rx * 2.6 * delta)

func _stick_pitch() -> float:
	var ry := Input.get_joy_axis(0, JOY_AXIS_RIGHT_Y)
	return -ry if absf(ry) > 0.2 else 0.0

func _trigger_power() -> float:
	return Input.get_joy_axis(0, JOY_AXIS_TRIGGER_RIGHT) - Input.get_joy_axis(0, JOY_AXIS_TRIGGER_LEFT)

func _human_intent():
	var i = Intent.new()
	var mv := Vector2.ZERO
	if Input.is_physical_key_pressed(KEY_W): mv.y += 1.0
	if Input.is_physical_key_pressed(KEY_S): mv.y -= 1.0
	if Input.is_physical_key_pressed(KEY_D): mv.x += 1.0
	if Input.is_physical_key_pressed(KEY_A): mv.x -= 1.0
	var lx := Input.get_joy_axis(0, JOY_AXIS_LEFT_X)
	var ly := Input.get_joy_axis(0, JOY_AXIS_LEFT_Y)
	if absf(lx) > 0.2: mv.x += lx
	if absf(ly) > 0.2: mv.y -= ly
	mv = mv.limit_length(1.0)
	i.move = mv
	var world: Vector3 = cam.right_flat() * mv.x + cam.forward_flat() * mv.y
	i.move_world = world if world.length() <= 1.0 else world.normalized()
	i.jump_held = _down(KEY_SPACE, JOY_BUTTON_A)
	i.jump_pressed = _edge("jump", i.jump_held)
	i.slide_pressed = _edge("slide", _down(KEY_SHIFT, JOY_BUTTON_B))
	i.catch_pressed = _edge("catch", _down(KEY_E, JOY_BUTTON_X))
	var throw_now := _down(KEY_F, JOY_BUTTON_RIGHT_SHOULDER) or _lmb
	i.throw_pressed = _edge("throw", throw_now)
	return i

func _auto_intent():
	var i = Intent.new()
	i.move_world = Vector3(Arena.attack_dir(OFFENSE), 0, 0)   # always run toward the target end zone
	match phase:
		PLACE_QB: i.catch_pressed = _phase_ticks == 25
		AIM: i.throw_pressed = _phase_ticks == 10
		PRE_THROW: i.throw_pressed = _phase_ticks == 30
	return i

func _down(key: int, button: int) -> bool:
	return Input.is_physical_key_pressed(key) or Input.is_joy_button_pressed(0, button)

func _edge(name: String, now: bool) -> bool:
	var was: bool = _prev[name]
	_prev[name] = now
	return now and not was

# ------------------------------------------------------------ aim arc + HUD

func _show_arc(start: Vector3, v: Vector3) -> void:
	for n in _arc_dots.size():
		var t := float(n) * 0.06
		var p := start + v * t + Vector3(0, -0.5 * Cfg.BALL_GRAVITY * t * t, 0)
		_arc_dots[n].global_position = p
		_arc_dots[n].visible = p.y > -2.0

func _hide_arc() -> void:
	for d in _arc_dots:
		d.visible = false

func _draw_hud() -> void:
	var phase_name: String = ["PLACE QB", "AIM", "SNAP IN", "LIVE", "", ""][phase]
	var clock := ""
	if phase in [PLACE_QB, AIM, PRE_THROW]:
		clock = "   |   %0.0fs" % max(0.0, timer)
	hud.set_top("You %d   AI %d   |   Down %d/%d   |   %s%s" % [score[OFFENSE], score[DEFENSE], down_num, Cfg.DOWNS_PER_POSSESSION, phase_name, clock])
	hud.set_center(result_msg if phase in [DEAD, GAME_OVER] else "")
	hud.set_cross("+" if phase == AIM else "")
	match phase:
		PLACE_QB: hud.set_hint("WASD move the QB into your half, mouse look.  E: confirm the spot.   (L: level, R: restart, Esc: mouse)")
		AIM: hud.set_hint("Mouse: aim (move = pitch, look = direction).  Wheel / triggers: power %0.0f.  F / click: lock in & snap." % aim_power)
		PRE_THROW: hud.set_hint("Get open!  WASD + Space (double-jump), Shift slide, walls to climb.  F: throw now.")
		LIVE:
			if ball.held_by == wr: hud.set_hint("You have the ball - reach the RED end zone. Keep away from the defender!")
			elif ball.held_by == defender: hud.set_hint("Intercepted! Chase the defender down to stop them.")
			else: hud.set_hint("Ball is live - get under it to catch it.")
		GAME_OVER: hud.set_hint("R: new match.")
		_: hud.set_hint("")
