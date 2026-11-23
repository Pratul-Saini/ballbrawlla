extends RefCounted
## Tuning for the 3-D prototype. Units are YARDS and SECONDS (1 world unit = 1 yard).
##
## The numbers are seeded from the 2-D game's config.py (value in px / 24 px-per-yard) so the feel
## starts from the tuned 2-D game, then is free to change for 3-D. See ../3d-prototype.md section 13.
## Access as: const Cfg = preload("res://scripts/config.gd"); Cfg.RUN_SPEED

# --- field (length along X, width along Z, up is Y). Midfield is X = 0. ---
const FIELD_YARDS := 100.0          # goal line to goal line
const END_ZONE_YARDS := 10.0        # each end zone
const FIELD_WIDTH := 40.0           # sideline to sideline
const HALF_LENGTH := FIELD_YARDS / 2.0 + END_ZONE_YARDS   # 60: back wall to midfield
const HALF_WIDTH := FIELD_WIDTH / 2.0
const GOAL_X := FIELD_YARDS / 2.0   # 50: the goal line (end zone starts here, out to HALF_LENGTH)

# --- gravity ---
const GRAVITY := 91.7               # 2200 px/s^2
const MAX_FALL := 50.0              # 1200 px/s

# --- running / air ---
const RUN_SPEED := 13.3             # 320 px/s
const AIR_SPEED := 13.3             # 320 px/s
const CARRY_MULT := 0.78            # carrier is slower on the ground

# --- jumping ---
const JUMP_SPEED := 34.2            # 820 px/s ; rises ~6.4 yd
const DOUBLE_JUMP_SPEED := 28.3     # 680 px/s ; replaces vertical velocity
const AIR_JUMPS := 1                # one air jump (double jump)
const JUMP_CUT := 0.5               # release rising -> *0.5 once (short hop)

# --- walls ---
const WALL_JUMP_UP := 30.0          # 720 px/s
const WALL_JUMP_AWAY := 15.8        # 380 px/s
const WALL_HOP_UP := 21.7           # 520 px/s (straight up the wall, once)
const WALL_DROP_AWAY := 13.3        # 320 px/s (let go, keep the jump)
const WALL_SLIDE_MAX := 5.8         # 140 px/s (falling friction while clinging)
const WALL_GRAVITY_SCALE := 0.3     # gentle fall while clinging
const WALL_JUMPS := 1               # one jump per wall
const WALL_CONTROL_LOCK := 0.18     # s of no air steering after a wall jump

# --- slide / crouch ---
const SLIDE_SPEED := 23.3           # 560 px/s
const SLIDE_DURATION := 0.45        # s
const SLIDE_FRICTION := 2.5         # vel *= (1 - friction*dt)
const CROUCH_SPEED := 4.6           # 110 px/s (crawl)

# --- ball ---
const BALL_RADIUS := 0.5            # 12 px
const BALL_GRAVITY := 91.7
const BALL_RESTITUTION := 0.75
const BALL_FRICTION := 0.1
const BALL_REST_SPEED := 2.0        # a gentle-enough bounce settles the ball
const BALL_STOPPED := 0.33          # 8 px/s : "has come to rest"

# --- throwing / aiming ---
const POWER_MIN := 12.5             # 300 px/s
const POWER_MAX := 58.3             # 1400 px/s
const POWER_RATE := 37.5            # 900 px/s per second while adjusting
const AIM_PITCH_MIN := -20.0        # degrees
const AIM_PITCH_MAX := 70.0

# --- catching / tagging (sphere radii) ---
const PICKUP_RADIUS := 2.3          # 55 px
const TAG_RADIUS := 1.7             # 40 px

# --- phase timers ---
const PLAY_CALL_SECONDS := 20.0     # soft cap on placement+aim before an auto-lock
const PRE_THROW_SECONDS := 8.0      # free running before the auto-throw
const LOOSE_BALL_SECONDS := 3.0     # recover a resting ball or the play is dead
const RESULT_SECONDS := 2.75        # show the outcome before the next down

# --- match ---
const DOWNS_PER_POSSESSION := 4
const POINTS_TO_WIN := 5
const DEFENDER_GAP_YARDS := 10.0    # defender spawns at least this far past the QB, toward its end zone

# --- player body (capsule) ---
const PLAYER_RADIUS := 0.5          # ~1 yd wide
const PLAYER_HEIGHT := 1.75         # standing
const PLAYER_CROUCH_HEIGHT := 1.1   # crouch/slide
