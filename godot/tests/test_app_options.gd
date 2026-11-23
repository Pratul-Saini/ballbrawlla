extends "res://tests/test_case.gd"
## The command-line options (mirrors the Python game's flags in src/ballbrawlla/main.py).

const App = preload("res://scripts/app.gd")

func _cfg(args: Array) -> Dictionary:
	var r := App.parse_options(PackedStringArray(args))
	check(r.has("config"), "expected a launch for %s, got %s" % [str(args), str(r)])
	return r.get("config", {})

func test_no_options_opens_the_launcher() -> void:
	check_eq(App.parse_options(PackedStringArray([])), {})
	check_eq(App.parse_options(PackedStringArray(["--smoke", "--autoplay"])), {}, "test hooks are not launch options")

func test_a_level_alone_is_practice() -> void:
	var c := _cfg(["--level=field_05"])
	check_eq(c["mode"], "practice")
	check_eq(c["level"], "res://levels/field_05.json")
	check_eq(c["port"], 50555)

func test_each_mode_flag_picks_its_mode_and_default_level() -> void:
	check_eq(_cfg(["--catch"])["mode"], "catch")
	check_eq(_cfg(["--local", "--level=field_09"])["level"], "res://levels/field_09.json")
	var s := _cfg(["--sandbox"])
	check(s["mode"] == "sandbox" and s["level"] == "res://levels/arena_01.json", "free play defaults to the arena")
	check_eq(_cfg(["--catch"])["level"], "res://levels/field_01.json", "a match defaults to field_01")

func test_hosting_and_joining() -> void:
	var h := _cfg(["--host", "--level=field_03", "--port=50999"])
	check(h["mode"] == "host" and h["port"] == 50999, str(h))
	var o := _cfg(["--host", "--online", "--relay=relay.example.com:50601", "--no-router"])
	check(o["mode"] == "host" and o["relay"] == "relay.example.com:50601" and o["no_router"], str(o))
	var j := _cfg(["--join=10.0.0.5"])
	check(j["mode"] == "join" and j["address"] == "10.0.0.5" and j["level"] == "", str(j))
	var c := _cfg(["--join-code=KQ7-M3X", "--relay=127.0.0.1"])
	check(c["mode"] == "join_code" and c["code"] == "KQ7-M3X" and c["relay"] == "127.0.0.1", str(c))

func test_conflicting_modes_and_bad_numbers_are_refused() -> void:
	check("only one" in App.parse_options(PackedStringArray(["--host", "--local"])).get("error", ""), "two modes")
	check("only one" in App.parse_options(PackedStringArray(["--join=1.2.3.4", "--catch"])).get("error", ""), "join and catch")
	check("number" in App.parse_options(PackedStringArray(["--host", "--port=abc"])).get("error", ""), "a port must be a number")

func test_a_level_given_as_a_path_or_with_an_extension_still_works() -> void:
	check_eq(_cfg(["--level=field_05.json"])["level"], "res://levels/field_05.json")
	check_eq(_cfg(["--level=some/where/field_07.json"])["level"], "res://levels/field_07.json")
