extends "res://tests/test_case.gd"
## Session notes files and the per-run log (mirrors tests/test_notes.py).

const Notes = preload("res://scripts/notes.gd")
const Diag = preload("res://scripts/diag.gd")

func _clean(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	var d := DirAccess.open(dir)
	for sub in d.get_directories():
		_clean("%s/%s" % [dir, sub])
		d.remove(sub)
	for f in d.get_files():
		d.remove(f)

const WHEN := {"year": 2026, "month": 11, "day": 22, "hour": 3, "minute": 4, "second": 5}

func test_slugs_are_filename_safe() -> void:
	check_eq(Notes.SessionLog.slug("Field 05"), "field-05")
	check_eq(Notes.SessionLog.slug("  Caverns!! "), "caverns")
	check_eq(Notes.SessionLog.slug("***"), "level", "nothing usable falls back")
	check_eq(Notes.SessionLog.slug("local 2-player"), "local-2-player")

func test_a_session_has_one_file_named_by_time_mode_and_level() -> void:
	var root := "user://notes_test"
	_clean(root)
	var log := Notes.SessionLog.new("practice", "Field 05", root, WHEN)
	check_eq(log.id, "2026-11-22_03-04-05_practice_field-05")
	check_eq(log.notes_path, root + "/2026-11-22_03-04-05_practice_field-05/notes.md")
	check(not FileAccess.file_exists(log.notes_path), "the file is created on the first save, not before")
	var path := log.save("first thoughts", "Blue 0 - 0 Red, 1st down", WHEN)
	check_eq(path, log.notes_path)
	var text := FileAccess.get_file_as_string(path)
	check("# Session notes" in text and "- Mode: practice" in text and "- Level: Field 05" in text, text)
	check("- Started: 2026-11-22 03:04:05" in text and "- At last save: Blue 0 - 0 Red, 1st down" in text, text)
	check(text.ends_with("first thoughts\n"), "the notes end the file with one newline")
	log.save("rewritten", "", WHEN)
	var again := FileAccess.get_file_as_string(log.notes_path)
	check("rewritten" in again and not "first thoughts" in again, "a second save replaces the first")
	check(not "At last save" in again, "no context line when there is none")

func test_two_sessions_started_in_the_same_second_get_different_folders() -> void:
	var root := "user://notes_test2"
	_clean(root)
	var a := Notes.SessionLog.new("local", "Field 01", root, WHEN)
	a.save("a", "", WHEN)
	var b := Notes.SessionLog.new("local", "Field 01", root, WHEN)
	b.save("b", "", WHEN)
	var c := Notes.SessionLog.new("local", "Field 01", root, WHEN)
	check(a.id != b.id and b.id != c.id and a.id != c.id, "ids %s %s %s" % [a.id, b.id, c.id])
	check_eq(b.id, a.id + "-2")
	check("a" in FileAccess.get_file_as_string(a.notes_path) and "b" in FileAccess.get_file_as_string(b.notes_path), "neither overwrote the other")

func test_the_notes_node_saves_once_and_skips_empty_or_unchanged_text() -> void:
	var root := "user://notes_test3"
	_clean(root)
	var n := Notes.new()
	Engine.get_main_loop().root.add_child(n)
	n.setup("catch", "Field 03", func(): return "ctx", root)
	check_eq(n.save(), "", "nothing to save yet")
	n.open_panel()
	check(n.is_open, "opens")
	n._edit.text = "   \n  "
	check_eq(n.save(), "", "whitespace only is not worth a file")
	n._edit.text = "the throw felt late"
	check(n.save() != "", "saves real text")
	check_eq(n.save(), "", "unchanged text is not rewritten")
	n.close_panel()
	check(not n.is_open, "closes")
	check("the throw felt late" in FileAccess.get_file_as_string(n.log.notes_path), "on disk")
	check("At last save: ctx" in FileAccess.get_file_as_string(n.log.notes_path), "with the context")
	Engine.get_main_loop().root.remove_child(n)
	n.free()

func test_f2_toggles_and_the_open_panel_swallows_other_keys() -> void:
	var root := "user://notes_test4"
	_clean(root)
	var n := Notes.new()
	Engine.get_main_loop().root.add_child(n)
	n.setup("local", "Field 01", Callable(), root)
	var key := func(code: int) -> InputEventKey:
		var e := InputEventKey.new()
		e.keycode = code
		e.pressed = true
		return e
	check(not n.handle_event(key.call(KEY_Z)), "closed: keys go to the game")
	check(n.handle_event(key.call(KEY_F2)) and n.is_open, "F2 opens")
	check(n.handle_event(key.call(KEY_Z)), "open: even other keys are the notes'")
	check(n.handle_event(key.call(KEY_ESCAPE)) and not n.is_open, "Esc closes")
	check(n.handle_event(key.call(KEY_F2)) and n.is_open, "F2 opens again")
	check(n.handle_event(key.call(KEY_F2)) and not n.is_open, "F2 closes")
	Engine.get_main_loop().root.remove_child(n)
	n.free()

func test_diag_writes_a_log_keeps_only_a_few_and_never_throws() -> void:
	var dir := "user://diag_test"
	_clean(dir)
	for k in 8:
		var d := Diag.new()
		var p := d.setup(dir)
		check(p != "", "log %d created" % k)
		d.info("hello %d" % k)
		d.where("menu")
		d.beat()
		d.warn("careful")
		d.error("oops")
		d.close()
		OS.delay_msec(5)
	var logs := Array(DirAccess.open(dir).get_files()).filter(func(f): return f.begins_with("run-"))
	check(logs.size() <= Diag.KEEP, "kept %d logs, limit %d" % [logs.size(), Diag.KEEP])
	var latest := FileAccess.get_file_as_string(dir + "/latest.log").strip_edges()
	check(latest.ends_with(".log") and FileAccess.file_exists(latest), "latest.log points at a real file: " + latest)
	var text := FileAccess.get_file_as_string(latest)
	check("INFO" in text and "WARNING careful" in text and "ERROR   oops" in text and "now in: menu" in text, text)
	# A logger whose file never opened (unwritable folder, full disk) must be harmless to call.
	var broken := Diag.new()
	broken.info("this goes nowhere")
	broken.warn("nor this")
	broken.error("nor this")
	broken.where("menu")
	broken.beat()
	broken.beat()
	broken.close()
	check_eq(broken.path, "", "no file, no path")
