extends "res://tests/test_case.gd"
## Music: every file in the folder plays in order and loops; no files means silence; nothing takes the game down.

const Music = preload("res://scripts/music.gd")

## A Music node placed in the scene tree (an AudioStreamPlayer can only play from inside it).
func _music() -> Node:
	var m := Music.new()
	Engine.get_main_loop().root.add_child(m)
	return m

func _done(m: Node) -> void:
	m.stop()
	Engine.get_main_loop().root.remove_child(m)
	m.free()

func _tmp_dir(name: String) -> String:
	var d := "user://music_test_%s" % name
	DirAccess.make_dir_recursive_absolute(d)
	var dir := DirAccess.open(d)
	for f in dir.get_files():
		dir.remove(f)
	return d

func _touch(folder: String, name: String, bytes: PackedByteArray = PackedByteArray([1, 2, 3])) -> void:
	var f := FileAccess.open("%s/%s" % [folder, name], FileAccess.WRITE)
	f.store_buffer(bytes)
	f.close()

func _wav_bytes(seconds: float = 0.2) -> PackedByteArray:
	var rate := 22050
	var n := int(rate * seconds)
	var data := PackedByteArray()
	data.resize(n * 2)
	for i in n:
		data.encode_s16(i * 2, int(8000.0 * sin(i / 8.0)))
	var out := PackedByteArray()
	out.append_array("RIFF".to_ascii_buffer())
	var size := PackedByteArray()
	size.resize(4)
	size.encode_u32(0, 36 + data.size())
	out.append_array(size)
	out.append_array("WAVEfmt ".to_ascii_buffer())
	var hdr := PackedByteArray()
	hdr.resize(16)
	hdr.encode_u32(0, 16)
	hdr.encode_u16(4, 1)
	hdr.encode_u16(6, 1)
	hdr.encode_u32(8, rate)
	hdr.encode_u32(12, rate * 2)
	out.append_array(hdr)
	var tail := PackedByteArray()
	tail.resize(4)
	tail.encode_u16(0, 2)
	tail.encode_u16(2, 16)
	out.append_array(tail)
	out.append_array("data".to_ascii_buffer())
	var dsize := PackedByteArray()
	dsize.resize(4)
	dsize.encode_u32(0, data.size())
	out.append_array(dsize)
	out.append_array(data)
	return out

func test_missing_or_empty_folder_means_no_tracks() -> void:
	check_eq(Music.find_tracks("user://nope_not_here"), [], "missing folder")
	check_eq(Music.find_tracks(_tmp_dir("empty")), [], "empty folder")

func test_every_audio_file_is_found_in_name_order_and_the_rest_ignored() -> void:
	var d := _tmp_dir("order")
	for n in ["b_song.mp3", "A_song.ogg", "10_last.wav", "notes.txt", ".hidden.mp3", "cover.png"]:
		_touch(d, n)
	var got := Music.find_tracks(d).map(func(p): return p.get_file())
	check_eq(got, ["10_last.wav", "A_song.ogg", "b_song.mp3"])

func test_the_shipped_folder_lists_only_audio_not_the_readme() -> void:
	# The folder ships empty, but a player may drop their own tracks in: whatever is there
	# must be audio (the README is never mistaken for music), the same as the Python side.
	var found := Music.find_tracks("res://assets/music")
	for p in found:
		check(Music.EXTENSIONS.has(p.get_extension().to_lower()), "only audio is listed, not %s" % p)
	check(not found.map(func(p): return p.get_file()).has("README.txt"), "the README is never mistaken for music")

func test_off_switch_means_nothing_loads() -> void:
	OS.set_environment("BALLBRAWLLA_MUSIC", "off")
	var m := _music()
	check_eq(m.start([_tmp_dir("off")]), false)
	_done(m)

func test_empty_folder_stays_silent_and_quiet() -> void:
	OS.set_environment("BALLBRAWLLA_MUSIC", "on")
	var m := _music()
	check_eq(m.start([_tmp_dir("silent")]), false)
	check(not m.playing and m.current() == "", "nothing playing")
	m.toggle_mute()
	m.set_context("game")
	_done(m)
	OS.set_environment("BALLBRAWLLA_MUSIC", "off")

func test_a_folder_of_unreadable_files_stays_silent() -> void:
	OS.set_environment("BALLBRAWLLA_MUSIC", "on")
	var d := _tmp_dir("bad")
	_touch(d, "a.mp3")
	_touch(d, "b.ogg")
	var m := _music()
	check_eq(m.start([d]), false, "nothing could be played")
	check(not m.playing, "and it says so")
	_done(m)
	OS.set_environment("BALLBRAWLLA_MUSIC", "off")

func test_an_unreadable_file_is_skipped_and_the_rest_play() -> void:
	OS.set_environment("BALLBRAWLLA_MUSIC", "on")
	var d := _tmp_dir("skip")
	_touch(d, "01_bad.ogg")
	_touch(d, "02_good.wav", _wav_bytes())
	var m := _music()
	var ok: bool = m.start([d])
	check(ok and m.current().ends_with("02_good.wav"), "played the good one (got '%s')" % m.current())
	_done(m)
	OS.set_environment("BALLBRAWLLA_MUSIC", "off")

func test_mute_and_context_change_the_volume_and_m_toggles_mute() -> void:
	var m := Music.new()
	check_near(m.volume(), Music.VOLUME["menu"], 1e-9, "menu volume")
	m.set_context("game")
	check_near(m.volume(), Music.VOLUME["game"], 1e-9, "game volume is lower")
	check(Music.VOLUME["game"] < Music.VOLUME["menu"], "games are quieter than menus")
	var press := func(key: int, ctrl: bool) -> InputEventKey:
		var e := InputEventKey.new()
		e.keycode = key
		e.pressed = true
		e.ctrl_pressed = ctrl
		return e
	check(m.handle_event(press.call(KEY_M, false)) and m.muted, "M mutes")
	check_near(m.volume(), 0.0, 1e-9, "muted volume")
	check(not m.handle_event(press.call(KEY_M, true)) and m.muted, "Ctrl+M is not the mute key")
	check(not m.handle_event(press.call(KEY_A, false)), "other keys are not used")
	m.set_context("menu")
	check_near(m.volume(), 0.0, 1e-9, "stays muted across contexts")
	m.toggle_mute()
	check_near(m.volume(), Music.VOLUME["menu"], 1e-9, "unmuted")
	m.free()

func test_files_are_recognised_by_their_first_bytes() -> void:
	check(Music.looks_like("wav", _wav_bytes()), "a real wav")
	check(not Music.looks_like("wav", "this is just a text file".to_utf8_buffer()), "text renamed .wav")
	check(not Music.looks_like("ogg", _wav_bytes()), "a wav renamed .ogg")
	check(Music.looks_like("mp3", PackedByteArray([0x49, 0x44, 0x33, 3, 0, 0, 0, 0, 0, 0, 0, 0])), "an ID3-tagged mp3")
	check(Music.looks_like("mp3", PackedByteArray([0xFF, 0xFB, 0x90, 0, 0, 0, 0, 0, 0, 0, 0, 0])), "a bare mp3 frame")
	check(not Music.looks_like("mp3", PackedByteArray()), "an empty file")
