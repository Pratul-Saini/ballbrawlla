extends SceneTree
## Plays every file in a folder through the real audio path for a few seconds and prints each track change.
##   Godot --headless --path godot -s res://tools/music_probe.gd -- FOLDER SECONDS
const Music = preload("res://scripts/music.gd")
var _m
var _t0 := 0.0
var _seen: Array = []
var _secs := 5.0
func _process(_d: float) -> bool:
	if _m == null:
		var args := OS.get_cmdline_user_args()
		OS.set_environment("BALLBRAWLLA_MUSIC", "on")
		_secs = float(args[1])
		_m = Music.new()
		root.add_child(_m)
		print("PROBE started=", _m.start([args[0]]), " tracks=", _m.tracks.size())
		_t0 = Time.get_ticks_msec() / 1000.0
		return false
	var c: String = _m.current()
	if c != "" and (_seen.is_empty() or _seen[-1] != c):
		_seen.append(c)
		print("PROBE now playing ", c.get_file())
	if Time.get_ticks_msec() / 1000.0 - _t0 > _secs:
		print("PROBE changes=", _seen.size(), " sequence=", ",".join(_seen.map(func(p): return p.get_file())))
		quit(0)
		return true
	return false
