extends Node2D
## The launcher menu screen: draws MenuState (menu_state.gd) over the animated backdrop and turns keyboard, mouse and
## controller input into menu actions (src/ballbrawlla/menu.py, drawing and event handling).
## Emits `chosen(result)` when the player starts something and `quit_requested` when they quit.

signal chosen(result: Dictionary)
signal quit_requested

const MenuState = preload("res://scripts/menu_state.gd")
const MenuAnim = preload("res://scripts/menu_anim.gd")
const Protocol = preload("res://scripts/protocol.gd")
const Version = preload("res://scripts/version.gd")
const Invite = preload("res://scripts/invite.gd")

const TITLE := "GRIDIRON SCRAMBLE"
const TAGLINE := "Catch it. Run it. Don't get tagged."
const ROW_H := 44.0
const MAX_ROWS := 12

static func c8(r: int, g: int, b: int) -> Color:
	return Color(r / 255.0, g / 255.0, b / 255.0)

var PANEL := c8(20, 72, 36)       # darker green behind the selected row and dialogs
var FG := Color.WHITE             # options
var DIM := c8(160, 196, 168)      # unavailable options and small print
var ACCENT := c8(150, 92, 44)     # title and tagline: leather brown
var BAD := c8(255, 170, 160)

var state
var anim
var music = null                  # optional Music node: M mutes, except while typing
var pad_names: Array = []
var _rects: Array = []
var _t := 0.0
var _font: Font

func _ready() -> void:
	state = MenuState.new()
	anim = MenuAnim.new()
	_font = ThemeDB.fallback_font
	RenderingServer.set_default_clear_color(c8(30, 104, 52))

func _process(delta: float) -> void:
	_t += delta
	state.pad_names = pad_names
	state.update()
	if state.result != null:
		var r = state.result
		state.result = null
		state.close()
		chosen.emit(r)
	elif state.quit:
		state.quit = false
		quit_requested.emit()
	queue_redraw()

# ------------------------------------------------------------ input

func _unhandled_input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	if event is InputEventKey and event.pressed:
		_key(event)
	elif event is InputEventMouseMotion:
		for k in _rects.size():
			if _rects[k].has_point(event.position):
				state.hover(k)
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if state.error != "":
			state.error = ""
			return
		for k in _rects.size():
			if _rects[k].has_point(event.position):
				state.hover(k)
				state.select()
	elif event is InputEventJoypadButton and event.pressed:
		if state.error != "":
			state.error = ""
		else:
			match event.button_index:
				JOY_BUTTON_DPAD_UP: state.move(-1)
				JOY_BUTTON_DPAD_DOWN: state.move(1)
				JOY_BUTTON_A, JOY_BUTTON_X: state.select()      # Cross or Square
				JOY_BUTTON_B: state.back()                        # Circle

func _key(e: InputEventKey) -> void:
	if state.error != "":
		if not e.echo:
			state.error = ""
		return
	var code: int = e.keycode
	if code == KEY_ESCAPE:
		if not e.echo:
			if state.stack.is_empty():
				state.quit = true
			else:
				state.back()
	elif code == KEY_V and (e.ctrl_pressed or e.meta_pressed) and state.editing():
		state.paste(DisplayServer.clipboard_get())
	elif code == KEY_BACKSPACE:
		if state.editing():
			state.backspace()
		elif not e.echo:
			state.back()
	elif (code == KEY_UP or (code == KEY_W and not state.editing())):
		state.move(-1)
	elif (code == KEY_DOWN or (code == KEY_S and not state.editing())):
		state.move(1)
	elif code == KEY_ENTER or code == KEY_KP_ENTER or (code == KEY_SPACE and not state.editing()):
		if not e.echo:
			if state.editing():
				state.move(1)
			else:
				state.select()
	elif code == KEY_M and music != null and not state.editing() and not e.ctrl_pressed and not e.meta_pressed:
		if not e.echo:
			music.toggle_mute()
	elif e.unicode > 31 and e.unicode != 127:
		state.type_char(String.chr(e.unicode))

# ------------------------------------------------------------ drawing

func _rows(size: Vector2) -> Array:
	var n: int = state.items().size()
	var top := maxf(150.0, floorf(size.y / 2.0) - floorf(minf(n, MAX_ROWS) * ROW_H / 2.0) + 30.0)
	var first := maxi(0, state.cursor - (MAX_ROWS - 1)) if n > MAX_ROWS else 0
	var out: Array = []
	for k in n:
		out.append(Rect2(size.x / 2.0 - 330.0, top + (k - first) * ROW_H, 660.0, ROW_H - 6.0))
	return out

func _text(s: String, pos: Vector2, color: Color, px: int, anchor: String = "topleft") -> void:
	var w := _font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	var x := pos.x
	var y := pos.y
	match anchor:
		"midtop": x -= w / 2.0
		"midleft": y -= px * 0.5
		"midright":
			x -= w
			y -= px * 0.5
		"midbottom":
			x -= w / 2.0
			y -= px
		"bottomright":
			x -= w
			y -= px
	draw_string(_font, Vector2(x, y + px * 0.82), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, color)

## Split a message into lines no wider than max_w pixels, breaking at spaces.
func _wrapped_lines(message: String, max_w: float, px: int) -> Array:
	var lines: Array = []
	var line := ""
	for word in message.split(" ", false):
		var trial := (line + " " + word).strip_edges()
		if _font.get_string_size(trial, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x > max_w and line != "":
			lines.append(line)
			line = word
		else:
			line = trial
	if line != "":
		lines.append(line)
	return lines

func _wrap(message: String, box: Rect2, color: Color, px: int, center_x: float) -> void:
	var line := ""
	var y := box.position.y
	for word in message.split(" ", false):
		var trial := (line + " " + word).strip_edges()
		if _font.get_string_size(trial, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x > box.size.x and line != "":
			_text(line, Vector2(center_x, y), color, px, "midtop")
			line = word
			y += px + 6.0
		else:
			line = trial
	_text(line, Vector2(center_x, y), color, px, "midtop")

func _draw() -> void:
	if state == null:
		return
	var size := get_viewport_rect().size
	anim.draw(self, size, _t, state.screen in ["main", "play", "freeplay", "online"])
	if state.screen == "main":
		_text(" ".join(Array(TITLE.split())).replace(" ", " "), Vector2(size.x / 2.0, 40.0), ACCENT, 60, "midtop")
		_text(TAGLINE, Vector2(size.x / 2.0, 104.0), ACCENT, 22, "midtop")
	else:
		_text(state.title(), Vector2(size.x / 2.0, 40.0), ACCENT, 56, "midtop")
	var its: Array = state.items()
	_rects = _rows(size)
	var n := its.size()
	var first := maxi(0, state.cursor - (MAX_ROWS - 1)) if n > MAX_ROWS else 0
	for k in n:
		if k < first or k > first + MAX_ROWS - 1:
			continue
		var item = its[k]
		var rect: Rect2 = _rects[k]
		var sel: bool = k == state.cursor
		if sel:
			draw_rect(rect, PANEL)
			draw_rect(rect, FG, false, 2.0)
		_text(item.label, Vector2(rect.position.x + 16.0, rect.get_center().y), FG if item.enabled() else DIM, 32, "midleft")
		if item.hint != "":
			_text(item.hint, Vector2(rect.end.x - 16.0, rect.get_center().y), DIM, 20, "midright")
		if not item.enabled() and sel:
			# Long reasons (the missing-relay one is 230 characters) wrap inside the screen, above the footer lines.
			var lines := _wrapped_lines(item.reason, 900.0, 20)
			var y := size.y - 100.0 - 26.0 * lines.size()
			for line in lines:
				_text(line, Vector2(size.x / 2.0, y), BAD, 20, "midtop")
				y += 26.0
	if state.screen == "main":
		var pads := ", ".join(pad_names)
		_text("controller: %s" % pads if pads != "" else "no controller found (keyboard and mouse work)", Vector2(size.x / 2.0, size.y - 50.0), DIM, 20, "midbottom")
	elif state.screen == "online":
		_text("your address: %s" % Protocol.lan_ip(), Vector2(size.x / 2.0, size.y - 74.0), DIM, 20, "midbottom")
		_text("First time hosting? If your computer asks, allow incoming connections.", Vector2(size.x / 2.0, size.y - 50.0), DIM, 20, "midbottom")
	elif state.screen == "code":
		_text("The host sees the code on their waiting screen (Ctrl+C there copies it).", Vector2(size.x / 2.0, size.y - 50.0), DIM, 20, "midbottom")
	elif state.screen == "join":
		_text("Nothing showing up? You and the host must be on the same Wi-Fi, and your firewall must allow this game.", Vector2(size.x / 2.0, size.y - 50.0), DIM, 20, "midbottom")
	_text("v%s" % Version.VERSION, Vector2(size.x - 14.0, size.y - 10.0), DIM, 20, "bottomright")
	_text("Up/Down: move   Enter / click / Cross: select   Esc / Circle: back   M: music", Vector2(size.x / 2.0, size.y - 20.0), DIM, 20, "midbottom")
	if state.error != "":
		var box := Rect2(size.x / 2.0 - 380.0, size.y / 2.0 - 85.0, 760.0, 170.0)
		draw_rect(box, PANEL)
		draw_rect(box, BAD, false, 2.0)
		_wrap(state.error, Rect2(box.position.x + 30.0, box.position.y + 30.0, box.size.x - 60.0, 100.0), FG, 20, size.x / 2.0)
		_text("press any key", Vector2(size.x / 2.0, box.end.y - 12.0), DIM, 18, "midbottom")
