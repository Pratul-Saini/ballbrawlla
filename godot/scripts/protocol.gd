extends RefCounted
## Wire format: newline-delimited JSON over TCP, Nagle disabled (src/ballbrawlla/net/protocol.py). The same messages
## pass through the relay server for internet play, and are identical to the Python game's, so a Python and a Godot
## game can play each other.
##
##   client -> host  {"t":"hello","v":PROTOCOL_VERSION,"game":VERSION}
##                   {"t":"in","mx":-1|0|1,"v":-1|0|1,"j":0|1,"z":0|1,"x":0|1,"m":[x,y]|null,"mh":0|1,"mp":0|1,
##                    "b":0|1,"jh":0|1,"as":[x,y]|null}
##   host -> client  {"t":"welcome","id":pid,"level":{...},"tuning":{...}}   {"t":"reject","reason":str}
##                   {"t":"snap",...}   this client's view (view.gd)

const PROTOCOL_VERSION := 5
const DEFAULT_PORT := 50555
const MAX_OUTBOX := 1 << 20     # drop a peer that stops reading rather than buffer forever
const MAX_INBOX := 1 << 20

## A non-blocking, line-framed JSON message connection. Call poll() every frame, then receive()/send(); none block.
class Connection:
	var peer: StreamPeerTCP
	var closed := false
	var _in := PackedByteArray()
	var _out := PackedByteArray()

	func _init(p_peer: StreamPeerTCP) -> void:
		peer = p_peer
		peer.set_no_delay(true)

	func send(msg: Dictionary) -> void:
		if closed:
			return
		_out.append_array((JSON.stringify(msg) + "\n").to_utf8_buffer())
		if _out.size() > MAX_OUTBOX:
			close()
			return
		flush()

	## Push out what the socket will take. Called by send() and poll().
	func flush() -> void:
		if closed:
			return
		peer.poll()
		if peer.get_status() == StreamPeerTCP.STATUS_CONNECTING:
			return
		if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			close()
			return
		if _out.is_empty():
			return
		var r := peer.put_partial_data(_out)
		if r[0] != OK:
			close()
			return
		_out = _out.slice(int(r[1]))

	## Complete messages received since the last call. Garbage lines are skipped.
	func receive() -> Array:
		var msgs: Array = []
		if closed:
			return msgs
		peer.poll()
		var status := peer.get_status()
		if status == StreamPeerTCP.STATUS_CONNECTED:
			var avail := peer.get_available_bytes()
			if avail > 0:
				var r := peer.get_partial_data(avail)
				if r[0] == OK:
					_in.append_array(r[1])
				else:
					close()
			if _in.size() > MAX_INBOX:
				close()
		elif status != StreamPeerTCP.STATUS_CONNECTING:
			closed = true            # the peer went away; still hand back what it sent before it did
		while true:
			var nl := _in.find(10)
			if nl < 0:
				break
			var line := _in.slice(0, nl)
			_in = _in.slice(nl + 1)
			if line.size() == 0:
				continue
			var parsed = JSON.parse_string(line.get_string_from_utf8())
			if typeof(parsed) == TYPE_DICTIONARY:
				msgs.append(parsed)
		return msgs

	func close() -> void:
		closed = true
		if peer != null:
			peer.disconnect_from_host()

## An Intent as the "in" message.
static func intent_to_msg(i) -> Dictionary:
	return {
		"t": "in", "mx": i.move_x, "v": i.vertical, "j": int(i.jump_pressed), "z": int(i.z_pressed), "x": int(i.x_pressed),
		"m": null if i.mouse == null else [snappedf(i.mouse[0], 0.1), snappedf(i.mouse[1], 0.1)],
		"mh": int(i.mouse_held), "mp": int(i.mouse_pressed), "b": int(i.button_pressed), "jh": int(i.jump_held),
		"as": null if i.aim_stick == null else [snappedf(i.aim_stick[0], 0.001), snappedf(i.aim_stick[1], 0.001)],
	}

## This machine's LAN address (best guess): the first private IPv4 address that isn't loopback.
static func lan_ip() -> String:
	var best := ""
	for a in IP.get_local_addresses():
		if a.contains(":") or a.begins_with("127.") or a.begins_with("169.254."):
			continue
		if a.begins_with("192.168.") or a.begins_with("10.") or (a.begins_with("172.") and _is_172_private(a)):
			return a
		if best == "":
			best = a
	return best if best != "" else "127.0.0.1"

static func _is_172_private(a: String) -> bool:
	var parts := a.split(".")
	return parts.size() == 4 and int(parts[1]) >= 16 and int(parts[1]) <= 31
