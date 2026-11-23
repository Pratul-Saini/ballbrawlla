extends RefCounted
## The animated backdrop of the menu: a scrolling field, and two players throwing a football back and forth
## (src/ballbrawlla/menu_anim.py). Everything is drawn in code, so the game needs no image files.
## pose(t, width) is a pure function of time, so the animation has no state to get out of step. Each throw takes
## PERIOD seconds: wind-up, flight along an arc, catch, hold. Then the players swap roles.

const PlayerSprites = preload("res://scripts/player_sprites.gd")

const PERIOD := 3.6
const WINDUP := 0.5
const FLIGHT := 1.8
const CATCH := 0.4              # seconds; the rest of PERIOD is the hold
const TRAIL := 6                # ghost balls behind the real one
const TRAIL_STEP := 0.028       # seconds between ghosts
const SCROLL_PX_PER_S := 18.0
const STRIPE := 80.0            # px per field stripe
const BALL_W := 42.0
const BALL_H := 26.0
const PLAYER_W := 36.0
const PLAYER_H := 64.0
const SPRITE_H := 88.0          # drawn height of the player art (puts its hand near where the ball is thrown from)
const ARC_HEIGHT := 92.0
const GROUND := 300.0

static func c8(r: int, g: int, b: int, a: int = 255) -> Color:
	return Color(r / 255.0, g / 255.0, b / 255.0, a / 255.0)

static func layout(width: float) -> Array:
	return [width * 0.22, width * 0.78, GROUND]   # left x, right x, ground y

## Where the ball is and what everyone is doing at time t. Returns a Dictionary.
static func pose(t: float, width: float) -> Dictionary:
	var lay := layout(width)
	var left: float = lay[0]
	var right: float = lay[1]
	var gy: float = lay[2]
	var cycle := int(floor(t / PERIOD))
	var local := t - cycle * PERIOD
	var direction := 1 if cycle % 2 == 0 else -1
	var x0 := left if direction == 1 else right
	var x1 := right if direction == 1 else left
	var hand := gy - PLAYER_H * 0.75
	var lean := 0.0
	var lift := 0.0
	var phase := ""
	var x := 0.0
	var y := 0.0
	var angle := 0.0
	if local < WINDUP:
		phase = "windup"
		x = x0
		y = hand
		angle = 20.0 * direction
		lean = sin(local / WINDUP * PI / 2.0)
	elif local < WINDUP + FLIGHT:
		phase = "flight"
		var u := (local - WINDUP) / FLIGHT
		x = x0 + (x1 - x0) * u
		y = hand - 4.0 * ARC_HEIGHT * u * (1.0 - u)          # a parabola from hand to hand
		var dy_du := -4.0 * ARC_HEIGHT * (1.0 - 2.0 * u)
		angle = atan2(-dy_du, x1 - x0) * (180.0 / PI)         # nose follows the path
		lean = maxf(0.0, 1.0 - u * 6.0)
	elif local < WINDUP + FLIGHT + CATCH:
		phase = "catch"
		var v := (local - WINDUP - FLIGHT) / CATCH
		lift = sin(v * PI)
		x = x1
		y = hand - 34.0 * lift
		angle = 70.0 * direction
	else:
		phase = "hold"
		x = x1
		y = hand
		angle = 70.0 * direction
	return {"x": x, "y": y, "angle": angle, "phase": phase, "direction": direction, "receiver_lift": lift, "thrower_lean": lean}

## Poses a moment ago, newest first, only while the ball is in flight.
static func ball_trail(t: float, width: float) -> Array:
	var out: Array = []
	for k in range(1, TRAIL + 1):
		var p := pose(maxf(0.0, t - k * TRAIL_STEP), width)
		if p["phase"] != "flight":
			break
		out.append(p)
	return out

# ---------------------------------------------------------------- drawing

var GRASS_A := c8(30, 104, 52)
var GRASS_B := c8(34, 112, 56)
var LINE := c8(44, 128, 70)
var BLUE := c8(72, 140, 240)
var RED := c8(232, 84, 84)
var BALL_BROWN := c8(140, 82, 40)
var BALL_DARK := c8(96, 54, 26)
var LACE := c8(240, 240, 240)
var SKIN := c8(236, 208, 176)
var _ellipse := PackedVector2Array()
var _inner := PackedVector2Array()
var sprites := PlayerSprites.new()

func _init() -> void:
	for k in 28:
		var a := TAU * k / 28.0
		_ellipse.append(Vector2(cos(a) * BALL_W / 2.0, sin(a) * BALL_H / 2.0))
		_inner.append(Vector2(cos(a) * (BALL_W / 2.0 - 2.5), sin(a) * (BALL_H / 2.0 - 3.0)))

## Draw the backdrop onto `ci`. with_players = false draws only the scrolling field (the long lists need the room).
func draw(ci: CanvasItem, size: Vector2, t: float, with_players: bool) -> void:
	var offset := -STRIPE - fmod(t * SCROLL_PX_PER_S, 2.0 * STRIPE)
	var n := int(size.x / STRIPE) + 4
	for k in n:
		ci.draw_rect(Rect2(offset + k * STRIPE, 0.0, STRIPE, size.y), GRASS_A if k % 2 == 0 else GRASS_B)
	for k in range(0, n, 2):
		ci.draw_line(Vector2(offset + k * STRIPE, 0.0), Vector2(offset + k * STRIPE, size.y), LINE, 2.0)
	if not with_players:
		return
	var lay := layout(size.x)
	var p := pose(t, size.x)
	var thrower_left: bool = p["direction"] == 1
	var local: float = fposmod(t, PERIOD)
	var catch_u: float = clampf((local - WINDUP - FLIGHT) / CATCH, 0.0, 1.0) if p["phase"] == "catch" else -1.0
	_player(ci, lay[0], lay[2], BLUE, 0.0 if thrower_left else p["receiver_lift"], p["thrower_lean"] if thrower_left else 0.0, 1, 0,
			t, -1.0 if thrower_left else catch_u)
	_player(ci, lay[1], lay[2], RED, p["receiver_lift"] if thrower_left else 0.0, 0.0 if thrower_left else p["thrower_lean"], -1, 1,
			t + 0.5, catch_u if thrower_left else -1.0)
	var height: float = maxf(0.0, lay[2] - PLAYER_H * 0.75 - p["y"])
	_ellipse_at(ci, Vector2(p["x"], lay[2] + 2.0), BALL_W / 2.0, 5.0, Color(0, 0, 0, maxf(30.0, 90.0 - height * 0.5) / 255.0))
	var ghosts := ball_trail(t, size.x)
	for k in ghosts.size():
		var g: Dictionary = ghosts[k]
		_ball(ci, Vector2(g["x"], g["y"]), g["angle"], t - (k + 1) * TRAIL_STEP, true, maxf(10.0, 110.0 - k * 20.0) / 255.0)
	_ball(ci, Vector2(p["x"], p["y"]), p["angle"], t, p["phase"] == "flight", 1.0)

func _ellipse_at(ci: CanvasItem, c: Vector2, rx: float, ry: float, color: Color) -> void:
	var pts := PackedVector2Array()
	for k in 20:
		var a := TAU * k / 20.0
		pts.append(c + Vector2(cos(a) * rx, sin(a) * ry))
	ci.draw_colored_polygon(pts, color)

## `clock` is the animation time in seconds (the animation is a pure function of it, like pose()). `catch_u` is -1 when
## the player is not jumping for the catch, else how far through the jump he is (0..1): the first half is the rise,
## the second half the fall.
func _player(ci: CanvasItem, cx: float, gy: float, color: Color, lift: float, lean: float, facing: int, team: int = 0,
		clock: float = 0.0, catch_u: float = -1.0) -> void:
	var spr: Dictionary = {}
	if sprites.available:
		if catch_u < 0.0:
			spr = sprites.get_frame_at(team, facing, "idle", clock)
		elif catch_u < 0.5:
			spr = sprites.get_frame_at(team, facing, "jump", catch_u * CATCH)
		else:
			spr = sprites.get_frame_at(team, facing, "fall", (catch_u - 0.5) * CATCH)
	if not spr.is_empty():
		_ellipse_at(ci, Vector2(cx, gy), PLAYER_W * 0.8, 5.0, c8(20, 72, 36))
		var k: float = SPRITE_H / PlayerSprites.ART_H
		var dst: Rect2 = PlayerSprites.dest_rect(spr, cx + lean * 3.0 * -facing, gy - lift * 34.0, k)
		ci.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		ci.draw_texture_rect_region(spr["tex"], dst, spr["src"])
		return
	var w := PLAYER_W
	var h := PLAYER_H
	var top := gy - h - lift * 34.0
	var body := Rect2(cx - w / 2.0 + lean * 3.0 * -facing, top, w, h)
	_ellipse_at(ci, Vector2(cx, gy), w * 0.7, 5.0, c8(20, 72, 36))
	ci.draw_rect(body, color)
	ci.draw_rect(body, Color.WHITE, false, 2.0)
	ci.draw_circle(Vector2(body.get_center().x, body.position.y + 13.0), 10.0, SKIN)
	var arm := Vector2(body.get_center().x + facing * 10.0, body.position.y + 26.0)
	var reach := Vector2(arm.x + facing * (12.0 + 8.0 * lean + 10.0 * lift), arm.y - 8.0 - 16.0 * lift - 8.0 * lean)
	ci.draw_line(arm, reach, Color.WHITE, 4.0)

## A football at `c`, its nose turned to `angle` degrees (0 = pointing right, y up). In flight it also squashes and
## stretches as it spirals about its long axis.
func _ball(ci: CanvasItem, c: Vector2, angle: float, t: float, spiral: bool, alpha: float) -> void:
	var squash := 0.8 + 0.2 * absf(cos(t * 16.0)) if spiral else 1.0
	ci.draw_set_transform(c, deg_to_rad(-angle), Vector2(1.0, squash))
	var dark := Color(BALL_DARK.r, BALL_DARK.g, BALL_DARK.b, alpha)
	var brown := Color(BALL_BROWN.r, BALL_BROWN.g, BALL_BROWN.b, alpha)
	var lace := Color(LACE.r, LACE.g, LACE.b, alpha)
	ci.draw_colored_polygon(_ellipse, dark)
	ci.draw_colored_polygon(_inner, brown)
	ci.draw_line(Vector2(-BALL_W * 0.22, 0), Vector2(BALL_W * 0.22, 0), lace, 2.0)
	for k in 5:
		var x := -BALL_W * 0.16 + BALL_W * 0.08 * k
		ci.draw_line(Vector2(x, -BALL_H * 0.16), Vector2(x, BALL_H * 0.12), lace, 1.0)
	ci.draw_arc(Vector2(-BALL_W * 0.34, 0), BALL_H * 0.4, -0.9, 0.9, 8, lace, 2.0)
	ci.draw_arc(Vector2(BALL_W * 0.34, 0), BALL_H * 0.4, PI - 0.9, PI + 0.9, 8, lace, 2.0)
	ci.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
