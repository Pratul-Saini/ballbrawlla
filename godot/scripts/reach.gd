extends RefCounted
## How a hosted game becomes reachable (src/ballbrawlla/net/online.py and net/upnp.py). Works out the one invite code
## to show and says, in words, who can join:
##
##     relay server set         open a room on it            -> relay code, "Internet: ready"
##     otherwise (or it fails)   ask the router to open the port (UPnP, in a thread)
##         router opened it                                  -> address code of the public IP, "Internet: ready"
##         router can't                                      -> address code of the LAN IP, "Internet: not available
##                                                              because ..." (same Wi-Fi still works)
##
## Poll it every frame. A relay room is handed to the Host straight away (`room`); if it fails, `room` goes back to
## null and the router is asked instead.

const Invite = preload("res://scripts/invite.gd")
const RelayClient = preload("res://scripts/relay_client.gd")
const Protocol = preload("res://scripts/protocol.gd")

const CHECKING := "checking"
const READY := "ready"
const UNAVAILABLE := "unavailable"
const DESCRIPTION := "Gridiron Scramble"
const LEASE := 3600          # seconds; renewed every RENEW while hosting, so a crash doesn't leave it open for long
const RENEW := 1500.0
const FIX := ("To fix it, turn on UPnP in your router's settings, or forward TCP port %d to %s. "
		+ "Players on the same Wi-Fi can join either way.")

var port: int
var lan_ip: String
var use_router := true
var room = null               # RelayRoom while it opens and once it is open; null without a relay
var relay_error := ""
var router_state := ""        # "" (not asked), "checking", "open", "failed"
var public_ip := ""
var router_reason := ""
var done := false             # the relay/router question is settled
var _upnp = null
var _thread: Thread = null
var _result := {}
var _mutex := Mutex.new()
var _last_map := 0.0

func _init(p_port: int, p_lan_ip: String, relay = null, p_use_router: bool = true) -> void:
	port = p_port
	lan_ip = p_lan_ip
	use_router = p_use_router
	if relay != null:
		room = RelayClient.RelayRoom.new(relay)
	else:
		_start_router()

func _start_router() -> void:
	if not use_router or port != Protocol.DEFAULT_PORT:
		done = true
		return
	router_state = CHECKING
	_thread = Thread.new()
	_thread.start(_router_work)

## Runs in the thread: never touches anything but _result.
func _router_work() -> void:
	var res := {}
	if lan_ip.begins_with("127."):
		res = {"state": "failed", "why": "This computer isn't connected to a network."}
	else:
		var u := UPNP.new()
		var err := u.discover(2500, 2, "InternetGatewayDevice")
		var gw = u.get_gateway() if err == UPNP.UPNP_RESULT_SUCCESS else null
		if gw == null or not gw.is_valid_gateway():
			res = {"state": "failed", "why": "Your router didn't answer the request to open a port (UPnP is off, or not supported)."}
		else:
			var ext := u.query_external_address()
			if ext == "":
				res = {"state": "failed", "why": "Your router didn't say what its internet address is."}
			elif not is_public(ext):
				res = {"state": "failed", "why": ("Your router is behind another router, or your internet provider "
						+ "shares one address between many homes, so players elsewhere can't reach this computer.")}
			else:
				var r := u.add_port_mapping(port, port, DESCRIPTION, "TCP", LEASE)
				if r == UPNP.UPNP_RESULT_ONLY_PERMANENT_LEASE_SUPPORTED:
					r = u.add_port_mapping(port, port, DESCRIPTION, "TCP", 0)
				if r == UPNP.UPNP_RESULT_SUCCESS:
					res = {"state": "open", "ip": ext, "upnp": u}
				elif r == UPNP.UPNP_RESULT_CONFLICT_WITH_OTHER_MAPPING:
					res = {"state": "failed", "why": "Your router already gives port %d to another computer on your network." % port}
				else:
					res = {"state": "failed", "why": "Your router refused to open port %d (error %d)." % [port, r]}
	_mutex.lock()
	_result = res
	_mutex.unlock()

func _renew_work() -> void:
	if _upnp != null:
		_upnp.add_port_mapping(port, port, DESCRIPTION, "TCP", LEASE)

## Call every frame (after the Host polled the room).
func poll() -> void:
	var now := Time.get_ticks_msec() / 1000.0
	if room != null and not done:
		if not room.ready and room.error == "":
			room.poll()                  # until it opens (no joiners yet); after that the Host polls it
		if room.ready:
			done = true
		elif room.error != "":
			relay_error = room.error
			room.close()
			room = null
			_start_router()
	if _thread != null and router_state == CHECKING:
		_mutex.lock()
		var res := _result
		_mutex.unlock()
		if not res.is_empty():
			_thread.wait_to_finish()
			_thread = null
			if res["state"] == "open":
				router_state = "open"
				public_ip = res["ip"]
				_upnp = res["upnp"]
				_last_map = now
			else:
				router_state = "failed"
				router_reason = "%s %s" % [res["why"], FIX % [port, lan_ip]]
			done = true
	elif router_state == "open" and now - _last_map > RENEW:
		_last_map = now
		if _thread != null and not _thread.is_alive():
			_thread.wait_to_finish()
			_thread = null
		if _thread == null:
			_thread = Thread.new()
			_thread.start(_renew_work)

# ---- what to show

## The invite code to share (bare), or "" while it's still being worked out.
func code() -> String:
	if room != null and room.ready:
		return room.code
	if not done or port != Protocol.DEFAULT_PORT:
		return ""
	if router_state == "open":
		return Invite.address_code(public_ip)
	return Invite.address_code(lan_ip)

## Every code that leads here, for the LAN beacon: the shown one, and the LAN address code.
func codes() -> Array:
	var out: Array = []
	for c in [code(), Invite.address_code(lan_ip) if port == Protocol.DEFAULT_PORT else ""]:
		if c != "" and not out.has(c):
			out.append(c)
	return out

## [label, text, state]
func internet() -> Array:
	if room != null and room.ready:
		if room.lost():
			return ["Internet", "lost the relay server: only players on your Wi-Fi can join now", UNAVAILABLE]
		return ["Internet", "ready (through the relay server)", READY]
	if not done:
		return ["Internet", "asking your router to open the game's port...", CHECKING]
	if router_state == "open":
		return ["Internet", "ready: your router opened the game's port", READY]
	if router_state == "failed":
		return ["Internet", "not available. %s" % router_reason, UNAVAILABLE]
	if port != Protocol.DEFAULT_PORT:
		return ["Internet", "not set up (port %d isn't the standard one)" % port, UNAVAILABLE]
	return ["Internet", "not available (automatic port opening is off)", UNAVAILABLE]

func lines() -> Array:
	var lan: Array
	if port == Protocol.DEFAULT_PORT:
		lan = ["Same Wi-Fi", "ready: they pick your game in Join game, or type the code", READY]
	else:
		lan = ["Same Wi-Fi", "ready: they join %s:%d" % [lan_ip, port], READY]
	return [lan, internet()]

func close() -> void:
	if _thread != null:
		_thread.wait_to_finish()      # at most the router search (2.5 s)
		_thread = null
	if room != null:
		room.close()
	if router_state == "open" and _upnp != null:
		_upnp.delete_port_mapping(port, "TCP")
		router_state = "closed"

# ---- helpers

static func _in(ip: int, net: String, bits: int) -> bool:
	var base := _ip_int(net)
	var mask := ((1 << 32) - 1) ^ ((1 << (32 - bits)) - 1)
	return (ip & mask) == (base & mask)

static func _ip_int(ip: String) -> int:
	var parts := ip.split(".")
	if parts.size() != 4:
		return -1
	var v := 0
	for p in parts:
		if not p.is_valid_int() or int(p) < 0 or int(p) > 255:
			return -1
		v = v * 256 + int(p)
	return v

## A public internet address (the same answer as Python's ipaddress checks in net/upnp.py).
static func is_public(ip: String) -> bool:
	var v := _ip_int(ip)
	if v < 0:
		return false
	if v == _ip_int("192.0.0.9") or v == _ip_int("192.0.0.10"):
		return true
	for n in [["0.0.0.0", 8], ["10.0.0.0", 8], ["100.64.0.0", 10], ["127.0.0.0", 8], ["169.254.0.0", 16],
			["172.16.0.0", 12], ["192.0.0.0", 24], ["192.0.2.0", 24], ["192.168.0.0", 16], ["198.18.0.0", 15],
			["198.51.100.0", 24], ["203.0.113.0", 24], ["240.0.0.0", 4], ["255.255.255.255", 32]]:
		if _in(v, n[0], n[1]):
			return false
	return true
