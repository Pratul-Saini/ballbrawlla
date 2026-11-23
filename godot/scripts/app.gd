extends Node
## The whole game: shows the launcher, starts whatever the player picks, returns to the menu when they leave it, and
## ends the program when they close the window (src/ballbrawlla/main.py). It also understands command-line options
## (after a double dash on the engine's own line; the README lists them). A game started that way ends the program when
## you leave it, since there is no menu to return to. With no options the launcher opens. A launch that cannot work
## prints one line and exits with status 2, like the Python game.

const Launch = preload("res://scripts/launch.gd")
const Diag = preload("res://scripts/diag.gd")
const Music = preload("res://scripts/music.gd")
const Invite = preload("res://scripts/invite.gd")
const Protocol = preload("res://scripts/protocol.gd")
const Version = preload("res://scripts/version.gd")

const MODE_FLAGS := ["catch", "local", "host", "sandbox"]    # each one picks the mode by itself

var diag
var music
var launcher
var current: Node = null
var pending_error := ""

func _ready() -> void:
	get_tree().set_auto_accept_quit(false)         # the close button is handled here, so notes get saved first
	diag = Diag.new()
	diag.setup()
	diag.info("game version %s" % Version.VERSION)
	_pick_display()
	music = Music.new()
	add_child(music)
	if music.start():
		diag.info("music: playing %d file(s), first: %s" % [music.tracks.size(), music.current().get_file()])
	else:
		diag.info("music: none (no audio files in assets/music, or music is off)")
	var cmd := parse_options(OS.get_cmdline_user_args())
	if cmd.has("error"):
		_refuse(cmd["error"])
		return
	if cmd.has("config"):
		var why := _check(cmd["config"])
		if why != "":
			_refuse(why)
			return
		_start(cmd["config"], true)
	else:
		_show_launcher()

func _refuse(why: String) -> void:
	printerr("ballbrawlla: " + why)
	diag.warn("launch refused: %s" % why)
	_quit_with(2)

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if diag != null:
			diag.info("window closed: quitting the app")
		_quit_with(0)

func _quit_with(code: int) -> void:
	if current != null:
		current.queue_free()
		current = null
	if diag != null:
		diag.close()
	get_tree().quit(code)

## Open the window on the main display (override with BALLBRAWLLA_DISPLAY), so it cannot land on a second monitor.
func _pick_display() -> void:
	var wanted := 0
	var env := OS.get_environment("BALLBRAWLLA_DISPLAY")
	if env.is_valid_int():
		wanted = int(env)
	if wanted < 0 or wanted >= DisplayServer.get_screen_count():
		wanted = 0
	DisplayServer.window_set_current_screen(wanted)

# ------------------------------------------------------------ command line

## Options are written like `--name` or `--name=value`. Returns {} (no options: show the launcher),
## {"error": text}, or {"config": {mode, level, port, address, code, relay, no_router}}.
static func parse_options(args: PackedStringArray) -> Dictionary:
	var opts := {}
	for arg in args:
		if not arg.begins_with("--"):
			continue
		var body := arg.substr(2)
		var eq := body.find("=")
		if eq < 0:
			opts[body] = ""
		else:
			opts[body.substr(0, eq)] = body.substr(eq + 1)
	for key in ["smoke", "autoplay", "shot", "at", "mode"]:
		opts.erase(key)                          # test hooks of the individual screens, not launch options
	if opts.is_empty():
		return {}
	var modes: Array = []
	for flag in MODE_FLAGS:
		if opts.has(flag):
			modes.append(flag)
	if opts.has("join"):
		modes.append("join")
	if opts.has("join-code"):
		modes.append("join_code")
	if modes.size() > 1:
		return {"error": "choose only one of: host, join, join-code, local, catch, sandbox"}
	var mode: String = modes[0] if not modes.is_empty() else "practice"     # --online (old) changes nothing: hosting always is
	var port: int = Protocol.DEFAULT_PORT
	if opts.has("port"):
		if not str(opts["port"]).is_valid_int():
			return {"error": "port needs a number"}
		port = int(opts["port"])
	var path := ""
	if not mode in ["join", "join_code"]:
		var stem: String = str(opts.get("level", ""))
		if stem == "":
			stem = "arena_01" if mode == "sandbox" else "field_01"
		path = "%s/%s.json" % [Launch.LEVELS_DIR, stem.get_file().get_basename()]
	return {"config": {"mode": mode, "level": path, "port": port, "address": str(opts.get("join", "")),
			"code": str(opts.get("join-code", "")), "relay": str(opts.get("relay", "")), "no_router": opts.has("no-router")}}

## Why this launch cannot work, or "". Same checks as the menu uses. An explicit relay stands in for a configured one.
func _check(c: Dictionary) -> String:
	if c["relay"] != "" and c["mode"] in ["join_code", "host"]:
		OS.set_environment(Invite.RELAY_ENV, c["relay"])
	return Launch.check_launch(c["mode"], c["level"], c["port"], c["address"], c["code"])

# ------------------------------------------------------------ screens

func _show_launcher() -> void:
	diag.where("menu")
	music.set_context("menu")
	launcher = load("res://scenes/launcher.tscn").instantiate()
	launcher.music = music
	launcher.pad_names = Input.get_connected_joypads().map(func(id): return Input.get_joy_name(id))
	add_child(launcher)
	current = launcher
	launcher.chosen.connect(_on_chosen)
	launcher.quit_requested.connect(func(): _quit_with(0))
	if pending_error != "":
		launcher.state.error = pending_error
		pending_error = ""

func _on_chosen(result: Dictionary) -> void:
	diag.info("launch requested: %s" % str(result))
	var cfg := {"mode": result["mode"], "level": result["level"], "port": result["port"], "address": result["address"],
			"code": result["code"], "relay": "", "no_router": false}
	var why := Launch.check_launch(cfg["mode"], cfg["level"], cfg["port"], cfg["address"], cfg["code"])
	if why != "":
		diag.warn("launch refused: %s" % why)
		launcher.state.error = why
		return
	launcher.queue_free()
	launcher = null
	_start(cfg, false)

func _start(cfg: Dictionary, from_command_line: bool) -> void:
	cfg["music"] = music
	cfg["diag"] = diag
	var scene := "res://scenes/sandbox.tscn" if cfg["mode"] == "sandbox" else "res://scenes/match.tscn"
	var node: Node = load(scene).instantiate()
	node.setup(cfg)
	add_child(node)
	current = node
	node.finished.connect(func(reason: String, message: String): _on_finished(reason, message, from_command_line))

func _on_finished(reason: String, message: String, from_command_line: bool) -> void:
	if current != null:
		current.queue_free()
		current = null
	if reason == "quit":
		_quit_with(0)
	elif from_command_line:
		if message != "":
			printerr("ballbrawlla: " + message)
		_quit_with(2 if message != "" else 0)
	else:
		diag.where("menu")
		pending_error = message
		_show_launcher()
