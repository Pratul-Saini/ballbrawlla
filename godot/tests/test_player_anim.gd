extends "res://tests/test_case.gd"
## Which animation and frame a player gets from his state and speed (player_sprites.gd pick_anim, frame_at, get_frame),
## and that the generated player_anim.json is complete. None of this touches the simulation.
const PlayerSprites = preload("res://scripts/player_sprites.gd")

func _anim() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(PlayerSprites.ANIM_PATH))

func test_state_to_animation_table() -> void:
	var cases := [
		# state, vx, vy, landing, expected tag, expected hold
		["grounded", 0.0, 0.0, false, "idle", -1],
		["grounded", 15.0, 0.0, false, "idle", -1],
		["grounded", 25.0, 0.0, false, "run", -1],
		["grounded", -320.0, 0.0, false, "run", -1],
		["grounded", 320.0, 0.0, true, "land", -1],
		["airborne", 100.0, -820.0, false, "jump", -1],
		["airborne", 100.0, -151.0, false, "jump", -1],
		["airborne", 100.0, -100.0, false, "apex", -1],
		["airborne", 100.0, 100.0, false, "apex", -1],
		["airborne", 100.0, 151.0, false, "fall", -1],
		["wall_cling", 0.0, 60.0, false, "fall", 0],
		["crouch", 0.0, 0.0, false, "idle", 1],
		["slide", 300.0, 0.0, false, "idle", 1],
		["aiming", 0.0, 0.0, false, "idle", 0],
	]
	for c in cases:
		var r: Dictionary = PlayerSprites.pick_anim(c[0], c[1], c[2], c[3])
		check_eq(r["tag"], c[4], "tag for %s vx=%s vy=%s landing=%s" % [c[0], c[1], c[2], c[3]])
		check_eq(r["hold"], c[5], "hold for %s" % c[0])

func test_landing_only_applies_on_the_ground() -> void:
	check_eq(PlayerSprites.pick_anim("airborne", 0.0, 400.0, true)["tag"], "fall", "still falling: no landing yet")
	check_eq(PlayerSprites.pick_anim("crouch", 0.0, 0.0, true)["tag"], "idle", "crouching after a landing keeps the crouch frame")

func test_run_cycle_speed_follows_horizontal_speed() -> void:
	check_near(PlayerSprites.run_rate(320.0), 1.0, 1e-9, "top speed plays the drawn pace")
	check_near(PlayerSprites.run_rate(-320.0), 1.0, 1e-9, "left is the same as right")
	check_near(PlayerSprites.run_rate(250.0), 250.0 / 320.0, 1e-9, "carrying the ball (250 px/s) is slower in proportion")
	check(PlayerSprites.run_rate(160.0) < PlayerSprites.run_rate(250.0), "slower speed, slower cycle")
	check_near(PlayerSprites.run_rate(1.0), PlayerSprites.RUN_RATE_MIN, 1e-9, "never frozen")
	check_near(PlayerSprites.run_rate(5000.0), PlayerSprites.RUN_RATE_MAX, 1e-9, "never a blur")

func test_frame_at_loops_and_holds() -> void:
	var d := [80, 80, 80, 80]
	check_eq(PlayerSprites.frame_at(d, true, 0.0), 0)
	check_eq(PlayerSprites.frame_at(d, true, 0.079), 0)
	check_eq(PlayerSprites.frame_at(d, true, 0.081), 1)
	check_eq(PlayerSprites.frame_at(d, true, 0.319), 3)
	check_eq(PlayerSprites.frame_at(d, true, 0.321), 0, "a looping tag wraps")
	check_eq(PlayerSprites.frame_at(d, true, 0.321 + 3.2), 0, "and keeps wrapping")
	check_eq(PlayerSprites.frame_at(d, false, 0.319), 3)
	check_eq(PlayerSprites.frame_at(d, false, 5.0), 3, "a one-shot tag holds its last frame")
	check_eq(PlayerSprites.frame_at([60, 120], false, 0.07), 1, "durations differ per frame")
	check_eq(PlayerSprites.frame_at(d, true, -1.0), 0, "negative time is the start")

func test_json_is_complete() -> void:
	var a: Dictionary = _anim()
	for tag in ["idle", "run", "jump", "apex", "fall", "land"]:
		check(a["tags"].has(tag), "tag %s exists" % tag)
		var info: Dictionary = a["tags"][tag]
		check_eq(info["durations_ms"].size(), int(info["to"]) - int(info["from"]) + 1, "%s has a duration per frame" % tag)
		check(info.has("loop"), "%s says whether it loops" % tag)
	check_eq(a["tags"]["run"]["durations_ms"].size(), 8, "the run cycle has 8 frames")
	check(bool(a["tags"]["run"]["loop"]) and bool(a["tags"]["idle"]["loop"]), "run and idle loop")
	check(not bool(a["tags"]["land"]["loop"]), "landing plays once")
	var frames: int = a["frames"].size()
	for name in ["navy", "navy_left", "red", "red_left"]:
		check_eq(a["hands"][name].size(), frames, "%s has a hand anchor for every frame" % name)
		for h in a["hands"][name]:
			check(float(h[0]) >= 0.0 and float(h[0]) <= 96.0 and float(h[1]) >= 0.0 and float(h[1]) <= 96.0,
					"%s hand anchor %s is inside the 96x96 frame" % [name, str(h)])

func test_left_and_right_use_the_same_frame() -> void:
	var s := PlayerSprites.new()
	if not s.animated:
		return
	for tag in ["idle", "run", "jump", "fall", "land"]:
		for sec in [0.0, 0.09, 0.17, 0.4]:
			for team in [0, 1]:
				var r: Dictionary = s.get_frame_at(team, 1, tag, sec)
				var l: Dictionary = s.get_frame_at(team, -1, tag, sec)
				check_eq(r["frame"], l["frame"], "turning around keeps the frame (%s %s)" % [tag, str(sec)])
				check_eq(r["tag"], l["tag"])
	var right: Dictionary = s.get_frame_at(0, 1, "run", 0.0)
	var left: Dictionary = s.get_frame_at(0, -1, "run", 0.0)
	check(right["tex"] != left["tex"], "left uses the separate left-facing strip (the 23 stays readable)")
	check(right["hand"].x > 0.5 and left["hand"].x < 0.5, "the ball hand is on the front side either way")
	check(s.get_frame_at(0, 1, "run", 0.0)["tex"] != s.get_frame_at(1, 1, "run", 0.0)["tex"], "red has its own strip")

func test_frames_are_full_cells_standing_on_the_feet_line() -> void:
	var s := PlayerSprites.new()
	if not s.animated:
		return
	var f: Dictionary = s.get_frame_at(0, 1, "run", 0.0)
	check_eq((f["src"] as Rect2).size, Vector2(96, 96), "frames are drawn whole, so the feet stay on one line")
	var k := PlayerSprites.art_scale(42.0)
	var d: Rect2 = PlayerSprites.dest_rect(f, 100.0, 500.0, k)
	check_near(d.position.y + PlayerSprites.FOOT_Y * k, 500.0, 0.6, "row 85 sits on the hitbox bottom")
	check_near(d.position.x + PlayerSprites.FOOT_X * k, 100.0, 0.6, "the body is centred on the hitbox")

func test_clock_runs_a_jump_land_sequence() -> void:
	var s := PlayerSprites.new()
	if not s.animated:
		return
	var a: Dictionary = s.get_frame("p", 0, 1, "grounded", 0.0, 0.0, 0.016)
	check_eq(a["tag"], "idle", "standing")
	a = s.get_frame("p", 0, 1, "airborne", 100.0, -800.0, 0.016)
	check_eq(a["tag"], "jump", "rising")
	for i in 20:
		a = s.get_frame("p", 0, 1, "airborne", 100.0, -800.0 + 40.0 * i, 0.016)
	check_eq(a["tag"], "apex", "slowing at the top")
	for i in 20:
		a = s.get_frame("p", 0, 1, "airborne", 100.0, 400.0, 0.016)
	check_eq(a["tag"], "fall", "falling")
	a = s.get_frame("p", 0, 1, "grounded", 0.0, 0.0, 0.016)
	check_eq(a["tag"], "land", "touching down after a real fall squashes once")
	for i in 12:
		a = s.get_frame("p", 0, 1, "grounded", 0.0, 0.0, 0.016)
	check_eq(a["tag"], "idle", "then back to idle")

func test_a_one_tick_hop_does_not_flash_the_landing() -> void:
	var s := PlayerSprites.new()
	if not s.animated:
		return
	s.get_frame("p", 0, 1, "grounded", 300.0, 0.0, 0.016)
	s.get_frame("p", 0, 1, "airborne", 300.0, 20.0, 0.008)
	var a: Dictionary = s.get_frame("p", 0, 1, "grounded", 300.0, 0.0, 0.016)
	check_eq(a["tag"], "run", "stepping off and onto a ledge keeps running")

func test_run_cycle_advances_with_speed_and_not_with_facing() -> void:
	var fast := PlayerSprites.new()
	var slow := PlayerSprites.new()
	if not fast.animated:
		return
	var f: Dictionary = {}
	var sl: Dictionary = {}
	for i in 12:
		f = fast.get_frame("p", 0, 1, "grounded", 320.0, 0.0, 0.05)
		sl = slow.get_frame("p", 0, 1, "grounded", 160.0, 0.0, 0.05)
	check(int(f["frame"]) != int(sl["frame"]), "after the same time the faster runner is further into the cycle")
	var before: int = int(fast.get_frame("p", 0, 1, "grounded", 320.0, 0.0, 0.0)["frame"])
	var after: int = int(fast.get_frame("p", 0, -1, "grounded", -320.0, 0.0, 0.0)["frame"])
	check_eq(after, before, "turning around mid-stride does not change the frame")

func test_each_team_and_role_has_its_own_clock_and_forget_resets_it() -> void:
	var s := PlayerSprites.new()
	if not s.animated:
		return
	for i in 6:
		s.get_frame("0:QB", 0, 1, "grounded", 320.0, 0.0, 0.08)
	var old: Dictionary = s.get_frame("0:QB", 0, 1, "grounded", 320.0, 0.0, 0.0)
	var other: Dictionary = s.get_frame("1:QB", 1, 1, "grounded", 320.0, 0.0, 0.0)
	check(int(old["frame"]) != int(other["frame"]), "the same role on the other team starts its own clock")
	s.forget("0:QB")
	var fresh: Dictionary = s.get_frame("0:QB", 0, 1, "grounded", 320.0, 0.0, 0.0)
	check_eq(int(fresh["frame"]), int(other["frame"]), "after forget() the clock starts again at frame 0")
func test_missing_animation_falls_back_to_the_static_pose() -> void:
	var s := PlayerSprites.new()
	s.animated = false
	var f: Dictionary = s.get_frame("p", 0, 1, "airborne", 0.0, -800.0, 0.016)
	if f.is_empty():
		return   # the old art is missing too (then there is nothing to draw, and callers draw a box)
	check(f.has("foot") and f.has("src") and f.has("hand"), "the static pose carries what the draw code needs")
