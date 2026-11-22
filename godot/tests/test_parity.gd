extends "res://tests/test_case.gd"
## Replays the Python game's recorded scenarios (tools/parity_traces.py) through the GDScript simulation and
## compares positions, velocities, states and the ball at every sampled tick. Only the first mismatch per scenario
## is reported (tick, what, expected, got): after one divergence everything later differs.

const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Game = preload("res://scripts/game.gd")
const Intent = preload("res://scripts/intent.gd")

const EPS := 1e-6   # px; the two engines use the same 64-bit math, so this is very loose. Raise only with a reason.
const PLAYER_FIELDS := ["x", "y", "vx", "vy", "h", "facing", "jumps_left", "control_lock", "pickup_buffer", "state",
		"contacts", "holding", "aim_angle", "aim_power", "ground_x", "ground_y"]
const BALL_FIELDS := ["x", "y", "vx", "vy", "resting", "holder"]

func _traces() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/traces.json"))

func _contacts_bits(c) -> int:
	return int(c.on_ground) | (int(c.on_ceiling) << 1) | (int(c.wall_left) << 2) | (int(c.wall_right) << 3)

func _player_row(p) -> Array:
	return [p.body.px, p.body.py, p.body.vx, p.body.vy, p.h, p.facing, p.jumps_left, p.control_lock,
			p.pickup_buffer, p.state.state_name, _contacts_bits(p.contacts), int(p.held_ball != null),
			p.aim_angle, p.aim_power, p.last_ground_x, p.last_ground_y]

func _ball_row(g) -> Array:
	var b = g.ball
	return [b.body.px, b.body.py, b.body.vx, b.body.vy, int(b.resting), -1 if b.held_by == null else b.held_by.pid]

## "" when equal, else a description of the first difference.
func _diff(names: Array, want: Array, got: Array) -> String:
	for i in names.size():
		var a = want[i]
		var b = got[i]
		if typeof(a) == TYPE_STRING:
			if a != b:
				return "%s expected %s, got %s" % [names[i], a, b]
		elif absf(float(a) - float(b)) > EPS:
			return "%s expected %s, got %s (off by %s)" % [names[i], str(a), str(b), str(absf(float(a) - float(b)))]
	return ""

func _replay(name: String, tr: Dictionary) -> String:
	var lv = Level.load_file("res://levels/%s.json" % tr["level"])["level"]
	var t = Tuning.new()
	var g = Game.new(lv, t, int(tr["players"]))
	for i in g.players.size():
		var p = g.players[i]
		var pos: Array = tr["start"]["players"][i]
		p.body.px = pos[0]
		p.body.py = pos[1]
		p.last_ground_x = pos[0] + p.w / 2.0
		p.last_ground_y = pos[1] + p.h
	var b: Array = tr["start"]["ball"]
	g.ball.body.px = b[0]
	g.ball.body.py = b[1]
	g.ball.body.vx = b[2]
	g.ball.body.vy = b[3]
	var frames: Array = tr["frames"]
	var next_frame := 0
	var tick := 0
	for run in tr["inputs"]:
		for k in int(run[0]):
			var intents := []
			for row in run[1]:
				intents.append(Intent.from_array(row))
			g.step(intents, t.dt())
			if next_frame < frames.size() and int(frames[next_frame][0]) == tick:
				var snap: Dictionary = frames[next_frame][1]
				for i in g.players.size():
					var d := _diff(PLAYER_FIELDS, snap["p"][i], _player_row(g.players[i]))
					if d != "":
						return "tick %d, player %d: %s" % [tick, i, d]
				var db := _diff(BALL_FIELDS, snap["b"], _ball_row(g))
				if db != "":
					return "tick %d, ball: %s" % [tick, db]
				next_frame += 1
			tick += 1
	return ""

func test_every_recorded_scenario_matches_python() -> void:
	var traces := _traces()
	check(traces.size() >= 15, "expected at least 15 scenarios, found %d" % traces.size())
	var names := traces.keys()
	names.sort()
	for name in names:
		var msg := _replay(name, traces[name])
		if msg != "":
			failures.append("%s: %s" % [name, msg])
