extends RefCounted
## Simulation root: owns the level, players and ball and advances them one tick (src/ballbrawlla/game.py).
## No rendering, windowing or networking here, so tests (and a network host) can drive it with one Intent per player.

const Player = preload("res://scripts/player.gd")
const Ball = preload("res://scripts/ball.gd")

var level
var t
var num_players: int
var players: Array = []
var ball
var ball_trail: Array = []   # recent free-ball centers, newest last; empty while the ball is held
## Extra solids for single players (index in `players`), e.g. the line of scrimmage during the route window. The ball
## ignores them.
var barriers := {}

func _init(p_level, tuning, p_num_players: int = 1) -> void:
	level = p_level
	t = tuning
	num_players = p_num_players
	reset()

func player():
	return players[0]

func _spawn(pid: int):
	var s: Array = level.spawn_for(pid)
	return Player.new(s[0], s[1], t, pid)

func reset() -> void:
	var was_connected: Array = []
	for p in players:
		was_connected.append(p.connected)
	if was_connected.is_empty():
		for i in num_players:
			was_connected.append(true)
	players = []
	for i in num_players:
		players.append(_spawn(i))
		players[i].connected = was_connected[i]
	ball = Ball.new(level.ball_spawn, t)
	ball_trail.clear()
	barriers.clear()

## Respawn one player (e.g. on join/leave), dropping the ball if they held it.
func reset_player(pid: int, p_connected: bool = true) -> void:
	var old = players[pid]
	if ball.held_by == old:
		ball.release(old.center_x(), old.center_y(), 0.0, 0.0)
	ball_trail.clear()
	players[pid] = _spawn(pid)
	players[pid].connected = p_connected

func step(intents: Array, dt: float) -> void:
	for i in mini(players.size(), intents.size()):
		var p = players[i]
		if p.connected:
			var solids: Array = level.solids
			if barriers.has(i):
				solids = level.solids + [barriers[i]]
			p.update(intents[i], dt, solids, ball, level.thin, ball_trail)
	_resolve_pickups()
	ball.update(dt, level.solids, level.thin)
	if ball.held_by == null:
		ball_trail.append([ball.body.px, ball.body.py])
		while ball_trail.size() > t.pickup_grace_ticks() + 1:
			ball_trail.pop_front()
	else:
		ball_trail.clear()

## Players only request a pickup during their update; if several ask on the same tick the closest one gets it.
func _resolve_pickups() -> void:
	var requesters: Array = []
	for p in players:
		if p.pickup_requested and p.ball_in_grace_reach():
			requesters.append(p)
	for p in players:
		p.pickup_requested = false
	if requesters.is_empty():
		return
	var winner = requesters[0]
	for p in requesters:
		var dp: float = p.pickup_distance()
		var dw: float = winner.pickup_distance()
		if dp < dw or (dp == dw and p.pid < winner.pid):
			winner = p
	winner.held_ball = ball
	ball.held_by = winner
	for p in players:
		p.pickup_buffer = 0
	ball_trail.clear()
