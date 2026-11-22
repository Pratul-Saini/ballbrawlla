extends "res://tests/test_case.gd"
## The in-game pause menu (mirrors the pause tests in tests/test_menu.py).

const PauseMenu = preload("res://scripts/pause_menu.gd")

func _key(code: int) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = code
	e.pressed = true
	return e

func _pad(button: int) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.button_index = button
	e.pressed = true
	return e

func test_pause_menu_flow() -> void:
	var p := PauseMenu.new()
	check(not p.handle_event(_key(KEY_LEFT)) and not p.freezes(), "closed: the game gets the key")
	check(p.handle_event(_key(KEY_ESCAPE)) and p.freezes(), "Esc opens it and freezes the game")
	check(p.handle_event(_key(KEY_LEFT)), "open: the game gets nothing")
	p.handle_event(_key(KEY_DOWN))
	p.handle_event(_key(KEY_ENTER))
	check_eq(p.page, "controls", "CONTROLS opens the key list")
	p.handle_event(_key(KEY_A))
	check_eq(p.page, "menu", "any key goes back")
	p.handle_event(_key(KEY_ESCAPE))
	check(not p.is_open, "Esc resumes")
	p.handle_event(_key(KEY_ESCAPE))
	p.handle_event(_key(KEY_UP))        # wraps to MAIN MENU
	p.handle_event(_key(KEY_ENTER))
	check_eq(p.result, "menu", "MAIN MENU asks to leave")
	check(not p.is_open, "and closes")

func test_network_games_are_not_frozen_by_the_menu() -> void:
	var p := PauseMenu.new([], false)
	p.handle_event(_key(KEY_ESCAPE))
	check(p.is_open and not p.freezes(), "open but the game keeps running")

func test_mouse_picks_a_row_and_a_click_leaves_the_controls_page() -> void:
	var p := PauseMenu.new()
	p.handle_event(_key(KEY_ESCAPE))
	var size := Vector2(1280, 720)
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = p.item_rects(size)[1].get_center()
	p.handle_event(click, size)
	check_eq(p.page, "controls", "clicking CONTROLS opens it")
	p.handle_event(click, size)
	check_eq(p.page, "menu", "a click goes back")
	click.position = Vector2(2, 2)
	p.handle_event(click, size)
	check(p.is_open and p.result == "", "a click on empty space does nothing")
	click.position = p.item_rects(size)[2].get_center()
	p.handle_event(click, size)
	check_eq(p.result, "menu", "clicking MAIN MENU")

func test_pad_works_in_the_pause_menu() -> void:
	var p := PauseMenu.new()
	p.handle_event(_key(KEY_ESCAPE))
	p.handle_event(_pad(JOY_BUTTON_DPAD_DOWN))
	p.handle_event(_pad(JOY_BUTTON_X))           # Square selects, like Cross
	check_eq(p.page, "controls")
	p.handle_event(_key(KEY_A))
	p.handle_event(_pad(JOY_BUTTON_B))           # Circle closes
	check(not p.is_open, "Circle closes the menu")

func test_the_hint_badge_takes_no_input() -> void:
	var p := PauseMenu.new()
	check(not p.handle_event(InputEventMouseMotion.new()), "mouse motion is not captured while closed")
	check(not p.handle_event(_pad(JOY_BUTTON_A)), "pad buttons are not captured while closed")

func test_controls_lists_cover_the_mute_key_and_both_players() -> void:
	check(PauseMenu.COMMON.any(func(l): return "mute" in l), "single player lists the music key")
	check(PauseMenu.LOCAL.any(func(l): return "Blue" in l) and PauseMenu.LOCAL.any(func(l): return "Red" in l), "local lists both")
