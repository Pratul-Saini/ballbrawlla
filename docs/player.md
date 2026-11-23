# Player

Source: `entities/player.py` (the body, tick order, ball actions) and `entities/player_states.py` (the state machine). Numbers are the defaults in `config.py`.

## The body

- A box 24 px wide and 42 px tall (26 px tall while crouching or sliding), moved by the rules in [physics.md](physics.md).
- `facing` is -1 or +1. It follows the last direction pressed and drives the slide direction and where a held ball sits.
- `contacts` holds the four contact flags from the last tick.
- `jumps_left` counts air jumps (1 by default, so a double jump).
- `control_lock` is a timer that ignores air steering after a wall jump.

## Controls

| Key | Action |
|---|---|
| Left / Right | run (fixed speed). While aiming: rotate the aim |
| Up | jump, double jump, climb a wall. While aiming: more power |
| Down | crouch or slide. While aiming: less power |
| Z | pick up the ball, enter aim, cancel aim |
| X | throw (while aiming) |

Horizontal movement is **fixed speed**, with no acceleration. A direction held sets `vel.x` to `move_x * speed` directly, and releasing it stops you at once (except while sliding).

## One tick for a player

1. **Pickup attempt.** If a Z press happened, or an armed Z buffer is still running, try to claim the ball. See [catching-and-throwing.md](catching-and-throwing.md).
2. **State update.** The current state reads the Intent and the contacts, sets velocity, and may return a new state.
3. **Stand up.** If the state wants full height and the player is crouched, try to stand up (needs room, solids only).
4. **Gravity.** `vel.y += gravity * state_scale * dt`, then `vel.y` is capped by the state's maximum fall speed.
5. **Move and collide.** `move_aabb`, then update position.
6. **Probe contacts** for the next tick.

## State machine

```
Grounded --Up--> Airborne --touch wall + press into it--> WallCling
   |  ^             ^  |                                     |
Down|  |release     |  +--land--> Grounded   Up+away (wall jump) / away (drop)
    v  |            +--------------------------------------+   / lose wall
 Crouch / Slide

Grounded or Crouch --Z (holding ball)--> Aiming --X throw / Z cancel--> Grounded
```

Each state's `update` runs before physics for the tick. It sets velocity and returns the next state, or nothing to stay.

### Grounded
- If `on_ground` is false, becomes Airborne (walking off a ledge).
- `vel.x = move_x * run_speed` (320 px/s). Updates `facing`.
- Z with the ball in hand enters Aiming.
- Up jumps: `vel.y = -jump_speed` (820 px/s), becomes Airborne.
- Down becomes Slide if moving (and sliding is enabled), otherwise Crouch.
- On entry: refills air jumps and clears `control_lock`.

### Carrying the ball
While holding the ball, run, slide and crawl speed are multiplied by `carry_speed_multiplier` (0.78: about 250 px/s instead of 320). Air speed and jumps are unchanged. A free defender wins a straight race on open ground, so the carrier escapes by using the level: jumps, climbs and the skill routes all still work with the ball.

### Airborne
- Lands (becomes Grounded) when `on_ground` is true and `vel.y >= 0`.
- Steering: `vel.x = move_x * air_speed` (320 px/s), unless `control_lock` is running.
- Pressing into a wall (`wall_left` with left held, or `wall_right` with right held) becomes WallCling, unless the rest of the current jump will carry the feet above that wall's top (**ledge assist**, `Player.will_clear_wall`). Running up a step you can clear never sticks you to its face.
- **One cling per wall:** you can't cling to the wall you last clung to (`Player.last_wall`) until you've clung to a different wall or landed. Wall-jumping off a wall and steering back into it just slides you past it; bouncing between two walls (a chimney) still works.
- **Late wall jump:** for `wall_jump_grace` (0.1 s) after dropping off a wall, Up still wall-jumps off it, so pressing away a moment before Up counts as pressing them together.
- Up with air jumps left: double jump, `vel.y = -double_jump_speed` (680 px/s), costing one air jump. This **replaces** the vertical velocity, so doing it near the apex gains the most.
- **Jump cut:** after a jump, releasing Up while still rising multiplies `vel.y` by 0.5 once. A short tap gives a short hop. Holding Up gives the full jump.

### WallCling
- Entered from Airborne by pressing into a wall. On entry: the wall is remembered as `last_wall`, velocity zeroed, air jumps set to `wall_jumps` (1): **one jump per wall**, spent on a hop, a wall jump, or an air jump after dropping off (landing restores the double jump), player turns to face away from the wall.
- Leaves to Grounded if on the ground, or to Airborne if the wall is gone.
- `vel.x` is held at 0.
- **Wall jump:** Up + away from the wall. Sets velocity to (380 px/s away, -720 px/s up), locks air control for 0.18 s, becomes Airborne. Up a moment before away (within `wall_jump_grace`, 0.1 s) also counts.
- **Drop off:** away without Up. Lets go: 320 px/s away, no upward kick, no control lock. The wall's jump is kept, so Up later is one air jump (680 px/s).
- **Wall hop:** Up alone gives one hop of -520 px/s, using the wall's jump. After that Up does nothing and you slide down (or drop off with no jump): walls can't be climbed.
- Gravity is full while rising and scaled by 0.3 while falling, with a maximum slide speed of 140 px/s. This is the wall friction.
- `wall_hold_sticks` (off by default) would stop sliding entirely while pressing into the wall.

### Crouch
- Height 26 px. The player **crawls** at `crawl_speed` (110 px/s, about 35% of run speed) in the direction held, so a slide that ends under a low gap never traps them.
- Becomes Airborne if the ground goes away.
- Up jumps if there is room to stand. Releasing Down returns to Grounded if there is room.
- Z picks up or aims as in Grounded.

### Slide
- Entered from Grounded with Down while moving. Height 26 px.
- Starts at `slide_speed` 560 px/s in the facing direction. Speed decays by a factor of `(1 - 2.5 * dt)` each tick.
- Lasts 0.45 s, or ends earlier if speed drops under 30% of run speed. A full slide covers roughly 150 px.
- Up jumps out of it if there is room to stand.
- At the end: Crouch if Down is held or there is no room to stand, otherwise Grounded.
- Z picks up the ball while sliding. Aim cannot start from a slide.

### Aiming
- Fixed in place (`vel.x = 0`). Entered with Z while holding the ball, from Grounded or Crouch.
- On entry: aim angle 45 degrees if facing right, 135 if facing left. Power is the midpoint of the range (850).
- Left/right rotates the aim at 180 degrees per second (full circle). Right is clockwise.
- Up/down changes power at 900 per second, clamped to 300..1400.
- X throws and returns to Grounded. Z cancels and returns to Grounded. Leaving the ground returns to Airborne.
- Z does not pick anything up while aiming.

## Reference numbers

| Move | Number | Result |
|---|---|---|
| Jump | 820 px/s, gravity 2200 | rises about 153 px, airborne 0.75 s |
| Horizontal reach of a full jump | 320 px/s for 0.75 s | about 240 px |
| Double jump from the apex | 680 px/s | about 105 px more, so about 258 px total |
| Wall jump | 720 px/s up | about 118 px rise |
| Wall climb hop | 520 px/s up | about 61 px rise |
| Max fall speed | 1200 px/s | reached after about 0.55 s of falling |

These numbers are what the level design guidelines in [level.md](level.md) are based on.

## Multiplayer notes

- Each player has an id (`pid`) and a `connected` flag. Disconnected slots are not simulated and are drawn dimmed.
- Players do not collide with each other.
