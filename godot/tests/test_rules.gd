extends "res://tests/test_case.gd"
## Field, downs and the match must behave exactly like the Python game (data: tools/parity_rules.py).

const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Field = preload("res://scripts/field.gd")
const Down = preload("res://scripts/down.gd")
const Match = preload("res://scripts/match.gd")
const Teams = preload("res://scripts/teams.gd")

const EPS := 1e-9

func _data() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/rules.json"))

func _near(a, b) -> bool:
	if a == null or b == null:
		return a == b
	if typeof(a) == TYPE_ARRAY:
		if a.size() != b.size():
			return false
		for i in a.size():
			if not _near(a[i], b[i]):
				return false
		return true
	return absf(float(a) - float(b)) <= EPS

# ------------------------------------------------------------ field

func test_teams() -> void:
	check_eq(Teams.other(Teams.LEFT), Teams.RIGHT)
	check_eq(Teams.attack_dir(Teams.LEFT), 1)
	check_eq(Teams.attack_dir(Teams.RIGHT), -1)
	check_eq(Teams.display(Teams.LEFT), "Blue")
	check_eq(Teams.display(Teams.RIGHT), "Red")
	check(Teams.can_throw("QB") and not Teams.can_throw("WR") and not Teams.can_throw("DEF"), "only the QB throws")

func test_field_matches_python_on_every_level() -> void:
	var t = Tuning.new()
	var want: Dictionary = _data()["field"]
	for stem in want:
		var lv = Level.load_file("res://levels/%s.json" % stem)["level"]
		var r := Field.create(lv, t)
		var w: Dictionary = want[stem]
		if w.has("error"):
			check(r["field"] == null, "%s should not be a football field" % stem)
			check_eq(r["error"], w["error"], stem + " error text")
			continue
		if r["field"] == null:
			failures.append("%s: %s" % [stem, r["error"]])
			continue
		var f = r["field"]
		check_near(f.yard_px, w["yard_px"], EPS, stem + " yard_px")
		check_near(f.end_zone_px, w["end_zone_px"], EPS, stem + " end_zone_px")
		check_near(f.floor_y(), w["floor_y"], EPS, stem + " floor_y")
		check_near(f.goal_line_x(Teams.LEFT), w["goal"]["0"], EPS, stem + " left goal")
		check_near(f.goal_line_x(Teams.RIGHT), w["goal"]["1"], EPS, stem + " right goal")
		check_eq(f.surfaces.size(), w["surfaces"].size(), stem + " number of standing surfaces")
		check(_near(f.surfaces, w["surfaces"]), stem + " standing surfaces differ")
		for q in w["queries"]:
			var rng: Array = q["range"]
			var sn = f.snap(q["p"][0], q["p"][1], rng[0], rng[1])
			check(_near(sn, q["snap"]), "%s snap(%s, %s) expected %s got %s" % [stem, str(q["p"]), str(rng), str(q["snap"]), str(sn)])
			var sp = f.spawn_spot(q["p"][0], q["p"][1], rng[0], rng[1])
			check(_near(sp, q["spawn"]), "%s spawn_spot(%s, %s) expected %s got %s" % [stem, str(q["p"]), str(rng), str(q["spawn"]), str(sp)])
		for y in w["yards"]:
			var team: int = int(y["team"])
			var x: float = f.x_at(team, y["yards"])
			check_near(x, y["x"], EPS, "%s x_at" % stem)
			check_near(f.yards_from_goal(team, x), y["back"], EPS, "%s yards_from_goal" % stem)
			check_eq(f.in_end_zone(team, x), y["in_ez"], stem + " in_end_zone")
			check(_near(f.x_range(team, y["yards"], y["yards"] + 17.0), y["range"]), stem + " x_range")

# ------------------------------------------------------------ downs

func _down(d: Dictionary):
	var spawn: Dictionary = d["qb_spawn"]
	if spawn["kind"] == "region":
		return Down.new(int(d["number"]), int(d["offense"]), Down.region(spawn["start"], spawn["end"]))
	return Down.new(int(d["number"]), int(d["offense"]), Down.fixed([spawn["x"], spawn["y"]]))

func _same_down(got, want: Dictionary) -> bool:
	if got.number != int(want["number"]) or got.offense != int(want["offense"]):
		return false
	var a: Dictionary = got.qb_spawn
	var b: Dictionary = want["qb_spawn"]
	if a["kind"] != b["kind"]:
		return false
	for k in b:
		if k != "kind" and absf(float(a[k]) - float(b[k])) > EPS:
			return false
	return true

func test_every_down_transition_matches_python() -> void:
	var t = Tuning.new()
	var checked := 0
	for tr in _data()["down"]["transitions"]:
		var r := Down.next_down(_down(tr["down"]), {"outcome": tr["outcome"], "spot": tr["spot"]}, t)
		check(_same_down(r["down"], tr["next"]), "after %s from %s: expected %s got %s/%s" % [tr["outcome"], str(tr["down"]), str(tr["next"]), r["down"].number, str(r["down"].qb_spawn)])
		check_eq(r["scorer"], int(tr["scorer"]), "scorer after %s" % tr["outcome"])
		checked += 1
	check_eq(checked, 120, "transitions checked")

func test_spawn_ranges_match_python() -> void:
	var t = Tuning.new()
	var lv = Level.load_file("res://levels/field_01.json")["level"]
	var f = Field.create(lv, t)["field"]
	for rg in _data()["down"]["ranges"]:
		var d = _down(rg["down"])
		check(_near(Down.qb_x_range(d, f), rg["qb_range"]), "qb_x_range for %s" % str(rg["down"]))
		check_near(Down.qb_furthest_yards(d, f), rg["qb_furthest"], EPS, "qb_furthest")
		check_near(Down.defender_min_yards(d, f, t), rg["def_min"], EPS, "defender_min_yards")
		check(_near(Down.defender_x_range(d, f, t), rg["def_range"]), "defender_x_range for %s" % str(rg["down"]))

# ------------------------------------------------------------ match

func test_scripted_matches_follow_python_step_by_step() -> void:
	var t = Tuning.new()
	var matches: Array = _data()["match"]
	check_eq(matches.size(), 14, "scripted matches")
	for n in matches.size():
		var mw: Dictionary = matches[n]
		var m = Match.start(t, int(mw["first"]), bool(mw["practice"]))
		for k in mw["steps"].size():
			var st: Dictionary = mw["steps"][k]
			var scorer: int = m.apply({"outcome": st["outcome"], "spot": st["spot"]})
			var where := "match %d step %d (%s)" % [n, k, st["outcome"]]
			check_eq(scorer, int(st["scorer"]), where + " scorer")
			check(_same_down(m.down, st["down"]), where + ": down expected %s got %d/%s" % [str(st["down"]), m.down.number, str(m.down.qb_spawn)])
			check_eq(m.score, [int(st["score"][0]), int(st["score"][1])], where + " score")
			check_eq(m.winner, int(st["winner"]), where + " winner")
			check_eq(m.human, int(st["human"]), where + " human team")
