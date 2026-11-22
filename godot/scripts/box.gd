extends RefCounted
## Axis-aligned box; (x, y) is the top-left corner, y is down. Plain 64-bit floats, never Vector2 (which is 32-bit
## in Godot), so the simulation matches the Python game exactly.

var x: float
var y: float
var w: float
var h: float

func _init(px: float = 0.0, py: float = 0.0, pw: float = 0.0, ph: float = 0.0) -> void:
	x = px
	y = py
	w = pw
	h = ph

func left() -> float:
	return x

func right() -> float:
	return x + w

func top() -> float:
	return y

func bottom() -> float:
	return y + h

func center_x() -> float:
	return x + w / 2.0

func center_y() -> float:
	return y + h / 2.0

## Strict overlap: boxes that merely touch edges do not overlap.
func overlaps(o) -> bool:
	return left() < o.right() and right() > o.left() and top() < o.bottom() and bottom() > o.top()

func shifted(dx: float, dy: float):
	return get_script().new(x + dx, y + dy, w, h)

func to_array() -> Array:
	return [x, y, w, h]
