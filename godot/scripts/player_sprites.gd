extends RefCounted
## The hand-drawn player sprites in assets/sprites/player/, now animated. Team 0 is blue, team 1 is red, each facing
## right and (with the jersey number still reading 23) left.
##
## Animation: assets/sprites/player/anim/player_anim.json lists the tags (idle, run, jump, apex, fall, land) of a
## horizontal strip of 96x96 frames per team and facing, plus where the near hand is in every frame. Rebuild it all from
## the hand-drawn fball_*.aseprite files with tools/make_run_cycle.sh. If the JSON or a strip is missing, the old single
## running pose (fball_*.png, made by tools/make_team_sprites.py and tools/make_left_sprite.py) is drawn instead.
##
## get_frame() keeps one animation clock per player, advanced by the render time you pass in, so the animation is smooth
## at any display rate and never touches the 120 Hz simulation. pick_anim() and frame_at() are pure functions.

const FILES := [
	["res://assets/sprites/player/fball_navy.png", "res://assets/sprites/player/fball_navy_left.png"],
	["res://assets/sprites/player/fball_red.png", "res://assets/sprites/player/fball_red_left.png"],
]

## How tall the art is drawn, as a multiple of the player's hitbox height (1.0 = exactly as tall as the hitbox).
## The collision box does not change; this only changes how big he looks.
const VISUAL_SCALE := 1.35

## The double-jump effect: a strip of square frames (frame size = the strip's height) played once at the feet.
const FX_PATH := "res://assets/sprites/player/fx_double_jump.png"
const FX_SECONDS := 0.32
const FX_SCALE := 1.6      # world px per art pixel

## Where the ball sits: the fist of the arm nearest the number's "3", in the art's own pixels (right-facing).
const HAND_RIGHT := Vector2(76.2, 39.4)
const SRC_SIZE := 96.0

## --- animation ---
const ANIM_PATH := "res://assets/sprites/player/anim/player_anim.json"
const SHEETS := [["navy", "navy_left"], ["red", "red_left"]]    # keys of "sheets" and "hands" in the JSON
## The art is scaled as if it were this tall (rows 2..85 of the 96x96 frame: helmet to sole), as before the animation.
const ART_H := 84.0
## Where the feet stand inside a 96x96 frame: the body centre column (right-facing; mirrored for left) and the bottom
## edge of the lowest row (85), which every grounded frame shares.
const FOOT_X := 50.5
const FOOT_Y := 86.0
const RUN_SPEED := 320.0          # px/s at which the 8-frame run cycle plays at its drawn pace
const RUN_RATE_MIN := 0.35        # slowest and fastest the run cycle is played, as a multiple of the drawn pace
const RUN_RATE_MAX := 1.6
const RUN_MIN_SPEED := 20.0       # |vx| above this on the ground is running
const AIR_VY := 150.0             # |vy| above this in the air is rising or falling; below it is the apex
const LAND_SECONDS := 0.12        # how long the landing squash shows
const LAND_MIN_AIR := 0.08        # a hop shorter than this (a bump, a one-tick step off a ledge) shows no landing squash
const MAX_DT := 0.25

var _cache := {}   # "team:facing" -> {tex, src (Rect2), hand (Vector2, 0..1 inside src), foot (Vector2, art px in src)}
var available := false
var animated := false
var _anim := {}                  # parsed player_anim.json, or {} when the animation is missing
var _sheet_tex := {}             # sheet name -> Texture2D
var _clocks := {}                # actor key -> {tag, t, air, land, was_air}
var _fx = null

func _init() -> void:
	available = true
	for pair in FILES:
		for path in pair:
			if not ResourceLoader.exists(path):
				available = false
	_load_anim()
	if animated:
		available = true

func _load_anim() -> void:
	if not FileAccess.file_exists(ANIM_PATH):
		return
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(ANIM_PATH))
	if not (parsed is Dictionary) or not parsed.has("tags") or not parsed.has("hands") or not parsed.has("sheets"):
		return
	for pair in SHEETS:
		for name in pair:
			var path: String = str(parsed["sheets"].get(name, ""))
			if path == "" or not ResourceLoader.exists(path) or not parsed["hands"].has(name):
				return
			var tex = load(path)
			if tex == null:
				return
			_sheet_tex[name] = tex
	_anim = parsed
	animated = true

## {tex, src, hand} for a team and facing (1 right, -1 left), or {} if the art is missing.
func get_sprite(team: int, facing: int, _team_color: Color = Color.WHITE) -> Dictionary:
	if not available:
		return {}
	var side: int = 0 if facing >= 0 else 1
	var key := "%d:%d" % [team, side]
	if _cache.has(key):
		return _cache[key]
	var base: Texture2D = load(FILES[clampi(team, 0, FILES.size() - 1)][side])
	if base == null:
		available = false
		return {}
	var src := Rect2(base.get_image().get_used_rect())
	var hand: Vector2 = HAND_RIGHT if side == 0 else Vector2(SRC_SIZE - HAND_RIGHT.x, HAND_RIGHT.y)
	var entry := {
		"tex": base,
		"src": src,
		"hand": Vector2((hand.x - src.position.x) / src.size.x, (hand.y - src.position.y) / src.size.y),
		"foot": Vector2(src.size.x / 2.0, src.size.y),
	}
	_cache[key] = entry
	return entry
## One animation frame of a team (0 blue, 1 red) facing 1 (right) or -1 (left): {tex, src, hand, foot, tag, frame}.
## `tag` is an animation name and `seconds` the time since it started (looping tags wrap, the others hold their last
## frame); `hold` >= 0 shows that frame of the tag instead. Pure in the clock: call it with the same arguments, get the
## same frame. Falls back to the single static pose (get_sprite) when the animation is missing.
func get_frame_at(team: int, facing: int, tag: String, seconds: float, hold: int = -1) -> Dictionary:
	if not animated:
		return get_sprite(team, facing)
	var side: int = 0 if facing >= 0 else 1
	var name: String = SHEETS[clampi(team, 0, SHEETS.size() - 1)][side]
	var info: Dictionary = _anim["tags"].get(tag, _anim["tags"]["idle"])
	var n: int = int(info["to"]) - int(info["from"]) + 1
	var local: int = clampi(hold, 0, n - 1) if hold >= 0 else frame_at(info["durations_ms"], bool(info["loop"]), seconds)
	var index: int = int(info["from"]) + local
	var hand_px: Array = _anim["hands"][name][index]
	var foot_x: float = FOOT_X if side == 0 else SRC_SIZE - FOOT_X
	return {
		"tex": _sheet_tex[name],
		"src": _frame_rect(index),
		"hand": Vector2(float(hand_px[0]) / SRC_SIZE, float(hand_px[1]) / SRC_SIZE),
		"foot": Vector2(foot_x, FOOT_Y),
		"tag": tag,
		"frame": local,
	}
func _frame_rect(index: int) -> Rect2:
	var r: Array = _anim["frames"][index]
	return Rect2(float(r[0]), float(r[1]), float(r[2]), float(r[3]))
## The frame to draw for the actor `key` now, and advance its clock by `dt` render seconds. `state` is the engine's
## state name (grounded, airborne, wall_cling, crouch, slide, aiming), vx and vy are px/s with y down. Facing only picks
## the left or right strip, never the frame, so turning around does not restart or skip the animation.
func get_frame(key: String, team: int, facing: int, state: String, vx: float, vy: float, dt: float) -> Dictionary:
	if not animated:
		return get_sprite(team, facing)
	dt = clampf(dt, 0.0, MAX_DT)
	var c: Dictionary = _clocks.get(key, {})
	if c.is_empty():
		c = {"tag": "", "t": 0.0, "air": 0.0, "land": 0.0, "was_air": false}
		_clocks[key] = c
	var air: bool = state == "airborne"
	if air:
		c["air"] = float(c["air"]) + dt
	else:
		if bool(c["was_air"]) and float(c["air"]) >= LAND_MIN_AIR:
			c["land"] = LAND_SECONDS
		c["air"] = 0.0
		c["land"] = maxf(0.0, float(c["land"]) - dt)
	c["was_air"] = air
	var pick: Dictionary = pick_anim(state, vx, vy, float(c["land"]) > 0.0)
	var tag: String = pick["tag"]
	if tag != c["tag"]:
		c["tag"] = tag
		c["t"] = 0.0
	else:
		c["t"] = float(c["t"]) + dt * (run_rate(vx) if tag == "run" else 1.0)
	return get_frame_at(team, facing, tag, float(c["t"]), int(pick["hold"]))
## Forget an actor's clock (a player who left, or a new match).
func forget(key: String) -> void:
	_clocks.erase(key)
## Which animation a state and velocity call for: {tag, hold}. `hold` is -1 to play the tag, or the frame of it to
## freeze on (the states with no art of their own borrow the nearest frame). `landing` is true for LAND_SECONDS after
## touching down from a real jump or fall.
static func pick_anim(state: String, vx: float, vy: float, landing: bool = false) -> Dictionary:
	match state:
		"airborne":
			if vy < -AIR_VY:
				return {"tag": "jump", "hold": -1}
			if vy > AIR_VY:
				return {"tag": "fall", "hold": -1}
			return {"tag": "apex", "hold": -1}
		"wall_cling":
			return {"tag": "fall", "hold": 0}
		"crouch", "slide":
			return {"tag": "idle", "hold": 1}
		"aiming":
			return {"tag": "idle", "hold": 0}
	if landing:
		return {"tag": "land", "hold": -1}
	if absf(vx) > RUN_MIN_SPEED:
		return {"tag": "run", "hold": -1}
	return {"tag": "idle", "hold": -1}
## How fast the run cycle plays: 1.0 at RUN_SPEED (the engine's top speed), proportionally slower when slower, so
## carrying the ball (250 px/s) runs at 250/320 of the pace without a special case.
static func run_rate(vx: float) -> float:
	return clampf(absf(vx) / RUN_SPEED, RUN_RATE_MIN, RUN_RATE_MAX)
## Index (0-based, within the tag) of the frame showing `seconds` after the tag started. durations_ms: per frame.
## A looping tag wraps around; a tag that is not looping holds on its last frame.
static func frame_at(durations_ms: Array, loop: bool, seconds: float) -> int:
	var total := 0.0
	for d in durations_ms:
		total += float(d)
	var ms: float = maxf(0.0, seconds) * 1000.0
	if total <= 0.0:
		return 0
	if loop:
		ms = fmod(ms, total)
	elif ms >= total:
		return durations_ms.size() - 1
	var acc := 0.0
	for i in durations_ms.size():
		acc += float(durations_ms[i])
		if ms < acc:
			return i
	return durations_ms.size() - 1
## Screen px per art pixel for a player whose hitbox is `h` tall (times `zoom`), so the art is VISUAL_SCALE times the box.
static func art_scale(h: float, zoom: float = 1.0) -> float:
	return h / ART_H * VISUAL_SCALE * zoom
## Where to draw a sprite entry so its feet stand at (cx, feet_y); `k` is the scale from art_scale().
static func dest_rect(spr: Dictionary, cx: float, feet_y: float, k: float) -> Rect2:
	var foot: Vector2 = spr["foot"]
	var src: Rect2 = spr["src"]
	return Rect2(Vector2(roundf(cx - foot.x * k), roundf(feet_y - foot.y * k)), src.size * k)

## {tex, frames, size} for the double-jump effect, or {} if the strip is missing.
func get_fx() -> Dictionary:
	if _fx == null:
		_fx = {}
		if ResourceLoader.exists(FX_PATH):
			var tex: Texture2D = load(FX_PATH)
			var h: int = tex.get_height()
			_fx = {"tex": tex, "frames": maxi(1, tex.get_width() / h), "size": float(h)}
	return _fx

## Draw the effect `age` seconds after it started, centred on `at`, with art pixels `k` canvas units wide.
func draw_fx(ci: CanvasItem, at: Vector2, age: float, k: float) -> void:
	var fx: Dictionary = get_fx()
	if fx.is_empty() or age >= FX_SECONDS:
		return
	var n: int = fx["frames"]
	var f: int = mini(n - 1, int(age / FX_SECONDS * n))
	var sz: float = fx["size"]
	var dst := Rect2(at - Vector2(sz, sz) * k / 2.0, Vector2(sz, sz) * k)
	ci.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	ci.draw_texture_rect_region(fx["tex"], dst, Rect2(f * sz, 0.0, sz, sz))

## Which way a player faces when the view doesn't say: toward where he last moved, starting from `start`.
## `memory` maps a key to {x, f}; call this every frame with the player's current x. A jump of more than `reset_px`
## in one frame is a respawn, not a step, so it goes back to `start`.
static func track_facing(memory: Dictionary, key: String, x: float, start: int, reset_px: float = 60.0) -> int:
	if not memory.has(key) or absf(x - float(memory[key]["x"])) > reset_px:
		memory[key] = {"x": x, "f": start}
		return start
	var m: Dictionary = memory[key]
	if x > float(m["x"]) + 0.01:
		m["f"] = 1
	elif x < float(m["x"]) - 0.01:
		m["f"] = -1
	m["x"] = x
	return int(m["f"])

## A small football (an ellipse with a lace) centred at `at`; rx is its half-length in the canvas' units.
static func draw_football(ci: CanvasItem, at: Vector2, rx: float, color: Color) -> void:
	var ry: float = rx * 0.62
	var pts := PackedVector2Array()
	for i in 20:
		var a := TAU * i / 20.0
		pts.append(Vector2(cos(a) * rx, sin(a) * ry))
	ci.draw_set_transform(at, -0.35, Vector2.ONE)
	ci.draw_colored_polygon(pts, color)
	ci.draw_line(Vector2(-rx * 0.35, 0.0), Vector2(rx * 0.35, 0.0), Color.WHITE, maxf(1.0, rx * 0.12))
	ci.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
