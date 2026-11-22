"""Every tunable number in one place.

Units: pixels, seconds, degrees. Screen coordinates are y-down, so "up" is -y.
Tweak these to change game feel; nothing else should hardcode gameplay numbers.
"""

import math
from dataclasses import dataclass


@dataclass
class Tuning:
    # --- Simulation ---
    physics_hz: int = 120
    max_players: int = 2  # network play: host + (max_players - 1) clients

    # --- Player body ---
    # Smaller than the first prototype (28 x 48) so levels feel bigger. 42 px standing is
    # still taller than every slide-under gap in the levels (<= 40 px), and the 26 px
    # crouch still fits under them.
    player_width: float = 24
    player_height: float = 42
    player_crouch_height: float = 26
    player_gravity: float = 2200
    player_max_fall_speed: float = 1200

    # --- Running / jumping ---
    run_speed: float = 320            # fixed ground speed
    air_speed: float = 320            # fixed horizontal speed while airborne
    jump_speed: float = 820           # initial upward speed of a ground jump
    jump_cut_multiplier: float = 0.5  # releasing Up early scales upward speed by this
    air_jumps: int = 1                # 1 = double jump, 0 = disabled (e.g. make it a power-up later)
    double_jump_speed: float = 680

    # --- Down: crouch / slide ---
    slide_enabled: bool = True
    slide_speed: float = 560
    slide_duration: float = 0.45
    slide_friction: float = 2.5       # per-second decay of slide speed
    crawl_speed: float = 110          # crouched walking speed (about 35% of run); 0 = frozen while crouched
    # Holding the ball scales ground speed (run, slide, crawl) but not air speed or jumps:
    # a defender out-runs the carrier on open ground, so the carrier has to use the level.
    carry_speed_multiplier: float = 0.78

    # --- Wall cling ---
    wall_gravity_scale: float = 0.3   # gravity multiplier while clinging (wall friction)
    wall_slide_max_speed: float = 140  # max downward speed while clinging
    wall_hold_sticks: bool = False    # pressing into the wall stops sliding entirely
    wall_jump_x: float = 380          # horizontal kick away from the wall
    wall_jump_y: float = 720
    wall_jump_control_lock: float = 0.18  # seconds air control is ignored after a wall jump
    wall_climb_speed: float = 520     # Up while clinging: hop up the wall

    # --- Ball ---
    ball_radius: float = 12
    ball_gravity: float = 2200        # starts equal to player gravity per design doc
    # Platforms and walls absorb a lot of the ball's energy on impact:
    # a head-on hit keeps 0.4 of its speed (16% of its energy), and a glancing
    # hit loses 35% of its speed along the surface.
    ball_restitution: float = 0.4     # fraction of speed into the surface kept (1.0 = no loss)
    ball_bounce_friction: float = 0.35  # fraction of speed along the surface lost per impact
    ball_rest_speed: float = 40       # impacts slower than this stop instead of bouncing
    ball_rolling_drag: float = 1.5    # per-second horizontal decay while resting on a floor

    # --- Pick up / aim / throw ---
    pickup_radius: float = 55         # player-center to ball-center distance for Z pickup
    pickup_buffer_time: float = 0.1   # seconds a Z press stays armed waiting for the ball to arrive
    pickup_grace_time: float = 0.1    # seconds a Z press still counts after the ball left reach (host-judged)
    throw_enabled: bool = True        # set False to disable the throw phase for testing
    aim_rate: float = 180             # degrees per second (left/right)
    power_min: float = 300
    power_max: float = 1400
    power_rate: float = 900           # power units per second (up/down)

    # --- Field (see gameplay-rules.md) ---
    yard_px: float = 24               # 1 yard in pixels (player is ~2 yd tall)
    field_yards: float = 100          # goal line to goal line
    end_zone_yards: float = 10        # each end zone

    # --- Downs and play call ---
    downs_per_possession: int = 4
    touchdowns_to_win: int = 5
    play_call_seconds: float = 15     # restarts (same down) if both sides haven't locked in
    qb_region_start_yards: float = 0  # 1st-down QB spawn region, yards from offense's goal line
    qb_region_end_yards: float = 10
    defender_gap_yards: float = 10    # defender spawns >= this far past the QB's furthest spot
    qb_grab_radius: float = 40        # px, clicking this close to the QB while aiming goes back to moving it
    aim_drag_radius: float = 200      # px, mouse distance from the QB that maps to max power

    # --- Play execution ---
    pre_throw_seconds: float = 10     # free running before the QB throws automatically
    ball_stopped_speed: float = 8     # px/s; a resting ball slower than this has "landed"
    loose_ball_seconds: float = 3     # after landing, play is dead if nobody picks it up
    tag_radius: float = 40            # px, center to center
    result_pause_seconds: float = 2.5  # shows the play result before the next play call

    @property
    def dt(self) -> float:
        return 1.0 / self.physics_hz

    @property
    def pickup_buffer_ticks(self) -> int:
        return max(0, math.ceil(self.pickup_buffer_time * self.physics_hz - 1e-9))

    @property
    def pickup_grace_ticks(self) -> int:
        return max(0, math.ceil(self.pickup_grace_time * self.physics_hz - 1e-9))


TUNING = Tuning()
