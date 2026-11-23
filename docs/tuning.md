# Tuning reference

Every gameplay number lives in `src/ballbrawlla/config.py` as the `Tuning` dataclass. Change a value there to change game feel. Units: pixels, seconds, degrees. y is down.

In network play the host's `Tuning` is sent to the joiner, so both sides use the host's values.

## Simulation
| Field | Default | Meaning |
|---|---|---|
| `physics_hz` | 120 | fixed simulation rate |
| `max_players` | 2 | slots in a hosted game (host plus joiners) |

## Player body
| Field | Default | Meaning |
|---|---|---|
| `player_width` | 24 | box width |
| `player_height` | 42 | standing height |
| `player_crouch_height` | 26 | crouch and slide height |
| `player_gravity` | 2200 | px/s² |
| `player_max_fall_speed` | 1200 | px/s cap |

## Running and jumping
| Field | Default | Meaning |
|---|---|---|
| `run_speed` | 320 | fixed ground speed |
| `air_speed` | 320 | fixed horizontal speed in the air |
| `jump_speed` | 820 | upward speed of a ground jump (about 153 px rise) |
| `jump_cut_multiplier` | 0.5 | releasing Up early scales the upward speed by this |
| `air_jumps` | 1 | extra jumps in the air. 0 disables the double jump |
| `double_jump_speed` | 680 | upward speed of an air jump |

## Crouch and slide
| Field | Default | Meaning |
|---|---|---|
| `slide_enabled` | True | Down while moving slides instead of crouching |
| `slide_speed` | 560 | starting slide speed |
| `slide_duration` | 0.45 | maximum slide time in seconds |
| `slide_friction` | 2.5 | per-second decay of slide speed |
| `crawl_speed` | 110 | walking speed while crouched (0 freezes the crouch, the old behavior) |
| `carry_speed_multiplier` | 0.78 | scales run, slide and crawl speed while holding the ball (not air speed or jumps) |

## Wall cling
| Field | Default | Meaning |
|---|---|---|
| `wall_gravity_scale` | 0.3 | gravity multiplier while sliding down a wall |
| `wall_slide_max_speed` | 140 | maximum downward speed while clinging |
| `wall_hold_sticks` | False | pressing into the wall stops sliding entirely |
| `wall_jump_x` | 380 | horizontal kick away from the wall |
| `wall_jump_y` | 720 | upward speed of a wall jump |
| `wall_jump_control_lock` | 0.18 | seconds of ignored air steering after a wall jump |
| `wall_climb_speed` | 520 | Up while clinging: upward hop speed |
| `wall_jumps` | 1 | jumps a cling gives: a hop up it, a wall jump, or one air jump after dropping off |
| `wall_jump_grace` | 0.1 | seconds in which Up and away still count as pressed together |

## Ball
| Field | Default | Meaning |
|---|---|---|
| `ball_radius` | 12 | px |
| `ball_gravity` | 2200 | px/s², starts equal to the player's |
| `ball_restitution` | 0.75 | fraction of normal speed kept on a bounce (1.0 = no loss) |
| `ball_bounce_friction` | 0.1 | fraction of sliding speed lost per bounce |
| `ball_rest_speed` | 40 | impacts slower than this stop instead of bouncing |
| `ball_rolling_drag` | 1.5 | per-second horizontal decay while resting on a floor |

## Pick up, aim and throw
| Field | Default | Meaning |
|---|---|---|
| `pickup_radius` | 55 | player-center to ball-center distance for a pickup |
| `pickup_buffer_time` | 0.1 | seconds a Z press stays armed waiting for the ball. 0 disables |
| `pickup_grace_time` | 0.1 | seconds a Z press still counts after the ball left reach (host-judged). 0 disables |
| `throw_enabled` | True | False disables aiming and throwing |
| `aim_rate` | 180 | degrees per second the aim rotates |
| `power_min` | 300 | minimum throw speed |
| `power_max` | 1400 | maximum throw speed |
| `power_rate` | 900 | power change per second while Up or Down is held |

## Derived values (not fields)
| Property | Value | Meaning |
|---|---|---|
| `dt` | 1 / physics_hz | seconds per tick |
| `pickup_buffer_ticks` | 12 | `pickup_buffer_time` converted to ticks |
| `pickup_grace_ticks` | 12 | `pickup_grace_time` converted to ticks |

## Tuning tips

- **Catching feels too hard:** raise `pickup_radius`, `pickup_buffer_time` or `pickup_grace_time`. Grace helps joiners most.
- **Catching feels too easy or sticky:** lower the three values. Setting both times to 0 gives plain "press Z while the ball is within the radius".
- **Floaty or heavy jumps:** change `player_gravity` together with `jump_speed`. Jump height is `jump_speed² / (2 * gravity)`.
- **Ball too bouncy:** lower `ball_restitution`. Rest comes sooner with a higher `ball_rest_speed`.
- The aim arc uses `ball_gravity`, so it stays accurate if you change it, but it never accounts for platforms.
