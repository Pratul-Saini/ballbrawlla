extends Node2D
## Free play: one player, a ball, no rules (the Python game's `--sandbox`, "Explore" in the menu). The simulation
## (game.gd) is the ported physics; this file reads input, runs it at a fixed 120 Hz, and draws it. Esc opens the pause
## menu, F2 the notes, M mutes the music.
##
##   Arrows / left stick / D-pad  move, crouch, slide       Up / Cross (A)       jump (hold for full height)
##   Z / Square (X)               pick up the ball, or aim   X / Circle (B) / R1  throw
##   Right stick                  point the aim              R / Options          reset
##
## Run:  Godot --path godot res://scenes/sandbox.tscn [-- --level=field_05]    Test hooks:  -- --smoke   -- --shot=a.png
## config (from the launcher): {level (path), music, diag}. Emits finished(reason, message).

signal finished(reason: String, message: String)    # reason: "menu" | "quit"

const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Game = preload("res://scripts/game.gd")
const Intent = preload("res://scripts/intent.gd")
const InputSource = preload("res://scripts/input_source.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
const Notes = preload("res://scripts/notes.gd")
const PlayerSprites = preload("res://scripts/player_sprites.gd")

const MAX_FRAME_TIME := 0.25
const INTERP_MAX_STEP := 40.0      # px; one sim step never moves a player this far, so more is a teleport
const BG := Color(0.094, 0.106, 0.133)
const SOLID_COL := Color(0.52, 0.56, 0.66)
const BOUND_COL := Color(0.30, 0.32, 0.38)
const THIN_COL := Color(0.36, 0.63, 0.69)
const PLAYER_COL := Color(0.28, 0.55, 0.94)
const BALL_COL := Color(0.92, 0.55, 0.2)
const TEXT_COL := Color(0.9, 0.92, 0.95)

var cfg: Dictionary = {}
var t
var level
var game
var accumulator := 0.0
var camera: Camera2D
var input
var pause
var notes
var music = null
var diag = null
var _level_name := "field_01"
var _smoke := false
var _smoke_double := false   # --double: the scripted run jumps a second time in the air
var _smoke_jumps := 0        # how many scripted presses have been sent (each lasts exactly one tick)
var _shot_path := ""
var _elapsed := 0.0
var _debug := false
var _done := false
var sprites := PlayerSprites.new()
var _prev_pos := Vector2.ZERO    # the player's position one sim step ago, to draw between steps at any display rate
var _blend := 1.0                # how far the display frame is from that step to the latest one (0..1)
var _fx_list: Array = []
var _prev_jumps := -1
var _fx_spawned := 0
var _prev_air := false

func setup(p_cfg: Dictionary) -> void:
	cfg = p_cfg

func _ready() -> void:
	var level_path := ""
	if cfg.is_empty():
		for arg in OS.get_cmdline_user_args():
			if arg.begins_with("--level="):
				_level_name = arg.substr(8)
			elif arg == "--smoke":
				_smoke = true
			elif arg == "--double":
				_smoke_double = true
			elif arg.begins_with("--shot="):
				_shot_path = arg.substr(7)
		level_path = "res://levels/%s.json" % _level_name
	else:
		level_path = cfg.get("level", "res://levels/arena_01.json")
		music = cfg.get("music")
		diag = cfg.get("diag")
	t = Tuning.new()
	var r = Level.load_file(level_path)
	if r["level"] == null:
		_finish("menu", "Could not load %s: %s" % [level_path.get_file(), r["error"]])
		return
	level = r["level"]
	game = Game.new(level, t, 1)
	input = InputSource.new(InputSource.DEFAULT_KEYS, -1)
	pause = PauseMenu.new(PauseMenu.COMMON, true)
	notes = Notes.new()
	add_child(notes)
	notes.setup("sandbox", level.level_name, func(): return "free play on %s" % level.level_name)
	camera = Camera2D.new()
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = int(level.width)
	camera.limit_bottom = int(level.height)
	add_child(camera)
	camera.make_current()
	_snap_camera()
	get_window().title = "Gridiron Scramble (Godot) - explore %s" % level.level_name
	RenderingServer.set_default_clear_color(BG)
	if diag != null:
		diag.where("sandbox")
	if music != null:
		music.set_context("game")

# ------------------------------------------------------------ input

func _input(event: InputEvent) -> void:
	if _done or game == null:
		return
	if notes.handle_event(event):
		return
	if pause.handle_event(event, get_viewport_rect().size):
		if pause.result == "menu":
			_finish("menu", "")
		return
	if music != null and music.handle_event(event):
		return
	var action: String = input.handle_event(event)
	if action == "restart":
		game.reset()
	elif action == "debug":
		_debug = not _debug
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_R: game.reset()
			KEY_F1: _debug = not _debug

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_finish("quit", "")

func _finish(reason: String, message: String) -> void:
	if _done:
		return
	_done = true
	if notes != null:
		notes.save()
	finished.emit(reason, message)
	if cfg.is_empty():
		get_tree().quit(0 if message == "" else 2)

## Scripted input for `--smoke`, so a headless run exercises the whole loop without a person.
func _smoke_intent() -> Object:
	var i = Intent.new()
	i.move_x = 1 if _elapsed < 1.5 else 0
	var due := 1 if _elapsed > 0.6 else 0
	if _smoke_double and _elapsed > 0.8:
		due = 2
	if _smoke_jumps < due:
		_smoke_jumps += 1
		i.jump_pressed = true
	i.jump_held = _smoke_double and _elapsed > 0.6 and _elapsed < 1.1 or i.jump_pressed
	return i

# ------------------------------------------------------------ loop

func _process(delta: float) -> void:
	if _done or game == null:
		return
	_elapsed += delta
	for e in _fx_list:
		e["age"] += delta
	_fx_list = _fx_list.filter(func(e): return e["age"] < PlayerSprites.FX_SECONDS)
	if diag != null:
		diag.beat()
	var frozen: bool = pause.freezes() or notes.is_open
	if frozen:
		accumulator = 0.0
	else:
		accumulator += minf(delta, MAX_FRAME_TIME)
	var dt: float = t.dt()
	while accumulator >= dt:
		_prev_pos = Vector2(game.player().body.px, game.player().body.py)
		game.step([_smoke_intent() if _smoke else input.consume(get_viewport(), camera.position, 1.0, false)], dt)
		accumulator -= dt
	_blend = 1.0 if frozen else clampf(accumulator / dt, 0.0, 1.0)
	_follow_camera(delta)
	queue_redraw()
	if _smoke and _elapsed > 3.0:
		var p = game.player()
		print("SMOKE ok: state=%s x=%.1f y=%.1f on_ground=%s double_jump_effects=%d" % [p.state.state_name, p.body.px, p.body.py, str(p.contacts.on_ground), _fx_spawned])
		get_tree().quit()
	if _shot_path != "" and _elapsed > (0.95 if _smoke_double else 1.6):
		get_viewport().get_texture().get_image().save_png(_shot_path)
		print("SHOT saved: ", _shot_path)
		get_tree().quit()

func _snap_camera() -> void:
	var p = game.player()
	_prev_pos = Vector2(p.body.px, p.body.py)
	camera.position = Vector2(p.center_x(), p.center_y())
	camera.reset_smoothing()

## Where to draw the player's top-left corner: between the previous and the latest sim step, so the 120 Hz simulation
## looks smooth on any display. A jump of more than a few px in one step (a reset) is shown as it is.
func _draw_pos(p) -> Vector2:
	var cur := Vector2(p.body.px, p.body.py)
	if cur.distance_to(_prev_pos) > INTERP_MAX_STEP:
		return cur
	return _prev_pos.lerp(cur, _blend)

func _follow_camera(delta: float) -> void:
	var p = game.player()
	var target: Vector2 = _draw_pos(p) + Vector2(p.w / 2.0, p.h / 2.0)
	camera.position = camera.position.lerp(target, clampf(delta * 8.0, 0.0, 1.0))

# ------------------------------------------------------------ drawing

func _draw() -> void:
	if game == null:
		return
	for pl in level.platforms:
		var r = pl.rect
		var col: Color = BOUND_COL if pl.kind == "bound" else (THIN_COL if pl.is_thin() else SOLID_COL)
		draw_rect(Rect2(r.x, r.y, r.w, r.h), col)
		if pl.is_thin():
			draw_rect(Rect2(r.x, r.y, r.w, 3), col.lightened(0.35))
	var p = game.player()
	var air: bool = p.state.state_name == "airborne"
	if air and _prev_air and p.jumps_left < _prev_jumps:
		_fx_list.append({"x": _draw_pos(p).x + p.w / 2.0, "y": _draw_pos(p).y + p.h, "age": 0.0})
		_fx_spawned += 1
	_prev_air = air
	_prev_jumps = p.jumps_left
	for e in _fx_list:
		sprites.draw_fx(self, Vector2(e["x"], e["y"]), e["age"], PlayerSprites.FX_SCALE)
	var hand := _draw_player(p)
	var b = game.ball
	if b.held_by != null and hand != Vector2.INF:
		PlayerSprites.draw_football(self, hand, b.radius * 1.5, BALL_COL)
	else:
		draw_circle(Vector2(b.body.px, b.body.py), b.radius, BALL_COL)
		draw_arc(Vector2(b.body.px, b.body.py), b.radius, 0.0, TAU, 20, Color.WHITE, 1.5)
	if p.state.state_name == "aiming":
		var d: Array = p.aim_direction()
		var start := Vector2(p.center_x(), p.center_y())
		var frac: float = (p.aim_power - t.power_min) / (t.power_max - t.power_min)
		draw_line(start, start + Vector2(d[0], d[1]) * (40.0 + 120.0 * frac), Color(1, 0.9, 0.3), 3.0)
	_draw_hud(p)

## The player art, animated from his state and speed. Returns the near hand (world px), or Vector2.INF if the art is
## missing and a box was drawn instead.
func _draw_player(p) -> Vector2:
	var at := _draw_pos(p)
	var facing: int = int(p.facing)
	var running: bool = p.state.state_name == "grounded" and absf(p.body.vx) > PlayerSprites.RUN_MIN_SPEED
	if running:
		facing = 1 if p.body.vx > 0.0 else -1
	var spr: Dictionary = {}
	if sprites.available:
		spr = sprites.get_frame("player", 0, facing, p.state.state_name, p.body.vx, p.body.vy, get_process_delta_time())
	if spr.is_empty():
		draw_rect(Rect2(at.x, at.y, p.w, p.h), PLAYER_COL)
		draw_rect(Rect2(at.x, at.y, p.w, p.h), Color.WHITE, false, 2.0)
		return Vector2.INF
	var k: float = PlayerSprites.art_scale(p.h)
	var dst: Rect2 = PlayerSprites.dest_rect(spr, at.x + p.w / 2.0, at.y + p.h, k)
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	draw_texture_rect_region(spr["tex"], dst, spr["src"])
	return dst.position + (spr["hand"] as Vector2) * dst.size

func _draw_hud(p) -> void:
	var font := ThemeDB.fallback_font
	var size := get_viewport_rect().size
	var tl := camera.get_screen_center_position() - size / 2.0
	var lines := ["%s   |   %s   |   %d fps" % [level.level_name, p.state.state_name, Engine.get_frames_per_second()],
			"Arrows move  Up jump  Z catch/aim  X throw  R reset  F1 debug  F2 notes  Esc menu"]
	if _debug:
		lines.append("pos (%.1f, %.1f)  vel (%.1f, %.1f)  contacts g%d c%d l%d r%d" % [p.body.px, p.body.py, p.body.vx, p.body.vy,
				int(p.contacts.on_ground), int(p.contacts.on_ceiling), int(p.contacts.wall_left), int(p.contacts.wall_right)])
	for k in lines.size():
		draw_string(font, tl + Vector2(16, 28 + k * 22), lines[k], HORIZONTAL_ALIGNMENT_LEFT, -1, 16, TEXT_COL)
	# The pause menu is drawn in screen space; this node is in world space under a camera, so draw it translated.
	draw_set_transform(tl, 0.0, Vector2.ONE)
	pause.draw(self, size)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
