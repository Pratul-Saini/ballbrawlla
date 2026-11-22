extends RefCounted
## The player: a kinematic box driven by a state machine (src/ballbrawlla/entities/player.py).
## Each tick: the state reads the Intent and sets velocity or requests a transition; gravity is applied (scaled and
## capped by the state); the box is moved and pushed out of solids one axis at a time; contacts are probed.

const Box = preload("res://scripts/box.gd")
const Body = preload("res://scripts/body.gd")
const Collision = preload("res://scripts/collision.gd")
const States = preload("res://scripts/player_states.gd")

var t
var pid: int
var connected := true
var role = null              # gameplay role (QB / WR / DEF) when in a match
var team = null
var can_throw := true
var w: float
var h: float
var body                      # position is the top-left of the box
var facing := 1
var contacts
var jumps_left: int
var jump_cut_ready := false
var control_lock := 0.0
var held_ball = null
var last_wall = null          # the wall I last clung to; I can't re-grab it until I cling elsewhere or land
var ball = null
var pickup_requested := false
var pickup_buffer := 0
var ball_trail: Array = []    # recent [x, y] positions of the free ball
var aim_angle := 45.0
var aim_power: float
var last_ground_x: float
var last_ground_y: float
var _solids: Array = []
var state

func _init(spawn_x: float, spawn_y: float, tuning, p_pid: int = 0) -> void:
	t = tuning
	pid = p_pid
	w = tuning.player_width
	h = tuning.player_height
	body = Body.new(spawn_x - w / 2.0, spawn_y - h / 2.0, tuning.player_gravity)
	contacts = Collision.Contacts.new()
	jumps_left = tuning.air_jumps
	aim_power = (tuning.power_min + tuning.power_max) / 2.0
	last_ground_x = spawn_x
	last_ground_y = spawn_y + h / 2.0
	state = States.Airborne.new()
	state.enter(self)

# ------------------------------------------------------------ geometry

func box():
	return Box.new(body.px, body.py, w, h)

func center_x() -> float:
	return body.px + w / 2.0

func center_y() -> float:
	return body.py + h / 2.0

func hand_pos() -> Array:
	return [center_x() + facing * w * 0.6, center_y() + (-h * 0.15)]

## Change height keeping feet planted. Fails (returns false) if blocked.
func set_height(new_h: float) -> bool:
	var dy := h - new_h
	var candidate := Box.new(body.px, body.py + dy, w, new_h)
	if new_h > h and not Collision.box_is_free(candidate, _solids):
		return false
	body.py += dy
	h = new_h
	return true

# ------------------------------------------------------------ speeds

func _carry() -> float:
	return t.carry_speed_multiplier if held_ball != null else 1.0

func run_speed() -> float:
	return t.run_speed * _carry()

func air_speed() -> float:
	return t.air_speed   # not slowed by the ball: jumping is how a carrier escapes

func slide_speed() -> float:
	return t.slide_speed * _carry()

func crawl_speed() -> float:
	return t.crawl_speed * _carry()

# ------------------------------------------------------------ walls

## The solid I'm pressed against on `side` (-1 left, +1 right), or null. Ties go to the first, as in Python.
func touching_wall(side: int):
	var probe = box().shifted(float(side), 0.0)
	var best = null
	var best_overlap := 0.0
	for s in _solids:
		if probe.overlaps(s):
			var ov: float = minf(s.bottom(), probe.bottom()) - maxf(s.top(), probe.top())
			if best == null or ov > best_overlap:
				best = s
				best_overlap = ov
	return best

func can_cling(side: int) -> bool:
	var wall = touching_wall(side)
	return wall != null and wall != last_wall

## True if the rest of the current upward motion will lift my feet above the top of the wall I'm touching.
func will_clear_wall(side: int, up_held: bool = true) -> bool:
	var vy: float = body.vy
	if vy >= 0.0:
		return false
	if jump_cut_ready and not up_held:
		vy *= t.jump_cut_multiplier   # releasing Up is about to cut this jump
	var probe = box().shifted(float(side), 0.0)
	var have := false
	var min_top := 0.0
	for s in _solids:
		if probe.overlaps(s):
			if not have or s.top() < min_top:
				min_top = s.top()
				have = true
	if not have:
		return false
	var rise: float = vy * vy / (2.0 * t.player_gravity)
	return rise >= box().bottom() - min_top

func can_stand() -> bool:
	var full: float = t.player_height
	var dy := h - full
	return Collision.box_is_free(Box.new(body.px, body.py + dy, w, full), _solids)

# ------------------------------------------------------------ ball actions

func _dist_to(x: float, y: float) -> float:
	var dx := center_x() - x
	var dy := center_y() - y
	return sqrt(dx * dx + dy * dy)

## Smallest distance from my center to the ball's current or recent positions; -1 if there is no free ball.
func pickup_distance() -> float:
	if ball == null or ball.held_by != null or held_ball != null:
		return -1.0
	var best := _dist_to(ball.body.px, ball.body.py)
	for q in ball_trail:
		best = minf(best, _dist_to(q[0], q[1]))
	return best

func ball_in_grace_reach() -> bool:
	var d := pickup_distance()
	return d >= 0.0 and d <= t.pickup_radius

## The one place a pickup is attempted. Game grants it at the end of the tick (closest requester wins).
func _pickup_step(z_pressed: bool) -> void:
	if held_ball != null:
		pickup_buffer = 0
		return
	if not state.allows_pickup:
		return
	if z_pressed:
		pass
	elif pickup_buffer > 0:
		pickup_buffer -= 1
	else:
		return
	if ball_in_grace_reach():
		pickup_requested = true
	elif z_pressed:
		pickup_buffer = t.pickup_buffer_ticks()

func aim_direction() -> Array:
	var a := aim_angle * (PI / 180.0)
	return [cos(a), -sin(a)]   # y-down screen coords

func throw() -> void:
	if held_ball == null:
		return
	var d := aim_direction()
	if absf(d[0]) > 1e-3:
		facing = 1 if d[0] > 0.0 else -1
	held_ball.release(center_x(), center_y(), d[0] * aim_power, d[1] * aim_power)
	held_ball = null

# ------------------------------------------------------------ tick

func change_state(new_state) -> void:
	state.exit(self)
	state = new_state
	state.enter(self)

func update(intent, dt: float, solids: Array, p_ball, thin: Array = [], p_trail: Array = []) -> void:
	_solids = solids
	ball = p_ball
	ball_trail = p_trail
	_pickup_step(intent.z_pressed)
	var nxt = state.update(self, intent, dt)
	if nxt != null:
		change_state(nxt)
	if state.wants_full_height and h < t.player_height:
		set_height(t.player_height)
	body.integrate_velocity(dt, state.gravity_scale(self))
	body.vy = minf(body.vy, state.max_fall_speed(self))
	var new_box = Collision.move_aabb(box(), body, dt, solids, thin)
	body.px = new_box.x
	body.py = new_box.y
	contacts = Collision.probe_contacts(new_box, solids, thin)
	if contacts.on_ground and state.state_name != "wall_cling":
		last_ground_x = new_box.center_x()
		last_ground_y = new_box.bottom()
