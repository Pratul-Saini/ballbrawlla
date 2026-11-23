extends RefCounted
## Draws a match from a view dictionary (view.gd), so the host's screen and a client's screen go through exactly the
## same code and the same hidden-information rules (src/ballbrawlla/render/match_renderer.py + field_markers.py).
## The world is larger than the window: a camera follows what you control, and a minimap across the top shows the
## whole field. In local play (view["local"]) the camera zooms out to keep both players in frame and both sides'
## choices are shown.
##
## Call draw(canvas_item, view, ...) from a CanvasItem's _draw(). Coordinates are converted by hand (not by scaling
## the canvas) so lines and text keep their pixel size at any zoom, as in the Python renderer.

const Teams = preload("res://scripts/teams.gd")

static func c8(r: int, g: int, b: int, a: int = 255) -> Color:
	return Color(r / 255.0, g / 255.0, b / 255.0, a / 255.0)

var BG := c8(24, 26, 32)
var BOUND := c8(70, 74, 86)
var PLATFORM := c8(120, 128, 148)
var THIN_FILL := c8(84, 140, 160)
var THIN_EDGE := c8(190, 235, 245)
var BALL := c8(235, 140, 50)
var AIM_RING := c8(80, 90, 110)
var AIM_LINE := c8(255, 230, 120)
var TRAJ := c8(255, 230, 120)
var TEXT := c8(220, 220, 220)
var QB_REGION := c8(255, 220, 90)
var SPOT_OK := c8(120, 230, 140)
var SPOT_BAD := c8(240, 90, 90)
var BANNER := c8(255, 240, 180)
var DIM := c8(150, 155, 170)
var BUTTON := c8(60, 120, 80)
var BUTTON_EDGE := c8(150, 230, 170)
var BUTTON_OFF := c8(60, 62, 70)
var BUTTON_OFF_EDGE := c8(110, 114, 126)
var HUD_BAND := c8(16, 17, 22, 200)
var TEAM_COLORS := [c8(80, 170, 255), c8(255, 110, 110)]
var YARD_LINE := c8(44, 48, 58)
var MIDFIELD_LINE := c8(70, 76, 92)
var GOAL_LINE := c8(200, 200, 210)
var YARD_TICK := c8(56, 60, 72)
var LABEL := c8(150, 155, 170)
var FLOOR_PAINT := c8(52, 56, 68)
const END_ZONE_ALPHA := 28
const THIN_EDGE_HEIGHT := 3.0
const MINIMAP_H := 40.0
const AIM_RING_RADIUS := 60.0
const MIN_ZOOM := 0.4                      # local play: how far the shared camera may zoom out
const FRAME_MARGIN := Vector2(260, 200)    # world px kept around the players when framing them

var level
var field
var t
var ci: CanvasItem
var font: Font
var size := Vector2(1280, 720)

# Camera: pos is the world position of the screen's top-left corner; zoom is the scale.
var cam := Vector2.ZERO
var zoom := 1.0
var _placed := false

var debug := false
var show_controls := true      # F3: key instructions in the hints and the bottom line
var key_names := {"grab": "Z / Square", "lock": "X / Circle", "restart": "R"}
var button_rect := Rect2()     # the on-screen play-call button (size zero when there is none)
var hud_h := MINIMAP_H + 54.0

func _init(p_level, p_field, tuning) -> void:
	level = p_level
	field = p_field
	t = tuning
	font = ThemeDB.fallback_font

func button_hit(pos: Vector2) -> bool:
	return button_rect.size != Vector2.ZERO and button_rect.has_point(pos)

# ------------------------------------------------------------ camera

func world_size() -> Vector2:
	return size / zoom

func _clamp_axis(c: float, view: float, lvl: float) -> float:
	if lvl <= view:
		return (lvl - view) / 2.0     # level smaller than the view: center it
	return minf(maxf(c - view / 2.0, 0.0), lvl - view)

func _place(center: Vector2, dt: float, p_zoom: float) -> void:
	if not _placed:
		zoom = p_zoom
	else:
		zoom += (p_zoom - zoom) * minf(1.0, dt * 4.0)
	var ws := world_size()
	var desired := Vector2(_clamp_axis(center.x, ws.x, level.width), _clamp_axis(center.y, ws.y, level.height))
	if not _placed:
		cam = desired
		_placed = true
	else:
		cam += (desired - cam) * minf(1.0, dt * 8.0)

## Keep `target` centred at normal scale.
func follow(target: Vector2, dt: float) -> void:
	_place(target, dt, 1.0)

## Keep every point on screen, zooming out (down to MIN_ZOOM) if needed. top_inset: screen px covered by the HUD.
func frame(points: Array, dt: float, top_inset: float = 0.0) -> void:
	var min_x := INF
	var max_x := -INF
	var min_y := INF
	var max_y := -INF
	for p in points:
		min_x = minf(min_x, p.x)
		max_x = maxf(max_x, p.x)
		min_y = minf(min_y, p.y)
		max_y = maxf(max_y, p.y)
	var bw := max_x - min_x + 2.0 * FRAME_MARGIN.x
	var bh := max_y - min_y + 2.0 * FRAME_MARGIN.y
	var z := maxf(MIN_ZOOM, minf(1.0, minf(size.x / bw, (size.y - top_inset) / bh)))
	var center := Vector2((max_x + min_x) / 2.0, (max_y + min_y) / 2.0 - top_inset / (2.0 * z))
	_place(center, dt, z)

func _camera_target(view: Dictionary) -> Vector2:
	var h: float = t.player_height
	var call = view.get("call")
	if call != null:
		var spot: Array = call["def"] if (view["side"] == "defense" and call.has("def")) else call["qb"]
		return Vector2(spot[0], spot[1] - h / 2.0)
	for a in view.get("actors", []):
		if a["team"] == view["team"] and a["role"] != "QB":
			return Vector2(a["x"] + a["w"] / 2.0, a["y"] + a["h"] / 2.0)
	return Vector2(level.width / 2.0, level.height / 2.0)

## Local play: what both players need to see (their spawn picks during the play call; both runners and a ball in
## flight during the play).
func _focus_points(view: Dictionary) -> Array:
	var h: float = t.player_height
	var pts: Array = []
	var call = view.get("call")
	if call != null:
		pts.append(Vector2(call["qb"][0], call["qb"][1] - h / 2.0))
		if call.has("def"):
			pts.append(Vector2(call["def"][0], call["def"][1] - h / 2.0))
	for a in view.get("actors", []):
		if a["role"] != "QB":
			pts.append(Vector2(a["x"] + a["w"] / 2.0, a["y"] + a["h"] / 2.0))
	var ball = view.get("ball")
	if ball != null and view["phase"] == "live" and ball["holder"] == null:
		pts.append(Vector2(ball["x"], ball["y"]))
	if pts.is_empty():
		pts.append(Vector2(level.width / 2.0, level.height / 2.0))
	return pts

# ------------------------------------------------------------ helpers

func _w(x: float, y: float) -> Vector2:
	return Vector2((x - cam.x) * zoom, (y - cam.y) * zoom)

func _wrect(x: float, y: float, w: float, h: float) -> Rect2:
	var s := _w(x, y)
	return Rect2(roundf(s.x), roundf(s.y), maxf(1.0, roundf(w * zoom)), maxf(1.0, roundf(h * zoom)))

func _team_color(team: int, alpha: float = 1.0) -> Color:
	var c: Color = TEAM_COLORS[team]
	return Color(c.r, c.g, c.b, alpha)

static func _ordinal(n: int) -> String:
	return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, "%dth" % n)

## Text with its TOP-left (or top-centre) at pos, like pygame; `px` is the font size in pixels.
func _text(s: String, pos: Vector2, color: Color = Color.TRANSPARENT, px: int = 16, center: bool = false) -> void:
	if color == Color.TRANSPARENT:
		color = TEXT
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
	var x := pos.x - (w / 2.0 if center else 0.0)
	ci.draw_string(font, Vector2(x, pos.y + px * 0.82), s, HORIZONTAL_ALIGNMENT_LEFT, -1, px, color)

func _rect_outline(r: Rect2, color: Color, width: float = 1.0) -> void:
	ci.draw_rect(r, color, false, width)

# ------------------------------------------------------------ main

## `status` (e.g. network state) is always shown; `controls` (the key list) only while show_controls is on.
## `invite`: the host's waiting panel, shown while waiting for the other player: {"code": "KQ7M-3XPA" or "" while it
## is being worked out, "lines": [[label, text, state]], "copied": bool, "test": bool (offer N: open a test window)}.
func draw(p_ci: CanvasItem, p_size: Vector2, view: Dictionary, fps: float, dt: float, status: String = "",
		controls: String = "", invite: Dictionary = {}) -> void:
	ci = p_ci
	size = p_size
	if view.get("local", false):
		frame(_focus_points(view), dt, hud_h)
	else:
		follow(_camera_target(view), dt)
	ci.draw_rect(Rect2(Vector2.ZERO, size), BG)
	_draw_field()
	_draw_platforms()
	var phase: String = view["phase"]
	if phase == "play_call":
		_draw_play_call(view)
	if view.has("actors"):
		_draw_actors(view)
	_draw_hud(view, fps, status, controls)
	if not invite.is_empty() and phase == "waiting":
		_draw_invite(invite)

func _wrapped(s: String, width: float, px: int) -> Array:
	var out: Array = []
	var line := ""
	for word in s.split(" ", false):
		var trial := word if line == "" else "%s %s" % [line, word]
		if line != "" and font.get_string_size(trial, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x > width:
			out.append(line)
			line = word
		else:
			line = trial
	if line != "":
		out.append(line)
	return out

## The host's waiting panel: the code to share, and who can join (same Wi-Fi / internet).
func _draw_invite(invite: Dictionary) -> void:
	var colors := {"ready": SPOT_OK, "checking": BANNER, "unavailable": c8(255, 170, 160)}
	var px := 16
	var line_h := 20.0
	var w := minf(760.0, size.x - 40.0)
	var label_w := 120.0
	var body: Array = []
	var n_lines := 0
	for ln in invite.get("lines", []):
		var wrapped := _wrapped(ln[1], w - 60.0 - label_w, px)
		body.append([ln[0], wrapped, colors.get(ln[2], DIM)])
		n_lines += wrapped.size()
	var h := 150.0 + n_lines * line_h + body.size() * 6.0 + (30.0 if invite.get("test", false) else 0.0)
	var box := Rect2(size.x / 2.0 - w / 2.0, size.y / 2.0 - h / 2.0, w, h)
	ci.draw_rect(box, c8(16, 17, 22))
	_rect_outline(box, BANNER, 2.0)
	var cx := box.get_center().x
	_text("Waiting for the other player. Send them this invite code:", Vector2(cx, box.position.y + 14.0), DIM, px, true)
	var code: String = invite.get("code", "")
	var hint := ""
	if code != "":
		_text(code, Vector2(cx, box.position.y + 40.0), BANNER, 64, true)
		hint = "copied!" if invite.get("copied", false) else "Ctrl+C copies it. They pick JOIN GAME and type it."
	else:
		_text("getting your code...", Vector2(cx, box.position.y + 56.0), DIM, px, true)
	_text(hint, Vector2(cx, box.position.y + 104.0), DIM, px, true)
	var y := box.position.y + 136.0
	for b in body:
		_text("%s:" % b[0], Vector2(box.position.x + 30.0, y), DIM, px)
		for k in b[1].size():
			_text(b[1][k], Vector2(box.position.x + 30.0 + label_w, y + k * line_h), b[2], px)
		y += b[1].size() * line_h + 6.0
	if invite.get("test", false):
		_text("No second player handy? N opens a second window on this computer that joins.",
				Vector2(cx, box.end.y - 28.0), DIM, px, true)

# ------------------------------------------------------------ world

func _draw_field() -> void:
	var f = field
	var floor_sy: float = (f.floor_y() - cam.y) * zoom
	var ez_w: float = f.end_zone_px * zoom
	# End zones, tinted in the defending team's colour, with the team name painted on the floor.
	for team in [Teams.LEFT, Teams.RIGHT]:
		var x0: float = f.goal_line_x(team) - (f.end_zone_px if team == Teams.LEFT else 0.0)
		var sx: float = (x0 - cam.x) * zoom
		if sx + ez_w < 0.0 or sx > size.x:
			continue
		ci.draw_rect(Rect2(sx, 0.0, roundf(ez_w), size.y), _team_color(team, END_ZONE_ALPHA / 255.0))
		var name_w := font.get_string_size(Teams.display(team).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 32).x
		_text(Teams.display(team).to_upper(), Vector2(sx + (ez_w - name_w) / 2.0 + name_w / 2.0, floor_sy - 70.0), FLOOR_PAINT, 32, true)
	# Lines every 5 yards
	var yards := 0
	while yards <= int(t.field_yards):
		var sx: float = (f.x_at(Teams.LEFT, yards) - cam.x) * zoom
		if sx >= -60.0 and sx <= size.x + 60.0:
			if yards == 0 or yards == int(t.field_yards):
				ci.draw_line(Vector2(sx, 0), Vector2(sx, size.y), GOAL_LINE, 2.0)
			elif yards * 2 == int(t.field_yards):
				ci.draw_line(Vector2(sx, 0), Vector2(sx, size.y), MIDFIELD_LINE, 2.0)
			elif yards % 10 == 0:
				ci.draw_line(Vector2(sx, 0), Vector2(sx, size.y), YARD_LINE, 1.0)
			else:   # 5-yard tick at the floor
				ci.draw_line(Vector2(sx, floor_sy - 14.0), Vector2(sx, floor_sy), YARD_TICK, 1.0)
			if yards % 10 == 0 and yards > 0 and yards < int(t.field_yards):
				var label := str(int(minf(yards, t.field_yards - yards)))
				_text(label, Vector2(sx, floor_sy - 34.0), FLOOR_PAINT, 32, true)
				_text(label, Vector2(sx, hud_h + 4.0), LABEL, 14, true)    # pinned so it stays readable
		yards += 5

func _draw_platforms() -> void:
	for plat in level.platforms:
		var r = plat.rect
		var rect := _wrect(r.x, r.y, r.w, r.h)
		if plat.kind == "bound":
			ci.draw_rect(rect, BOUND)
		elif plat.is_thin():
			ci.draw_rect(rect, THIN_FILL)
			ci.draw_rect(Rect2(rect.position.x, rect.position.y, rect.size.x, minf(THIN_EDGE_HEIGHT, rect.size.y)), THIN_EDGE)
		else:
			ci.draw_rect(rect, PLATFORM)

func _draw_figure(x: float, feet_y: float, team: int, label: String, outline_only: bool = false, me: bool = false,
		p_h: float = -1.0) -> void:
	var w: float = t.player_width
	var h: float = p_h if p_h > 0.0 else t.player_height
	var rect := _wrect(x - w / 2.0, feet_y - h, w, h)
	var color := _team_color(team)
	if outline_only:
		_rect_outline(rect.grow(-1.0), color, 2.0)
	else:
		ci.draw_rect(rect, color)
	if me:
		_rect_outline(rect.grow(2.0), Color.WHITE, 1.0)
	_text(label, Vector2(rect.get_center().x, rect.position.y - 16.0), color, 14, true)

func _draw_aim(cx: float, cy: float, angle: float, power: float) -> void:
	var c := _w(cx, cy)
	var a := angle * (PI / 180.0)
	var d := Vector2(cos(a), -sin(a))
	var ring := maxf(24.0, AIM_RING_RADIUS * zoom)
	ci.draw_arc(c, ring, 0.0, TAU, 48, AIM_RING, 1.0)
	var frac: float = (power - t.power_min) / maxf(1e-6, t.power_max - t.power_min)
	ci.draw_line(c, c + d * (ring * (0.3 + 0.7 * frac)), AIM_LINE, 3.0)
	var vel := d * power
	for i in range(1, 22):
		var tt := i * 0.05
		var pt := Vector2(cx, cy) + vel * tt + Vector2(0, 0.5 * t.ball_gravity * tt * tt)   # world
		ci.draw_circle(_w(pt.x, pt.y), 2.0, TRAJ)

# ------------------------------------------------------------ phases

func _draw_band(x0: float, x1: float, color: Color) -> void:
	var sx0 := _w(x0, 0.0).x
	var sx1 := _w(x1, 0.0).x
	var w := maxf(2.0, floorf(sx1 - sx0 + t.player_width * zoom))
	ci.draw_rect(Rect2(sx0 - t.player_width * zoom / 2.0, 0.0, w, size.y), color)

func _draw_play_call(view: Dictionary) -> void:
	var call: Dictionary = view["call"]
	var off: int = view["offense"]
	var dfn := 1 - off
	var h: float = t.player_height
	var local: bool = bool(view.get("local", false))
	var me_off: bool = local or view["side"] == "offense"
	var me_def: bool = local or view["side"] == "defense"
	if call["picks"] and not call["off_locked"]:
		_draw_band(call["qb_range"][0], call["qb_range"][1], Color(QB_REGION.r, QB_REGION.g, QB_REGION.b, 30.0 / 255.0))
	if me_def and not call["def_locked"]:
		_draw_band(call["def_range"][0], call["def_range"][1], _team_color(dfn, 30.0 / 255.0))
	var qb: Array = call["qb"]
	var placing: bool = call["placing"] and not call["off_locked"]
	_draw_figure(qb[0], qb[1], off, "QB", false, placing and me_off, call.get("qb_h", -1.0))
	if placing:
		_draw_spot_marker(call["qb_ok"], qb, call.get("qb_h", -1.0))
	if call.has("def"):
		_draw_figure(call["def"][0], call["def"][1], dfn, "DEF", call["def_locked"], true, call.get("def_h", -1.0))
		if not call["def_locked"]:
			_draw_spot_marker(call["def_ok"], call["def"], call.get("def_h", -1.0))
	if call.has("aim") and not call["placing"]:
		_draw_aim(qb[0], qb[1] - call.get("qb_h", h) / 2.0, call["aim"][0], call["aim"][1])

## Green bar under the player if it's standing somewhere it can lock in; otherwise a red box.
func _draw_spot_marker(ok: bool, feet: Array, p_h: float) -> void:
	var w: float = t.player_width
	var h: float = p_h if p_h > 0.0 else t.player_height
	if ok:
		ci.draw_rect(_wrect(feet[0] - w, feet[1] - 2.0, 2.0 * w, 4.0), SPOT_OK)
	else:
		var box := _wrect(feet[0] - w / 2.0, feet[1] - h, w, h)
		_rect_outline(box.grow(3.0), SPOT_BAD, 2.0)
		_text("not on a platform in your zone", Vector2(box.get_center().x, box.end.y + 4.0), SPOT_BAD, 14, true)

func _is_mine(view: Dictionary, team: int, role: String) -> bool:
	return role != "QB" and (bool(view.get("local", false)) or team == view["team"])

func _draw_actors(view: Dictionary) -> void:
	for a in view["actors"]:
		var feet_x: float = a["x"] + a["w"] / 2.0
		var me := _is_mine(view, a["team"], a["role"])
		_draw_figure(feet_x, a["y"] + a["h"], a["team"], a["role"], false, me)
		if me:
			ci.draw_arc(_w(feet_x, a["y"] + a["h"] / 2.0), maxf(4.0, t.tag_radius * zoom), 0.0, TAU, 40,
					c8(90, 200, 120), 1.0)
	if view.has("aim"):
		var qb: Dictionary = view["actors"][0]
		_draw_aim(qb["x"] + qb["w"] / 2.0, qb["y"] + qb["h"] / 2.0, view["aim"][0], view["aim"][1])
	var b: Dictionary = view["ball"]
	ci.draw_circle(_w(b["x"], b["y"]), maxf(3.0, t.ball_radius * zoom), BALL)

# ------------------------------------------------------------ HUD

func _draw_minimap(view: Dictionary) -> void:
	var x0 := 40.0
	var y0 := 6.0
	var w := size.x - 80.0
	var h := MINIMAP_H
	var sx: float = w / level.width
	var sy: float = h / level.height
	ci.draw_rect(Rect2(x0, y0, w, h), c8(16, 17, 22))
	var ez_w: float = field.end_zone_px
	for team in [Teams.LEFT, Teams.RIGHT]:
		var gx: float = field.goal_line_x(team) - (ez_w if team == Teams.LEFT else 0.0)
		var tc: Color = TEAM_COLORS[team]
		ci.draw_rect(Rect2(x0 + gx * sx, y0, ez_w * sx, h), Color(tc.r / 3.0, tc.g / 3.0, tc.b / 3.0))
	for plat in level.platforms:
		if plat.kind == "bound":
			continue
		var r = plat.rect
		ci.draw_rect(Rect2(x0 + r.x * sx, y0 + r.y * sy, maxf(1.0, r.w * sx), maxf(1.0, r.h * sy)), DIM)
	var call = view.get("call")
	if call != null:
		_dot(x0, y0, sx, sy, call["qb"][0], call["qb"][1] - 20.0, _team_color(view["offense"]), 3.0)
		if call.has("def"):
			_dot(x0, y0, sx, sy, call["def"][0], call["def"][1] - 20.0, _team_color(1 - int(view["offense"])), 3.0)
	for a in view.get("actors", []):
		_dot(x0, y0, sx, sy, a["x"] + a["w"] / 2.0, a["y"] + a["h"] / 2.0, _team_color(a["team"]), 3.0)
	if view.has("ball"):
		_dot(x0, y0, sx, sy, view["ball"]["x"], view["ball"]["y"], BALL, 2.0)
	var ws := world_size()
	_rect_outline(Rect2(x0 + cam.x * sx, y0 + cam.y * sy, ws.x * sx, ws.y * sy), c8(200, 200, 200), 1.0)

func _dot(x0: float, y0: float, sx: float, sy: float, x: float, y: float, color: Color, rad: float) -> void:
	ci.draw_circle(Vector2(x0 + x * sx, y0 + y * sy), rad, color)

func _draw_hud(view: Dictionary, fps: float, status: String, controls: String) -> void:
	var local: bool = bool(view.get("local", false))
	var me: int = view["team"]
	var off: int = view["offense"]
	var hints: Array = []
	if local and view["phase"] == "play_call" and show_controls:
		hints = ["%s (offense): %s" % [Teams.display(off), _phase_hint(view, "offense")],
				"%s (defense): %s" % [Teams.display(1 - off), _phase_hint(view, "defense", false)]]
	else:
		var h := _phase_hint(view)
		if h != "":
			hints = [h]
	hud_h = MINIMAP_H + 34.0 + 20.0 * maxi(1, hints.size())
	ci.draw_rect(Rect2(0, 0, size.x, hud_h), HUD_BAND)
	_draw_minimap(view)
	var score: Array = view["score"]
	var top := MINIMAP_H + 12.0
	var line := "Blue %d - %d Red   |   %s down, %s on offense" % [score[0], score[1], _ordinal(view["down"]), Teams.display(off)]
	if local:
		line += "   |   local 2-player"
	else:
		line += "   |   You: %s (%s)" % [Teams.display(me), view["side"]]
	if view["practice"]:
		line += "   |   practice" if view.get("defender", true) else "   |   catch practice"
	_text(line, Vector2(40, top), TEXT, 16)
	for i in hints.size():
		_text(hints[i], Vector2(40, top + 20.0 + 20.0 * i), DIM, 16)
	var bottom_parts: Array = []
	if status != "":
		bottom_parts.append(status)
	bottom_parts.append(controls if show_controls else "F3: show controls")
	var bottom := "   |   ".join(bottom_parts.filter(func(b): return b != ""))
	if bottom != "":
		_text(bottom, Vector2(40, size.y - 26.0), DIM, 16)
	var msg: String = view.get("message", "")
	if msg != "" and (view["phase"] == "dead" or view["phase"] == "game_over"):
		_text(msg, Vector2(size.x / 2.0, size.y / 2.0 - 60.0), BANNER, 36, true)
		if view["phase"] == "game_over":
			var who := "Press" if local else "Host: press"
			_text("%s %s for a new match" % [who, key_names["restart"]], Vector2(size.x / 2.0, size.y / 2.0 - 20.0), DIM, 16, true)
	button_rect = Rect2()
	var label := _button_label(view)
	if label != "":
		var enabled := not label.begins_with("Move ")
		var rect := Rect2(size.x - 24.0 - 240.0, hud_h + 12.0, 240.0, 40.0)   # top-right under the HUD
		ci.draw_rect(rect, BUTTON if enabled else BUTTON_OFF)
		_rect_outline(rect, BUTTON_EDGE if enabled else BUTTON_OFF_EDGE, 2.0)
		_text(label, Vector2(rect.get_center().x, rect.position.y + 11.0), TEXT if enabled else DIM, 16, true)
		button_rect = rect
	if debug:
		_draw_debug(view, fps)

func _button_label(view: Dictionary) -> String:
	var call = view.get("call")
	if view["phase"] != "play_call" or call == null:
		return ""
	if view.get("local", false) or view["side"] == "offense":   # local: the mouse belongs to the offense
		if call["off_locked"]:
			return ""
		if call["placing"]:
			return "Confirm QB spot" if call["qb_ok"] else "Move QB onto a platform"
		return "Lock in throw"
	if call["def_locked"]:
		return ""
	return "Lock in Defender" if call.get("def_ok", true) else "Move onto a platform"

func _fmt1(v: float, width: int) -> String:
	return ("%" + str(width) + ".1f") % v

## The phase line. With show_controls off, only the game state (timers, locks, who has the ball), no key instructions.
func _phase_hint(view: Dictionary, p_side: String = "", head: bool = true) -> String:
	var phase: String = view["phase"]
	var timer = view.get("timer")
	var side: String = p_side if p_side != "" else view["side"]
	var grab: String = key_names["grab"]
	var lock: String = key_names["lock"]
	if phase == "waiting":
		return "Waiting for the other player to join..."
	if not show_controls:
		return _state_hint(view)
	if phase == "play_call":
		var call: Dictionary = view["call"]
		var mine_locked: bool = call["off_locked"] if side == "offense" else call["def_locked"]
		var prefix := _state_hint(view) + "   " if head else ""
		if mine_locked:
			return prefix + "Locked in - waiting for the other side"
		if side == "defense":
			return prefix + "Run the Defender to a platform in your zone - %s / button: lock in" % grab
		if call["placing"]:
			return prefix + "Run the QB to a platform in the yellow zone - %s / button: confirm - %s: lock in" % [grab, lock]
		var back := " - %s / click QB: move it" % grab if call["picks"] else ""
		return prefix + "Aim (mouse, right stick or keys) - %s / button: lock in" % lock + back
	if phase == "pre_throw":
		if not view.get("defender", true):
			return "THROW IN %s - get open" % [_fmt1(timer, 4) + "s"]
		return "THROW IN %s - get open (WR) / get in position (DEF)" % [_fmt1(timer, 4) + "s"]
	if phase == "live":
		var holder = view["ball"]["holder"]
		if holder == null:
			if timer != null:
				return "LOOSE BALL - dead in %ss, %s to pick up" % [_fmt1(timer, 3), grab]
			return "Ball in the air - %s to catch" % grab
		if holder == "WR":
			if not view.get("defender", true):
				return "You have the ball: run to the end zone"
			return "WR has the ball: run to the end zone / DEF: %s to tag" % grab
		return "INTERCEPTION: DEF runs the other way / WR: %s to tag" % grab
	return ""

func _state_hint(view: Dictionary) -> String:
	var phase: String = view["phase"]
	var timer = view.get("timer")
	if phase == "play_call":
		var call: Dictionary = view["call"]
		var locks := "offense %s" % ("locked" if call["off_locked"] else "...")
		if view.get("defender", true):
			locks += ", defense %s" % ("locked" if call["def_locked"] else "...")
		var restarted := "  (play call restarted)" if call["restarts"] > 0 else ""
		return "PLAY CALL %ss   [%s]%s" % [_fmt1(timer, 4), locks, restarted]
	if phase == "pre_throw":
		return "THROW IN %ss" % _fmt1(timer, 4)
	if phase == "live":
		var holder = view["ball"]["holder"]
		if holder == null:
			return "LOOSE BALL - dead in %ss" % _fmt1(timer, 3) if timer != null else "Ball in the air"
		return "WR has the ball" if holder == "WR" else "INTERCEPTION: DEF has the ball"
	return ""

func _draw_debug(view: Dictionary, fps: float) -> void:
	var lines := ["fps %5.1f  tick %d  phase %s" % [fps, view["tick"], view["phase"]]]
	for a in view.get("actors", []):
		if _is_mine(view, a["team"], a["role"]):
			var flags := ""
			var names := "GCLR"
			for k in 4:
				flags += names[k] if a["c"][k] else "."
			lines.append("%s %-10s vel (%7.1f, %7.1f) contacts %s" % [a["role"], a["s"], a["vx"], a["vy"], flags])
	for i in lines.size():
		_text(lines[i], Vector2(40, size.y - 70.0 + i * 18.0), DIM, 14)
