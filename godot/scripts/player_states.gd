extends RefCounted
## Player state machine (src/ballbrawlla/entities/player_states.py).
##
##     Grounded --Up--> Airborne --touch wall + press into it--> WallCling
##        |  ^             ^  |                                     |
##   Down |  | release     |  +--land--> Grounded   Up+away (wall jump) / away (drop)
##        v  |             +--------------------------------------+   / lose wall
##     Crouch / Slide
##
##     Sticking to a wall gives one jump (wall_jumps): hop up it (Up), wall-jump (Up + away),
##     or drop off (away) and jump once in the air. Walls can't be climbed.
##     Grounded/Crouch --Z (holding ball)--> Aiming --X throw / Z cancel--> Grounded
##
## Each state's update() runs before physics for the tick. It sets velocity and returns a new State to transition
## to, or null to stay. `p` is the Player (untyped here to avoid a circular preload).

class State:
	var state_name := "state"
	var wants_full_height := true   # player stands back up when possible
	var allows_pickup := true       # false: Z means something else in this state
	func enter(_p) -> void:
		pass
	func exit(_p) -> void:
		pass
	func update(_p, _intent, _dt: float):
		return null
	func gravity_scale(_p) -> float:
		return 1.0
	func max_fall_speed(p) -> float:
		return p.t.player_max_fall_speed
	func _jump(p, speed: float) -> void:
		p.body.vy = -speed
		p.jump_cut_ready = true
	## Kick off the wall on `side` (-1 left, +1 right).
	func _wall_jump(p, side: int) -> void:
		p.body.vx = -side * p.t.wall_jump_x
		p.body.vy = -p.t.wall_jump_y
		p.control_lock = p.t.wall_jump_control_lock
		p.facing = -side
		p.wall_jump_grace = 0.0
		p.jumps_left = 0   # that was the wall's one jump
	func _face(p, move_x: int) -> void:
		if move_x != 0:
			p.facing = move_x
	## Z on the ground while holding the ball: aim. Pickups are handled in Player.update.
	func _grab_or_aim(p, intent):
		if intent.z_pressed and p.held_ball != null and p.t.throw_enabled and p.can_throw:
			return Aiming.new()
		return null

class Grounded extends State:
	func _init() -> void:
		state_name = "grounded"
	func enter(p) -> void:
		p.jumps_left = p.t.air_jumps
		p.control_lock = 0.0
		p.wall_jump_grace = 0.0
		p.last_wall = null   # back on the ground: any wall can be grabbed again
	func update(p, intent, _dt: float):
		if not p.contacts.on_ground:
			return Airborne.new()
		p.body.vx = intent.move_x * p.run_speed()
		_face(p, intent.move_x)
		var nxt = _grab_or_aim(p, intent)
		if nxt != null:
			return nxt
		if intent.jump_pressed:
			_jump(p, p.t.jump_speed)
			return Airborne.new()
		if intent.slide_pressed and p.t.slide_enabled:   # Circle: slide in the facing direction
			return Slide.new()
		if intent.down_held():
			return Slide.new() if (intent.move_x != 0 and p.t.slide_enabled) else Crouch.new()
		return null

class Airborne extends State:
	func _init() -> void:
		state_name = "airborne"
	func update(p, intent, dt: float):
		if p.contacts.on_ground and p.body.vy >= 0.0:
			return Grounded.new()
		# Dropped off a wall a moment ago: Up now is a late "Up + away", a wall jump.
		if p.wall_jump_grace > 0.0:
			p.wall_jump_grace -= dt
			if intent.jump_pressed and p.jumps_left > 0:
				_wall_jump(p, p.wall_jump_side)
				return null
		if p.control_lock > 0.0:
			p.control_lock -= dt
		else:
			p.body.vx = intent.move_x * p.air_speed()
			_face(p, intent.move_x)
		# Press into a wall to stick to it, unless this jump will carry you over it anyway (ledge assist), or it
		# is the wall you last clung to (grab a different wall or land first).
		var sides := [[-1, p.contacts.wall_left, intent.move_x < 0], [1, p.contacts.wall_right, intent.move_x > 0]]
		for sd in sides:
			var side: int = sd[0]
			if sd[1] and sd[2] and not p.will_clear_wall(side, intent.up_held()) and p.can_cling(side):
				return WallCling.new(side)
		if intent.jump_pressed and p.jumps_left > 0:
			p.jumps_left -= 1
			_jump(p, p.t.double_jump_speed)
		elif p.jump_cut_ready and p.body.vy < 0.0 and not intent.up_held():
			p.body.vy *= p.t.jump_cut_multiplier   # short hop on early release
			p.jump_cut_ready = false
		if p.body.vy >= 0.0:
			p.jump_cut_ready = false
		return null

class WallCling extends State:
	var side: int   # -1 wall on the left, +1 wall on the right
	var hop_timer := 0.0   # just hopped: pressing away now is a late "Up + away"
	func _init(s: int = -1) -> void:
		state_name = "wall_cling"
		side = s
	func enter(p) -> void:
		p.last_wall = p.touching_wall(side)
		p.body.vx = 0.0   # stick
		p.body.vy = 0.0
		p.jumps_left = p.t.wall_jumps   # one jump from the wall, however you use it
		p.jump_cut_ready = false
		p.wall_jump_grace = 0.0
		p.facing = -side   # face away from the wall
	func update(p, intent, dt: float):
		if p.contacts.on_ground:
			return Grounded.new()
		var touching: bool = p.contacts.wall_left if side < 0 else p.contacts.wall_right
		if not touching:
			return Airborne.new()
		p.body.vx = 0.0
		hop_timer = maxf(0.0, hop_timer - dt)
		var away: bool = intent.move_x == -side
		if away and ((intent.jump_pressed and p.jumps_left > 0) or hop_timer > 0.0):
			_wall_jump(p, side)   # Up + away (or a hop a moment ago): wall jump
			return Airborne.new()
		if away:   # away alone: let go and drift off, no upward kick; the jump is kept
			p.body.vx = -side * p.air_speed()
			p.wall_jump_grace = p.t.wall_jump_grace if p.jumps_left > 0 else 0.0
			p.wall_jump_side = side
			return Airborne.new()
		if intent.jump_pressed and p.jumps_left > 0:   # Up alone: hop up the wall
			p.jumps_left -= 1
			_jump(p, p.t.wall_climb_speed)
			p.jump_cut_ready = false
			hop_timer = p.t.wall_jump_grace
		if intent.move_x == side and p.t.wall_hold_sticks and p.body.vy > 0.0:
			p.body.vy = 0.0
		return null
	func gravity_scale(p) -> float:
		# Rising: full gravity. Falling: wall friction.
		return 1.0 if p.body.vy < 0.0 else p.t.wall_gravity_scale
	func max_fall_speed(p) -> float:
		return p.t.wall_slide_max_speed

class Crouch extends State:
	func _init() -> void:
		state_name = "crouch"
		wants_full_height = false
	func enter(p) -> void:
		p.set_height(p.t.player_crouch_height)
		p.body.vx = 0.0
	func update(p, intent, _dt: float):
		if not p.contacts.on_ground:
			return Airborne.new()
		# Crawl: a slide that ends under a low gap must not trap the player there.
		p.body.vx = intent.move_x * p.crawl_speed()
		_face(p, intent.move_x)
		var nxt = _grab_or_aim(p, intent)
		if nxt != null:
			return nxt
		if intent.jump_pressed and p.can_stand():
			_jump(p, p.t.jump_speed)
			return Airborne.new()
		if not intent.down_held() and p.can_stand():
			return Grounded.new()
		return null

class Slide extends State:
	var timer := 0.0
	func _init() -> void:
		state_name = "slide"
		wants_full_height = false
	func enter(p) -> void:
		p.set_height(p.t.player_crouch_height)
		p.body.vx = p.facing * p.slide_speed()
		timer = p.t.slide_duration
	func update(p, intent, dt: float):
		if not p.contacts.on_ground:
			return Airborne.new()
		if intent.slide_pressed:            # Circle again cancels the slide, back to running
			return Grounded.new()
		timer -= dt
		p.body.vx *= maxf(0.0, 1.0 - p.t.slide_friction * dt)
		if intent.jump_pressed and p.can_stand():
			_jump(p, p.t.jump_speed)
			return Airborne.new()
		if timer <= 0.0 or absf(p.body.vx) < p.run_speed() * 0.3:
			if intent.down_held() or not p.can_stand():
				return Crouch.new()
			return Grounded.new()
		return null

## Fixed in place. Left/right rotates the aim (full circle), up/down sets power.
class Aiming extends State:
	func _init() -> void:
		state_name = "aiming"
		allows_pickup = false
	func enter(p) -> void:
		p.body.vx = 0.0
		p.body.vy = 0.0
		p.pickup_buffer = 0
		p.aim_angle = 45.0 if p.facing > 0 else 135.0
		p.aim_power = (p.t.power_min + p.t.power_max) / 2.0
	func update(p, intent, dt: float):
		p.body.vx = 0.0
		if not p.contacts.on_ground:
			return Airborne.new()
		# Right = clockwise, left = counter-clockwise.
		if intent.aim_stick != null:   # controller: right stick points the throw
			p.aim_angle = fposmod(atan2(intent.aim_stick[1], intent.aim_stick[0]) * (180.0 / PI), 360.0)
		p.aim_angle = fposmod(p.aim_angle - intent.move_x * p.t.aim_rate * dt, 360.0)
		p.aim_power = minf(p.t.power_max, maxf(p.t.power_min, p.aim_power + intent.vertical * p.t.power_rate * dt))
		if intent.x_pressed:
			p.throw()
			return Grounded.new()
		if intent.z_pressed:
			return Grounded.new()
		return null
