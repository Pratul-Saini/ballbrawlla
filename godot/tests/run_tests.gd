extends SceneTree
## Headless test runner:  godot --headless --path godot -s res://tests/run_tests.gd
## Runs every res://tests/test_*.gd. A test file extends TestCase and has methods named test_*.

var _failures := 0
var _passed := 0

var _ran := false

## Tests run on the first frame, not in _init/_initialize: the scene tree is fully started by then, like in the real game.
func _process(_delta: float) -> bool:
	if _ran:
		return false
	_ran = true
	_run_all()
	return true

func _run_all() -> void:
	var dir := DirAccess.open("res://tests")
	var files: Array[String] = []
	for f in dir.get_files():
		if f.begins_with("test_") and f.ends_with(".gd"):
			files.append(f)
	files.sort()
	for f in files:
		var script: GDScript = load("res://tests/" + f)
		if script == null or not script.can_instantiate():
			_failures += 1
			print("FAIL  %s: the script does not load (see the parse error above)" % f)
			continue
		var probe = script.new()
		for m in probe.get_method_list():
			if String(m.name).begins_with("test_"):
				var t = script.new()
				t.failures = []
				t.call(m.name)
				if t.failures.is_empty():
					_passed += 1
				else:
					_failures += 1
					print("FAIL  %s::%s" % [f, m.name])
					for msg in t.failures:
						print("      " + msg)
	print("%d passed, %d failed" % [_passed, _failures])
	quit(1 if _failures > 0 else 0)
