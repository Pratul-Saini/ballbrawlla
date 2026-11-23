extends RefCounted
## Invite codes and the relay address (src/ballbrawlla/net/invite.py). The relay connection itself lives in
## relay_client.gd; this file is the part the menu needs: what a valid code looks like, and where the relay is.
## Two kinds of code: an address code (8 characters, KQ7M-3XPA) is the host's IPv4 address plus a check value; a
## relay code (6 characters, KQ7-M3X) names a room on a relay server.

const RELAY_PORT := 50600
## The public relay everyone uses unless --relay or BALLBRAWLLA_RELAY says otherwise. Fill this in once a relay is
## deployed, e.g. "relay.example.com" or "203.0.113.5:50600".
const DEFAULT_RELAY := ""
const RELAY_ENV := "BALLBRAWLLA_RELAY"
const ALPHABET := "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L: easy to read out loud
const CODE_LEN := 6       # relay room codes
const DIRECT_LEN := 8     # address codes
const _CHECK := 198       # 2**32 * 198 < 31**8, so an IPv4 address and a check value fit in 8 characters

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
	if c.length() == DIRECT_LEN:
		return "%s-%s" % [c.substr(0, 4), c.substr(4)]
	return c

## The address code for an IPv4 address "a.b.c.d" (bare; show it with format_code). "" if it isn't one.
static func address_code(ip: String) -> String:
	var parts := ip.split(".")
	if parts.size() != 4:
		return ""
	var v := 0
	for p in parts:
		if not p.is_valid_int() or int(p) < 0 or int(p) > 255:
			return ""
		v = v * 256 + int(p)
	var n: int = v * _CHECK + v % 197
	var out := ""
	for _k in DIRECT_LEN:
		out = ALPHABET[n % ALPHABET.length()] + out
		n = n / ALPHABET.length()
	return out

## The IPv4 address in an address code, or "" if it isn't one (wrong length, or a typo).
static func code_address(text: String) -> String:
	var code := normalize_code(text)
	if code.length() != DIRECT_LEN:
		return ""
	var n := 0
	for ch in code:
		var d := ALPHABET.find(ch)
		if d < 0:
			return ""
		n = n * ALPHABET.length() + d
	var v: int = n / _CHECK
	if v >= (1 << 32) or n % _CHECK != v % 197:
		return ""
	return "%d.%d.%d.%d" % [(v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255]

static func is_relay_code(code: String) -> bool:
	return normalize_code(code).length() == CODE_LEN

## Why this isn't a valid invite code, or "" when it is.
static func check_code(text: String) -> String:
	var code := normalize_code(text)
	if code == "":
		return "Type the invite code from the host's screen (like KQ7M-3XPA)."
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
	if code.length() != CODE_LEN and code.length() != DIRECT_LEN:
		return "An invite code has %d characters (like KQ7M-3XPA); this one has %d." % [DIRECT_LEN, code.length()]
	if code.length() == DIRECT_LEN and code_address(code) == "":
		return "That code has a typo. Check it against the host's screen, character by character."
	return ""

## Where the relay runs: `override` (--relay), else the environment variable, else DEFAULT_RELAY.
## Returns [host, port], or null when none is set.
static func relay_address(override: String = ""):
	var text := override
	if text.strip_edges() == "":
		text = OS.get_environment(RELAY_ENV)
	if text.strip_edges() == "":
		text = DEFAULT_RELAY
	return parse_relay(text)

## "host", "host:port" or "[v6]:port" -> [host, port]; null for "" or something that can't be an address
## (src/ballbrawlla/net/invite.py parse_relay).
static func parse_relay(text: String):
	text = text.strip_edges()
	if text == "":
		return null
	for ch in text:
		if ch == " " or ch == "	" or ch == "
" or ch == "/" or ch == "\\" or ch == "@":
			return null
	var idx := text.rfind(":")
	var host := text.substr(0, idx) if idx >= 0 else ""
	var port := text.substr(idx + 1) if idx >= 0 else ""
	var addr: Array
	if idx >= 0 and host != "" and not host.ends_with(":") and (host.begins_with("[") or host.find(":") < 0):
		if not port.is_valid_int() or port.begins_with("+") or port.begins_with("-") or int(port) < 1 or int(port) > 65535:
			return null
		addr = [host.lstrip("[").rstrip("]"), int(port)]
	else:
		addr = [text.lstrip("[").rstrip("]"), RELAY_PORT]
	if addr[0] == "":
		return null
	return addr

## Why a relay code can't be used here, or "".
static func check_relay(override: String = "") -> String:
	if relay_address(override) == null:
		return ("That is a relay server code (6 characters), and this copy of the game has no relay server "
				+ "set. Ask the host for the code on their screen now: it has 8 characters.")
	return ""
