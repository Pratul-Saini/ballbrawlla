extends "res://tests/test_case.gd"
## Replays whole recorded football sessions (tools/parity_sessions.py) through the GDScript Session and compares the
## full state at every sampled tick: phase, down, score, messages, timers, the play call, every actor and the ball.
## Only the first mismatch per scenario is reported, since everything after it differs.

const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Session = preload("res://scripts/session.gd")
const View = preload("res://scripts/view.gd")
const Intent = preload("res://scripts/intent.gd")

const EPS := 1e-6

func _data() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/sessions.json"))

func _same(a, b) -> bool:
	if a == null or b == null:
		return a == b
	if typeof(a) == TYPE_STRING or typeof(b) == TYPE_STRING:
		return str(a) == str(b)
	return absf(float(a) - float(b)) <= EPS

func _first_diff(label: String, want: Array, got: Array) -> String:
	if want.size() != got.size():
		return "%s: %d values expected, got %d" % [label, want.size(), got.size()]
	for i in want.size():
		if not _same(want[i], got[i]):
			return "%s[%d] expected %s, got %s" % [label, i, str(want[i]), str(got[i])]
	return ""

func _actor_row(p) -> Array:
	return [p.body.px, p.body.py, p.body.vx, p.body.vy, p.h, p.facing, p.state.state_name,
			int(p.held_ball != null), p.last_ground_x, p.last_ground_y, p.pid]

func _check_snapshot(s, w: Dictionary) -> String:
	var d = s.down()
	var res = null if s.result == null else s.result["outcome"]
	var top := [s.phase, s.tick, d.number, d.offense, "region" if d.offense_picks_spawn() else "fixed",
			s.match_.score[0], s.match_.score[1], s.match_.winner, s.message, s.timer,
			-1.0 if s.loose_timer == null else s.loose_timer, "" if res == null else res]
	var wl = w["loose"]
	var want := [w["ph"], w["tick"], w["down"][0], w["down"][1], w["spawn"], w["score"][0], w["score"][1], w["winner"],
			w["msg"], w["timer"], -1.0 if wl == null else wl, "" if w["res"] == null else w["res"]]
	var m := _first_diff("session", want, top)
	if m != "":
		return m
	if not _same(w["los"], s.los_x):
		return "los expected %s, got %s" % [str(w["los"]), str(s.los_x)]
	if s.team_of_human != w["humans"].map(func(x): return int(x)):
		return "humans expected %s, got %s" % [str(w["humans"]), str(s.team_of_human)]
	if w.has("call"):
		if s.call == null:
			return "play call expected but none exists"
		var c = s.call
		var got := [c.qb_spot[0], c.qb_spot[1], int(c.qb_ok), int(c.placing), c.aim_angle, c.aim_power,
				int(c.offense_locked), int(c.defense_locked), c.restarts, c.timer, c.def_spot[0], c.def_spot[1],
				int(c.def_ok), c.qb_lo, c.qb_hi, c.def_lo, c.def_hi,
				c.qb_player.body.px, c.qb_player.body.py, c.qb_player.body.vx, c.qb_player.body.vy,
				c.qb_player.state.state_name, c.def_player.body.px, c.def_player.body.py,
				c.def_player.body.vx, c.def_player.body.vy, c.def_player.state.state_name]
		m = _first_diff("call", w["call"], got)
		if m != "":
			return m
	if w.has("game"):
		if s.game == null:
			return "game expected but none exists"
		var rows := []
		for p in s.game.players:
			rows.append(_actor_row(p))
		rows.append(_actor_row(s.qb))
		var wa: Array = w["game"]["actors"]
		if rows.size() != wa.size():
			return "%d actors expected, got %d" % [wa.size(), rows.size()]
		for k in rows.size():
			m = _first_diff("actor %d" % k, wa[k], rows[k])
			if m != "":
				return m
		var b = s.game.ball
		m = _first_diff("ball", w["game"]["ball"], [b.body.px, b.body.py, b.body.vx, b.body.vy, int(b.resting),
				-1 if b.held_by == null else b.held_by.pid])
		if m != "":
			return m
	return ""

## "" when equal, else a path to the first difference. Numbers are compared with a tolerance, everything else exactly.
func _view_diff(path: String, want, got) -> String:
	if typeof(want) == TYPE_DICTIONARY:
		if typeof(got) != TYPE_DICTIONARY:
			return "%s: expected an object, got %s" % [path, str(got)]
		for k in want:
			if not got.has(k):
				return "%s.%s is missing" % [path, k]
		for k in got:
			if not want.has(k):
				return "%s.%s should not be there (it would leak or break the protocol)" % [path, k]
		for k in want:
			var m := _view_diff(path + "." + str(k), want[k], got[k])
			if m != "":
				return m
		return ""
	if typeof(want) == TYPE_ARRAY:
		if typeof(got) != TYPE_ARRAY or got.size() != want.size():
			return "%s: expected %s, got %s" % [path, str(want), str(got)]
		for i in want.size():
			var m := _view_diff("%s[%d]" % [path, i], want[i], got[i])
			if m != "":
				return m
		return ""
	if want == null or got == null:
		return "" if want == got else "%s: expected %s, got %s" % [path, str(want), str(got)]
	if typeof(want) == TYPE_BOOL or typeof(got) == TYPE_BOOL:
		return "" if want == got else "%s: expected %s, got %s" % [path, str(want), str(got)]
	if typeof(want) == TYPE_STRING:
		return "" if str(want) == str(got) else "%s: expected %s, got %s" % [path, str(want), str(got)]
	return "" if absf(float(want) - float(got)) <= 0.011 else "%s: expected %s, got %s" % [path, str(want), str(got)]

func _check_views(s, tr_views: Array, tick: int, cursor: int) -> Array:
	## Returns [message, new_cursor]. A view is compared at exactly the tick it was recorded at.
	if cursor >= tr_views.size() or int(tr_views[cursor][0]) != tick:
		return ["", cursor]
	var want: Dictionary = tr_views[cursor][1]
	for key in want:
		var local: bool = key == "L"
		var pid: int = 0 if local else int(key)
		var got := View.make_view(s, pid, local)
		got = JSON.parse_string(JSON.stringify(got))      # what actually crosses the wire
		var m := _view_diff("view[%s]" % key, want[key], got)
		if m != "":
			return [m, cursor]
	return ["", cursor + 1]

func _apply_event(s, ev: Array) -> void:
	match ev[1]:
		"connect": s.set_connected(int(ev[2]), true)
		"disconnect": s.set_connected(int(ev[2]), false)
		"new_match": s.new_match()

func _replay(name: String, tr: Dictionary) -> String:
	var t = Tuning.new()
	for k in tr["tuning"]:
		var cur = t.get(k)
		if typeof(cur) == TYPE_BOOL:
			t.set(k, bool(tr["tuning"][k]))
		else:
			t.set(k, int(tr["tuning"][k]) if typeof(cur) == TYPE_INT else float(tr["tuning"][k]))
	var lv = Level.load_file("res://levels/%s.json" % tr["level"])["level"]
	var created := Session.create(lv, t, int(tr["humans"]), tr["flips"], bool(tr["defender"]))
	if created["session"] == null:
		return "could not create the session: " + created["error"]
	var s = created["session"]
	var events: Array = tr["events"]
	for ev in events:
		if int(ev[0]) < 0:
			_apply_event(s, ev)
	var frames: Array = tr["frames"]
	var next_frame := 0
	var tick := 0
	var ev_i := 0
	var view_cursor := 0
	var tr_views: Array = tr.get("views", [])
	while ev_i < events.size() and int(events[ev_i][0]) < 0:
		ev_i += 1
	for run in tr["inputs"]:
		for n in int(run[0]):
			while ev_i < events.size() and int(events[ev_i][0]) == tick:
				_apply_event(s, events[ev_i])
				ev_i += 1
			var intents := []
			for row in run[1]:
				intents.append(Intent.from_array(row))
			s.step(intents, t.dt())
			if next_frame < frames.size() and int(frames[next_frame][0]) == tick:
				var m := _check_snapshot(s, frames[next_frame][1])
				if m != "":
					return "tick %d: %s" % [tick, m]
				next_frame += 1
			var vr := _check_views(s, tr_views, tick, view_cursor)
			if vr[0] != "":
				return "tick %d: %s" % [tick, vr[0]]
			view_cursor = vr[1]
			tick += 1
	return ""

func test_every_recorded_session_matches_python() -> void:
	var data := _data()
	check(data.size() >= 12, "expected 12 sessions, found %d" % data.size())
	var names := data.keys()
	names.sort()
	for name in names:
		var msg := _replay(name, data[name])
		if msg != "":
			failures.append("%s: %s" % [name, msg])
