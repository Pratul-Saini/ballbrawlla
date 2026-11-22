extends Node
## Background music: every audio file in assets/music/ plays in name order, then the list starts over, forever
## (src/ballbrawlla/music.py). No files means no music and no complaint. One file loops on its own. The music plays at
## menu volume in the menus and at a lower volume during a game; M mutes it.
##
## Files are looked for next to the game first (so players can drop their own in a packaged build), then inside it.
## A file that won't load is skipped; if none will load the game stays silent. BALLBRAWLLA_MUSIC=off turns music off
## completely (the tests do). Add this as an autoload, or create one and add_child it.

const EXTENSIONS := ["mp3", "ogg", "wav"]
const VOLUME := {"menu": 0.7, "game": 0.25}

var tracks: Array = []         # paths
var index := 0
var playing := false
var muted := false
var context := "menu"
var _player: AudioStreamPlayer

static func enabled() -> bool:
	return not OS.get_environment("BALLBRAWLLA_MUSIC").to_lower() in ["off", "0", "no"]

## Every audio file in a folder, in name order (case-insensitive). Empty if the folder is missing or has none.
static func find_tracks(folder: String) -> Array:
	var out: Array = []
	var dir := DirAccess.open(folder)
	if dir == null:
		return out
	for f in dir.get_files():
		if f.begins_with("."):
			continue
		var ext := f.get_extension().to_lower()
		if EXTENSIONS.has(ext):
			out.append("%s/%s" % [folder, f])
		elif ext == "import":       # exported/imported projects list "song.mp3.import": the song itself is next to it
			var base := f.trim_suffix(".import")
			if EXTENSIONS.has(base.get_extension().to_lower()) and not out.has("%s/%s" % [folder, base]):
				out.append("%s/%s" % [folder, base])
	out.sort_custom(func(a, b): return a.get_file().to_lower() < b.get_file().to_lower())
	return out

## A cheap check of the file's first bytes, so a text file renamed .mp3 is skipped without noise.
static func looks_like(ext: String, bytes: PackedByteArray) -> bool:
	if bytes.size() < 12:
		return false
	match ext:
		"wav":
			return bytes.slice(0, 4).get_string_from_ascii() == "RIFF" and bytes.slice(8, 12).get_string_from_ascii() == "WAVE"
		"ogg":
			return bytes.slice(0, 4).get_string_from_ascii() == "OggS"
		"mp3":
			# An ID3 tag, or an MPEG audio frame sync (11 set bits).
			return bytes.slice(0, 3).get_string_from_ascii() == "ID3" or (bytes[0] == 0xFF and (bytes[1] & 0xE0) == 0xE0)
	return false

## The folders searched, best first: beside the game, then the project's own assets.
static func music_folders() -> Array:
	var folders: Array = []
	var beside := OS.get_executable_path().get_base_dir().path_join("assets/music")
	folders.append(beside)
	folders.append("res://assets/music")
	return folders

static func load_stream(path: String):
	if path.begins_with("res://"):
		var res = load(path)
		return res if res is AudioStream else null
	var ext := path.get_extension().to_lower()
	var bytes := FileAccess.get_file_as_bytes(path)
	if not looks_like(ext, bytes):
		return null       # not even the right kind of file: skip it quietly instead of making the decoder complain
	if ext == "mp3":
		var s := AudioStreamMP3.new()
		s.data = bytes
		return s if s.get_length() > 0.0 else null
	if ext == "ogg":
		var s2 := AudioStreamOggVorbis.load_from_buffer(bytes)
		return s2
	if ext == "wav":
		return AudioStreamWAV.load_from_buffer(bytes)
	return null

## Begin playing the list from `folders` (default: the usual places). Returns true if music is playing.
func start(folders: Array = []) -> bool:
	if playing or not enabled():
		return playing
	tracks = []
	for f in (folders if not folders.is_empty() else music_folders()):
		tracks = find_tracks(f)
		if not tracks.is_empty():
			break
	if tracks.is_empty():
		return false
	if _player == null:
		_player = AudioStreamPlayer.new()
		_player.finished.connect(_on_finished)
		add_child(_player)
	index = 0
	playing = _play_from(0)
	return playing

func _play_from(first: int) -> bool:
	var n := tracks.size()
	for step in n:
		var i := (first + step) % n
		var stream = load_stream(tracks[i])
		if stream == null:
			continue
		if n == 1 and stream.has_method("set_loop"):
			stream.set_loop(true)           # a single track repeats by itself
		_player.stream = stream
		_player.volume_db = linear_to_db(maxf(volume(), 0.0001))
		_player.play()
		index = i
		return true
	return false

func volume() -> float:
	return 0.0 if muted else VOLUME[context]

## When a track ends, start the next one (the first again after the last).
func _on_finished() -> void:
	if playing and tracks.size() > 1:
		playing = _play_from(index + 1)
	elif playing and tracks.size() == 1:
		_player.play()

func set_context(p_context: String) -> void:
	context = p_context
	_apply_volume()

func toggle_mute() -> bool:
	muted = not muted
	_apply_volume()
	return muted

## M toggles mute. Returns true if the event was used. Don't call this while text is being typed.
func handle_event(event: InputEvent) -> bool:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_M and not event.ctrl_pressed and not event.meta_pressed:
		toggle_mute()
		return true
	return false

func _apply_volume() -> void:
	if playing and _player != null:
		_player.volume_db = -80.0 if muted else linear_to_db(VOLUME[context])

func stop() -> void:
	if playing and _player != null:
		_player.stop()
	playing = false

func current() -> String:
	return tracks[index] if playing and not tracks.is_empty() else ""
