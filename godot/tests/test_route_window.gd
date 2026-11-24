extends "res://tests/test_case.gd"
## The no-throw version (tests/test_route_window.py): after the play call the WR carries the ball through a route
## window in which neither side may cross the line of scrimmage, then play goes live with nothing thrown.
## The recorded route_* scenarios in test_session.gd prove exact parity; these prove the intent on a flat level.
const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Session = preload("res://scripts/session.gd")
const Game = preload("res://scripts/game.gd")
const Down = preload("res://scripts/down.gd")
const Teams = preload("res://scripts/teams.gd")
const Intent = preload("res://scripts/intent.gd")

const WINDOW := 1.0
const FLOOR_Y := 400.0 - 32.0

func _tuning(extra: Dictionary = {}):
	var t = Tuning.new()
	t.yard_px = 8.0
	t.pre_throw_seconds = 0.05
	t.result_pause_seconds = 0.05
	t.route_window_seconds = WINDOW
	for k in extra:
		t.set(k, extra[k])
	return t

func _level(platforms: Array = []):
	var data := {"name": "flat", "width": 1024, "height": 400, "platforms": platforms,
			"player_spawns": [[100, 300]], "ball_spawn": [200, 300]}
	return Level.parse(data, "flat")["level"]

## A two-human session (Blue offense) on a flat 1024x400 level; with qb_x the down is a fixed-spot down at that x.
func _session(offense: int = Teams.LEFT, qb_x = null, extra: Dictionary = {}, platforms: Array = []):
	var r := Session.create(_level(platforms), _tuning(extra), 2, [offense, offense])   # two flips: create() and set_connected() each start a match
	var s = r["session"]
	s.set_connected(1, true)
	if qb_x != null:
		s.match_.down = Down.new(2, offense, Down.fixed([qb_x, FLOOR_Y]))
		s._start_play_call()
	return s

func _step(s, off = null, dfn = null, ticks: int = 1) -> void:
	for _i in ticks:
		var intents := [Intent.new(), Intent.new()]
		var op: int = s.human_of(s.down().offense)
		var dp: int = s.human_of(s.down().defense())
		if off != null and op >= 0:
			intents[op] = off
		if dfn != null and dp >= 0:
			intents[dp] = dfn
		s.step(intents, s.t.dt())

func _z() -> Intent:
	var i := Intent.new()
	i.z_pressed = true
	return i

func _x() -> Intent:
	var i := Intent.new()
	i.x_pressed = true
	return i

func _move(dir: int) -> Intent:
	var i := Intent.new()
	i.move_x = dir
	return i

func _jumpy(dir: int, tick: int, period: int) -> Intent:
	var i := Intent.new()
	i.move_x = dir
	i.vertical = 1
	i.jump_pressed = tick % period == 0
	i.jump_held = true
	return i

func _ticks() -> int:
	return int(WINDOW * 120.0)

# ------------------------------------------------------------ defaults and the line

func test_defaults_are_no_throw_with_a_five_second_window() -> void:
	var t = Tuning.new()
	check_eq(t.throw_enabled, false, "throw_enabled")
	check_eq(t.route_window_seconds, 5.0, "route_window_seconds")

func _los_ok(s, d: int, los: float) -> String:
	var wr = s.game.players[0]
	var df = s.game.players[1]
	if d * (wr.center_x() - los) > 1.0:
		return "WR center %s is past the line %s" % [str(wr.center_x()), str(los)]
	if d * (df.center_x() - los) < -1.0:
		return "Defender center %s is past the line %s" % [str(df.center_x()), str(los)]
	for p in [wr, df]:
		if p.center_y() < -1.0 or p.center_y() > 401.0:
			return "a player left the level vertically (%s)" % str(p.center_y())
	return ""

func test_los_holds_under_push_for_both_teams() -> void:
	for offense in [Teams.LEFT, Teams.RIGHT]:
		for qb_x in [300.37, 512.5, 700.63]:
			for kind in ["hold", "jump", "double"]:
				var tag := "%s qb_x %s %s" % [Teams.display(offense), str(qb_x), kind]
				var s = _session(offense, qb_x)
				var d: int = Teams.attack_dir(offense)
				_step(s, null, _z())
				_step(s, _x())
				check_eq(s.phase, Session.PRE_THROW, tag + " phase")
				check_eq(s.los_x, qb_x, tag + " los_x")
				check_eq(s.game.barriers.size(), 2, tag + " barriers")
				for tick in _ticks() - 2:
					var off: Intent
					var dfn: Intent
					match kind:
						"hold":
							off = _move(d)
							dfn = _move(-d)
						"jump":
							off = _jumpy(d, tick, 40)
							dfn = _jumpy(-d, tick, 40)
						_:
							off = _jumpy(d, tick, 20)
							dfn = _jumpy(-d, tick, 20)
					_step(s, off, dfn)
					var m := _los_ok(s, d, qb_x)
					if m != "":
						failures.append("%s tick %d: %s" % [tag, tick, m])
						break
				check_eq(s.phase, Session.PRE_THROW, tag + " still in the window")
				if kind == "hold":
					check(absf(s.game.players[0].center_x() - qb_x) < 2.0, tag + " WR pressed against the line")
					check(absf(s.game.players[1].center_x() - qb_x) < 2.0, tag + " Defender pressed against the line")

## A level solid resolved before the barrier in the same step used to zero the X velocity, so the barrier was
## skipped and the Y pass teleported the player on top of it, past the line (tests/test_route_window.py).
func test_los_holds_when_a_level_wall_is_just_beyond_the_barrier_edge() -> void:
	var w: float = Tuning.new().player_width
	for who in ["wr", "df"]:
		for offense in [Teams.LEFT, Teams.RIGHT]:
			for gap in [1.0, 1.5, 2.5]:
				for qb_x in [400.0, 400.37, 400.8]:
					var d: int = Teams.attack_dir(offense)
					var far_edge: float = ceil(qb_x + w / 2.0 + 1e-6) if d > 0 else floor(qb_x - w / 2.0 - 1e-6)
					var near_edge: float = floor(qb_x - w / 2.0 - 1e-6) if d > 0 else ceil(qb_x + w / 2.0 + 1e-6)
					var wall_x: float
					if who == "wr":
						wall_x = far_edge + gap if d > 0 else far_edge - gap - 20.0
					else:
						wall_x = near_edge - gap - 20.0 if d > 0 else near_edge + gap
					var tag := "%s %s gap %s qb_x %s" % [who, Teams.display(offense), str(gap), str(qb_x)]
					var s = _session(offense, qb_x, {}, [{"x": wall_x, "y": 100.0, "w": 20.0, "h": FLOOR_Y - 100.0}])
					_step(s, null, _z())
					_step(s, _x())
					check_eq(s.phase, Session.PRE_THROW, tag + " phase")
					check_eq(s.los_x, qb_x, tag + " los_x")
					for tick in _ticks() - 2:
						_step(s, _move(d), _move(-d))
						var m := _los_ok(s, d, qb_x)
						if m != "":
							failures.append("%s tick %d: %s" % [tag, tick, m])
							break
					var p = s.game.players[0] if who == "wr" else s.game.players[1]
					check(absf(p.center_x() - qb_x) < 2.0 + w, tag + " pressed against its barrier")
func test_line_lifts_at_expiry_and_both_can_cross() -> void:
	for offense in [Teams.LEFT, Teams.RIGHT]:
		var s = _session(offense, 512.5)
		var d: int = Teams.attack_dir(offense)
		_step(s, null, _z())
		_step(s, _x())
		var los: float = s.los_x
		_step(s, _move(d), _move(-d), _ticks() + 2)
		check_eq(s.phase, Session.LIVE, "live after the window")
		check(s.los_x == null and s.game.barriers.is_empty(), "the line is gone")
		_step(s, _move(d), _move(-d), 60)
		var wr = s.game.players[0]
		var df = s.game.players[1]
		check(d * (wr.center_x() - los) > 20.0, "WR crossed the line")
		check(d * (df.center_x() - los) < -20.0, "Defender crossed the line")
		check(s.game.ball.held_by == wr, "WR still carries the ball")

# ------------------------------------------------------------ no throw, no catch

func test_no_throw_and_no_catch_while_the_offense_mashes_buttons() -> void:
	var s = _session()
	_step(s, null, _z())
	_step(s, _x())
	check_eq(s.phase, Session.PRE_THROW, "window started")
	var wr = s.game.players[0]
	var ball = s.game.ball
	check(ball.held_by == wr and wr.held_ball == ball and s.qb.held_ball == null, "the WR carries the ball from the snap")
	for tick in _ticks() + 3 * 120:
		var i := Intent.new()
		i.z_pressed = tick % 2 == 0
		i.x_pressed = tick % 3 == 0
		i.mouse = [300.0, 100.0]
		i.mouse_held = true
		i.mouse_pressed = tick % 5 == 0
		i.button_pressed = tick % 7 == 0
		i.aim_stick = [0.7, 0.7]
		i.move_x = 1 if tick % 90 < 45 else -1
		_step(s, i)
		if s.phase == Session.DEAD:
			break
		if s.qb.held_ball != null or s.game.ball.held_by != wr or wr.held_ball != s.game.ball:
			failures.append("tick %d: the ball was thrown or re-caught" % tick)
			break
		if wr.state.state_name == "aiming" or wr.pickup_buffer != 0:
			failures.append("tick %d: the WR aimed or armed a pickup" % tick)
			break
	check_eq(s.phase, Session.LIVE, "live after the window")

func test_player_throw_is_a_no_op_when_throwing_is_off() -> void:
	var lv = _level()
	var t = _tuning({"throw_enabled": false, "ball_gravity": 0.0})
	var g = Game.new(lv, t, 1)
	var p = g.players[0]
	var ball = g.ball
	ball.held_by = p
	p.held_ball = ball
	p.throw()
	check(p.held_ball == ball and ball.held_by == p, "throw() keeps the ball")
	var t2 = _tuning({"throw_enabled": true, "ball_gravity": 0.0})
	var g2 = Game.new(lv, t2, 1)
	var p2 = g2.players[0]
	var b2 = g2.ball
	b2.held_by = p2
	p2.held_ball = b2
	p2.throw()
	check(p2.held_ball == null and b2.held_by == null, "throw() releases the ball when throwing is on")

# ------------------------------------------------------------ spawn guard and WR spawn

func test_illegal_spawn_runs_the_window_without_a_line() -> void:
	var s = _session(Teams.LEFT, 400.0)
	check(s.call.offense_locked, "fixed spot: offense locked in")
	# Walk the Defender's spot to the offense's side of the line (the zone is widened so it counts).
	var dp = s.call.def_player
	s.call.def_lo = 0.0
	s.call.def_hi = 1024.0
	dp.body.px = 300.0 - dp.w / 2.0
	_step(s, null, null, 10)
	check(s.call.def_ok and absf(s.call.def_spot[0] - 300.0) < 1.0, "the Defender stands at x = 300")
	_step(s, null, _z())
	check_eq(s.phase, Session.PRE_THROW, "window started")
	check_near(s.game.players[1].center_x(), s.call.def_spot[0], 1e-6, "Defender spawned at its spot")
	check(s.los_x == null and s.game.barriers.is_empty(), "no line when the spawn is illegal")
	_step(s, null, null, _ticks() + 2)
	check_eq(s.phase, Session.LIVE, "live after the window")

func test_wr_spawns_behind_the_qb_on_its_own_side() -> void:
	for offense in [Teams.LEFT, Teams.RIGHT]:
		var s = _session(offense, 500.0)
		_step(s, null, _z())
		_step(s, _x())
		var wr = s.game.players[0]
		check_near(wr.center_x(), 500.0 - Teams.attack_dir(offense) * 28.0, 1e-6, "WR spawn x")

# ------------------------------------------------------------ views and legacy

func test_views_agree_and_never_carry_aim() -> void:
	var View = load("res://scripts/view.gd")
	var s = _session()
	for pair in [[0, false], [1, false], [0, true]]:
		var v: Dictionary = View.make_view(s, pair[0], pair[1])
		check(v["throwing"] == false and not v["call"].has("aim") and v["los"] == null, "play-call view")
	_step(s, null, _z())
	_step(s, _x())
	check_eq(s.phase, Session.PRE_THROW, "window started")
	for pair in [[0, false], [1, false], [0, true]]:
		var v: Dictionary = View.make_view(s, pair[0], pair[1])
		check(v["throwing"] == false and not v.has("aim") and v["ball"]["holder"] == "WR", "window view")
		check_near(float(v["los"]), s.los_x, 0.011, "view los")

func test_legacy_mode_still_throws_and_has_no_line() -> void:
	var s = _session(Teams.LEFT, null, {"throw_enabled": true})
	_step(s, _x(), _z())
	check_eq(s.phase, Session.PRE_THROW, "window started")
	check(s.los_x == null and s.game.barriers.is_empty(), "no line when throwing")
	check(s.qb.held_ball != null, "the QB holds the ball")
	_step(s, null, null, 10)
	check_eq(s.phase, Session.LIVE, "the QB throws at zero")
	check(s.game.ball.held_by == null, "the ball is in the air")

# ------------------------------------------------------------ HUD wording

func test_hud_text_says_route_not_throw() -> void:
	var View = load("res://scripts/view.gd")
	var Renderer = load("res://scripts/match_renderer.gd")
	var s = _session()
	var r = Renderer.new(s.level, s.field, s.t)
	var v: Dictionary = View.make_view(s, 0)
	check_eq(r._button_label(v), "Move QB onto a platform" if not v["call"]["qb_ok"] else "Confirm QB spot", "offense button")
	_step(s, null, null, 3)
	v = View.make_view(s, 0)
	check_eq(r._button_label(v), "Confirm QB spot", "offense button once standing")
	check(not r._phase_hint(v).contains("Aim"), "no aim wording in the play call")
	_step(s, _x(), _z())
	check_eq(s.phase, Session.PRE_THROW, "window started")
	var wr_view: Dictionary = View.make_view(s, 0)
	var def_view: Dictionary = View.make_view(s, 1)
	check(r._phase_hint(wr_view).begins_with("ROUTE ") and r._phase_hint(wr_view).contains("run your route"), "WR hint")
	check(r._phase_hint(def_view).contains("hold the line"), "Defender hint")
	check(r._state_hint(wr_view).begins_with("ROUTE "), "state hint")
	var legacy = _session(Teams.LEFT, null, {"throw_enabled": true})
	_step(legacy, _x(), _z())
	check(r._state_hint(View.make_view(legacy, 0)).begins_with("THROW IN"), "throwing keeps the THROW IN wording")
