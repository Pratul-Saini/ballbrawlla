extends "res://tests/test_case.gd"
## Which way the QB and defender face while they are being placed (player_sprites.gd track_facing).
const PlayerSprites = preload("res://scripts/player_sprites.gd")

func test_starts_facing_the_way_the_team_attacks() -> void:
	var m := {}
	check_eq(PlayerSprites.track_facing(m, "QB", 500.0, 1), 1, "left team starts facing right")
	var m2 := {}
	check_eq(PlayerSprites.track_facing(m2, "QB", 500.0, -1), -1, "right team starts facing left")

func test_turns_toward_the_last_move_and_keeps_it_when_still() -> void:
	var m := {}
	PlayerSprites.track_facing(m, "QB", 500.0, 1)
	check_eq(PlayerSprites.track_facing(m, "QB", 495.0, 1), -1, "stepping left turns him left")
	check_eq(PlayerSprites.track_facing(m, "QB", 495.0, 1), -1, "standing still keeps the facing")
	check_eq(PlayerSprites.track_facing(m, "QB", 500.0, 1), 1, "stepping right turns him right")
	check_eq(PlayerSprites.track_facing(m, "QB", 500.003, 1), 1, "a tiny drift is not a step")

func test_a_respawn_resets_instead_of_turning() -> void:
	var m := {}
	PlayerSprites.track_facing(m, "DEF", 800.0, -1)
	PlayerSprites.track_facing(m, "DEF", 790.0, -1)
	check_eq(PlayerSprites.track_facing(m, "DEF", 1500.0, -1), -1, "a 700 px jump is a respawn: start facing")
	check_eq(PlayerSprites.track_facing(m, "DEF", 1510.0, -1), 1, "then it follows moves again")

func test_the_two_players_are_tracked_separately() -> void:
	var m := {}
	PlayerSprites.track_facing(m, "QB", 100.0, 1)
	PlayerSprites.track_facing(m, "DEF", 900.0, -1)
	check_eq(PlayerSprites.track_facing(m, "QB", 90.0, 1), -1)
	check_eq(PlayerSprites.track_facing(m, "DEF", 905.0, -1), 1)
	check_eq(PlayerSprites.track_facing(m, "QB", 90.0, 1), -1, "the defender's move did not touch the QB")
