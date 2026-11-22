extends "res://tests/test_case.gd"
## The launch checks and invite-code helpers must give the same answers, word for word, as the Python game
## (data: tools/parity_launch.py).

const Launch = preload("res://scripts/launch.gd")
const Invite = preload("res://scripts/invite.gd")

func _data() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://tests/data/launch.json"))

func test_level_list_matches_python_order_and_details() -> void:
	var d := _data()
	var infos := Launch.list_levels()
	check_eq(infos.size(), d["levels"].size(), "number of levels")
	var keys := []
	for i in infos:
		keys.append(i.key)
	check_eq(keys, d["order"], "order: football fields first, then the rest")
	for k in mini(infos.size(), d["levels"].size()):
		var got = infos[k]
		var want: Dictionary = d["levels"][k]
		check_eq(got.key, want["key"], "key")
		check_eq(got.level_name, want["name"], got.key + " name")
		check_near(got.width, want["width"], 0.0, got.key + " width")
		check_near(got.height, want["height"], 0.0, got.key + " height")
		check_near(got.yard_px, want["yard_px"], 0.0, got.key + " yard_px")
		check_eq(got.platforms, int(want["platforms"]), got.key + " platforms")
		check_eq(got.thin, int(want["thin"]), got.key + " thin")
		check_eq(got.football, want["football"], got.key + " football")
		check_eq(got.summary(), want["summary"], got.key + " summary")

func test_every_mode_check_on_every_level_says_what_python_says() -> void:
	var d := _data()
	var infos := Launch.list_levels()
	var n := 0
	for k in infos.size():
		var want: Dictionary = d["levels"][k]["checks"]
		for mode in want:
			var got: String = Launch.check_level(mode, infos[k])
			check_eq(got, want[mode] if want[mode] != null else "", "%s / %s" % [infos[k].key, mode])
			n += 1
	check_eq(n, 15 * 8, "combinations checked")

func test_invite_codes_match_python() -> void:
	for c in _data()["codes"]:
		check_eq(Invite.normalize_code(c["in"]), c["normal"], "normalize %s" % c["in"])
		check_eq(Invite.format_code(c["in"]), c["format"], "format %s" % c["in"])
		check_eq(Invite.check_code(c["in"]), c["check"] if c["check"] != null else "", "check_code '%s'" % c["in"])

func test_relay_address_parsing_matches_python() -> void:
	for r in _data()["relays"]:
		if r["in"].strip_edges() == "" and OS.get_environment(Invite.RELAY_ENV) != "":
			continue    # an empty override falls back to the environment, which this machine has set
		var got = Invite.relay_address(r["in"])
		if r["addr"] == null:
			check(got == null, "relay_address '%s' should be unset" % r["in"])
		elif got == null:
			failures.append("relay_address '%s' is unset, expected %s" % [r["in"], str(r["addr"])])
		else:
			check_eq(got[0], r["addr"][0], "relay host for '%s'" % r["in"])
			check_eq(got[1], int(r["addr"][1]), "relay port for '%s'" % r["in"])
		if r["addr"] != null:
			check_eq(Invite.check_relay(r["in"]), "", "check_relay accepts '%s'" % r["in"])
		else:
			check("No relay server is set" in Invite.check_relay(r["in"]), "check_relay explains the problem")

func test_address_and_port_checks_match_python() -> void:
	var d := _data()
	for a in d["addresses"]:
		check_eq(Launch.check_address(a["in"]), a["check"] if a["check"] != null else "", "address '%s'" % a["in"])
	for p in d["ports"]:
		check_eq(Launch.check_port_number(int(p["in"])), p["check"] if p["check"] != null else "", "port %s" % str(p["in"]))
	check_near(Launch.expected_field_width(-1.0), d["expected_width"], 0.0, "expected field width")

func test_check_launch_on_real_files_and_a_busy_port() -> void:
	check_eq(Launch.check_launch("practice", "res://levels/field_01.json"), "", "a football field in practice")
	check_eq(Launch.check_launch("sandbox", "res://levels/arena_01.json"), "", "the arena in free play")
	check("football field" in Launch.check_launch("practice", "res://levels/arena_01.json"), "arena refused for a match")
	check("not found" in Launch.check_launch("practice", "res://levels/field_99.json"), "missing level")
	check("Type the host's IP" in Launch.check_launch("join", "", 50555, ""), "join needs an address")
	check_eq(Launch.check_launch("join", "", 50555, "10.0.0.5"), "", "join with an address")
	check("Unknown mode" in Launch.check_launch("nonsense"), "unknown mode")
	var server := TCPServer.new()
	check_eq(server.listen(0, "127.0.0.1"), OK, "open a port to hold")
	var busy := server.get_local_port()
	# Hold a listener on 0.0.0.0 so the port is genuinely taken for the check.
	server.stop()
	var holder := TCPServer.new()
	check_eq(holder.listen(busy, "0.0.0.0"), OK, "hold the port")
	check("already in use" in Launch.check_port(busy), "a busy port is refused")
	holder.stop()
	check_eq(Launch.check_port(busy), "", "a free port is accepted")

func test_menu_animation_flight_path_matches_python() -> void:
	const Anim = preload("res://scripts/menu_anim.gd")
	var poses: Array = _data()["poses"]
	check(poses.size() >= 80, "poses recorded")
	for p in poses:
		var got: Dictionary = Anim.pose(p["t"], p["width"])
		var where := "t=%s width=%s" % [str(p["t"]), str(p["width"])]
		check_eq(got["phase"], p["phase"], where + " phase")
		check_eq(got["direction"], int(p["direction"]), where + " direction")
		for k in ["x", "y", "angle", "receiver_lift", "thrower_lean"]:
			check_near(got[k], p[k], 1e-9, "%s %s" % [where, k])
