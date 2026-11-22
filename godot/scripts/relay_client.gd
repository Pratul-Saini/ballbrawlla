extends RefCounted
## The game's side of the relay server (src/ballbrawlla/net/invite.py): a host opens a room and gets an invite code; a
## friend dials that code. The relay joins the two connections and then only passes bytes, so the normal game protocol
## runs over it unchanged. Everything here is asynchronous: call poll() every frame.
##
##   host control  -> {"t":"open","v":1}   <- {"t":"room","code":"KQ7M3X","key":hex} | {"t":"error","reason":str}
##                 <- {"t":"incoming","n":7}          a joiner is waiting for slot n
##                 -> {"t":"ping"}                    every PING_INTERVAL
##   host data     -> {"t":"accept","code":..,"key":..,"n":7}   then raw bytes
##   joiner        -> {"t":"join","v":1,"code":"KQ7M3X"}   <- {"t":"ok"} then raw bytes | {"t":"error","reason":str}

const Protocol = preload("res://scripts/protocol.gd")
const Invite = preload("res://scripts/invite.gd")

const RELAY_VERSION := 1
const PING_INTERVAL := 10.0
const MAX_LINE := 1024

static func _line(msg: Dictionary) -> PackedByteArray:
	return (JSON.stringify(msg) + "\n").to_utf8_buffer()

## Read from `peer` until one newline-terminated JSON line has arrived. Returns {"done": bool, "msg": Dictionary,
## "rest": PackedByteArray, "error": String}. `buf` is the caller's accumulator.
static func _read_line(peer: StreamPeerTCP, buf: PackedByteArray) -> Dictionary:
	var avail := peer.get_available_bytes()
	if avail > 0:
		var r := peer.get_partial_data(avail)
		if r[0] == OK:
			buf.append_array(r[1])
	var nl := buf.find(10)
	if nl < 0:
		if buf.size() > MAX_LINE:
			return {"done": true, "error": "the relay server sent something unexpected", "buf": buf}
		return {"done": false, "buf": buf}
	var parsed = JSON.parse_string(buf.slice(0, nl).get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		return {"done": true, "error": "the relay server sent something unexpected", "buf": buf}
	return {"done": true, "msg": parsed, "rest": buf.slice(nl + 1), "error": "", "buf": buf}

# ------------------------------------------------------------ host side

## A room on the relay, held open by a control connection. Poll it every frame: it returns sockets to new joiners,
## already joined through the relay, ready for the game handshake.
class RelayRoom:
	var relay: Array
	var code := ""
	var error := ""
	var ready := false
	var _key := ""
	var _ctrl: StreamPeerTCP
	var _buf := PackedByteArray()
	var _sent_open := false
	var _deadline := 0.0
	var _last_ping := 0.0
	var _accepting: Array = []     # [peer, n, sent]

	func _init(p_relay: Array, timeout: float = 5.0) -> void:
		relay = p_relay
		_ctrl = StreamPeerTCP.new()
		if _ctrl.connect_to_host(relay[0], int(relay[1])) != OK:
			error = "Could not reach the relay server at %s:%d (the address can't be used)." % [relay[0], relay[1]]
		_deadline = Time.get_ticks_msec() / 1000.0 + timeout

	func display_code() -> String:
		return Invite.format_code(code)

	## The relay dropped the room: the current game goes on, but nobody new can join.
	func lost() -> bool:
		return ready and _ctrl.get_status() != StreamPeerTCP.STATUS_CONNECTED

	func poll() -> Array:
		var Self = load("res://scripts/relay_client.gd")
		var socks: Array = []
		if error != "":
			return socks
		var now := Time.get_ticks_msec() / 1000.0
		_ctrl.poll()
		var st := _ctrl.get_status()
		if not ready:
			if st == StreamPeerTCP.STATUS_ERROR or st == StreamPeerTCP.STATUS_NONE:
				error = "Could not reach the relay server at %s:%d." % [relay[0], relay[1]]
			elif st == StreamPeerTCP.STATUS_CONNECTED:
				if not _sent_open:
					_ctrl.put_data(Self._line({"t": "open", "v": RELAY_VERSION}))
					_sent_open = true
				var r: Dictionary = Self._read_line(_ctrl, _buf)
				_buf = r["buf"]
				if r["done"]:
					if r["error"] != "":
						error = "Could not open a game on the relay server: %s" % r["error"]
					elif r["msg"].get("t") != "room":
						error = "The relay server refused: %s." % str(r["msg"].get("reason", "unknown reason"))
					else:
						code = str(r["msg"]["code"])
						_key = str(r["msg"]["key"])
						ready = true
						_last_ping = now
						_buf = r["rest"]
			if not ready and error == "" and now > _deadline:
				error = "Could not open a game on the relay server: it didn't answer in time"
			return socks
		if st == StreamPeerTCP.STATUS_CONNECTED:
			if now - _last_ping >= PING_INTERVAL:
				_last_ping = now
				_ctrl.put_data(Self._line({"t": "ping"}))
			var avail := _ctrl.get_available_bytes()
			if avail > 0:
				var rr := _ctrl.get_partial_data(avail)
				if rr[0] == OK:
					_buf.append_array(rr[1])
			while true:
				var nl := _buf.find(10)
				if nl < 0:
					break
				var parsed = JSON.parse_string(_buf.slice(0, nl).get_string_from_utf8())
				_buf = _buf.slice(nl + 1)
				if typeof(parsed) == TYPE_DICTIONARY and parsed.get("t") == "incoming" and typeof(parsed.get("n")) in [TYPE_INT, TYPE_FLOAT]:
					var p := StreamPeerTCP.new()
					if p.connect_to_host(relay[0], int(relay[1])) == OK:
						_accepting.append([p, int(parsed["n"]), false, now])
		# Open the data connection for each waiting joiner, and hand it over once the accept line is sent.
		for a in _accepting.duplicate():
			var p: StreamPeerTCP = a[0]
			p.poll()
			var s := p.get_status()
			if s == StreamPeerTCP.STATUS_CONNECTED:
				p.put_data(Self._line({"t": "accept", "code": code, "key": _key, "n": a[1]}))
				_accepting.erase(a)
				socks.append(p)
			elif s == StreamPeerTCP.STATUS_ERROR or s == StreamPeerTCP.STATUS_NONE or now - a[3] > 3.0:
				_accepting.erase(a)
		return socks

	func close() -> void:
		if _ctrl != null:
			_ctrl.disconnect_from_host()
		for a in _accepting:
			a[0].disconnect_from_host()
		_accepting.clear()

# ------------------------------------------------------------ joiner side

## Join the room with this code. Poll every frame until `state` is DONE or FAILED. On DONE, `peer` leads to the host
## and `rest` holds any game bytes that arrived right behind the relay's reply.
class Dial:
	enum { CONNECTING, DONE, FAILED }
	var state := CONNECTING
	var error := ""
	var peer: StreamPeerTCP
	var rest := PackedByteArray()
	var _code := ""
	var _relay: Array
	var _buf := PackedByteArray()
	var _sent := false
	var _deadline := 0.0

	func _init(p_relay: Array, p_code: String, timeout: float = 10.0) -> void:
		_relay = p_relay
		_code = Invite.normalize_code(p_code)
		peer = StreamPeerTCP.new()
		if peer.connect_to_host(_relay[0], int(_relay[1])) != OK:
			state = FAILED
			error = "Could not reach the relay server at %s:%d (the address can't be used)." % [_relay[0], _relay[1]]
		_deadline = Time.get_ticks_msec() / 1000.0 + timeout

	func poll() -> void:
		if state != CONNECTING:
			return
		var Self = load("res://scripts/relay_client.gd")
		peer.poll()
		var st := peer.get_status()
		if st == StreamPeerTCP.STATUS_ERROR or st == StreamPeerTCP.STATUS_NONE:
			_fail("Could not reach the relay server at %s:%d." % [_relay[0], _relay[1]])
			return
		if st == StreamPeerTCP.STATUS_CONNECTED:
			if not _sent:
				peer.put_data(Self._line({"t": "join", "v": RELAY_VERSION, "code": _code}))
				_sent = true
			var r: Dictionary = Self._read_line(peer, _buf)
			_buf = r["buf"]
			if r["done"]:
				if r["error"] != "":
					_fail("Could not join %s: %s." % [Invite.format_code(_code), r["error"]])
				elif r["msg"].get("t") != "ok":
					_fail("Could not join %s: %s." % [Invite.format_code(_code), str(r["msg"].get("reason", "unknown reason"))])
				else:
					rest = r["rest"]
					state = DONE
				return
		if Time.get_ticks_msec() / 1000.0 > _deadline:
			_fail("Could not reach the relay server at %s:%d (timed out)." % [_relay[0], _relay[1]])

	func _fail(why: String) -> void:
		state = FAILED
		error = why
		peer.disconnect_from_host()
