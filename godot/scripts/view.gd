extends RefCounted
## What one human is allowed to see, as a JSON-able Dictionary (src/ballbrawlla/net/view.py).
## The host builds a view per human every frame: its own screen draws view 0, and each client is sent only its own
## view. Hidden information is left out entirely, so a client can't peek at it: the offense's throw angle and power are
## never in the defense's view, and the defense's Defender spot (during the play call) is never in the offense's view.
## Local play (both players at one screen) uses local = true, which shows both.

const Teams = preload("res://scripts/teams.gd")
const Session = preload("res://scripts/session.gd")

## Round to 2 decimals (the wire format sends no more than that).
static func _r(v: float) -> float:
	return snappedf(v, 0.01)

static func _actor(p) -> Dictionary:
	var c = p.contacts
	return {
		"role": p.role, "team": int(p.team),
		"x": _r(p.body.px), "y": _r(p.body.py), "w": p.w, "h": p.h,
		"vx": _r(p.body.vx), "vy": _r(p.body.vy),
		"s": p.state.state_name, "f": p.facing,
		"c": [c.on_ground, c.on_ceiling, c.wall_left, c.wall_right],
	}

## The view for human `pid`. local = true: one shared screen, nothing hidden.
static func make_view(s, pid: int, local: bool = false) -> Dictionary:
	var my_team: int = s.team_of_human[pid]
	var d = s.down()
	var side := "offense" if my_team == d.offense else "defense"
	var v := {
		"t": "snap", "tick": s.tick, "phase": s.phase, "you": pid, "team": my_team, "side": side,
		"practice": s.practice, "defender": s.defender, "connected": s.connected.duplicate(),
		"down": d.number, "offense": d.offense, "score": [s.match_.score[Teams.LEFT], s.match_.score[Teams.RIGHT]],
		"winner": null if s.match_.winner < 0 else s.match_.winner,
		"message": s.message, "timer": null, "local": local,
	}
	if s.phase == Session.PLAY_CALL:
		var c = s.call
		var qf := [c.qb_player.center_x(), c.qb_player.box().bottom()]
		var call := {
			"qb": [_r(qf[0]), _r(qf[1])],                              # where the QB is (feet)
			"qb_h": c.qb_player.h,
			"qb_spot": [_r(c.qb_spot[0]), _r(c.qb_spot[1])],           # the spawn it would take
			"qb_ok": c.qb_ok,                                          # standing on a platform in its zone
			"picks": d.offense_picks_spawn(),
			"placing": c.placing,
			"qb_range": [_r(c.qb_lo), _r(c.qb_hi)],
			"def_range": [_r(c.def_lo), _r(c.def_hi)],
			"off_locked": c.offense_locked, "def_locked": c.defense_locked,
			"restarts": c.restarts,
		}
		if local or side == "offense":
			call["aim"] = [_r(c.aim_angle), _r(c.aim_power)]
		if local or side == "defense":
			var df := [c.def_player.center_x(), c.def_player.box().bottom()]
			call["def"] = [_r(df[0]), _r(df[1])]
			call["def_h"] = c.def_player.h
			call["def_spot"] = [_r(c.def_spot[0]), _r(c.def_spot[1])]
			call["def_ok"] = c.def_ok
		v["call"] = call
		v["timer"] = _r(c.timer)
	if s.game != null and (s.phase == Session.PRE_THROW or s.phase == Session.LIVE or s.phase == Session.DEAD):
		var players: Array = s.game.players
		var actors := [_actor(s.qb)]
		for p in players:
			actors.append(_actor(p))
		var b = s.game.ball
		v["actors"] = actors
		v["ball"] = {
			"x": _r(b.body.px), "y": _r(b.body.py), "vx": _r(b.body.vx), "vy": _r(b.body.vy),
			"holder": null if b.held_by == null else _actor(b.held_by)["role"],
		}
		if s.phase == Session.PRE_THROW:
			v["timer"] = _r(s.timer)
			if local or side == "offense":   # your own locked-in throw
				v["aim"] = [_r(s.qb.aim_angle), _r(s.qb.aim_power)]
		elif s.phase == Session.LIVE and s.loose_timer != null:
			v["timer"] = _r(s.loose_timer)
	return v

## A view that came over the wire has every number as a float; restore the integer fields so the renderer can use
## them as team ids and counters.
static func normalize(v: Dictionary) -> Dictionary:
	for k in ["tick", "you", "team", "offense", "down"]:
		if v.has(k) and v[k] != null:
			v[k] = int(v[k])
	if v.get("winner") != null:
		v["winner"] = int(v["winner"])
	v["score"] = [int(v["score"][0]), int(v["score"][1])]
	if v.has("call"):
		v["call"]["restarts"] = int(v["call"]["restarts"])
	for a in v.get("actors", []):
		a["team"] = int(a["team"])
		a["f"] = int(a["f"])
	return v
