extends Node2D
## A football match: practice, catch practice, two players on one screen, hosting a game (on this network or online with
## an invite code), or joining one. Reads input, runs the Session at a fixed 120 Hz (or, when joining, sends input and
## draws what the host sends), and draws it with the match renderer. Esc opens the pause menu, F2 the notes.
##
## The launcher (app.gd) calls setup(config) before adding this node. Run on its own for testing:
##   Godot --path godot res://scenes/match.tscn -- --mode=practice|catch|local|host|join --level=field_01
##   Test hooks:  -- --smoke   -- --shot=/tmp/a.png --at=2.5   -- --autoplay (a scripted player)
## config: {mode, level (path), port, address, code, relay, music, diag}. Emits finished(reason, message).

signal finished(reason: String, message: String)    # reason: "menu" | "quit"

const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Field = preload("res://scripts/field.gd")
const Session = preload("res://scripts/session.gd")
const View = preload("res://scripts/view.gd")
const MatchRenderer = preload("res://scripts/match_renderer.gd")
const InputSource = preload("res://scripts/input_source.gd")
const Intent = preload("res://scripts/intent.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const Notes = preload("res://scripts/notes.gd")
const Host = preload("res://scripts/host.gd")
const Client = preload("res://scripts/client.gd")
const Protocol = preload("res://scripts/protocol.gd")
const Discovery = preload("res://scripts/discovery.gd")
const RelayClient = preload("res://scripts/relay_client.gd")
const Invite = preload("res://scripts/invite.gd")

const MAX_FRAME_TIME := 0.25

var cfg: Dictionary = {}
var t
var level
var session                   # Session (everything except joining)
var renderer
var inputs: Array = []
var pause
var notes
var music = null
var diag = null
var mode := "practice"
var local := false
var networked := false        # hosting or joining: the game keeps running under the menu
var accumulator := 0.0
var _fps := 60.0
var _smoke := false
var _autoplay := false
var _shot_path := ""
var _shot_at := 1.6
var _elapsed := 0.0
var _last_view := {}
var _host                     # Host, when hosting
var _room                     # RelayRoom, when hosting online
var _beacon
var _client                   # Client, when joining
var _dial                     # Dial, while joining with a code
var _status := ""
var _invite := ""
var _done := false

func setup(p_cfg: Dictionary) -> void:
	cfg = p_cfg

func _ready() -> void:
	if cfg.is_empty():
		cfg = _cfg_from_command_line()
	mode = cfg.get("mode", "practice")
	music = cfg.get("music")
	diag = cfg.get("diag")
	local = mode == "local"
	networked = mode in ["host", "host_online", "join", "join_code"]
	t = Tuning.new()
	pause = PauseMenu.new(PauseMenu.LOCAL if local else PauseMenu.COMMON, not networked)
	if diag != null:
		diag.where(mode)
	if music != null:
		music.set_context("game")
	var level_path: String = cfg.get("level", "res://levels/field_01.json")
	if mode in ["join", "join_code"]:
		_begin_join()
	else:
		var lr = Level.load_file(level_path)
		if lr["level"] == null:
			_finish("menu", "Could not load %s: %s" % [level_path.get_file(), lr["error"]])
			return
		level = lr["level"]
		var created := Session.create(level, t, 2 if (local or mode in ["host", "host_online"]) else 1, [], mode != "catch")
		if created["session"] == null:
			_finish("menu", "Can't start %s on %s: %s" % [mode, level.level_name, created["error"]])
			return
		session = created["session"]
		if local:
			session.set_connected(1, true)
			inputs = [InputSource.new(InputSource.BLUE_KEYS, 0), InputSource.new(InputSource.RED_KEYS, 1)]
		else:
			inputs = [InputSource.new(InputSource.DEFAULT_KEYS, -1)]
		if mode in ["host", "host_online"] and not _begin_host():
			return
		_make_renderer(session.field)
	_setup_notes()
	if level != null:
		get_window().title = "Gridiron Scramble (Godot) - %s on %s" % [mode, level.level_name]

func _cfg_from_command_line() -> Dictionary:
	var c := {"mode": "practice", "level": "res://levels/field_01.json", "port": Protocol.DEFAULT_PORT, "address": "", "code": "", "relay": ""}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mode="):
			c["mode"] = arg.substr(7)
		elif arg.begins_with("--level="):
			c["level"] = "res://levels/%s.json" % arg.substr(8)
		elif arg.begins_with("--port="):
			c["port"] = int(arg.substr(7))
		elif arg.begins_with("--address="):
			c["address"] = arg.substr(10)
		elif arg.begins_with("--code="):
			c["code"] = arg.substr(7)
		elif arg.begins_with("--relay="):
			c["relay"] = arg.substr(8)
		elif arg == "--smoke":
			_smoke = true
		elif arg == "--autoplay":
			_autoplay = true
		elif arg.begins_with("--shot="):
			_shot_path = arg.substr(7)
		elif arg.begins_with("--at="):
			_shot_at = float(arg.substr(5))
	return c

func _make_renderer(field) -> void:
	renderer = MatchRenderer.new(level, field, t)
	if local:
		renderer.key_names = {"grab": "F / . / Square", "lock": "G / slash / Circle", "restart": "F5"}
	RenderingServer.set_default_clear_color(renderer.BG)

func _setup_notes() -> void:
	notes = Notes.new()
	add_child(notes)
	notes.setup(mode, level.level_name if level != null else "joined game", func(): return _notes_context())

func _notes_context() -> String:
	if _last_view.is_empty():
		return ""
	var s: Array = _last_view["score"]
	return "Blue %d - %d Red, %s down, %s on offense, phase %s" % [s[0], s[1], Session.ordinal(_last_view["down"]),
			load("res://scripts/teams.gd").display(_last_view["offense"]), _last_view["phase"]]

# ------------------------------------------------------------ hosting

func _begin_host() -> bool:
	var room = null
	if mode == "host_online":
		var relay = Invite.relay_address(cfg.get("relay", ""))
		if relay == null:
			_finish("menu", Invite.check_relay())
			return false
		room = RelayClient.RelayRoom.new(relay)
	var hr := Host.create({"level": level.to_dict(), "tuning": t.to_dict()}, 2, int(cfg.get("port", Protocol.DEFAULT_PORT)), "0.0.0.0", room)
	if hr["host"] == null:
		_finish("menu", hr["error"])
		return false
	_host = hr["host"]
	_room = room
	var user := OS.get_environment("USER") if OS.get_environment("USER") != "" else OS.get_environment("USERNAME")
	_beacon = Discovery.Beacon.new("%s's game" % (user if user != "" else "Player"), level.level_name, _host.port)
	_status = "hosting on %s:%d" % [Protocol.lan_ip(), _host.port]
	if diag != null:
		diag.info("hosting on %s (online=%s)" % [_status, str(room != null)])
	return true

func _host_tick() -> void:
	_beacon.tick(_host.clients.size() < _host.max_players - 1)
	var r: Dictionary = _host.poll()
	for pid in r["joined"]:
		session.set_connected(pid, true)
	for pid in r["left"]:
		session.set_connected(pid, false)
	if _room != null:
		if _room.error != "" and _invite == "" and not _room.ready:
			_finish("menu", _room.error)
			return
		if _room.ready:
			_invite = _room.display_code()
		_status = "hosting on %s:%d   |   invite code %s%s" % [Protocol.lan_ip(), _host.port, _invite, "  (relay lost)" if _room.lost() else ""]

# ------------------------------------------------------------ joining

func _begin_join() -> void:
	var address: String = cfg.get("address", "")
	var port: int = int(cfg.get("port", Protocol.DEFAULT_PORT))
	if mode == "join_code":
		var relay = Invite.relay_address(cfg.get("relay", ""))
		if relay == null:
			_finish("menu", Invite.check_relay())
			return
		_dial = RelayClient.Dial.new(relay, cfg.get("code", ""))
		_status = "joining %s via the relay ..." % Invite.format_code(cfg.get("code", ""))
	else:
		_client = Client.connect_to(address, port)
		_status = "connecting to %s:%d ..." % [address, port]
	inputs = [InputSource.new(InputSource.DEFAULT_KEYS, -1)]

func _join_tick() -> void:
	if _dial != null:
		_dial.poll()
		if _dial.state == RelayClient.Dial.FAILED:
			_finish("menu", _dial.error)
		elif _dial.state == RelayClient.Dial.DONE:
			_client = Client.from_peer(_dial.peer, _dial.rest)
			_dial = null
		return
	if _client == null:
		return
	_client.poll()
	if _client.state == Client.FAILED:
		_finish("menu", "Could not join: %s" % _client.error)
	elif _client.state == Client.READY and renderer == null:
		var lr = Level.parse(_client.level_data)
		if lr["level"] == null:
			_finish("menu", "The host sent a level this version can't read: %s" % lr["error"])
			return
		level = lr["level"]
		t.apply_dict(_client.tuning_data)
		var fr := Field.create(level, t)
		if fr["field"] == null:
			_finish("menu", "The host's level isn't a football field: %s" % fr["error"])
			return
		_make_renderer(fr["field"])
		var side_name := "Red" if _client.pid == 1 else "Blue"
		_status = "connected to %s:%d as %s" % [cfg.get("address", "the relay"), cfg.get("port", 0), side_name]
		get_window().title = "Gridiron Scramble (Godot) - joined %s" % level.level_name
		if notes != null:
			notes.log = Notes.SessionLog.new(mode, level.level_name)
		if diag != null:
			diag.info("joined as player %d on %s" % [_client.pid, level.level_name])

# ------------------------------------------------------------ input

func _input(event: InputEvent) -> void:
	if _done or notes == null:
		return
	if notes.handle_event(event):
		return
	if pause.handle_event(event, get_viewport_rect().size):
		if pause.result == "menu":
			_finish("menu", "")
		return
	if music != null and music.handle_event(event):
		return
	for inp in inputs:
		var action: String = inp.handle_event(event, renderer.button_hit if renderer != null else Callable())
		if action == "restart":
			_restart()
		elif action == "debug" and renderer != null:
			renderer.debug = not renderer.debug
	if event is InputEventKey and event.pressed and not event.echo and renderer != null:
		match event.keycode:
			KEY_R: if not local: _restart()
			KEY_F5: if local: _restart()
			KEY_F1: renderer.debug = not renderer.debug
			KEY_F3: renderer.show_controls = not renderer.show_controls

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_finish("quit", "")      # the window's close button ends the whole app, not just the game

func _restart() -> void:
	if session != null and _client == null and _dial == null:
		session.new_match()

## A scripted player so a headless run (or a screenshot) sees real play, not just the play call.
func _autoplay_intent(pid: int) -> Object:
	var i = Intent.new()
	if session == null:
		return i
	var ph: String = session.phase
	if ph == Session.PLAY_CALL:
		var c = session.call
		var off: bool = session.team_of_human[pid] == session.down().offense
		if off:
			i.x_pressed = c.qb_ok and _elapsed > 0.6
			i.z_pressed = c.placing and c.qb_ok and _elapsed > 0.3 and _elapsed < 0.35
		else:
			i.z_pressed = c.def_ok and _elapsed > 0.6
	elif ph == Session.PRE_THROW or ph == Session.LIVE:
		i.move_x = 1 if session.team_of_human[pid] == 0 else -1
		i.jump_pressed = int(_elapsed * 3.0) % 4 == 0 and fmod(_elapsed * 3.0, 1.0) < 0.05
		i.z_pressed = ph == Session.LIVE and fmod(_elapsed * 6.0, 1.0) < 0.05
	return i

# ------------------------------------------------------------ loop

func _finish(reason: String, message: String) -> void:
	if _done:
		return
	_done = true
	if _host != null:
		_host.close()
	if _beacon != null:
		_beacon.close()
	if _client != null:
		_client.close()
	if notes != null:
		notes.save()
	finished.emit(reason, message)
	if cfg.get("standalone", false) or get_parent() == get_tree().root:
		# Run on its own (no launcher to return to): leaving the match ends the program.
		get_tree().quit(0 if message == "" else 2)

func _process(delta: float) -> void:
	if _done:
		return
	_elapsed += delta
	_fps = lerpf(_fps, 1.0 / maxf(delta, 0.0001), 0.1)
	if diag != null:
		diag.beat()
	if music != null:
		pass   # the playlist advances itself (Music._on_finished)
	if mode in ["join", "join_code"]:
		_join_tick()
		_run_join(delta)
	else:
		_run_local(delta)
	queue_redraw()
	if _smoke and _elapsed > 4.0:
		var summary := "mode=%s" % mode
		if session != null:
			summary += " phase=%s down=%d score=%s tick=%d" % [session.phase, session.down().number, str(session.match_.score), session.tick]
		elif _client != null:
			summary += " client=%d pid=%d" % [_client.state, _client.pid]
			var call = _last_view.get("call")
			if call != null:
				summary += " qb=%s ok=%s side=%s" % [str(call["qb"]), str(call["qb_ok"]), str(_last_view.get("side"))]
		print("SMOKE ok: ", summary)
		get_tree().quit()
	if _shot_path != "" and _elapsed > _shot_at:
		get_viewport().get_texture().get_image().save_png(_shot_path)
		print("SHOT saved: ", _shot_path)
		get_tree().quit()

func _run_local(delta: float) -> void:
	if _host != null:
		_host_tick()
		if _done:
			return
	var frozen: bool = pause.freezes() or (notes != null and notes.is_open and not networked)
	if frozen:
		accumulator = 0.0
	else:
		accumulator += minf(delta, MAX_FRAME_TIME)
	var dt: float = t.dt()
	var stepped := false
	while accumulator >= dt:
		var intents: Array = []
		for pid in inputs.size():
			if _smoke or _autoplay:
				intents.append(_autoplay_intent(pid))
			else:
				var offense_pid: int = session.human_of(session.down().offense)
				intents.append(inputs[pid].consume(get_viewport(), renderer.cam, renderer.zoom, (pid == offense_pid) if local else true))
		if _host != null:
			intents.append(_host.intent_for(1))
		session.step(intents, dt)
		accumulator -= dt
		stepped = true
	if _host != null and stepped:
		for pid in _host.clients:
			_host.send_to(pid, View.make_view(session, pid))
	if renderer != null:
		_last_view = View.make_view(session, 0, local)

func _run_join(delta: float) -> void:
	if _client == null or _client.state != Client.READY or renderer == null:
		return
	accumulator += minf(delta, MAX_FRAME_TIME)
	var dt: float = t.dt()
	while accumulator >= dt:
		_client.send_intent(inputs[0].consume(get_viewport(), renderer.cam, renderer.zoom))
		accumulator -= dt
	var snap = _client.latest_snapshot()
	if snap != null:
		_last_view = View.normalize(snap)
	if _client.closed():
		_status = "disconnected from host - press Esc, then Main menu"

func _draw() -> void:
	var size := get_viewport_rect().size
	if renderer == null or _last_view.is_empty():
		var font := ThemeDB.fallback_font
		draw_rect(Rect2(Vector2.ZERO, size), Color(24 / 255.0, 26 / 255.0, 32 / 255.0))
		if _status != "":
			draw_string(font, Vector2(size.x / 2.0 - 200.0, size.y / 2.0), _status, HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color.WHITE)
		if pause != null:
			pause.draw(self, size)
		return
	renderer.draw(self, size, _last_view, _fps, get_process_delta_time(), _status, _controls_line(), _invite)
	pause.draw(self, size)

func _controls_line() -> String:
	if local:
		return "Blue: %s   Red: %s   |   F5: new match   F1: debug   F2: notes   F3: hide controls   Esc: menu" % [
				InputSource.BLUE_KEYS["label"], InputSource.RED_KEYS["label"]]
	if mode in ["join", "join_code"]:
		return "F1: debug   F2: notes   F3: hide controls   Esc: menu"
	return "R / Options: restart   F1: debug   F2: notes   F3: hide controls   Esc: menu"
