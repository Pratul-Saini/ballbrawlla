extends "res://tests/test_case.gd"
## The menu's logic: which screens exist, what each choice does, what is greyed out and why (mirrors tests/test_menu.py).

const MenuState = preload("res://scripts/menu_state.gd")
const Launch = preload("res://scripts/launch.gd")
const Invite = preload("res://scripts/invite.gd")
const Discovery = preload("res://scripts/discovery.gd")

## A finder that never touches the network: tests fill `games` by hand.
class FakeFinder:
	var available := true
	var found: Array = []
	func poll() -> Array:
		return found
	func close() -> void:
		available = false

func _menu():
	return MenuState.new()

func _labels(m) -> Array:
	return m.items().map(func(i): return i.label.split(":")[0])

func _goto(m, label: String) -> void:
	m.cursor = _labels(m).find(label)
	check(m.cursor >= 0, "'%s' is not on the %s screen (has %s)" % [label, m.screen, str(_labels(m))])
	if m.cursor >= 0:
		m.select()

func _with_relay(on: bool) -> void:
	OS.set_environment(Invite.RELAY_ENV, "relay.example.com" if on else "")

func test_main_and_play_menus() -> void:
	var m = _menu()
	check_eq(_labels(m), ["PLAY", "QUIT"])
	_goto(m, "PLAY")
	check_eq(_labels(m), ["FREE PLAY", "TWO PLAYERS", "ONLINE"])
	_goto(m, "FREE PLAY")
	check_eq(_labels(m), ["EXPLORE", "CATCH PRACTICE"])

func test_free_play_lists_every_level_and_launches_one() -> void:
	var m = _menu()
	_goto(m, "PLAY")
	_goto(m, "FREE PLAY")
	_goto(m, "EXPLORE")
	check_eq(m.screen, "level")
	check(m.result == null, "choosing a mode does not start it yet")
	var keys := m.shown_levels().map(func(i): return i.key)
	check(keys.has("arena_01") and keys.size() == 15, "free play shows all 15 levels")
	m.cursor = keys.find("field_05")
	m.select()
	check_eq(m.result["mode"], "sandbox")
	check(m.result["level"].ends_with("field_05.json"), "the picked level")

func test_free_play_can_launch_the_arena() -> void:
	var m = _menu()
	_goto(m, "PLAY")
	_goto(m, "FREE PLAY")
	_goto(m, "EXPLORE")
	m.cursor = m.shown_levels().map(func(i): return i.key).find("arena_01")
	m.select()
	check_eq(m.result["mode"], "sandbox")
	check(m.result["level"].ends_with("arena_01.json"), "arena level")

func test_match_modes_only_list_football_fields() -> void:
	for pair in [["TWO PLAYERS", "local"], ["CATCH PRACTICE", "catch"]]:
		var m = _menu()
		_goto(m, "PLAY")
		if pair[1] == "catch":
			_goto(m, "FREE PLAY")
		_goto(m, pair[0])
		var keys := m.shown_levels().map(func(i): return i.key)
		check(not keys.has("arena_01") and keys.size() == 14, "%s lists 14 football fields" % pair[1])
		m.cursor = keys.find("field_09")
		m.select()
		check_eq(m.result["mode"], pair[1])
		check(m.result["level"].ends_with("field_09.json"), "level for " + pair[1])

func test_escape_walks_back_one_screen_then_quits() -> void:
	var m = _menu()
	_goto(m, "PLAY")
	_goto(m, "FREE PLAY")
	_goto(m, "EXPLORE")
	m.back()
	check_eq(m.screen, "freeplay")
	m.back()
	check_eq(m.screen, "play")
	m.back()
	check_eq(m.screen, "main")
	check(not m.quit, "backing out of the main screen does not quit by itself")
	_goto(m, "QUIT")
	check(m.quit, "QUIT quits")

func test_selecting_a_greyed_item_shows_its_reason_and_launches_nothing() -> void:
	var m = _join_screen()
	check(not m.items()[2].enabled(), "CONNECT is greyed with no code")
	m.cursor = 2
	m.select()
	check(m.error != "" and m.result == null, "a reason is shown, nothing starts")
	m.back()
	check_eq(m.error, "", "any key dismisses the dialog")

func test_online_screen_is_host_or_join_and_needs_no_relay() -> void:
	_with_relay(false)
	var m = _menu()
	_goto(m, "PLAY")
	_goto(m, "ONLINE")
	check_eq(_labels(m), ["HOST GAME", "JOIN GAME"])
	check(m.items()[1].enabled(), "joining needs no relay")
	if m.items()[0].enabled():          # (greyed only if a game on this machine holds the port)
		_goto(m, "HOST GAME")
		check(m.screen == "level" and m.mode == "host", "hosting picks a level")

func test_a_broken_level_is_greyed_in_the_picker() -> void:
	var bad := Launch.LevelInfo.new()
	bad.key = "broken"
	bad.level_name = "broken"
	bad.path = "res://levels/broken.json"
	bad.error = "not valid JSON (x, line 1)"
	var m = MenuState.new([bad])
	_goto(m, "PLAY")
	_goto(m, "FREE PLAY")
	_goto(m, "EXPLORE")
	check(not m.items()[0].enabled(), "greyed")
	m.select()
	check(m.error != "" and m.result == null, "its problem is shown, nothing starts")

# ---- join a game

func _join_screen():
	var m = _menu()
	m.finder_factory = func(): return FakeFinder.new()
	_goto(m, "PLAY")
	_goto(m, "ONLINE")
	_goto(m, "JOIN GAME")
	return m

func test_found_games_appear_above_the_code_row_and_join_on_select() -> void:
	var m = _join_screen()
	var g := Discovery.FoundGame.new()
	g.address = "10.0.0.9"
	g.port = 50611
	g.name = "Kris's game"
	g.level = "Field 05"
	m.finder.found = [g]
	m.update()
	check_eq(m.items()[0].label, "Kris's game", "the game is listed first")
	check_eq(m.cursor, 1, "the cursor stayed on the code row")
	check(m.editing(), "still typing")
	m.cursor = 0
	m.select()
	check_eq(m.result["mode"], "join")
	check_eq(m.result["port"], 50611)
	check_eq(m.result["address"], "10.0.0.9")

func test_a_typed_code_of_a_game_on_this_network_connects_to_it_directly() -> void:
	var m = _join_screen()
	var code := Invite.address_code("203.0.113.5")
	var g := Discovery.FoundGame.new()
	g.address = "10.0.0.9"
	g.port = 50611
	g.name = "Kris's game"
	g.codes = [code]
	m.finder.found = [g]
	m.update()
	m.cursor = 1
	m.paste(code)
	m.cursor = 2
	m.select()
	check_eq(m.result["mode"], "join", "connects to the game it found")
	check_eq(m.result["address"], "10.0.0.9")

func test_leaving_join_closes_the_listener() -> void:
	var m = _join_screen()
	var f = m.finder
	m.back()
	check(m.finder == null and not f.available, "the finder is closed and dropped")

func test_join_without_discovery_says_so() -> void:
	var m = _menu()
	m.finder_factory = func():
		var f := FakeFinder.new()
		f.available = false
		return f
	_goto(m, "PLAY")
	_goto(m, "ONLINE")
	_goto(m, "JOIN GAME")
	check("Can't look" in m.items()[0].label, "tells the player to type the code")

# ---- typing the invite code

func test_join_screen_formats_typed_codes_and_connects() -> void:
	var m = _join_screen()
	check(m.editing() and not m.items()[2].enabled(), "an empty code cannot connect")
	var code := Invite.address_code("203.0.113.5")
	for ch in (code.substr(0, 4) + "-" + code.substr(4)).to_lower():
		m.type_char(ch)
	check_eq(m.code, code, "typed code is normalised: upper case, no dash")
	check_eq(m.items()[1].label, "CODE: %s_" % Invite.format_code(code), "and shown with the dash")
	check(m.items()[2].enabled(), "a good code can connect")
	m.cursor = 2
	m.select()
	check_eq(m.result["mode"], "join_code")
	check_eq(m.result["code"], code)

func test_a_mistyped_code_is_explained_not_silently_fixed() -> void:
	var m = _join_screen()
	for ch in "ABC123":
		m.type_char(ch)
	var c = m.items()[2]
	check(not c.enabled() and "can't contain 1" in c.reason and "never use" in c.reason, c.reason)
	m.code = Invite.address_code("203.0.113.5")
	m.code = m.code.substr(0, 7) + ("A" if m.code[7] != "A" else "B")
	if Invite.code_address(m.code) == "":
		check("typo" in m.items()[2].reason, m.items()[2].reason)

func test_a_relay_code_needs_a_relay() -> void:
	_with_relay(false)
	var m = _join_screen()
	m.paste("KQ7-M3X")
	check("8 characters" in m.items()[2].reason, m.items()[2].reason)
	_with_relay(true)
	check(m.items()[2].enabled(), "with a relay it can connect")
	_with_relay(false)

func test_code_length_is_capped() -> void:
	var m = _join_screen()
	for ch in "ABCDEFGHJKMNPQ":
		m.type_char(ch)
	check_eq(m.code.length(), Invite.DIRECT_LEN + 2, "capped just past the code length so the error can say 'too long'")

func test_paste_takes_the_code_out_of_a_sentence() -> void:
	_with_relay(true)
	var m = _join_screen()
	m.paste("Code: kq7-m3x")
	check_eq(m.code, "KQ7M3X")
	m.paste("join me! 2JDH-GC8A ok?")
	check_eq(m.code, "2JDHGC8A", "the code-shaped word is found")
	m.paste("")
	check_eq(m.code, "2JDHGC8A", "an empty paste changes nothing")
	_with_relay(false)

func test_the_level_picker_opens_on_the_last_level() -> void:
	var m = _menu()
	_goto(m, "PLAY")
	_goto(m, "TWO PLAYERS")
	var keys := m.shown_levels().map(func(i): return i.key)
	m.cursor = keys.find("field_09")
	m.select()
	m.result = null
	m.back()
	_goto(m, "TWO PLAYERS")
	check_eq(keys[m.cursor], "field_09", "opens where you left off")

func test_hover_and_move_wrap_and_respect_dialogs() -> void:
	var m = _menu()
	m.move(1)
	check_eq(m.cursor, 1)
	m.move(1)
	check_eq(m.cursor, 0, "wraps")
	m.move(-1)
	check_eq(m.cursor, 1, "wraps backwards")
	m.hover(0)
	check_eq(m.cursor, 0)
	m.hover(99)
	check_eq(m.cursor, 0, "an out-of-range hover is ignored")
	m.error = "something"
	m.move(1)
	check_eq(m.cursor, 0, "no movement while a dialog is open")

func _game(game_name: String, level: String, address: String, port: int):
	var g := Discovery.FoundGame.new()
	g.name = game_name
	g.level = level
	g.address = address
	g.port = port
	return g

func test_the_cursor_follows_the_address_row_as_games_come_and_go() -> void:
	var m = _join_screen()
	m.finder.found = [_game("A", "Field 01", "10.0.0.1", 50555)]
	m.update()
	check_eq(m.cursor, 1, "one game: the address row is row 1")
	m.finder.found = [_game("A", "Field 01", "10.0.0.1", 50555), _game("B", "Field 02", "10.0.0.2", 50555)]
	m.update()
	check_eq(m.cursor, 2, "a second game appears: the cursor moves down with the address row")
	check(m.editing(), "and you are still typing")
	m.finder.found = [_game("A", "Field 01", "10.0.0.1", 50555)]
	m.update()
	check_eq(m.cursor, 1, "a game disappears: the cursor moves back up")
	m.cursor = 0
	m.finder.found = [_game("A", "Field 01", "10.0.0.1", 50555), _game("B", "Field 02", "10.0.0.2", 50555)]
	m.update()
	check_eq(m.cursor, 0, "a cursor on a game row stays where it is")

func test_found_games_show_their_level_and_where_they_are() -> void:
	var m = _join_screen()
	m.finder.found = [_game("Kris's game", "Field 05", "10.0.0.9", 50611), _game("Quiet", "", "10.0.0.8", 50555)]
	m.update()
	check_eq(m.items()[0].hint, "Field 05 - on your Wi-Fi")
	check_eq(m.items()[1].hint, "on your Wi-Fi", "no level: just where it is")

func test_paste_prefers_the_last_code_shaped_word() -> void:
	var m = _join_screen()
	m.paste("old: KQ7-M3X new: 2JDH-GC8A")
	check_eq(m.code, "2JDHGC8A")
