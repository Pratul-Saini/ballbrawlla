extends RefCounted
## In-game pause menu: Resume, Controls, Main menu. Esc opens and closes it (src/ballbrawlla/pause.py).
## handle_event() returns true when it used the event, so the game skips it. While `open`, the game should stop
## stepping the simulation (`freezes()`): network games keep running (pauses = false), because freezing the host would
## freeze the other player.

const ITEMS := ["RESUME", "CONTROLS", "MAIN MENU"]
const COMMON := [
	"Move: left / right arrows, left stick       Jump: Up arrow, Cross",
	"Crouch, slide: Down arrow, down on stick    Catch, tag, confirm: Z, Square",
	"Throw, lock in: X, Circle, R1               Aim: mouse, right stick",
	"R / Options: restart   F1: debug   F2: notes   F3: hide controls   Esc: this menu",
	"M: mute or unmute the music",
]
const LOCAL := [
	"Blue: WASD + F (catch, tag, confirm) + G (lock in)",
	"Red: arrows + . (catch, tag, confirm) + / (lock in)",
	"Controllers: first pad is Blue, second is Red",
	"F5: new match   F1: debug   F2: notes   F3: hide controls   Esc: this menu",
	"M: mute or unmute the music",
]

var controls: Array
var pauses: bool
var is_open := false
var page := "menu"          # "menu" or "controls"
var cursor := 0
var result := ""            # "menu" when the player asked for the main menu

func _init(p_controls: Array = [], p_pauses: bool = true) -> void:
	controls = p_controls if not p_controls.is_empty() else COMMON
	pauses = p_pauses

func freezes() -> bool:
	return is_open and pauses

func item_rects(size: Vector2) -> Array:
	var out: Array = []
	for k in ITEMS.size():
		out.append(Rect2(size.x / 2.0 - 160.0, size.y / 2.0 - 70.0 + k * 52.0, 320.0, 44.0))
	return out

func _choose() -> void:
	if page == "controls":
		page = "menu"
	elif ITEMS[cursor] == "RESUME":
		is_open = false
	elif ITEMS[cursor] == "CONTROLS":
		page = "controls"
	else:
		result = "menu"
		is_open = false

func _close_or_back() -> void:
	if page == "controls":
		page = "menu"
	else:
		is_open = false

func _open_menu() -> void:
	is_open = true
	page = "menu"
	cursor = 0

## Returns true when the event was used. Closed: only Esc is used. Open: everything is, so the game sees no input.
func handle_event(event: InputEvent, size: Vector2 = Vector2(1280, 720)) -> bool:
	if not is_open:
		if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
			_open_menu()
			return true
		return false
	if event is InputEventKey and event.pressed and not event.echo:
		if page == "controls":
			page = "menu"
		elif event.keycode == KEY_ESCAPE:
			_close_or_back()
		elif event.keycode in [KEY_UP, KEY_W]:
			cursor = posmod(cursor - 1, ITEMS.size())
		elif event.keycode in [KEY_DOWN, KEY_S]:
			cursor = posmod(cursor + 1, ITEMS.size())
		elif event.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			_choose()
	elif event is InputEventMouseMotion and page == "menu":
		var rects := item_rects(size)
		for k in rects.size():
			if rects[k].has_point(event.position):
				cursor = k
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if page == "controls":
			page = "menu"
		else:
			var rects := item_rects(size)
			for k in rects.size():
				if rects[k].has_point(event.position):
					cursor = k
					_choose()
	elif event is InputEventJoypadButton and event.pressed:
		match event.button_index:
			JOY_BUTTON_DPAD_UP: cursor = posmod(cursor - 1, ITEMS.size())
			JOY_BUTTON_DPAD_DOWN: cursor = posmod(cursor + 1, ITEMS.size())
			JOY_BUTTON_A, JOY_BUTTON_X: _choose()
			JOY_BUTTON_B, JOY_BUTTON_START: _close_or_back()
	return true

func draw(ci: CanvasItem, size: Vector2) -> void:
	var font := ThemeDB.fallback_font
	var panel := Color(20 / 255.0, 72 / 255.0, 36 / 255.0)
	var dim := Color(160 / 255.0, 196 / 255.0, 168 / 255.0)
	if not is_open:
		_draw_hint(ci, font, size)
		return
	ci.draw_rect(Rect2(Vector2.ZERO, size), Color(0, 0, 0, 150.0 / 255.0))
	if page == "controls":
		var box := Rect2(0, 0, 900, 120 + 36 * controls.size())
		box.position = size / 2.0 - box.size / 2.0
		ci.draw_rect(box, panel)
		ci.draw_rect(box, Color.WHITE, false, 2.0)
		_center_text(ci, font, "CONTROLS", Vector2(size.x / 2.0, box.position.y + 20.0), 44, Color.WHITE)
		for k in controls.size():
			_center_text(ci, font, controls[k], Vector2(size.x / 2.0, box.position.y + 80.0 + 36.0 * k), 22, Color.WHITE)
		_center_text(ci, font, "any key or click to go back", Vector2(size.x / 2.0, box.end.y - 30.0), 18, dim)
		return
	_center_text(ci, font, "PAUSED" if pauses else "MENU (game keeps running)", Vector2(size.x / 2.0, size.y / 2.0 - 170.0), 44, Color.WHITE)
	var rects := item_rects(size)
	for k in ITEMS.size():
		if k == cursor:
			ci.draw_rect(rects[k], panel)
			ci.draw_rect(rects[k], Color.WHITE, false, 2.0)
		_center_text(ci, font, ITEMS[k], rects[k].get_center() - Vector2(0, 14), 30, Color.WHITE)

## A small "Esc: menu" badge in the bottom-right corner, on the same line as the status text; it takes no input.
func _draw_hint(ci: CanvasItem, font: Font, size: Vector2) -> void:
	var text := "Esc: menu"
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x
	var box := Rect2(size.x - w - 26.0, size.y - 34.0, w + 14.0, 22.0)
	ci.draw_rect(box, Color(0, 0, 0, 120.0 / 255.0))
	ci.draw_string(font, box.position + Vector2(7, 16), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.WHITE)

func _center_text(ci: CanvasItem, font: Font, text: String, top_center: Vector2, px: int, color: Color) -> void:
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	ci.draw_string(font, Vector2(top_center.x - w / 2.0, top_center.y + px * 0.82), text, HORIZONTAL_ALIGNMENT_LEFT, -1, px, color)
