extends RefCounted
## Collision detection and response (src/ballbrawlla/physics/collision.py).
## Player: an AABB moved one axis at a time and pushed out of solids. Ball: a circle against boxes.

const Box = preload("res://scripts/box.gd")
const EPS := 1e-9
const ABOVE_TOP_TOL := 1e-6   # px; tolerance for "mover bottom is at/above a thin top"
const MAX_AABB_STEP := 8.0    # px; keep below the thinnest platform to prevent tunnelling

## Which sides of a box are touching a solid (within 1px).
class Contacts:
	var on_ground := false
	var on_ceiling := false
	var wall_left := false
	var wall_right := false

class CircleContact:
	var nx: float
	var ny: float
	var depth: float

## The rects that can touch `box` once it is grown by `margin` on every side (cheap float compares only).
static func near_box(rects: Array, box, margin: float) -> Array:
	var x0: float = box.x - margin
	var x1: float = box.x + box.w + margin
	var y0: float = box.y - margin
	var y1: float = box.y + box.h + margin
	var out := []
	for r in rects:
		if r.x < x1 and r.x + r.w > x0 and r.y < y1 and r.y + r.h > y0:
			out.append(r)
	return out

## The rects within the square of half-size `margin` around a point (the ball's broad phase).
static func near_point(rects: Array, x: float, y: float, margin: float) -> Array:
	var x0 := x - margin
	var x1 := x + margin
	var y0 := y - margin
	var y1 := y + margin
	var out := []
	for r in rects:
		if r.x < x1 and r.x + r.w > x0 and r.y < y1 and r.y + r.h > y0:
			out.append(r)
	return out

## Move `box` by velocity*dt, resolving X then Y. Zeroes the velocity component on any axis that hits a solid
## (mutates body.vx / body.vy). Returns the new box. `thin` platforms only stop downward motion that started at or
## above their top. Large moves are split into sub-steps of at most MAX_AABB_STEP px.
static func move_aabb(box, body, dt: float, solids: Array, thin: Array = []):
	var travel := maxf(absf(body.vx), absf(body.vy)) * dt
	var steps := maxi(1, int(ceil(travel / MAX_AABB_STEP)))
	var reach := maxf(absf(body.vx), absf(body.vy)) * dt + 2.0
	var s := near_box(solids, box, reach)
	var t := near_box(thin, box, reach)
	for i in steps:
		box = _move_aabb_step(box, body, dt / steps, s, t)
	return box

static func _move_aabb_step(box, body, dt: float, solids: Array, thin: Array):
	var vx: float = body.vx   # the push-out direction must survive the first solid zeroing body.vx
	box = box.shifted(vx * dt, 0.0)
	for s in solids:
		if box.overlaps(s):
			if vx > 0.0:
				box.x = s.left() - box.w
			elif vx < 0.0:
				box.x = s.right()
			body.vx = 0.0
	var vy: float = body.vy
	var prev_bottom: float = box.bottom()
	box = box.shifted(0.0, body.vy * dt)
	for s in solids:
		if box.overlaps(s):
			if body.vy > 0.0:
				box.y = s.top() - box.h
			elif body.vy < 0.0:
				box.y = s.bottom()
			body.vy = 0.0
	if vy > 0.0:
		for t in thin:
			if box.overlaps(t) and prev_bottom <= t.top() + ABOVE_TOP_TOL:
				box.y = t.top() - box.h
				body.vy = 0.0
	return box

static func _touching(box, solids: Array, dx: float, dy: float) -> bool:
	var probe = box.shifted(dx, dy)
	for s in solids:
		if probe.overlaps(s):
			return true
	return false

## Detect touching solids by nudging the box 1px in each direction. Thin platforms only count for on_ground, when
## the box bottom rests on the top edge (within ABOVE_TOP_TOL) and overlaps it horizontally.
static func probe_contacts(box, solids: Array, thin: Array = []) -> Contacts:
	var s := near_box(solids, box, 2.0)
	var t := near_box(thin, box, 2.0)
	var c := Contacts.new()
	c.on_ground = _touching(box, s, 0.0, 1.0)
	if not c.on_ground:
		for th in t:
			if absf(box.bottom() - th.top()) <= ABOVE_TOP_TOL and box.left() < th.right() and box.right() > th.left():
				c.on_ground = true
				break
	c.on_ceiling = _touching(box, s, 0.0, -1.0)
	c.wall_left = _touching(box, s, -1.0, 0.0)
	c.wall_right = _touching(box, s, 1.0, 0.0)
	return c

static func box_is_free(box, solids: Array) -> bool:
	for s in solids:
		if box.overlaps(s):
			return false
	return true

## Circle against box. Returns null, or a CircleContact: unit normal pointing out of the solid, and penetration.
static func circle_vs_aabb(cx: float, cy: float, radius: float, box):
	var closest_x := minf(maxf(cx, box.left()), box.right())
	var closest_y := minf(maxf(cy, box.top()), box.bottom())
	var dx := cx - closest_x
	var dy := cy - closest_y
	var dist_sq := dx * dx + dy * dy
	if dist_sq >= radius * radius:
		return null
	var c := CircleContact.new()
	if dist_sq > EPS:
		var dist := sqrt(dist_sq)
		c.nx = dx / dist
		c.ny = dy / dist
		c.depth = radius - dist
		return c
	# Center is inside the box: push out along the shallowest axis (first one wins a tie).
	var best_pen: float = cx - box.left()
	var bx := -1.0
	var by := 0.0
	var opt: float = box.right() - cx
	if opt < best_pen:
		best_pen = opt
		bx = 1.0
		by = 0.0
	opt = cy - box.top()
	if opt < best_pen:
		best_pen = opt
		bx = 0.0
		by = -1.0
	opt = box.bottom() - cy
	if opt < best_pen:
		best_pen = opt
		bx = 0.0
		by = 1.0
	c.nx = bx
	c.ny = by
	c.depth = best_pen + radius
	return c

## Reflect velocity about `normal`: v' = v_t*(1-friction) - e*v_n. Impacts slower than rest_speed kill the normal
## component instead of bouncing, so a ball settles rather than jittering forever. Returns [vx, vy].
static func bounce(vx: float, vy: float, nx: float, ny: float, restitution: float, friction: float,
		rest_speed: float) -> Array:
	var vn := vx * nx + vy * ny
	if vn >= 0.0:   # already separating
		return [vx, vy]
	var vnx := nx * vn
	var vny := ny * vn
	var vtx := vx - vnx
	var vty := vy - vny
	if -vn < rest_speed:
		return [vtx, vty]
	return [vtx * (1.0 - friction) - vnx * restitution, vty * (1.0 - friction) - vny * restitution]
