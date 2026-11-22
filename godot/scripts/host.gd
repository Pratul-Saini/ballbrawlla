extends RefCounted
## Host side: accepts clients, turns their input messages into Intents, and sends each client its view
## (src/ballbrawlla/net/host.py). The host's own player is slot 0; clients get 1..N-1. Everything is non-blocking and
## driven from the game loop (no threads). Clients can arrive directly (LAN) or through a relay room (internet).

const Protocol = preload("res://scripts/protocol.gd")
const Intent = preload("res://scripts/intent.gd")
const Version = preload("res://scripts/version.gd")

## Latest held keys from a client plus press edges accumulated since the last tick, so a press is never lost if two
## messages land in one tick.
class RemoteInput:
	var move_x := 0
	var vertical := 0
	var jump := false
	var z := false
	var x := false
	var mouse = null
	var mouse_held := false
	var mouse_pressed := false
	var button := false
	var jump_held := false
	var aim_stick = null

	func feed(msg: Dictionary) -> void:
		move_x = clampi(int(msg.get("mx", 0)), -1, 1)
		vertical = clampi(int(msg.get("v", 0)), -1, 1)
		jump = jump or bool(msg.get("j", 0))
		z = z or bool(msg.get("z", 0))
		x = x or bool(msg.get("x", 0))
		var m = msg.get("m")
		mouse = [float(m[0]), float(m[1])] if typeof(m) == TYPE_ARRAY and m.size() == 2 else null
		mouse_held = bool(msg.get("mh", 0))
		mouse_pressed = mouse_pressed or bool(msg.get("mp", 0))
		button = button or bool(msg.get("b", 0))
		jump_held = bool(msg.get("jh", 0))
		var a = msg.get("as")
		aim_stick = [float(a[0]), float(a[1])] if typeof(a) == TYPE_ARRAY and a.size() == 2 else null

	func consume():
		var i = Intent.new()
		i.move_x = move_x
		i.vertical = vertical
		i.jump_pressed = jump
		i.z_pressed = z
		i.x_pressed = x
		i.mouse = mouse
		i.mouse_held = mouse_held
		i.mouse_pressed = mouse_pressed
		i.button_pressed = button
		i.jump_held = jump_held
		i.aim_stick = aim_stick
		jump = false
		z = false
		x = false
		mouse_pressed = false
		button = false
		return i

var welcome: Dictionary
var room = null                    # a RelayRoom, or null
var max_players: int
var listener := TCPServer.new()
var port := 0
var pending: Array = []            # Connection
var clients := {}                  # pid -> Connection
var inputs := {}                   # pid -> RemoteInput

## {"host": Host or null, "error": String}. `welcome` holds the level and tuning sent to every joining client.
static func create(p_welcome: Dictionary, p_max_players: int, p_port: int = Protocol.DEFAULT_PORT,
		bind_address: String = "0.0.0.0", p_room = null) -> Dictionary:
	var h = load("res://scripts/host.gd").new()
	h.welcome = p_welcome
	h.max_players = p_max_players
	h.room = p_room
	var err: int = h.listener.listen(p_port, bind_address)
	if err != OK:
		return {"host": null, "error": "Port %d is already in use. Close the other game, or pick a different port." % p_port}
	h.port = h.listener.get_local_port()
	return {"host": h, "error": ""}

func _free_slot() -> int:
	for pid in range(1, max_players):
		if not clients.has(pid):
			return pid
	return -1

## Accept, handshake, read. Returns {"joined": [pid...], "left": [pid...]} since the last poll.
func poll() -> Dictionary:
	var joined: Array = []
	var left: Array = []
	while listener.is_connection_available():
		pending.append(Protocol.Connection.new(listener.take_connection()))
	if room != null:
		for peer in room.poll():
			pending.append(Protocol.Connection.new(peer))
	for conn in pending.duplicate():
		var handled := false
		for msg in conn.receive():
			if msg.get("t") != "hello":
				continue
			pending.erase(conn)
			handled = true
			var pid := _free_slot()
			if int(msg.get("v", -1)) != Protocol.PROTOCOL_VERSION:
				var theirs := str(msg.get("game", "")).substr(0, 20)
				if theirs == "":
					theirs = "an older version"
				conn.send({"t": "reject", "reason": "version mismatch: the host has %s and you have %s. " % [Version.VERSION, theirs]
						+ "Both players need the same version, so ask for the latest build."})
				conn.close()
			elif pid < 0:
				conn.send({"t": "reject", "reason": "game is full"})
				conn.close()
			else:
				var w := {"t": "welcome", "id": pid}
				w.merge(welcome)
				conn.send(w)
				clients[pid] = conn
				inputs[pid] = RemoteInput.new()
				joined.append(pid)
			break
		if not handled and conn.closed:
			pending.erase(conn)
	for pid in clients.keys():
		var conn = clients[pid]
		for msg in conn.receive():
			if msg.get("t") == "in":
				inputs[pid].feed(msg)
		conn.flush()
		if conn.closed:
			clients.erase(pid)
			inputs.erase(pid)
			left.append(pid)
	return {"joined": joined, "left": left}

func intent_for(pid: int):
	return inputs[pid].consume() if inputs.has(pid) else Intent.new()

func send_to(pid: int, msg: Dictionary) -> void:
	if clients.has(pid):
		clients[pid].send(msg)

func broadcast(msg: Dictionary) -> void:
	for pid in clients:
		clients[pid].send(msg)

func close() -> void:
	for c in pending:
		c.close()
	for pid in clients:
		clients[pid].close()
	pending.clear()
	clients.clear()
	listener.stop()
	if room != null:
		room.close()
