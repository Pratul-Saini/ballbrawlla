extends RefCounted
## A match in progress: rules + physics driven by humans' Intents (src/ballbrawlla/session.py).
##
## Phase flow for every down:
##
##     PLAY_CALL --both locked--> PRE_THROW --timer--> LIVE --play ends--> DEAD
##         ^  |                                                              |
##         |  +--15 s timeout: restart same play call                       |
##         +------------------- next down (or GAME_OVER) <-------------------+
##
## PRE_THROW is the route window. With Tuning.throw_enabled false (the default) it lasts route_window_seconds, the WR
## already carries the ball, and neither the WR nor the Defender may cross the line of scrimmage until the timer ends;
## then LIVE starts with nothing thrown. With throw_enabled true it lasts pre_throw_seconds, the QB holds the ball and
## throws at zero.
##
## Humans: index 0 is Team.LEFT (Blue), index 1 is Team.RIGHT (Red). On offense a human controls the WR (the QB is
## placed in the play call and, with throwing on, throws by itself); on defense they control the Defender. With one human (practice)
## the defense never moves, or with defender = false (catch practice) there is no defender at all, and after a
## touchdown the human swaps to the other team and attacks the other end zone.

const Teams = preload("res://scripts/teams.gd")
const Down = preload("res://scripts/down.gd")
const Match = preload("res://scripts/match.gd")
const Field = preload("res://scripts/field.gd")
const PlayCall = preload("res://scripts/play_call.gd")
const Player = preload("res://scripts/player.gd")
const Ball = preload("res://scripts/ball.gd")
const Game = preload("res://scripts/game.gd")
const Intent = preload("res://scripts/intent.gd")
const Box = preload("res://scripts/box.gd")

const WAITING := "waiting"        # network: not every human has joined yet
const PLAY_CALL := "play_call"
const PRE_THROW := "pre_throw"    # the route window: free running behind the line of scrimmage (QB holds the ball if throwing)
const LIVE := "live"              # ball thrown: in the air, loose, or carried
const DEAD := "dead"              # play over; showing the result
const GAME_OVER := "game_over"

var level
var t
var field
var humans: int
var practice: bool
var defender: bool
var team_of_human: Array
var connected: Array
var tick := 0
var flips: Array = []             # coin flips to use first (tests set these); otherwise random
var _rng := RandomNumberGenerator.new()
var match_
var memory
var call = null
var game = null
var qb = null
var qb_spot = null
var result = null                 # {"outcome", "spot"} of the last play
var message := ""
var timer := 0.0
var loose_timer = null
var los_x = null                  # line of scrimmage x while the route window locks both sides, else null
var phase := WAITING

## {"session": Session or null, "error": String}. `p_flips` fixes the coin flips (tests); `defender` = false is catch
## practice (one human only; a 2-human game always has a defender).
static func create(p_level, tuning, p_humans: int = 1, p_flips: Array = [], p_defender: bool = true) -> Dictionary:
	if p_humans != 1 and p_humans != 2:
		return {"session": null, "error": "a session has 1 (practice) or 2 humans"}
	var fr := Field.create(p_level, tuning)
	if fr["field"] == null:
		return {"session": null, "error": fr["error"]}
	var s = load("res://scripts/session.gd").new()
	s.level = p_level
	s.t = tuning
	s.field = fr["field"]
	s.humans = p_humans
	s.practice = p_humans == 1
	s.defender = p_defender or p_humans == 2
	s.team_of_human = [Teams.LEFT, Teams.RIGHT].slice(0, p_humans)
	s.connected = [true] if p_humans == 1 else [true, false]
	s.flips = p_flips.duplicate()
	s._rng.randomize()
	s.new_match()
	return {"session": s, "error": ""}

# ------------------------------------------------------------ setup

func human_of(team: int) -> int:
	return team_of_human.find(team)   # -1 if no human plays that team

## A human joined or left. Either way a fresh match starts (or waits).
func set_connected(pid: int, p_connected: bool) -> void:
	connected[pid] = p_connected
	new_match()

func _coin_flip() -> int:
	if not flips.is_empty():
		return int(flips.pop_front())
	return _rng.randi() % 2

func new_match() -> void:
	match_ = Match.start(t, _coin_flip() if not practice else Teams.LEFT, practice)
	_follow_human_team()
	memory = PlayCall.Memory.new()
	call = null
	game = null
	qb = null
	qb_spot = null
	result = null
	message = ""
	timer = 0.0
	loose_timer = null
	los_x = null
	var all_here := true
	for c in connected:
		all_here = all_here and c
	if all_here:
		_start_play_call()
	else:
		phase = WAITING

## Practice: the human plays whichever team the match says (it swaps after a touchdown).
func _follow_human_team() -> void:
	if practice:
		team_of_human = [match_.human]

func down():
	return match_.down

# ------------------------------------------------------------ tick

## One physics tick. intents[i] is human i's input.
func step(intents: Array, dt: float) -> void:
	var padded: Array = intents.duplicate()
	while padded.size() < humans:
		padded.append(Intent.new())
	tick += 1
	var off_i = _intent_for(down().offense, padded)
	var def_i = _intent_for(down().defense(), padded)
	if phase == PLAY_CALL:
		if call.update(off_i, def_i, dt):
			_start_execution()
	elif phase == PRE_THROW or phase == LIVE:
		_step_execution(off_i, def_i, dt)
	elif phase == DEAD:
		timer -= dt
		if timer <= 0.0:
			if match_.winner >= 0:
				phase = GAME_OVER
				message = "%s wins %d-%d" % [Teams.display(match_.winner), match_.score[Teams.LEFT], match_.score[Teams.RIGHT]]
			else:
				_start_play_call()

func _intent_for(team: int, intents: Array):
	var pid := human_of(team)
	return intents[pid] if pid >= 0 else Intent.new()

# ------------------------------------------------------------ phases

func _start_play_call() -> void:
	phase = PLAY_CALL
	call = PlayCall.new(down(), field, t, memory, human_of(down().defense()) < 0)
	message = ""

func _make_actor(spot: Array, role: String, team: int, pid: int):
	var p = Player.new(spot[0], spot[1] - t.player_height / 2.0, t, pid)
	p.role = role
	p.team = team
	p.can_throw = Teams.can_throw(role)
	p.facing = Teams.attack_dir(team)
	return p

func _start_execution() -> void:
	var c = call
	var d = down()
	c.remember(memory)
	var off: int = d.offense
	var dfn: int = d.defense()
	var q = _make_actor(c.qb_spot, Teams.ROLE_QB, off, 2)
	q.aim_angle = c.aim_angle
	q.aim_power = c.aim_power
	var throwing: bool = t.throw_enabled
	var wr_spot
	if throwing:
		# WR: next to the QB, toward the defense's end zone.
		var wr_x: float = c.qb_spot[0] + Teams.attack_dir(off) * (t.player_width + 4.0)
		wr_spot = field.spawn_spot(wr_x, c.qb_spot[1], wr_x, wr_x)
	else:
		wr_spot = _route_wr_spot(c.qb_spot, off)
	var wr = _make_actor(wr_spot, Teams.ROLE_WR, off, 0)
	var actors := [wr]
	if defender:
		var df = _make_actor(c.def_spot, Teams.ROLE_DEF, dfn, 1)
		df.facing = Teams.attack_dir(dfn)
		actors.append(df)
	var g = Game.new(level, t, actors.size())
	g.players = actors
	var holder = q if throwing else wr
	var b = Ball.new(holder.hand_pos(), t)
	b.held_by = holder
	holder.held_ball = b
	g.ball = b
	g.ball_trail.clear()
	game = g
	qb = q
	qb_spot = c.qb_spot
	loose_timer = null
	phase = PRE_THROW
	if throwing:
		timer = t.pre_throw_seconds
	else:
		timer = t.route_window_seconds
		_lock_line_of_scrimmage(c.qb_spot[0], off, actors)

## No-throw WR spawn: 28 px behind the QB (toward the offense's own end zone), always on its side of the line.
func _route_wr_spot(p_qb_spot: Array, off: int) -> Array:
	var wr_x: float = p_qb_spot[0] - Teams.attack_dir(off) * (t.player_width + 4.0)
	var lo: float
	var hi: float
	if Teams.attack_dir(off) > 0:
		lo = field.inner_left
		hi = p_qb_spot[0]
	else:
		lo = p_qb_spot[0]
		hi = field.inner_right
	var spot = field.snap(wr_x, p_qb_spot[1], lo, hi)
	return spot if spot != null else p_qb_spot

## Wall the WR (and Defender) off from the far side of the line for the route window.
## Each gets one full-height solid whose face is half a player width past the line, so their centers can reach it but
## not cross. Edges are whole pixels (plus a hair) so a fractional edge can never leave a 1-ulp overlap, which the Y
## pass would resolve by teleporting.
func _lock_line_of_scrimmage(los: float, off: int, actors: Array) -> void:
	var w: float = t.player_width
	var big: float = float(level.width)
	var tall: float = level.height + 2.0 * big
	var d: int = Teams.attack_dir(off)
	var ahead = Box.new(ceilf(los + w / 2.0 + 1e-6), -big, big, tall)                 # right of the line
	var behind = Box.new(floorf(los - w / 2.0 - 1e-6) - big, -big, big, tall)         # left of the line
	var barriers := {0: ahead if d > 0 else behind}
	if actors.size() > 1:
		barriers[1] = behind if d > 0 else ahead
	for i in barriers:
		if actors[i].box().overlaps(barriers[i]):
			return          # illegal spawn (see Field.spawn_spot): run the window without a line
	game.barriers = barriers
	los_x = los

func _step_execution(off_i, def_i, dt: float) -> void:
	var g = game
	var wr = g.players[0]
	var df = g.players[1] if g.players.size() > 1 else null   # null in catch practice
	g.step([off_i, def_i], dt)
	if phase == PRE_THROW:
		timer -= dt
		if timer <= 0.0:
			if t.throw_enabled:
				qb.throw()
			else:
				g.barriers.clear()
				los_x = null
			phase = LIVE
		return
	var ball = g.ball
	var carrier = ball.held_by
	if carrier == null:
		# "Landed" = the ball has stopped moving. Then 3 s to pick it up.
		if loose_timer == null:
			if ball.resting and sqrt(ball.body.vx * ball.body.vx + ball.body.vy * ball.body.vy) < t.ball_stopped_speed:
				loose_timer = t.loose_ball_seconds
		else:
			loose_timer -= dt
			if loose_timer <= 0.0:
				_end({"outcome": Down.DEAD_BALL, "spot": qb_spot})
		return
	loose_timer = null
	var is_wr: bool = carrier == wr
	var goal_team: int = down().defense() if is_wr else down().offense
	if carrier.contacts.on_ground and field.in_end_zone(goal_team, carrier.center_x()):
		_end({"outcome": Down.TOUCHDOWN if is_wr else Down.PICK_SIX, "spot": null})
		return
	var tagger = df if is_wr else wr
	var tag_intent = def_i if is_wr else off_i
	if tagger != null and tag_intent.z_pressed:
		var dx: float = tagger.center_x() - carrier.center_x()
		var dy: float = tagger.center_y() - carrier.center_y()
		if sqrt(dx * dx + dy * dy) <= t.tag_radius:
			var spot := [carrier.last_ground_x, carrier.last_ground_y]
			_end({"outcome": Down.TAGGED if is_wr else Down.INTERCEPTION_TAGGED, "spot": spot})

func _end(res: Dictionary) -> void:
	var before = down()
	result = res
	var scorer: int = match_.apply(res)
	_follow_human_team()
	message = describe(before, res, scorer, down())
	phase = DEAD
	timer = t.result_pause_seconds

static func ordinal(n: int) -> String:
	return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, "%dth" % n)

static func describe(before, res: Dictionary, _scorer: int, after) -> String:
	var o: String = res["outcome"]
	if o == Down.TOUCHDOWN:
		return "Touchdown %s!" % Teams.display(before.offense)
	if o == Down.PICK_SIX:
		return "Pick six! %s scores" % Teams.display(before.defense())
	if o == Down.INTERCEPTION_TAGGED:
		return "Interception! %s ball, 1st down" % Teams.display(after.offense)
	var what := "Tagged" if o == Down.TAGGED else "Ball dead"
	if after.offense == before.offense:
		return "%s - %s down" % [what, ordinal(after.number)]
	return "%s - turnover on downs, %s ball" % [what, Teams.display(after.offense)]
