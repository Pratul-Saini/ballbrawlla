extends "res://tests/test_case.gd"
## Does the simulation load and run at all? (Exact behaviour is checked against Python traces in test_parity.gd.)

const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Game = preload("res://scripts/game.gd")
const Intent = preload("res://scripts/intent.gd")

func test_a_player_falls_lands_and_stands() -> void:
	var lv = Level.load_file("res://levels/field_01.json")["level"]
	var g = Game.new(lv, Tuning.new(), 1)
	var idle = Intent.new()
	for i in 600:
		g.step([idle], g.t.dt())
	check_eq(g.player().state.state_name, "grounded", "ends up standing")
	check(g.player().contacts.on_ground, "on the ground")
