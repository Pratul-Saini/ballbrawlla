extends "res://tests/test_case.gd"
## The GDScript level loader must produce exactly what Python's loader does, for every level file.

const Level = preload("res://scripts/level.gd")
const Box = preload("res://scripts/box.gd")

func _python() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/levels.json"))

func _boxes(arr: Array) -> Array:
	var out := []
	for b in arr:
		out.append(b.to_array())
	return out

func test_all_levels_load_and_match_python() -> void:
	var py := _python()
	check_eq(py.size(), 15, "number of levels in the parity data")
	for stem in py:
		var r = Level.load_file("res://levels/%s.json" % stem)
		if r["level"] == null:
			failures.append("%s: %s" % [stem, r["error"]])
			continue
		var lv = r["level"]
		var want: Dictionary = py[stem]
		check_eq(lv.level_name, want["name"], stem + " name")
		check_near(lv.width, want["width"], 0.0, stem + " width")
		check_near(lv.height, want["height"], 0.0, stem + " height")
		check_near(lv.wall_thickness, want["wall_thickness"], 0.0, stem + " wall_thickness")
		check_eq(lv.player_spawns, want["player_spawns"], stem + " spawns")
		check_eq(lv.ball_spawn, want["ball_spawn"], stem + " ball_spawn")
		check_eq(lv.has_yard_px(), want["yard_px"] != null, stem + " has yard_px")
		if want["yard_px"] != null:
			check_near(lv.yard_px, want["yard_px"], 0.0, stem + " yard_px")
		check_eq(_boxes(lv.solids), want["solids"], stem + " solids (boundaries first, then platforms in order)")
		check_eq(_boxes(lv.thin), want["thin"], stem + " thin platforms")

func test_boundaries_come_first_and_surround_the_level() -> void:
	var lv = Level.load_file("res://levels/field_01.json")["level"]
	check_eq(lv.platforms[0].kind, "bound", "first is a boundary")
	check_eq(lv.platforms[3].kind, "bound", "fourth is a boundary")
	check_eq(lv.platforms[4].kind, "platform", "then real platforms")
	var floor = lv.solids[0]
	check_near(floor.y, lv.height - lv.wall_thickness, 0.0, "floor sits at the bottom")
	check_near(floor.w, lv.width, 0.0, "floor spans the level")

func test_spawn_for_wraps_round_robin() -> void:
	var lv = Level.load_file("res://levels/field_01.json")["level"]
	var n: int = lv.player_spawns.size()
	check_eq(lv.spawn_for(0), lv.player_spawns[0], "first spawn")
	check_eq(lv.spawn_for(n), lv.player_spawns[0], "wraps")

# ---- the same bad files must fail, with the same reasons, as in Python

func test_missing_file() -> void:
	var r = Level.load_file("res://levels/nope.json")
	check(r["level"] == null and "not found" in r["error"], "missing file: " + r["error"])

func test_bad_platform_type_is_refused() -> void:
	var data := {"width": 1000, "height": 500, "player_spawn": [100, 100], "ball_spawn": [200, 100],
			"platforms": [{"x": 0, "y": 0, "w": 10, "h": 10, "type": "Thin"}]}
	var r = Level.parse(data)
	check(r["level"] == null and "invalid platform type 'Thin'" in r["error"], r["error"])

func test_bad_yard_px_is_refused() -> void:
	for bad in [0, -5, true, "x"]:
		var data := {"width": 1000, "height": 500, "player_spawn": [1, 1], "ball_spawn": [2, 2], "platforms": [], "yard_px": bad}
		var r = Level.parse(data)
		check(r["level"] == null and "invalid yard_px" in r["error"], "yard_px=%s: %s" % [str(bad), r["error"]])

func test_missing_field_is_named() -> void:
	var r = Level.parse({"width": 1000, "height": 500, "platforms": [], "ball_spawn": [1, 1]})
	check(r["level"] == null and "player_spawn" in r["error"], r["error"])

func test_broken_json_is_reported(tmp := "user://broken.json") -> void:
	var f := FileAccess.open("user://broken.json", FileAccess.WRITE)
	f.store_string("{nope")
	f.close()
	var r = Level.load_file("user://broken.json")
	check(r["level"] == null and "not valid JSON" in r["error"], r["error"])

func test_level_survives_the_wire_round_trip() -> void:
	for stem in ["field_01", "field_05", "arena_01"]:
		var lv = Level.load_file("res://levels/%s.json" % stem)["level"]
		var sent: Dictionary = JSON.parse_string(JSON.stringify(lv.to_dict()))
		var back = Level.parse(sent)["level"]
		check(back != null, stem + " parses after the round trip")
		if back == null:
			continue
		check_eq(back.level_name, lv.level_name, stem + " name")
		check_eq(_boxes(back.solids), _boxes(lv.solids), stem + " solids")
		check_eq(_boxes(back.thin), _boxes(lv.thin), stem + " thin")
		check_eq(back.player_spawns, lv.player_spawns, stem + " spawns")
		check_eq(back.has_yard_px(), lv.has_yard_px(), stem + " yard_px")
