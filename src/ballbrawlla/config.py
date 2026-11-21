"""Every tunable number in one place.

Units: pixels, seconds, degrees. Screen coordinates are y-down, so "up" is -y.
Tweak these to change game feel; nothing else should hardcode gameplay numbers.
"""

from dataclasses import dataclass


@dataclass
class Tuning:
    # --- Simulation ---
    physics_hz: int = 120

    # --- Player body ---
    player_width: float = 28
    player_height: float = 48
    player_crouch_height: float = 30
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
    ball_restitution: float = 0.75    # 1.0 = no energy loss on bounce
    ball_bounce_friction: float = 0.1  # fraction of tangential speed lost per impact
    ball_rest_speed: float = 40       # impacts slower than this stop instead of bouncing
    ball_rolling_drag: float = 1.5    # per-second horizontal decay while resting on a floor

    # --- Pick up / aim / throw ---
    pickup_radius: float = 40         # player-center to ball-center distance for Z pickup
    throw_enabled: bool = True        # set False to disable the throw phase for testing
    aim_rate: float = 180             # degrees per second (left/right)
    power_min: float = 300
    power_max: float = 1400
    power_rate: float = 900           # power units per second (up/down)

    @property
    def dt(self) -> float:
        return 1.0 / self.physics_hz


TUNING = Tuning()
