extends RefCounted
## The hand-drawn player sprites in assets/sprites/player/: one running pose per team, facing right and (mirrored,
## with the jersey number still reading 23) facing left. Team 0 is blue, team 1 is red. Make the red set from the blue
## with tools/make_team_sprites.py, and the mirrored copies with tools/make_left_sprite.py; all four are plain PNGs
## that can be repainted by hand.

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

var _cache := {}   # "team:facing" -> {tex, src (Rect2), hand (Vector2, 0..1 inside src)}
var available := false
var _fx = null

func _init() -> void:
	available = true
	for pair in FILES:
		for path in pair:
			if not ResourceLoader.exists(path):
				available = false

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
	}
	_cache[key] = entry
	return entry

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
