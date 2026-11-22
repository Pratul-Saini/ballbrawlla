extends SceneTree
## Prints every controller Godot sees and where its sticks rest (to find a stuck axis or a phantom device).
var _t := 0.0
func _process(d: float) -> bool:
	_t += d
	if _t < 1.0:
		return false
	var pads := Input.get_connected_joypads()
	print("PADS count=", pads.size())
	for p in pads:
		print("PADS id=%d name=%s guid=%s lx=%.2f ly=%.2f rx=%.2f ry=%.2f" % [p, Input.get_joy_name(p), Input.get_joy_guid(p),
				Input.get_joy_axis(p, JOY_AXIS_LEFT_X), Input.get_joy_axis(p, JOY_AXIS_LEFT_Y), Input.get_joy_axis(p, JOY_AXIS_RIGHT_X), Input.get_joy_axis(p, JOY_AXIS_RIGHT_Y)])
	quit(0)
	return true
