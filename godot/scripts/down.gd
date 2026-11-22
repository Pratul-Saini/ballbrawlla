extends RefCounted
## Downs: what a down is, where its players may spawn, and what follows it (src/ballbrawlla/rules/down.py).
## A Down is (number, offense, qb_spawn). qb_spawn is either
##   {"kind": "region", "start": yards, "end": yards}   the offense drags the QB anywhere in a region
##   {"kind": "fixed", "x": x, "y": y}                   the QB starts where the last play died

const Teams = preload("res://scripts/teams.gd")

const TOUCHDOWN := "touchdown"
const TAGGED := "tagged"
const DEAD_BALL := "dead_ball"
const INTERCEPTION_TAGGED := "interception_tagged"
const PICK_SIX := "pick_six"

var number: int
var offense: int
var qb_spawn: Dictionary

func _init(p_number: int = 1, p_offense: int = 0, p_qb_spawn: Dictionary = {}) -> void:
	number = p_number
	offense = p_offense
	qb_spawn = p_qb_spawn

func defense() -> int:
	return Teams.other(offense)

func offense_picks_spawn() -> bool:
	return qb_spawn["kind"] == "region"

static func region(start_yards: float, end_yards: float) -> Dictionary:
	return {"kind": "region", "start": start_yards, "end": end_yards}

static func fixed(spot: Array) -> Dictionary:
	return {"kind": "fixed", "x": spot[0], "y": spot[1]}

## 1st down from the offense's own end, QB placed by the offense.
static func possession_start(p_offense: int, t):
	return load("res://scripts/down.gd").new(1, p_offense, region(t.qb_region_start_yards, t.qb_region_end_yards))

# ------------------------------------------------------------ spawn ranges

## Where the QB's center x may be. A fixed spot is never inside the offense's own end zone (it is pushed out to the
## goal line). Returns [lo, hi].
static func qb_x_range(down, field) -> Array:
	if down.qb_spawn["kind"] == "region":
		return field.x_range(down.offense, down.qb_spawn["start"], down.qb_spawn["end"])
	var x: float = down.qb_spawn["x"]
	if field.in_end_zone(down.offense, x):
		x = field.goal_line_x(down.offense)
	return [x, x]

## Furthest the QB can be from the offense's goal line on this down.
static func qb_furthest_yards(down, field) -> float:
	if down.qb_spawn["kind"] == "region":
		return down.qb_spawn["end"]
	var r := qb_x_range(down, field)
	return field.yards_from_goal(down.offense, r[0])

## Closest (yards from the offense's goal line) the Defender may spawn: at least defender_gap_yards past the furthest
## the QB could be, but the defense's own end zone is always allowed.
static func defender_min_yards(down, field, t) -> float:
	return minf(qb_furthest_yards(down, field) + t.defender_gap_yards, t.field_yards)

static func defender_x_range(down, field, t) -> Array:
	var far: float = t.field_yards + t.end_zone_yards   # the defense's back wall
	return field.x_range(down.offense, defender_min_yards(down, field, t), far)

## The down that follows `result` ({"outcome": String, "spot": [x, y] or null}), and the team that scored (-1 if none).
## Returns {"down": Down, "scorer": int}.
static func next_down(down, result: Dictionary, t) -> Dictionary:
	var o: String = result["outcome"]
	var Down = load("res://scripts/down.gd")
	if o == TOUCHDOWN:
		return {"down": possession_start(down.defense(), t), "scorer": down.offense}
	if o == PICK_SIX:
		# The team that was scored on gets the ball back.
		return {"down": possession_start(down.offense, t), "scorer": down.defense()}
	if o == INTERCEPTION_TAGGED:
		return {"down": Down.new(1, down.defense(), fixed(result["spot"])), "scorer": -1}
	# TAGGED or DEAD_BALL: same offense, next down, unless that was the last one.
	if down.number >= t.downs_per_possession:
		return {"down": possession_start(down.defense(), t), "scorer": -1}
	return {"down": Down.new(down.number + 1, down.offense, fixed(result["spot"])), "scorer": -1}
