extends "res://tests/test_case.gd"
## The host's invite code and internet status (reach.gd), and beacons that carry codes (mirrors tests/test_online.py).

const Reach = preload("res://scripts/reach.gd")
const Invite = preload("res://scripts/invite.gd")
const Discovery = preload("res://scripts/discovery.gd")

func test_without_the_router_the_code_is_the_lan_address() -> void:
	var r = Reach.new(50555, "192.168.1.20", null, false)
	r.poll()
	check(r.done, "nothing to wait for")
	check_eq(r.code(), Invite.address_code("192.168.1.20"))
	var lines: Array = r.lines()
	check_eq(lines[0][2], Reach.READY, "same Wi-Fi works")
	check_eq(lines[1][2], Reach.UNAVAILABLE, "internet doesn't")
	r.close()

func test_router_results_turn_into_a_code_and_words() -> void:
	var r = Reach.new(50555, "192.168.1.20", null, false)
	r.router_state = "open"
	r.public_ip = "93.184.216.34"
	check_eq(r.code(), Invite.address_code("93.184.216.34"), "the public address once the router opened the port")
	check_eq(r.codes(), [Invite.address_code("93.184.216.34"), Invite.address_code("192.168.1.20")], "both codes for the beacon")
	check_eq(r.internet()[2], Reach.READY)
	r.router_state = "failed"
	r.router_reason = "Your router didn't answer. " + Reach.FIX % [50555, "192.168.1.20"]
	check_eq(r.code(), Invite.address_code("192.168.1.20"), "falls back to the LAN address")
	check("forward TCP port 50555 to 192.168.1.20" in r.internet()[1], r.internet()[1])

func test_a_non_standard_port_has_no_code() -> void:
	var r = Reach.new(50999, "192.168.1.20", null, true)
	r.poll()
	check(r.done and r.code() == "", "codes assume the standard port")
	check("50999" in r.lines()[0][1], "the LAN line gives the address instead")

func test_a_relay_that_cannot_be_reached_falls_back_to_the_router() -> void:
	var r = Reach.new(50555, "192.168.1.20", ["127.0.0.1", 1], false)
	for _k in 700:                  # a refused connection can take a few seconds to show on Windows
		r.poll()
		if r.done:
			break
		OS.delay_msec(10)
	check(r.done and r.room == null and r.relay_error != "", "relay failed: %s" % r.relay_error)
	check_eq(r.code(), Invite.address_code("192.168.1.20"))

func test_beacons_carry_codes() -> void:
	var g = Discovery.decode(Discovery.encode("Kris's game", "Field 05", 50555, ["KQ7M3XPA", "AB2CD3"]), "10.0.0.7")
	check_eq(g.codes, ["KQ7M3XPA", "AB2CD3"])
	var old = Discovery.decode(Discovery.encode("Old", "Field 01", 50555), "10.0.0.8")
	check_eq(old.codes, [], "an older beacon: no codes")
	var b := Discovery.Beacon.new("Kris's game", "Field 05", 50555, 1)
	b.set_codes(["KQ7M3XPA"])
	check_eq(Discovery.decode(b.packet, "10.0.0.7").codes, ["KQ7M3XPA"])
	b.close()
