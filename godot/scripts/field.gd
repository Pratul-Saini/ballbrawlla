extends RefCounted
## The football field laid over a level: yards, goal lines, end zones, and the platform-top spots where a player may
## be spawned (src/ballbrawlla/rules/field.py).
##
## Layout (Team.LEFT attacks right):
##   wall | LEFT end zone | 0 ......... 50 ......... 0 | RIGHT end zone | wall
## The level's inner width (between the side walls) must equal (field_yards + 2 * end_zone_yards) * yard_px, where
## yard_px is the level's own if it sets one, otherwise Tuning.yard_px.
##
## A Spot is a plain [x, y]: x of a player's center, y of their feet (a platform top).

const Box = preload("res://scripts/box.gd")
const Teams = preload("res://scripts/teams.gd")
const SAMPLE_PX := 2.0   # resolution when scanning platform tops for free spawn space

var level
var t
var yard_px: float
var inner_left: float
var inner_right: float
var end_zone_px: float
var surfaces: Array = []   # [x0, x1, y]: a run of platform top where a standing player fits (center x in [x0, x1])
var _goal := {}

## {"field": Field or null, "error": String}. The error text mirrors Python's ValueError.
static func create(p_level, tuning) -> Dictionary:
	var f = load("res://scripts/field.gd").new()
	f.level = p_level
	f.t = tuning
	f.yard_px = p_level.yard_px if p_level.has_yard_px() else tuning.yard_px
	f.inner_left = p_level.wall_thickness
	f.inner_right = p_level.width - p_level.wall_thickness
	var expected: float = (tuning.field_yards + 2.0 * tuning.end_zone_yards) * f.yard_px
	if absf((f.inner_right - f.inner_left) - expected) > 0.5:
		return {"field": null, "error": "level '%s' inner width is %spx but the field needs %spx (%s + 2x%s yards at %spx/yard)" % [
				p_level.level_name, _g(f.inner_right - f.inner_left), _g(expected), _g(tuning.field_yards),
				_g(tuning.end_zone_yards), _g(f.yard_px)]}
	f.end_zone_px = tuning.end_zone_yards * f.yard_px
	f._goal = {Teams.LEFT: f.inner_left + f.end_zone_px, Teams.RIGHT: f.inner_right - f.end_zone_px}
	f.surfaces = f._find_surfaces()
	return {"field": f, "error": ""}

## Number formatting like Python's %g (whole numbers without a trailing .0).
static func _g(v: float) -> String:
	if v == floorf(v):
		return str(int(v))
	return str(snappedf(v, 0.0001))

# ------------------------------------------------------------ yards

## x of the goal line in front of `team`'s own end zone.
func goal_line_x(team: int) -> float:
	return _goal[team]

## x that is `yards` from `team`'s own goal line, toward the field. Negative yards are inside the team's end zone.
func x_at(team: int, yards: float) -> float:
	return _goal[team] + Teams.attack_dir(team) * yards * yard_px

func yards_from_goal(team: int, x: float) -> float:
	return (x - _goal[team]) * Teams.attack_dir(team) / yard_px

## True if x is inside `team`'s own end zone.
func in_end_zone(team: int, x: float) -> bool:
	return yards_from_goal(team, x) < 0.0

func x_range(team: int, yards_a: float, yards_b: float) -> Array:
	var a := x_at(team, yards_a)
	var b := x_at(team, yards_b)
	return [minf(a, b), maxf(a, b)]

func floor_y() -> float:
	return level.height - level.wall_thickness

# ------------------------------------------------------------ spawn spots

## Scan every platform top (and the floor) for runs where a standing player fits.
func _find_surfaces() -> Array:
	var w: float = t.player_width
	var h: float = t.player_height
	var solids: Array = level.solids
	var out: Array = []
	for plat in level.platforms:
		var r = plat.rect
		if r.top() < level.wall_thickness:   # ceiling / side walls
			continue
		var lo := maxf(r.left(), inner_left + w / 2.0)
		var hi := minf(r.right(), inner_right - w / 2.0)
		# Only solids that can touch a player standing anywhere on this platform top matter.
		var near: Array = []
		for s in solids:
			if s.right() > lo - w / 2.0 and s.left() < hi + w / 2.0 and s.bottom() > r.top() - h and s.top() < r.top():
				near.append(s)
		var run_start = null
		var x := lo
		while x <= hi + 1e-9:
			var box := Box.new(x - w / 2.0, r.top() - h, w, h)
			var free := true
			for s in near:
				if box.overlaps(s):
					free = false
					break
			if free and run_start == null:
				run_start = x
			if not free and run_start != null:
				out.append([run_start, x - SAMPLE_PX, r.top()])
				run_start = null
			x += SAMPLE_PX
		if run_start != null:
			out.append([run_start, minf(x - SAMPLE_PX, hi), r.top()])
	var kept: Array = []
	for s in out:
		if s[1] >= s[0]:
			kept.append(s)
	return kept

## Nearest valid standing spot to (px, py) (feet coords) with center x in [x_lo, x_hi]; null if there is none.
func snap(px: float, py: float, x_lo: float, x_hi: float):
	var best = null
	var best_d := INF
	for s in surfaces:
		var a: float = maxf(s[0], x_lo)
		var b: float = minf(s[1], x_hi)
		if a > b:
			continue
		var x: float = minf(maxf(px, a), b)
		var d: float = (x - px) * (x - px) + (s[2] - py) * (s[2] - py)
		if d < best_d:
			best = [x, s[2]]
			best_d = d
	return best

## Like snap(), but widens the range if nothing fits, so it always returns a spot (unless the level has no surface).
func spawn_spot(px: float, py: float, x_lo: float, x_hi: float):
	for pad in [0.0, 3.0 * yard_px, INF]:
		var spot = snap(px, py, x_lo - pad, x_hi + pad)
		if spot != null:
			return spot
	return null
