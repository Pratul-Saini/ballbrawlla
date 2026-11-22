extends RefCounted
## Diagnostics: one log file per run, so a problem can be read instead of described (src/ballbrawlla/diag.py).
##
##     <user folder>/logs/run-<id>.log      this run (the five newest are kept)
##     <user folder>/logs/latest.log        the path of the newest run's log, one line
##
## It records the machine and engine, the window, a heartbeat every two seconds with the frame rate, any frame that took
## over 100 ms, menu and launch decisions, and every error. A problem writing the log must never stop the game.

const KEEP := 5
const HEARTBEAT_SECONDS := 2.0
const SLOW_FRAME_MS := 100.0

var path := ""
var _file: FileAccess
var _last_beat := 0.0
var _since := 0.0
var _frames := 0
var _worst := 0.0
var where_name := "startup"

## Open a new log file. Returns the path, or "" if the log could not be created.
func setup(dir: String = "user://logs") -> String:
	DirAccess.make_dir_recursive_absolute(dir)
	_prune(dir)
	var stamp := Time.get_datetime_dict_from_system()
	path = "%s/run-%04d%02d%02d-%02d%02d%02d-%d.log" % [dir, stamp["year"], stamp["month"], stamp["day"], stamp["hour"],
			stamp["minute"], stamp["second"], OS.get_process_id()]
	_file = FileAccess.open(path, FileAccess.WRITE)
	if _file == null:
		path = ""
		return ""
	var latest := FileAccess.open("%s/latest.log" % dir, FileAccess.WRITE)
	if latest != null:
		latest.store_string(ProjectSettings.globalize_path(path) + "\n")
		latest.close()
	info("start: Godot %s on %s %s, args=%s" % [Engine.get_version_info()["string"], OS.get_name(), OS.get_version(), str(OS.get_cmdline_user_args())])
	info("video=%s renderer=%s screens=%d" % [DisplayServer.get_name(), RenderingServer.get_video_adapter_name(), DisplayServer.get_screen_count()])
	_last_beat = Time.get_ticks_msec() / 1000.0
	_since = _last_beat
	return path

func _prune(dir: String) -> void:
	var d := DirAccess.open(dir)
	if d == null:
		return
	var logs: Array = Array(d.get_files()).filter(func(f): return f.begins_with("run-") and f.ends_with(".log"))
	logs.sort()
	while logs.size() >= KEEP:
		d.remove(logs.pop_front())

func _write(level: String, msg: String) -> void:
	if _file == null:
		return
	var t := Time.get_time_dict_from_system()
	_file.store_line("%02d:%02d:%02d.%03d %-7s %s" % [t["hour"], t["minute"], t["second"], Time.get_ticks_msec() % 1000, level, msg])
	_file.flush()

func info(msg: String) -> void:
	_write("INFO", msg)

func warn(msg: String) -> void:
	_write("WARNING", msg)

func error(msg: String) -> void:
	_write("ERROR", msg)

## Say what the main loop is doing (shown in heartbeats).
func where(name: String) -> void:
	if where_name != name:
		info("now in: %s" % name)
	where_name = name

## Call once per frame from every loop: writes the heartbeat and flags slow frames.
func beat() -> void:
	var now := Time.get_ticks_msec() / 1000.0
	var gap := (now - _last_beat) * 1000.0
	if gap > SLOW_FRAME_MS and _frames > 0:
		warn("slow frame: %.0f ms since the last frame (in %s)" % [gap, where_name])
	if _frames > 0:
		_worst = maxf(_worst, gap)
	_last_beat = now
	_frames += 1
	if now - _since >= HEARTBEAT_SECONDS:
		info("heartbeat in %s: %.0f fps, worst frame %.0f ms" % [where_name, _frames / (now - _since), _worst])
		_frames = 0
		_worst = 0.0
		_since = now

func close() -> void:
	info("exit")
	if _file != null:
		_file.close()
		_file = null
