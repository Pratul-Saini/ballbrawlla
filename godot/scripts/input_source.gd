extends RefCounted
## One person's input: keyboard bindings plus one controller slot, collected into an Intent each physics tick
## (src/ballbrawlla/input.py and gamepad.py). Presses are latched between ticks so none are dropped.
##
## Keyboard sets:  DEFAULT arrows + Z (catch) + X (throw)   BLUE  WASD + F + G   RED  arrows + . + /
## Controller (SDL layout, so a DualSense works):  left stick / D-pad move, Cross jump, Square catch,
## Circle or R1 or R2 throw, right stick aims, Options restart, Create or touchpad debug.

const Intent = preload("res://scripts/intent.gd")

const MOVE_DEADZONE := 0.35      # left stick: fraction of full tilt before it counts as left/right
const VERTICAL_DEADZONE := 0.5   # higher, so running on a slight diagonal doesn't crouch
const AIM_DEADZONE := 0.5        # right stick must be pushed this far to point the aim
const TRIGGER_THRESHOLD := 0.5   # R2 pulled this far counts as a press

const DEFAULT_KEYS := {"left": KEY_LEFT, "right": KEY_RIGHT, "up": KEY_UP, "down": KEY_DOWN, "grab": KEY_Z, "throw": KEY_X,
		"label": "arrows, Z, X"}
const BLUE_KEYS := {"left": KEY_A, "right": KEY_D, "up": KEY_W, "down": KEY_S, "grab": KEY_F, "throw": KEY_G,
		"label": "WASD, F, G"}
const RED_KEYS := {"left": KEY_LEFT, "right": KEY_RIGHT, "up": KEY_UP, "down": KEY_DOWN, "grab": KEY_PERIOD,
		"throw": KEY_SLASH, "label": "arrows, period, slash"}

var keys: Dictionary
var pad_slot := -1               # -1: every controller; otherwise the Nth controller to have connected
var _pressed := {}               # keycodes pressed since the last consume()
var _pad_jump := false
var _pad_grab := false
var _pad_throw := false
var _r2_down := {}
var _mouse_pressed := false
var _button_pressed := false
var _hold_on_button := false     # a press that began on the HUD button isn't a drag

func _init(p_keys: Dictionary = DEFAULT_KEYS, p_pad_slot: int = -1) -> void:
	keys = p_keys
	pad_slot = p_pad_slot

# ------------------------------------------------------------ controllers

## Device ids of the controllers this source listens to, in the order they connected.
func _devices() -> Array:
	var all: Array = Input.get_connected_joypads()
	all.sort()
	if pad_slot < 0:
		return all
	return [all[pad_slot]] if pad_slot < all.size() else []

func pad_names() -> Array:
	var out := []
	for d in _devices():
		out.append(Input.get_joy_name(d))
	return out

# ------------------------------------------------------------ events

## Feed every input event in. `button_hit` is a Callable(Vector2) -> bool for the on-screen play-call button.
## Returns "restart" or "debug" when a controller menu button is pressed, else "".
func handle_event(event: InputEvent, button_hit: Callable = Callable()) -> String:
	if event is InputEventKey and event.pressed and not event.echo:
		_pressed[event.keycode] = true
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			if button_hit.is_valid() and button_hit.call(event.position):
				_button_pressed = true
				_hold_on_button = true
			else:
				_mouse_pressed = true
		else:
			_hold_on_button = false
	elif event is InputEventJoypadButton and event.pressed and _devices().has(event.device):
		match event.button_index:
			JOY_BUTTON_A: _pad_jump = true                                    # Cross
			JOY_BUTTON_X: _pad_grab = true                                    # Square
			JOY_BUTTON_B, JOY_BUTTON_RIGHT_SHOULDER: _pad_throw = true        # Circle, R1
			JOY_BUTTON_START: return "restart"                                # Options
			JOY_BUTTON_BACK, JOY_BUTTON_TOUCHPAD: return "debug"              # Create, touchpad
	elif event is InputEventJoypadMotion and event.axis == JOY_AXIS_TRIGGER_RIGHT and _devices().has(event.device):
		var down: bool = event.axis_value >= TRIGGER_THRESHOLD
		if down and not _r2_down.get(event.device, false):
			_pad_throw = true
		_r2_down[event.device] = down
	return ""

# ------------------------------------------------------------ held state

func _held_pad() -> Dictionary:
	var out := {"move_x": 0, "vertical": 0, "jump_held": false, "aim_stick": null}
	var best_aim := 0.0
	for d in _devices():
		var lx: float = Input.get_joy_axis(d, JOY_AXIS_LEFT_X)
		var ly: float = -Input.get_joy_axis(d, JOY_AXIS_LEFT_Y)    # SDL: down is positive
		var mx := int(lx >= MOVE_DEADZONE) - int(lx <= -MOVE_DEADZONE)
		mx += int(Input.is_joy_button_pressed(d, JOY_BUTTON_DPAD_RIGHT)) - int(Input.is_joy_button_pressed(d, JOY_BUTTON_DPAD_LEFT))
		var vy := int(ly >= VERTICAL_DEADZONE) - int(ly <= -VERTICAL_DEADZONE)
		vy += int(Input.is_joy_button_pressed(d, JOY_BUTTON_DPAD_UP)) - int(Input.is_joy_button_pressed(d, JOY_BUTTON_DPAD_DOWN))
		if out["move_x"] == 0:
			out["move_x"] = clampi(mx, -1, 1)
		if out["vertical"] == 0:
			out["vertical"] = clampi(vy, -1, 1)
		out["jump_held"] = out["jump_held"] or Input.is_joy_button_pressed(d, JOY_BUTTON_A)
		var rx: float = Input.get_joy_axis(d, JOY_AXIS_RIGHT_X)
		var ry: float = -Input.get_joy_axis(d, JOY_AXIS_RIGHT_Y)
		var mag := sqrt(rx * rx + ry * ry)
		if mag >= AIM_DEADZONE and mag > best_aim:
			best_aim = mag
			out["aim_stick"] = [rx, ry]
	return out

## Everything pressed or held since the last call. `cam_pos` is the world position of the screen's top-left corner
## and `zoom` the camera scale (the mouse is reported in world coordinates). `use_mouse` = false leaves the mouse to
## the other player.
func consume(viewport: Viewport, cam_pos: Vector2 = Vector2.ZERO, zoom: float = 1.0, use_mouse: bool = true):
	var pad := _held_pad()
	var i = Intent.new()
	var key_x := int(Input.is_key_pressed(keys["right"])) - int(Input.is_key_pressed(keys["left"]))
	var key_v := int(Input.is_key_pressed(keys["up"])) - int(Input.is_key_pressed(keys["down"]))
	i.move_x = key_x if key_x != 0 else pad["move_x"]
	i.vertical = key_v if key_v != 0 else pad["vertical"]
	i.jump_pressed = _pressed.has(keys["up"]) or _pad_jump
	i.z_pressed = _pressed.has(keys["grab"]) or _pad_grab
	i.x_pressed = _pressed.has(keys["throw"]) or _pad_throw
	i.jump_held = pad["jump_held"]
	i.aim_stick = pad["aim_stick"]
	if use_mouse and DisplayServer.window_is_focused():
		var m := viewport.get_mouse_position()
		i.mouse = [m.x / zoom + cam_pos.x, m.y / zoom + cam_pos.y]
	i.mouse_held = use_mouse and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and not _hold_on_button
	i.mouse_pressed = use_mouse and _mouse_pressed
	i.button_pressed = use_mouse and _button_pressed
	_pressed.clear()
	_pad_jump = false
	_pad_grab = false
	_pad_throw = false
	_mouse_pressed = false
	_button_pressed = false
	return i
