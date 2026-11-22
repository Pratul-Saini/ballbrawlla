extends RefCounted
## Client side: connects to a host, sends Intents, receives snapshots (src/ballbrawlla/net/client.py).
## The handshake is asynchronous: call poll() every frame until state is READY or FAILED, so a window never freezes
## while it waits. `error` explains a failure in plain language.

const Protocol = preload("res://scripts/protocol.gd")
const Version = preload("res://scripts/version.gd")

enum { CONNECTING, WAITING, READY, FAILED }

var state := CONNECTING
var error := ""
var conn
var pid := -1
var level_data: Dictionary = {}
var tuning_data: Dictionary = {}
var address := ""
var port := 0
var _latest = null
var _deadline := 0.0
var _sent_hello := false

## Connect to a host directly (LAN or a typed address).
static func connect_to(p_address: String, p_port: int = Protocol.DEFAULT_PORT, timeout: float = 5.0):
	var c = load("res://scripts/client.gd").new()
	c.address = p_address
	c.port = p_port
	var peer := StreamPeerTCP.new()
	if peer.connect_to_host(p_address, p_port) != OK:
		c.state = FAILED
		c.error = "could not reach %s:%d (the address can't be used)" % [p_address, p_port]
		return c
	c.conn = Protocol.Connection.new(peer)
	c._deadline = Time.get_ticks_msec() / 1000.0 + timeout
	return c

## Use a socket that already leads to a host (through the relay). `leftover` holds bytes read past the relay's reply.
static func from_peer(peer: StreamPeerTCP, leftover: PackedByteArray = PackedByteArray(), timeout: float = 5.0):
	var c = load("res://scripts/client.gd").new()
	c.conn = Protocol.Connection.new(peer)
	c.conn._in.append_array(leftover)
	c._deadline = Time.get_ticks_msec() / 1000.0 + timeout
	return c

func closed() -> bool:
	return conn == null or conn.closed

func poll() -> void:
	if state == READY or state == FAILED:
		return
	var now := Time.get_ticks_msec() / 1000.0
	conn.peer.poll()
	var status: int = conn.peer.get_status()
	if status == StreamPeerTCP.STATUS_ERROR or (status == StreamPeerTCP.STATUS_NONE and not conn.closed):
		_fail("could not reach %s:%d" % [address, port])
		return
	if status == StreamPeerTCP.STATUS_CONNECTED and not _sent_hello:
		conn.send({"t": "hello", "v": Protocol.PROTOCOL_VERSION, "game": Version.VERSION})
		_sent_hello = true
		state = WAITING
	if _sent_hello:
		for msg in conn.receive():
			var kind = msg.get("t")
			if kind == "reject":
				conn.close()
				_fail("host refused: %s" % str(msg.get("reason")))
				return
			if kind == "welcome":
				pid = int(msg["id"])
				level_data = msg["level"]
				tuning_data = msg["tuning"]
				state = READY
			elif kind == "snap":
				_latest = msg
		if state == READY:
			return
		if conn.closed:
			_fail("host closed the connection during handshake")
			return
	if now > _deadline:
		conn.close()
		_fail("timed out waiting for host" if _sent_hello else "could not reach %s:%d (timed out)" % [address, port])

func _fail(why: String) -> void:
	state = FAILED
	error = why

func send_intent(intent) -> void:
	conn.send(Protocol.intent_to_msg(intent))

## The newest snapshot received since the last call, or null.
func latest_snapshot():
	for msg in conn.receive():
		if msg.get("t") == "snap":
			_latest = msg
	var s = _latest
	_latest = null
	return s

func close() -> void:
	if conn != null:
		conn.close()
