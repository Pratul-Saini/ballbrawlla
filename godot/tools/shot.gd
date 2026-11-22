extends SceneTree
## Take a screenshot of a scene after a short time:  Godot --path godot -s res://tools/shot.gd -- SCENE OUT.png [SECONDS] [setup=...]
## For the launcher, "setup" can be a path of menu choices such as "play,freeplay,explore" to open deeper screens.
var _scene := ""
var _out := ""
var _wait := 1.5
var _t := 0.0
var _setup := ""
var _node
func _process(delta: float) -> bool:
	if _node == null:
		var a := OS.get_cmdline_user_args()
		_scene = a[0]
		_out = a[1]
		if a.size() > 2:
			_wait = float(a[2])
		if a.size() > 3:
			_setup = a[3]
		_node = load(_scene).instantiate()
		root.add_child(_node)
		return false
	_t += delta
	if _setup != "" and _node.has_method("_ready") and _node.get("state") != null and _t > 0.3 and _t < 0.4:
		for step in _setup.split(","):
			var items: Array = _node.state.items()
			for k in items.size():
				if items[k].label.to_lower().begins_with(step.to_lower()):
					_node.state.cursor = k
			_node.state.select()
	if _t > _wait:
		root.get_viewport().get_texture().get_image().save_png(_out)
		print("SHOT saved ", _out)
		quit(0)
		return true
	return false
