extends RefCounted
## One player's input for one tick (src/ballbrawlla/input.py). The simulation only ever sees an Intent.

var move_x: int = 0              # -1 left, 0, +1 right (held)
var vertical: int = 0            # +1 up, 0, -1 down (held)
var jump_pressed: bool = false
var z_pressed: bool = false      # pick up / tag / confirm / enter or cancel aim
var x_pressed: bool = false      # throw / lock in
var slide_pressed: bool = false  # Circle (controller): start a slide, or cancel one in progress
var jump_held: bool = false
var aim_stick = null             # null, or [x, y] with y up
# Mouse (play call). Position is in world coordinates.
var mouse = null                 # null, or [x, y]
var mouse_held := false
var mouse_pressed := false
var button_pressed := false      # the on-screen play-call button was clicked

func up_held() -> bool:
	return vertical > 0 or jump_held

func down_held() -> bool:
	return vertical < 0

## [move_x, vertical, jump, z, x, jump_held, aim_stick, mouse, mouse_held, mouse_pressed, button] as exported by
## tools/export_parity.py. Rows shorter than 11 (older scenarios) leave the mouse fields at their defaults.
static func from_array(a: Array):
	var i = load("res://scripts/intent.gd").new()
	i.move_x = int(a[0])
	i.vertical = int(a[1])
	i.jump_pressed = int(a[2]) != 0
	i.z_pressed = int(a[3]) != 0
	i.x_pressed = int(a[4]) != 0
	i.jump_held = int(a[5]) != 0
	i.aim_stick = null if a[6] == null else [float(a[6][0]), float(a[6][1])]
	if a.size() >= 11:
		i.mouse = null if a[7] == null else [float(a[7][0]), float(a[7][1])]
		i.mouse_held = int(a[8]) != 0
		i.mouse_pressed = int(a[9]) != 0
		i.button_pressed = int(a[10]) != 0
	return i
