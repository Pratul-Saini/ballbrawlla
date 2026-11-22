extends "res://tests/test_case.gd"
## Every number in the Godot Tuning must equal the Python game's. Data comes from tools/export_parity.py.

const Tuning = preload("res://scripts/tuning.gd")

func _python() -> Dictionary:
	var f := FileAccess.open("res://tests/data/tuning.json", FileAccess.READ)
	return JSON.parse_string(f.get_as_text())

func test_every_python_tuning_value_exists_and_matches() -> void:
	var t = Tuning.new()
	var py := _python()
	var checked := 0
	for key in py:
		if String(key).begins_with("_"):
			continue
		var found := false
		for p in t.get_property_list():
			if p.name == key:
				found = true
		if not found:
			failures.append("Godot Tuning is missing '%s'" % key)
			continue
		var mine = t.get(key)
		var theirs = py[key]
		if typeof(theirs) == TYPE_BOOL:
			check_eq(mine, theirs, key)
		else:
			check_near(float(mine), float(theirs), 1e-12, key)
		checked += 1
	check(checked >= 50, "only %d values were compared" % checked)

func test_godot_has_no_extra_values_python_lacks() -> void:
	var t = Tuning.new()
	var py := _python()
	for p in t.get_property_list():
		if p.usage & PROPERTY_USAGE_SCRIPT_VARIABLE and not py.has(p.name):
			failures.append("Godot Tuning has '%s' which Python does not" % p.name)

func test_derived_values_match() -> void:
	var t = Tuning.new()
	var d: Dictionary = _python()["_derived"]
	check_near(t.dt(), d["dt"], 1e-15, "dt")
	check_eq(t.pickup_buffer_ticks(), int(d["pickup_buffer_ticks"]), "pickup_buffer_ticks")
	check_eq(t.pickup_grace_ticks(), int(d["pickup_grace_ticks"]), "pickup_grace_ticks")

func test_dictionary_round_trip_through_json_keeps_types() -> void:
	var t = Tuning.new()
	var sent: Dictionary = JSON.parse_string(JSON.stringify(t.to_dict()))     # what a joiner receives
	var other = Tuning.new()
	other.physics_hz = 60
	other.slide_enabled = false
	other.player_gravity = 1.0
	other.apply_dict(sent)
	check_eq(other.physics_hz, 120, "int field")
	check_eq(typeof(other.physics_hz), TYPE_INT, "stays an int")
	check_eq(other.slide_enabled, true, "bool field")
	check_near(other.player_gravity, 2200.0, 0.0, "float field")
	check_eq(other.to_dict(), t.to_dict(), "everything survives")
