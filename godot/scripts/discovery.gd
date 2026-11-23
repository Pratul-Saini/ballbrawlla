extends RefCounted
## Find games on the local network without typing an IP address (src/ballbrawlla/net/discovery.py).
## A host runs a Beacon (a small UDP broadcast about once a second while it has a free seat); the join screen runs a
## Finder, which keeps the list of games heard recently. The packet format is identical to Python's.
## The address of a game is the sender of its packet, never a value the packet claims. A beacon also lists the game's
## invite codes, so a joiner who types a code connects directly when the game is on the same network.

const Protocol = preload("res://scripts/protocol.gd")
const Version = preload("res://scripts/version.gd")

const DISCOVERY_PORT := 50556
const MAGIC := "ballbrawlla-game"
const BEACON_INTERVAL := 1.0
const GAME_TIMEOUT := 3.5      # a game not heard from for this long is dropped from the list
const MAX_TEXT := 40

class FoundGame:
	var address := ""
	var port := 0
	var name := ""
	var level := ""
	var version := ""
	var codes: Array = []      # invite codes (bare) that lead to this game

static func _clean(value) -> String:
	var out := ""
	for ch in str(value):
		if ch.unicode_at(0) >= 32 and ch.unicode_at(0) != 127:
			out += ch
	return out.substr(0, MAX_TEXT).strip_edges()

static func encode(game_name: String, level: String, port: int, codes: Array = []) -> PackedByteArray:
	return JSON.stringify({"magic": MAGIC, "v": Protocol.PROTOCOL_VERSION, "game": Version.VERSION, "name": game_name,
			"level": level, "port": port, "codes": codes}).to_utf8_buffer()

## A FoundGame for a valid beacon packet, else null. Never fails on garbage.
static func decode(data: PackedByteArray, sender: String):
	var parsed = JSON.parse_string(data.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		return null
	if parsed.get("magic") != MAGIC or typeof(parsed.get("v")) != TYPE_FLOAT and typeof(parsed.get("v")) != TYPE_INT:
		return null
	if int(parsed["v"]) != Protocol.PROTOCOL_VERSION:
		return null
	var port = parsed.get("port")
	if typeof(port) != TYPE_INT and typeof(port) != TYPE_FLOAT:
		return null
	if float(port) != floorf(float(port)) or int(port) < 1024 or int(port) > 65535:
		return null
	var g := FoundGame.new()
	g.address = sender
	g.port = int(port)
	g.name = _clean(parsed.get("name", ""))
	if g.name == "":
		g.name = sender
	g.level = _clean(parsed.get("level", ""))
	g.version = _clean(parsed.get("game", ""))
	var raw = parsed.get("codes", [])
	if typeof(raw) == TYPE_ARRAY:
		for c in raw.slice(0, 4):
			if typeof(c) == TYPE_STRING:
				g.codes.append(_clean(c).to_upper())
	return g

## Advertises a hosted game. Call tick() every frame; it sends at most once per BEACON_INTERVAL.
class Beacon:
	var packet: PackedByteArray
	var discovery_port: int
	var codes: Array = []
	var _name := ""
	var _level := ""
	var _port := 0
	var _udp := PacketPeerUDP.new()
	var _last := -1000.0
	var _open := false

	func _init(game_name: String, level: String, port: int, p_discovery_port: int = 50556) -> void:
		_name = game_name
		_level = level
		_port = port
		packet = load("res://scripts/discovery.gd").encode(game_name, level, port)
		discovery_port = p_discovery_port
		_udp.set_broadcast_enabled(true)
		_open = true

	## Advertise these invite codes from the next beacon on.
	func set_codes(p_codes: Array) -> void:
		if p_codes != codes:
			codes = p_codes.duplicate()
			packet = load("res://scripts/discovery.gd").encode(_name, _level, _port, codes)
			_last = -1000.0         # tell the network now

	## Send a beacon if one is due and a seat is open. Returns true if a packet went out.
	func tick(open_seat: bool = true, now: float = -1.0) -> bool:
		if now < 0.0:
			now = Time.get_ticks_msec() / 1000.0
		if not _open or not open_seat or now - _last < BEACON_INTERVAL:
			return false
		_last = now
		# The broadcast address reaches other machines; loopback lets a second copy on this machine see it.
		for target in ["255.255.255.255", "127.0.0.1"]:
			_udp.set_dest_address(target, discovery_port)
			_udp.put_packet(packet)
		return true

	func close() -> void:
		_open = false
		_udp.close()

## Listens for beacons. Call poll() every frame to read what arrived and get the current list.
class Finder:
	var _udp := PacketPeerUDP.new()
	var _seen := {}     # "address:port" -> [FoundGame, last_heard]
	var available := false

	func _init(p_port: int = 50556) -> void:
		# Address reuse lets more than one game on this machine listen at once (the engine sets SO_REUSEADDR).
		available = _udp.bind(p_port, "0.0.0.0") == OK

	func poll(now: float = -1.0) -> Array:
		if now < 0.0:
			now = Time.get_ticks_msec() / 1000.0
		var Discovery = load("res://scripts/discovery.gd")
		while available and _udp.get_available_packet_count() > 0:
			var data := _udp.get_packet()
			var sender := _udp.get_packet_ip()
			var g = Discovery.decode(data, sender)
			if g != null:
				_seen["%s:%d" % [g.address, g.port]] = [g, now]
		var keep := {}
		for k in _seen:
			if now - _seen[k][1] <= GAME_TIMEOUT:
				keep[k] = _seen[k]
		_seen = keep
		var games: Array = []
		for k in _seen:
			games.append(_seen[k][0])
		# On the host's own machine the same beacon arrives from its LAN address and from loopback: show it once.
		var real := {}
		for g in games:
			if not g.address.begins_with("127."):
				real["%s|%s|%d" % [g.name, g.level, g.port]] = true
		games = games.filter(func(g): return not (g.address.begins_with("127.") and real.has("%s|%s|%d" % [g.name, g.level, g.port])))
		games.sort_custom(func(a, b):
			var an: String = a.name.to_lower()
			var bn: String = b.name.to_lower()
			if an != bn:
				return an < bn
			if a.address != b.address:
				return a.address < b.address
			return a.port < b.port)
		return games

	func close() -> void:
		available = false
		_udp.close()
