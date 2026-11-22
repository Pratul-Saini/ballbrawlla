extends RefCounted
## The ball: a circle under gravity that bounces off every platform (src/ballbrawlla/entities/ball.py).
## Solid platforms bounce it from every side. Thin platforms are one-way: it lands on them from above and passes
## through from below and the sides.

const Body = preload("res://scripts/body.gd")
const Collision = preload("res://scripts/collision.gd")

var t
var radius: float
var body
var held_by = null       # Player or null
var resting := false     # sitting on a floor (normal pointing up)

func _init(spawn: Array, tuning) -> void:
	t = tuning
	radius = tuning.ball_radius
	body = Body.new(float(spawn[0]), float(spawn[1]), tuning.ball_gravity)

func release(x: float, y: float, vx: float, vy: float) -> void:
	held_by = null
	body.px = x
	body.py = y
	body.vx = vx
	body.vy = vy
	resting = false

func update(dt: float, solids: Array, thin: Array = []) -> void:
	if held_by != null:
		var h: Array = held_by.hand_pos()
		body.px = h[0]
		body.py = h[1]
		body.vx = 0.0
		body.vy = 0.0
		return
	body.integrate_velocity(dt)
	# Sub-step so a fast ball never moves more than half its radius per step (prevents tunnelling).
	var travel: float = sqrt(body.vx * body.vx + body.vy * body.vy) * dt
	var steps := maxi(1, int(ceil(travel / (radius * 0.5))))
	var sub_dt := dt / steps
	resting = false
	# Broad phase: a bounce never speeds the ball up and a push-out is at most one radius, so travel + 2 radii
	# (+ slack) covers everything it can touch this tick.
	var reach := travel + 2.0 * radius + 2.0
	var s := Collision.near_point(solids, body.px, body.py, reach)
	var th := Collision.near_point(thin, body.px, body.py, reach)
	for i in steps:
		var prev_bottom: float = body.py + radius
		var vy: float = body.vy
		body.px += body.vx * sub_dt
		body.py += body.vy * sub_dt
		for sol in s:
			var c = Collision.circle_vs_aabb(body.px, body.py, radius, sol)
			if c == null:
				continue
			body.px += c.nx * c.depth
			body.py += c.ny * c.depth
			var v := Collision.bounce(body.vx, body.vy, c.nx, c.ny, t.ball_restitution, t.ball_bounce_friction,
					t.ball_rest_speed)
			body.vx = v[0]
			body.vy = v[1]
			if c.ny < -0.7:
				resting = absf(body.vy) < 1e-6
		if vy > 0.0:
			for tp in th:
				if prev_bottom <= tp.top() + Collision.ABOVE_TOP_TOL and Collision.circle_vs_aabb(body.px, body.py, radius, tp) != null:
					body.py = tp.top() - radius
					var v2 := Collision.bounce(body.vx, body.vy, 0.0, -1.0, t.ball_restitution,
							t.ball_bounce_friction, t.ball_rest_speed)
					body.vx = v2[0]
					body.vy = v2[1]
					resting = absf(body.vy) < 1e-6
	if resting:
		body.vx *= maxf(0.0, 1.0 - t.ball_rolling_drag * dt)
