extends CanvasLayer
## Minimal 2-D overlay: a status line (score / down / clock), a center banner (results), and a hint line.

var _top: Label
var _center: Label
var _hint: Label
var _cross: Label

func _make(size: int, col: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	l.add_theme_constant_override("outline_size", 6)
	add_child(l)
	return l

func setup() -> void:
	# Fixed 1280x720 layout (prototype); plain positions, no anchors.
	_top = _make(22, Color(1, 1, 1))
	_top.position = Vector2(20, 14)
	_top.size = Vector2(1240, 30)
	_center = _make(40, Color(1, 0.95, 0.75))
	_center.position = Vector2(0, 120)
	_center.size = Vector2(1280, 60)
	_center.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint = _make(18, Color(0.85, 0.9, 1.0))
	_hint.position = Vector2(20, 684)
	_hint.size = Vector2(1240, 30)
	_cross = _make(26, Color(1, 1, 1, 0.8))
	_cross.position = Vector2(632, 344)
	_cross.text = ""

func set_top(t: String) -> void:
	_top.text = t

func set_center(t: String) -> void:
	_center.text = t

func set_hint(t: String) -> void:
	_hint.text = t

func set_cross(t: String) -> void:
	_cross.text = t
