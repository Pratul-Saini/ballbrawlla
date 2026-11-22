extends RefCounted
## Invite codes and the relay address (src/ballbrawlla/net/invite.py). The relay connection itself lives in
## relay_client.gd; this file is the part the menu needs: what a valid code looks like, and where the relay is.

const RELAY_PORT := 50600
## The public relay everyone uses unless --relay or BALLBRAWLLA_RELAY says otherwise. Fill this in once a relay is
## deployed, e.g. "relay.example.com" or "203.0.113.5:50600".
const DEFAULT_RELAY := ""
const RELAY_ENV := "BALLBRAWLLA_RELAY"
const ALPHABET := "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L: easy to read out loud
const CODE_LEN := 6

## What a player typed -> the bare code: uppercase, without spaces or dashes.
static func normalize_code(text: String) -> String:
	var out := ""
	for ch in text.to_upper():
		if ch != " " and ch != "-" and ch != "\t":
			out += ch
	return out

static func format_code(code: String) -> String:
	var c := normalize_code(code)
	if c.length() == CODE_LEN:
		return "%s-%s" % [c.substr(0, 3), c.substr(3)]
	return c

## Why this isn't a valid invite code, or "" when it is.
static func check_code(text: String) -> String:
	var code := normalize_code(text)
	if code == "":
		return "Type the invite code the host gave you (like KQ7-M3X)."
	var bad: Array = []
	for ch in code:
		if ALPHABET.find(ch) < 0 and not bad.has(ch):
			bad.append(ch)
	bad.sort()
	if not bad.is_empty():
		var hint := ""
		for ch in bad:
			if "0O1IL".find(ch) >= 0:
				hint = " Codes never use 0, O, 1, I or L."
		return "An invite code can't contain %s.%s" % [", ".join(bad), hint]
	if code.length() != CODE_LEN:
		return "An invite code has %d characters (like KQ7-M3X); this one has %d." % [CODE_LEN, code.length()]
	return ""

## Where the relay runs: `override` (--relay), else the environment variable, else DEFAULT_RELAY.
## Returns [host, port], or null when none is set.
static func relay_address(override: String = ""):
	var text := override
	if text.strip_edges() == "":
		text = OS.get_environment(RELAY_ENV)
	if text.strip_edges() == "":
		text = DEFAULT_RELAY
	text = text.strip_edges()
	if text == "":
		return null
	var idx := text.rfind(":")
	if idx > 0:
		var host := text.substr(0, idx)
		var port := text.substr(idx + 1)
		if port.is_valid_int() and port.length() > 0 and not host.ends_with(":"):
			return [host.lstrip("[").rstrip("]"), int(port)]
	return [text.lstrip("[").rstrip("]"), RELAY_PORT]

## Why invite codes can't be used right now, or "".
static func check_relay(override: String = "") -> String:
	if relay_address(override) == null:
		return ("No relay server is set, so invite codes can't work yet. Start one (python -m "
				+ "ballbrawlla.net.relay_server) and pass --relay HOST, set %s, or fill in " % RELAY_ENV
				+ "DEFAULT_RELAY in net/invite.py.")
	return ""
