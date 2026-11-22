extends RefCounted
## The play call phase of a down (src/ballbrawlla/rules/play_call.py).
##
## Both sides move a real player with the same movement as in the play. Offense: (1) place the QB (only when the down
## lets the offense pick the spawn): it can only be confirmed while standing on a platform inside the yellow zone;
## (2) aim with the mouse, the right stick, or left/right (angle) and up/down (power); X locks in.
## Defense: move the Defender the same way; it locks in only while standing on a platform inside its zone.
## Execution starts as soon as both sides are locked in. If the timer runs out first, the play call restarts.

const Intent = preload("res://scripts/intent.gd")
const Player = preload("res://scripts/player.gd")
const Down = preload("res://scripts/down.gd")

## Last inputs per team, used as the defaults for the next play call.
class Memory:
	var qb_target := {}     # team -> [x, y]
	var aim := {}           # team -> [angle, power]
	var def_target := {}    # team -> [x, y]

var down
var field
var t
var timer: float
var restarts := 0
var qb_lo: float
var qb_hi: float
var qb_spot: Array
var qb_player
var qb_ok := true
var placing: bool
var _dragging_aim := false
var aim_angle: float
var aim_power: float
var def_lo: float
var def_hi: float
var def_spot: Array
var def_player
var def_ok := true
var offense_locked := false
var defense_locked := false

func _init(p_down, p_field, tuning, memory = null, defense_auto: bool = false) -> void:
	down = p_down
	field = p_field
	t = tuning
	if memory == null:
		memory = Memory.new()
	var off: int = down.offense
	var dfn: int = down.defense()
	timer = t.play_call_seconds
	# --- QB: a player the offense moves around (while placing)
	var qr: Array = Down.qb_x_range(down, field)
	qb_lo = qr[0]
	qb_hi = qr[1]
	var target: Array
	if down.qb_spawn["kind"] == "region":
		var mid: float = (down.qb_spawn["start"] + down.qb_spawn["end"]) / 2.0
		target = memory.qb_target.get(off, [field.x_at(off, mid), field.floor_y()])
	else:
		target = [down.qb_spawn["x"], down.qb_spawn["y"]]
	qb_spot = field.spawn_spot(target[0], target[1], qb_lo, qb_hi)
	qb_player = _player(qb_spot, load("res://scripts/teams.gd").attack_dir(off))
	placing = down.offense_picks_spawn()
	# --- Aim
	var default_aim := [45.0 if load("res://scripts/teams.gd").attack_dir(off) > 0 else 135.0, (t.power_min + t.power_max) / 2.0]
	var am: Array = memory.aim.get(off, default_aim)
	aim_angle = am[0]
	aim_power = am[1]
	# --- Defender: a player the defense moves around
	var dr: Array = Down.defender_x_range(down, field, t)
	def_lo = dr[0]
	def_hi = dr[1]
	var default_def := [field.x_at(off, Down.defender_min_yards(down, field, t) + 5.0), field.floor_y()]
	var dt_target: Array = memory.def_target.get(dfn, default_def)
	def_spot = field.spawn_spot(dt_target[0], dt_target[1], def_lo, def_hi)
	def_player = _player(def_spot, load("res://scripts/teams.gd").attack_dir(dfn))
	defense_locked = defense_auto

func _player(spot: Array, facing: int):
	var p = Player.new(spot[0], spot[1] - t.player_height / 2.0, t)
	p.facing = facing
	p.can_throw = false
	for i in 2:   # settle onto the spot: contacts, then the Grounded state
		_move(p, Intent.new(), 0.0)
	return p

# ------------------------------------------------------------ queries

func done() -> bool:
	return offense_locked and defense_locked

## Where the QB is drawn and aimed from.
func qb_center() -> Array:
	return [qb_player.center_x(), qb_player.center_y()]

func remember(memory) -> void:
	if down.offense_picks_spawn():
		memory.qb_target[down.offense] = qb_spot
	memory.aim[down.offense] = [aim_angle, aim_power]
	memory.def_target[down.defense()] = def_spot

# ------------------------------------------------------------ tick

## Apply both sides' input. Returns true once both are locked in.
func update(offense, defense, dt: float) -> bool:
	_update_offense(offense, dt)
	_update_defense(defense, dt)
	if done():
		return true
	timer -= dt
	if timer <= 0.0:
		timer = t.play_call_seconds
		restarts += 1
	return false

func _move(p, intent, dt: float) -> void:
	var lv = field.level
	p.update(intent, dt, lv.solids, null, lv.thin)

## The spawn spot under the player's feet, and whether it counts: standing on a platform (not jumping, not clinging)
## inside [lo, hi]. Standing on a platform's edge counts too; the spot is then moved inward. Returns [spot or null, ok].
func _standing_spot(p, lo: float, hi: float) -> Array:
	if not p.contacts.on_ground or p.body.vy < 0.0 or p.state.state_name == "wall_cling":
		return [null, false]
	var fx: float = p.center_x()
	var fy: float = p.box().bottom()
	var spot = field.snap(fx, fy, lo, hi)
	var ok: bool = spot != null and absf(spot[1] - fy) <= 1.0 and absf(spot[0] - fx) <= t.player_width / 2.0
	return [spot, ok]

func _update_offense(i, dt: float) -> void:
	if offense_locked:
		return
	var can_place: bool = down.offense_picks_spawn()
	# Mouse: aiming only (and clicking the QB to go back to moving it)
	if i.mouse_pressed and i.mouse != null:
		var qc := qb_center()
		var near_qb: bool = sqrt((qc[0] - i.mouse[0]) * (qc[0] - i.mouse[0]) + (qc[1] - i.mouse[1]) * (qc[1] - i.mouse[1])) <= t.qb_grab_radius
		if can_place and near_qb and not placing:
			placing = true
		elif not placing:
			_dragging_aim = true
	if not i.mouse_held:
		_dragging_aim = false
	if _dragging_aim and i.mouse != null:
		_aim_at(i.mouse[0], i.mouse[1])
	if placing:
		_move(qb_player, i, dt)
		var r := _standing_spot(qb_player, qb_lo, qb_hi)
		qb_ok = r[1]
		if qb_ok:
			qb_spot = r[0]
		if (i.z_pressed or i.button_pressed) and qb_ok:
			placing = false
	else:
		if i.aim_stick != null:   # controller: right stick points the throw
			aim_angle = fposmod(atan2(i.aim_stick[1], i.aim_stick[0]) * (180.0 / PI), 360.0)
		aim_angle = fposmod(aim_angle - i.move_x * t.aim_rate * dt, 360.0)
		aim_power = _clamp_power(aim_power + i.vertical * t.power_rate * dt)
		if i.z_pressed and can_place:
			placing = true
		elif i.button_pressed:
			offense_locked = true
	if i.x_pressed and qb_ok:   # X locks in from either step, only standing on a platform
		placing = false
		offense_locked = true

func _update_defense(i, dt: float) -> void:
	if defense_locked:
		return
	_move(def_player, i, dt)
	var r := _standing_spot(def_player, def_lo, def_hi)
	def_ok = r[1]
	if def_ok:
		def_spot = r[0]
	if (i.z_pressed or i.x_pressed or i.button_pressed) and def_ok:
		defense_locked = true

# ------------------------------------------------------------ helpers

func _aim_at(tx: float, ty: float) -> void:
	var c := qb_center()
	var dx: float = tx - c[0]
	var dy: float = ty - c[1]
	var len_sq: float = dx * dx + dy * dy
	if len_sq < 1.0:
		return
	aim_angle = fposmod(atan2(-dy, dx) * (180.0 / PI), 360.0)
	var frac: float = minf(1.0, sqrt(len_sq) / t.aim_drag_radius)
	aim_power = _clamp_power(t.power_min + frac * (t.power_max - t.power_min))

func _clamp_power(p: float) -> float:
	return minf(t.power_max, maxf(t.power_min, p))
