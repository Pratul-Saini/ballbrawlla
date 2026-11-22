extends RefCounted
## Can this mode run with this level and port? One answer, shared by the command line and the menu
## (src/ballbrawlla/launch.py). Every check returns a plain-language reason when it fails, or "" when the launch is
## fine, so the caller decides how to show it: the menu greys the option out, a command line would print one line.
##
## Modes: "practice", "catch", "local", "host", "join", "host_online", "join_code", "sandbox".

const Level = preload("res://scripts/level.gd")
const Field = preload("res://scripts/field.gd")
const Tuning = preload("res://scripts/tuning.gd")
const Invite = preload("res://scripts/invite.gd")

const LEVELS_DIR := "res://levels"
const DEFAULT_PORT := 50555
const MATCH_MODES := ["practice", "catch", "local", "host", "host_online"]   # football rules: need a football field
const ALL_MODES := ["practice", "catch", "local", "host", "join", "host_online", "join_code", "sandbox"]
const MODE_LABELS := {
	"practice": "Practice", "catch": "Catch practice", "local": "Two players", "host": "Host a game",
	"join": "Join a game", "host_online": "Host online", "join_code": "Join with code", "sandbox": "Explore",
}

## What the menu knows about a level file without playing it.
class LevelInfo:
	var key := ""                 # file stem, e.g. "field_05"
	var path := ""
	var level_name := ""
	var width := 0.0
	var height := 0.0
	var yard_px := 0.0
	var platforms := 0
	var thin := 0
	var football := false         # satisfies the football field width rule
	var error := ""               # the file could not be read as a level
	func usable() -> bool:
		return error == ""
	func summary() -> String:
		if not usable():
			return "unreadable"
		return "%s x %s px, %d platforms" % [Field._g(width), Field._g(height), platforms]

# ---------------------------------------------------------------- levels

## Inner width a football field needs, between the side walls. yard_px <= 0 means the default.
static func expected_field_width(yard_px: float) -> float:
	var t = Tuning.new()
	return (t.field_yards + 2.0 * t.end_zone_yards) * (yard_px if yard_px > 0.0 else t.yard_px)

static func inspect_level(path: String) -> LevelInfo:
	var info := LevelInfo.new()
	info.path = path
	info.key = path.get_file().get_basename()
	if not FileAccess.file_exists(path):
		info.error = "file not found"
		return info
	var r := Level.load_file(path)
	if r["level"] == null:
		info.level_name = info.key
		info.error = r["error"]
		return info
	var lv = r["level"]
	var t = Tuning.new()
	var inner: float = lv.width - 2.0 * lv.wall_thickness
	info.football = absf(inner - expected_field_width(lv.yard_px if lv.has_yard_px() else -1.0)) <= 0.5
	info.level_name = info.key if lv.level_name == "untitled" else lv.level_name
	info.width = lv.width
	info.height = lv.height
	info.yard_px = lv.yard_px if lv.has_yard_px() else t.yard_px
	for p in lv.platforms:
		if p.kind == "platform":
			info.platforms += 1
			if p.is_thin():
				info.thin += 1
	return info

## Every level file in the folder, football fields first (in name order), then the rest.
static func list_levels(directory: String = LEVELS_DIR) -> Array:
	var infos: Array = []
	var dir := DirAccess.open(directory)
	if dir == null:
		return infos
	var files := Array(dir.get_files()).filter(func(f): return f.ends_with(".json"))
	files.sort()
	for f in files:
		infos.append(inspect_level("%s/%s" % [directory, f]))
	infos.sort_custom(func(a, b):
		if a.football != b.football:
			return a.football
		return a.key < b.key)
	return infos

# ---------------------------------------------------------------- checks

## Why `mode` can't use this level, or "".
static func check_level(mode: String, info) -> String:
	if info == null:
		return "No level selected."
	if not info.usable():
		return "\"%s\" can't be loaded: %s." % [info.key, info.error]
	if MATCH_MODES.has(mode) and not info.football:
		var t = Tuning.new()
		var yp: float = -1.0 if info.yard_px == t.yard_px else info.yard_px
		return ("\"%s\" isn't a football field: it is %s px wide inside the walls and a match needs %s px. " % [
				info.level_name, Field._g(info.width - 64.0), Field._g(expected_field_width(yp))]
				+ "Use Free play for it, or pick a Field level.")
	return ""

static func check_port_number(port: int) -> String:
	if port < 1024 or port > 65535:
		return "Port %d isn't valid. Use a number from 1024 to 65535." % port
	return ""

## Binding the port is a system call, so callers should not do this every frame.
static func check_port(port: int) -> String:
	var bad := check_port_number(port)
	if bad != "":
		return bad
	var server := TCPServer.new()
	if server.listen(port, "0.0.0.0") != OK:
		return "Port %d is already in use. Close the other game, or pick a different port." % port
	server.stop()
	return ""

static func check_address(address: String) -> String:
	var a := address.strip_edges()
	if a == "":
		return "Type the host's IP address first."
	for ch in a:
		if ch == " " or ch == "\t" or ch == "\n":
			return "An IP address can't contain spaces."
	return ""

## Everything that must be true before `mode` can start, checked against the real files and the real port.
static func check_launch(mode: String, level_path: String = "", port: int = DEFAULT_PORT, address: String = "",
		code: String = "") -> String:
	if not ALL_MODES.has(mode):
		return "Unknown mode '%s'." % mode
	if mode == "join":
		var a := check_address(address)
		return a if a != "" else check_port_number(port)
	if mode == "join_code":
		var c := Invite.check_code(code)
		return c if c != "" else Invite.check_relay()
	if not FileAccess.file_exists(level_path):
		return "Level \"%s\" was not found. Levels live in the levels folder (for example field_01)." % level_path.get_file().get_basename()
	var r := Level.load_file(level_path)
	if r["level"] == null:
		return "\"%s\" can't be loaded: %s" % [level_path.get_file(), r["error"]]
	if MATCH_MODES.has(mode):
		var t = Tuning.new()
		if Field.create(r["level"], t)["field"] == null:
			return check_level(mode, inspect_level(level_path))
	if mode == "host":
		return check_port(port)
	if mode == "host_online":
		var rl := Invite.check_relay()
		return rl if rl != "" else check_port(port)
	return ""
