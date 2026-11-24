extends RefCounted
## The launcher menu's logic, with no drawing, so it can be tested without a window (src/ballbrawlla/menu.py).
## Every option that starts a game asks Launch.check_launch / check_level. If the answer is a reason, the option is
## greyed out and the reason is shown, so a player can only start things that will run.

const Launch = preload("res://scripts/launch.gd")
const Invite = preload("res://scripts/invite.gd")
const Discovery = preload("res://scripts/discovery.gd")
const Protocol = preload("res://scripts/protocol.gd")

const DEFAULT_KEY := "field_01"

class Item:
	var label := ""
	var action := ""
	var reason := ""        # why it is unavailable; "" = available
	var hint := ""          # right-aligned note, e.g. the current level
	func _init(p_label: String = "", p_action: String = "", p_reason: String = "", p_hint: String = "") -> void:
		label = p_label
		action = p_action
		reason = p_reason
		hint = p_hint
	func enabled() -> bool:
		return reason == ""

var levels: Array = []                 # Launch.LevelInfo
var level_key := DEFAULT_KEY           # last level picked; the picker opens on it
var mode := ""                         # the mode waiting for a level
var port: int = Protocol.DEFAULT_PORT
var address := ""
var code := ""                         # invite code being typed on the Join screen (bare, without the dash)
var screen := "main"
var cursor := 0
var error := ""                        # message dialog; any key dismisses it
var pad_names: Array = []
var result = null                      # {"mode", "level", "port", "address", "code"} when something was chosen
var quit := false
var stack: Array = []
var finder = null                      # listens for hosted games while the Join screen is open
var games: Array = []
var finder_factory: Callable = Callable()   # tests replace this
var _port_cache = null                 # [port, time, reason]

func _init(p_levels: Array = []) -> void:
	levels = p_levels if not p_levels.is_empty() else Launch.list_levels()
	var keys := levels.map(func(i): return i.key)
	if not keys.has(level_key) and not levels.is_empty():
		level_key = levels[0].key

# ---- queries

func items() -> Array:
	match screen:
		"main":
			return [Item.new("PLAY", "go:play"), Item.new("QUIT", "quit")]
		"play":
			return [Item.new("FREE PLAY", "go:freeplay", "", "explore or catch practice"),
					Item.new("TWO PLAYERS", "mode:local", "", "one screen"),
					Item.new("ONLINE", "go:online")]
		"freeplay":
			return [Item.new("EXPLORE", "mode:sandbox", "", "no rules, any level"),
					Item.new("CATCH PRACTICE", "mode:catch", "", "run your route, then run to score, no defender")]
		"online":
			return [Item.new("HOST GAME", "mode:host", _port_reason(), "you get a code to send your friend"),
					Item.new("JOIN GAME", "go:join", "", "type your friend's code")]
		"join":
			var found: Array = []
			if not games.is_empty():
				for n in games.size():
					var g = games[n]
					var parts: Array = []
					if g.level != "":
						parts.append(g.level)
					parts.append("on your Wi-Fi")
					found.append(Item.new(g.name, "found:%d" % n, "", " - ".join(parts)))
			elif finder != null and finder.available:
				found.append(Item.new("Looking for games on your Wi-Fi...", "none", "", "or type the code below"))
			else:
				found.append(Item.new("Can't look for games on this network", "none", "", "type the code below"))
			found.append(Item.new("CODE: %s_" % Invite.format_code(code), "edit", "", "Ctrl+V pastes"))
			found.append(Item.new("CONNECT", "launch:join_code", Launch.check_launch("join_code", "", port, "", code)))
			return found
		"level":
			var out: Array = []
			for info in shown_levels():
				out.append(Item.new(info.level_name, "pick:%s" % info.key, _level_reason(info), info.summary() if info.usable() else ""))
			return out
	return []

## Levels for the waiting mode: Free play shows everything, match modes only football fields.
func shown_levels() -> Array:
	if mode == "sandbox":
		return levels
	return levels.filter(func(i): return i.football or not i.usable())

# Cheap: uses what list_levels already read. The full check (load the file, build the field, bind the port) runs
# once, when the player actually launches.
func _level_reason(info) -> String:
	return Launch.check_level(mode, info)

## Binding the port is a system call, so look at most once a second instead of every frame.
func _port_reason() -> String:
	var now := Time.get_ticks_msec() / 1000.0
	if _port_cache == null or _port_cache[0] != port or now - _port_cache[1] > 1.0:
		_port_cache = [port, now, Launch.check_port(port)]
	return _port_cache[2]

func title() -> String:
	if screen == "level":
		return "%s: CHOOSE A LEVEL" % Launch.MODE_LABELS[mode].to_upper()
	return {"main": "", "play": "PLAY", "freeplay": "FREE PLAY", "online": "ONLINE", "join": "JOIN GAME"}[screen]

# ---- navigation

func _new_finder():
	if finder_factory.is_valid():
		return finder_factory.call()
	return Discovery.Finder.new()

func go(target: String) -> void:
	stack.append(screen)
	screen = target
	cursor = 0
	if target == "join":
		finder = _new_finder()
		games = []
		cursor = 1                   # the code row; games found later appear above it
	if target == "level":
		cursor = 0
		var shown := shown_levels()
		for n in shown.size():
			if shown[n].key == level_key:
				cursor = n

func back() -> void:
	if error != "":
		error = ""
	elif not stack.is_empty():
		if screen == "join":
			close()
		screen = stack.pop_back()
		cursor = 0

func close() -> void:
	if finder != null:
		finder.close()
	finder = null
	games = []

## Once per frame: read broadcasts, and keep the cursor on the same row when the games list changes size.
func update() -> void:
	if screen != "join" or finder == null:
		return
	var before := maxi(1, games.size())
	games = finder.poll()
	var after := maxi(1, games.size())
	if after != before and cursor >= before:
		cursor += after - before

func move(step: int) -> void:
	if error != "" or items().is_empty():
		return
	cursor = posmod(cursor + step, items().size())

func hover(index: int) -> void:
	if error == "" and index >= 0 and index < items().size():
		cursor = index

func select() -> void:
	if error != "":
		error = ""
		return
	var its := items()
	if its.is_empty():
		return
	var item = its[cursor]
	if not item.enabled():
		error = item.reason
		return
	var parts: PackedStringArray = item.action.split(":", true, 1)
	var kind := parts[0]
	var arg := parts[1] if parts.size() > 1 else ""
	match kind:
		"go": go(arg)
		"quit": quit = true
		"found":
			var g = games[int(arg)]
			result = {"mode": "join", "level": "", "port": g.port, "address": g.address, "code": ""}
		"mode":
			mode = arg
			go("level")
		"pick":
			level_key = arg
			var path := ""
			for i in levels:
				if i.key == arg:
					path = i.path
			result = {"mode": mode, "level": path, "port": port, "address": "", "code": ""}
		"launch":
			var c := Invite.normalize_code(code)
			var lan = null
			for g in games:
				if g.codes.has(c):
					lan = g
			if arg == "join_code" and lan != null:      # on this network: connect straight to it
				result = {"mode": "join", "level": "", "port": lan.port, "address": lan.address, "code": ""}
			else:
				result = {"mode": arg, "level": "", "port": port, "address": address.strip_edges(), "code": c}

# ---- text entry (the invite code on the Join screen)

func editing() -> bool:
	if screen != "join" or error != "":
		return false
	var its := items()
	return not its.is_empty() and its[mini(cursor, its.size() - 1)].action == "edit"

func type_char(ch: String) -> void:
	if not editing():
		return
	# Keep anything code-like (so a typo is shown and explained) but ignore dashes and spaces.
	var c := Invite.normalize_code(ch)
	if c != "" and _is_alnum(c) and code.length() < Invite.DIRECT_LEN + 2:
		code += c

func _is_alnum(s: String) -> bool:
	for ch in s:
		var u := ch.unicode_at(0)
		if not ((u >= 65 and u <= 90) or (u >= 97 and u <= 122) or (u >= 48 and u <= 57)):
			return false
	return s != ""

func backspace() -> void:
	if editing():
		code = code.substr(0, code.length() - 1)

## Ctrl+V: a pasted code replaces what was typed. Pasting "Code: kq7m-3xpa" works too.
func paste(text: String) -> void:
	if not editing() or text == "":
		return
	var exact: Array = []
	for w in text.replace(":", " ").split(" ", false):
		var n := Invite.normalize_code(w)
		if n.length() == Invite.CODE_LEN or n.length() == Invite.DIRECT_LEN:
			var ok := true
			for ch in n:
				if Invite.ALPHABET.find(ch) < 0:
					ok = false
			if ok:
				exact.append(n)
	code = (exact[-1] if not exact.is_empty() else Invite.normalize_code(text)).substr(0, Invite.DIRECT_LEN + 2)
