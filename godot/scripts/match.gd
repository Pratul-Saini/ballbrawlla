extends RefCounted
## Match: score, current down, and the winner (src/ballbrawlla/rules/match.py).

const Teams = preload("res://scripts/teams.gd")
const Down = preload("res://scripts/down.gd")

var t
var down
var score := [0, 0]            # indexed by team: [LEFT, RIGHT]
var winner := -1               # -1 = no winner yet
var practice := false          # single player: the human is always on offense
var human: int = Teams.LEFT    # practice only: the team the human plays; swaps to the other side after a touchdown

## `first_offense` is the coin flip (the caller does the random draw so tests can fix it). Practice always starts LEFT.
static func start(tuning, p_first_offense: int, p_practice: bool = false):
	var m = load("res://scripts/match.gd").new()
	m.t = tuning
	m.practice = p_practice
	var first: int = Teams.LEFT if p_practice else p_first_offense
	m.down = Down.possession_start(first, tuning)
	return m

## Advance past a finished play. Returns the scoring team, or -1.
func apply(result: Dictionary) -> int:
	var r := Down.next_down(down, result, t)
	var nxt = r["down"]
	var scorer: int = r["scorer"]
	if scorer >= 0:
		score[scorer] += 1
		if score[scorer] >= t.touchdowns_to_win:
			winner = scorer
	if practice:
		if scorer >= 0:
			human = nxt.offense                           # touchdown: the other team gets the ball and you swap sides
		elif nxt.offense != human:
			nxt = Down.possession_start(human, t)         # turnover on downs: you keep the ball
	down = nxt
	return scorer
