extends SceneTree
## A headless network probe used by the interop tests (tools/interop_test.py):
##   Godot --headless --path godot -s res://tools/net_probe.gd -- join HOST PORT
##       Joins a game (Python's or this port's), sends a few inputs, prints what it received.
##   Godot --headless --path godot -s res://tools/net_probe.gd -- host PORT LEVEL SECONDS [RELAY]
##       Hosts a one-human-plus-one-remote game, prints who joined and what the remote's inputs did. With RELAY
##       (host or host:port) it also opens an invite-code room there and prints the code.
##   ... -- joincode RELAY CODE      Joins through the relay with an invite code.
##   ... -- discover SECONDS         Prints every game heard on the discovery port.
##   ... -- beacon SECONDS NAME PORT Advertises a game for that long.

const Protocol = preload("res://scripts/protocol.gd")
const Client = preload("res://scripts/client.gd")
const Host = preload("res://scripts/host.gd")
const Intent = preload("res://scripts/intent.gd")
const Level = preload("res://scripts/level.gd")
const Tuning = preload("res://scripts/tuning.gd")
const Session = preload("res://scripts/session.gd")
const View = preload("res://scripts/view.gd")
const RelayClient = preload("res://scripts/relay_client.gd")
const Invite = preload("res://scripts/invite.gd")
const Discovery = preload("res://scripts/discovery.gd")

var _mode := ""
var _client
var _host
var _session
var _t0 := 0.0
var _snaps := 0
var _last_view := {}
var _seconds := 6.0
var _ticks_accum := 0.0
var _joined_pid := -1
var _remote_moves := 0
var _room
var _dial
var _finder
var _beacon
var _heard := {}
var _printed_code := false

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	_mode = args[0]
	_t0 = Time.get_ticks_msec() / 1000.0
	if _mode == "join":
		_client = Client.connect_to(args[1], int(args[2]))
	elif _mode == "joincode":
		_dial = RelayClient.Dial.new(Invite.relay_address(args[1]), args[2])
		_mode = "join"
		_client = null
	elif _mode == "discover":
		_seconds = float(args[1])
		_finder = Discovery.Finder.new()
		print("PROBE finder available=", _finder.available)
	elif _mode == "beacon":
		_seconds = float(args[1])
		_beacon = Discovery.Beacon.new(args[2], "Caverns", int(args[3]))
	elif _mode == "host":
		var t = Tuning.new()
		var lv = Level.load_file("res://levels/%s.json" % args[2])["level"]
		_seconds = float(args[3])
		if args.size() > 4:
			_room = RelayClient.RelayRoom.new(Invite.relay_address(args[4]))
		var h := Host.create({"level": lv.to_dict(), "tuning": t.to_dict()}, 2, int(args[1]), "0.0.0.0", _room)
		if h["host"] == null:
			print("PROBE host-failed: ", h["error"])
			quit(2)
			return
		_host = h["host"]
		_session = Session.create(lv, t, 2)["session"]
		print("PROBE listening on ", _host.port)

func _process(delta: float) -> bool:
	var now: float = Time.get_ticks_msec() / 1000.0 - _t0
	if now > _seconds + 15.0:
		print("PROBE gave-up: still running %.0f s past its deadline (a script error above is the likely cause)" % (now - _seconds))
		quit(9)
		return true
	if _mode == "discover":
		for g in _finder.poll():
			var key := "%s:%d" % [g.address, g.port]
			if not _heard.has(key):
				_heard[key] = true
				print("PROBE heard name=%s level=%s port=%d version=%s from=%s" % [g.name, g.level, g.port, g.version, g.address])
		if now > _seconds:
			print("PROBE discover done: games=%d" % _heard.size())
			quit(0)
			return true
		return false
	if _mode == "beacon":
		_beacon.tick(true)
		if now > _seconds:
			print("PROBE beacon done")
			quit(0)
			return true
		return false
	if _mode == "join" and _client == null:
		_dial.poll()
		if _dial.state == RelayClient.Dial.FAILED:
			print("PROBE dial-failed: ", _dial.error)
			quit(4)
			return true
		if _dial.state == RelayClient.Dial.DONE:
			_client = Client.from_peer(_dial.peer, _dial.rest)
			_client.state = Client.CONNECTING
		return false
	if _mode == "join":
		_client.poll()
		if _client.state == Client.FAILED:
			print("PROBE join-failed: ", _client.error)
			quit(3)
			return true
		if _client.state == Client.READY:
			var i = Intent.new()
			i.move_x = 1
			i.jump_pressed = int(now * 2.0) % 2 == 0
			_client.send_intent(i)
			var s = _client.latest_snapshot()
			if s != null:
				_snaps += 1
				_last_view = s
		if now > _seconds:
			var lv = Level.parse(_client.level_data)
			print("PROBE joined pid=%d level=%s level_ok=%s snaps=%d phase=%s you=%s side=%s tick=%s" % [
					_client.pid, str(_client.level_data.get("name")), str(lv["level"] != null), _snaps,
					str(_last_view.get("phase")), str(_last_view.get("you")), str(_last_view.get("side")), str(_last_view.get("tick"))])
			var t = Tuning.new()
			t.apply_dict(_client.tuning_data)
			print("PROBE tuning jump_speed=%s hz=%s" % [str(t.jump_speed), str(t.physics_hz)])
			quit(0)
			return true
	else:
		if _room != null and _room.ready and not _printed_code:
			_printed_code = true
			print("PROBE invite code ", _room.code)
		if _room != null and _room.error != "" and not _printed_code:
			_printed_code = true
			print("PROBE room-error: ", _room.error)
		var r: Dictionary = _host.poll()
		for pid in r["joined"]:
			_joined_pid = pid
			_session.set_connected(pid, true)
			print("PROBE client joined as ", pid)
		for pid in r["left"]:
			_session.set_connected(pid, false)
			print("PROBE client left ", pid)
		_ticks_accum += delta
		var dt: float = _session.t.dt()
		while _ticks_accum >= dt:
			_ticks_accum -= dt
			var intents := [Intent.new(), _host.intent_for(1) if _joined_pid >= 0 else Intent.new()]
			if intents[1].move_x != 0:
				_remote_moves += 1
			_session.step(intents, dt)
			for pid in _host.clients:
				_host.send_to(pid, View.make_view(_session, pid))
		if now > _seconds:
			print("PROBE host done: remote_inputs_with_movement=%d phase=%s" % [_remote_moves, _session.phase])
			_host.close()
			quit(0)
			return true
	return false
