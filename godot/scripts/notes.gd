extends Node
## Session notes: press F2 in any mode to write notes about this play session (src/ballbrawlla/notes.py).
## A session is one run of the game. Its notes live in
##     <user folder>/logs/sessions/<YYYY-MM-DD_HH-MM-SS>_<mode>_<level>/notes.md
## Every save in the same session rewrites that same file (reopening the panel brings back what you wrote); the next run
## of the game starts a new session and a new file. Notes are also saved when the game quits. While the panel is open,
## keystrokes go to the notes, never to your player.

const SESSIONS_ROOT := "user://logs/sessions"

## Where this session's notes are written. The file is created on the first save.
class SessionLog:
	var mode := ""
	var level := ""
	var started: Dictionary
	var id := ""
	var dir := ""
	var notes_path := ""

	func _init(p_mode: String, p_level: String, root: String = "user://logs/sessions", now: Dictionary = {}) -> void:
		mode = p_mode
		level = p_level
		started = now if not now.is_empty() else Time.get_datetime_dict_from_system()
		var base := "%s_%s_%s" % [_stamp(started, "-", "_"), SessionLog.slug(mode), SessionLog.slug(level)]
		id = base
		var n := 2
		while DirAccess.dir_exists_absolute("%s/%s" % [root, id]):   # two runs started in the same second
			id = "%s-%d" % [base, n]
			n += 1
		dir = "%s/%s" % [root, id]
		notes_path = "%s/notes.md" % dir

	static func slug(s: String) -> String:
		var out := ""
		var last_dash := true
		for ch in s:
			var u := ch.unicode_at(0)
			if (u >= 65 and u <= 90) or (u >= 97 and u <= 122) or (u >= 48 and u <= 57):
				out += ch
				last_dash = false
			elif not last_dash:
				out += "-"
				last_dash = true
		out = out.trim_suffix("-").to_lower()
		return out if out != "" else "level"

	static func _stamp(d: Dictionary, date_sep: String, joiner: String) -> String:
		return "%04d-%02d-%02d%s%02d-%02d-%02d" % [d["year"], d["month"], d["day"], joiner, d["hour"], d["minute"], d["second"]]

	## Write the notes, replacing this session's previous save. Returns the file path, or "" on failure.
	func save(text: String, context: String = "", now: Dictionary = {}) -> String:
		var when: Dictionary = now if not now.is_empty() else Time.get_datetime_dict_from_system()
		var header := [
			"# Session notes", "",
			"- Session: %s" % id,
			"- Mode: %s" % mode,
			"- Level: %s" % level,
			"- Started: %04d-%02d-%02d %02d:%02d:%02d" % [started["year"], started["month"], started["day"], started["hour"], started["minute"], started["second"]],
			"- Last saved: %04d-%02d-%02d %02d:%02d:%02d" % [when["year"], when["month"], when["day"], when["hour"], when["minute"], when["second"]],
		]
		if context != "":
			header.append("- At last save: %s" % context)
		DirAccess.make_dir_recursive_absolute(dir)
		var f := FileAccess.open(notes_path, FileAccess.WRITE)
		if f == null:
			return ""
		f.store_string("\n".join(header) + "\n\n" + text.rstrip(" \n\t") + "\n")
		f.close()
		return notes_path

var log: SessionLog
var is_open := false
var saved_text = null               # what's on disk (null = nothing saved yet)
var status := ""
var context_fn: Callable = Callable()
var _edit: TextEdit
var _layer: CanvasLayer

func setup(p_mode: String, p_level: String, p_context: Callable = Callable(), root: String = SESSIONS_ROOT) -> void:
	log = SessionLog.new(p_mode, p_level, root)
	context_fn = p_context

func text() -> String:
	return _edit.text if _edit != null else (saved_text if saved_text != null else "")

## Create the overlay (a text box over a dimmed screen). Called once, when the panel is first opened.
func _ensure_ui() -> void:
	if _layer != null:
		return
	_layer = CanvasLayer.new()
	_layer.layer = 50
	_layer.visible = false
	add_child(_layer)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	_layer.add_child(dim)
	var title := Label.new()
	title.text = "Session notes   (F2 or Esc: save and close,  Ctrl+S: save now)"
	title.position = Vector2(80, 50)
	_layer.add_child(title)
	_edit = TextEdit.new()
	_edit.position = Vector2(80, 90)
	_edit.size = Vector2(1120, 520)
	_edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_edit.placeholder_text = "What did you notice? What felt off? Anything to fix or try?"
	_layer.add_child(_edit)

func open_panel() -> void:
	_ensure_ui()
	is_open = true
	_layer.visible = true
	_edit.grab_focus()

func close_panel() -> void:
	save()
	is_open = false
	if _layer != null:
		_layer.visible = false
		get_viewport().gui_release_focus()

## Save if there's anything new. Returns the file written, or "".
func save() -> String:
	var t := text()
	if t.strip_edges() == "" or (saved_text != null and t == saved_text):
		return ""
	var ctx := ""
	if context_fn.is_valid():
		ctx = str(context_fn.call())
	var path := log.save(t, ctx)
	if path != "":
		saved_text = t
		var d := Time.get_datetime_dict_from_system()
		status = "saved at %02d:%02d:%02d" % [d["hour"], d["minute"], d["second"]]
	return path

## Feed an event in. Returns true if the notes used it (don't pass it on).
func handle_event(event: InputEvent) -> bool:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F2:
			if is_open:
				close_panel()
			else:
				open_panel()
			get_viewport().set_input_as_handled()
			return true
		if is_open and event.keycode == KEY_ESCAPE:
			close_panel()
			get_viewport().set_input_as_handled()
			return true
		if is_open and event.keycode == KEY_S and (event.ctrl_pressed or event.meta_pressed):
			save()
			get_viewport().set_input_as_handled()
			return true
	return is_open     # while open, the panel takes every other event too

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		if log != null and _edit != null:
			save()
