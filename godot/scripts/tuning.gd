# GENERATED from src/ballbrawlla/config.py by tools/export_parity.py. Edit the Python file and rerun
# the tool; tests/test_tuning.gd checks every value against the Python game.
extends RefCounted

## Every tunable number in one place. Units: pixels, seconds, degrees. y is down, so "up" is -y.

# --- Simulation ---
var physics_hz: int = 120
var max_players: int = 2  # network play: host + (max_players - 1) clients

# --- Player body ---
# Smaller than the first prototype (28 x 48) so levels feel bigger. 42 px standing is
# still taller than every slide-under gap in the levels (<= 40 px), and the 26 px
# crouch still fits under them.
var player_width: float = 24
var player_height: float = 42
var player_crouch_height: float = 26
var player_gravity: float = 2200
var player_max_fall_speed: float = 1200

# --- Running / jumping ---
var run_speed: float = 320  # fixed ground speed
var air_speed: float = 320  # fixed horizontal speed while airborne
var jump_speed: float = 820  # initial upward speed of a ground jump
var jump_cut_multiplier: float = 0.5  # releasing Up early scales upward speed by this
var air_jumps: int = 1  # 1 = double jump, 0 = disabled (e.g. make it a power-up later)
var double_jump_speed: float = 680

# --- Down: crouch / slide ---
var slide_enabled: bool = true
var slide_speed: float = 560
var slide_duration: float = 0.45
var slide_friction: float = 2.5  # per-second decay of slide speed
var crawl_speed: float = 110  # crouched walking speed (about 35% of run); 0 = frozen while crouched
# Holding the ball scales ground speed (run, slide, crawl) but not air speed or jumps:
# a defender out-runs the carrier on open ground, so the carrier has to use the level.
var carry_speed_multiplier: float = 0.78

# --- Wall cling ---
var wall_gravity_scale: float = 0.3  # gravity multiplier while clinging (wall friction)
var wall_slide_max_speed: float = 140  # max downward speed while clinging
var wall_hold_sticks: bool = false  # pressing into the wall stops sliding entirely
var wall_jump_x: float = 380  # horizontal kick away from the wall
var wall_jump_y: float = 720
var wall_jump_control_lock: float = 0.18  # seconds air control is ignored after a wall jump
var wall_climb_speed: float = 520  # Up while clinging: hop up the wall

# --- Ball ---
var ball_radius: float = 12
var ball_gravity: float = 2200  # starts equal to player gravity per design doc
# Platforms and walls absorb a lot of the ball's energy on impact:
# a head-on hit keeps 0.4 of its speed (16% of its energy), and a glancing
# hit loses 35% of its speed along the surface.
var ball_restitution: float = 0.4  # fraction of speed into the surface kept (1.0 = no loss)
var ball_bounce_friction: float = 0.35  # fraction of speed along the surface lost per impact
var ball_rest_speed: float = 40  # impacts slower than this stop instead of bouncing
var ball_rolling_drag: float = 1.5  # per-second horizontal decay while resting on a floor

# --- Pick up / aim / throw ---
var pickup_radius: float = 55  # player-center to ball-center distance for Z pickup
var pickup_buffer_time: float = 0.1  # seconds a Z press stays armed waiting for the ball to arrive
var pickup_grace_time: float = 0.1  # seconds a Z press still counts after the ball left reach (host-judged)
var throw_enabled: bool = true  # set False to disable the throw phase for testing
var aim_rate: float = 180  # degrees per second (left/right)
var power_min: float = 300
var power_max: float = 1400
var power_rate: float = 900  # power units per second (up/down)

# --- Field (see gameplay-rules.md) ---
var yard_px: float = 24  # 1 yard in pixels (player is ~2 yd tall)
var field_yards: float = 100  # goal line to goal line
var end_zone_yards: float = 10  # each end zone

# --- Downs and play call ---
var downs_per_possession: int = 4
var touchdowns_to_win: int = 5
var play_call_seconds: float = 15  # restarts (same down) if both sides haven't locked in
var qb_region_start_yards: float = 0  # 1st-down QB spawn region, yards from offense's goal line
var qb_region_end_yards: float = 10
var defender_gap_yards: float = 10  # defender spawns >= this far past the QB's furthest spot
var qb_grab_radius: float = 40  # px, clicking this close to the QB while aiming goes back to moving it
var aim_drag_radius: float = 200  # px, mouse distance from the QB that maps to max power

# --- Play execution ---
var pre_throw_seconds: float = 10  # free running before the QB throws automatically
var ball_stopped_speed: float = 8  # px/s; a resting ball slower than this has "landed"
var loose_ball_seconds: float = 3  # after landing, play is dead if nobody picks it up
var tag_radius: float = 40  # px, center to center
var result_pause_seconds: float = 2.5  # shows the play result before the next play call


func dt() -> float:
	return 1.0 / physics_hz

func pickup_buffer_ticks() -> int:
	return maxi(0, int(ceil(pickup_buffer_time * physics_hz - 1e-9)))

func pickup_grace_ticks() -> int:
	return maxi(0, int(ceil(pickup_grace_time * physics_hz - 1e-9)))

## Every value as a Dictionary, for the host to send to a joining player (the "tuning" in the welcome message).
func to_dict() -> Dictionary:
	var out := {}
	for p in get_property_list():
		if p.usage & PROPERTY_USAGE_SCRIPT_VARIABLE:
			out[p.name] = get(p.name)
	return out

## Take the host's values (JSON turns every number into a float, so convert to each field's own type).
func apply_dict(d: Dictionary) -> void:
	for k in d:
		var cur = get(k)
		if cur == null:
			continue
		if typeof(cur) == TYPE_BOOL:
			set(k, bool(d[k]))
		elif typeof(cur) == TYPE_INT:
			set(k, int(d[k]))
		else:
			set(k, float(d[k]))
