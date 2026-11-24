# Ball Brawl: how the game works

This folder describes the game as it is implemented today. Each file covers one aspect and names the source files it describes, so you can read the doc and the code side by side.

| Doc | What it covers | Main source |
|---|---|---|
| [physics.md](physics.md) | Coordinates, integration, collision rules shared by everything | `physics/` |
| [player.md](player.md) | Movement, the state machine, jumps, walls, crouch and slide | `entities/player.py`, `entities/player_states.py` |
| [ball.md](ball.md) | Ball physics and behavior: gravity, bounces, resting, held | `entities/ball.py` |
| [catching-and-throwing.md](catching-and-throwing.md) | Picking the ball up (Z), aiming, throwing, the catch window | `entities/player.py`, `game.py` |
| [level.md](level.md) | Level format, platform types, spawns, the bundled arena, design guidelines | `world/level.py`, `levels/arena_01.json` |
| [networking.md](networking.md) | Host/join play, messages, per-player views, hidden information | `net/` |
| [input-and-rendering.md](input-and-rendering.md) | Keyboard/mouse/controller to Intent, the game modes and loops, session notes, drawing | `input.py`, `gamepad.py`, `main.py`, `notes.py`, `render/` |
| [../gameplay-rules.md](../gameplay-rules.md) | The football rules as built: downs, play call, execution, scoring, every field level | `rules/`, `session.py` |
| [tuning.md](tuning.md) | Every gameplay number in `config.py` | `config.py` |

## The game in one paragraph

A 2-player football platformer. Each down has a play call (both sides run their QB / Defender into place and lock in) and an execution: a 5 s route window in which the WR carries the ball and neither side may cross the line of scrimmage, then live play (the WR runs for the end zone, the Defender tags). Throwing is switched off (`throw_enabled`); with it on, the offense aims in the play call, the QB throws after 10 s, and catch, interception and pick six come back. 4 downs per possession, first to 5 touchdowns. Players run, jump, double jump, wall-cling and wall-jump, slide and crawl. Rules are in [../gameplay-rules.md](../gameplay-rules.md); the physics `Game` below is driven by the rules `Session`.

## How one tick works

The simulation runs at a fixed 120 Hz (`dt = 1/120` s) no matter the frame rate. Everything happens in `Game.step(intents, dt)`:

```
for each connected player:
    Player.update(intent, dt, solids, ball, thin, ball_trail)
        1. pickup attempt        (Z press or armed buffer)
        2. state.update          (sets velocity, may change state)
        3. stand back up         (if the state wants full height)
        4. gravity + fall cap    (semi-implicit Euler, velocity part)
        5. move_aabb             (X then Y, push out of platforms)
        6. probe_contacts        (ground / ceiling / walls for next tick)
resolve pickups                  (one winner for the ball)
Ball.update                      (held: follow hand; free: gravity, bounce)
update ball_trail                (recent free-ball positions, for catch grace)
```

Order matters in a few places:
- Players update before the ball, so a player judges a pickup against the ball position from the end of the previous tick.
- A state reads the contacts probed at the end of the previous tick. Landing is therefore noticed one tick after the box touches the floor.
- A held ball follows the hand after the player has moved, so it never lags behind its holder.

## Key ideas

- **The sim only sees Intents.** `Intent` is a small struct of held directions and one-tick press edges. Keyboard, network clients and tests all produce Intents. The simulation never reads keys or sockets.
- **The host is the only simulation.** In network play the host steps the game and sends snapshots. Clients draw them. See [networking.md](networking.md).
- **All gameplay numbers live in `Tuning`.** Nothing else should hardcode them. See [tuning.md](tuning.md).
- **Screen coordinates are y-down.** "Up" is negative y everywhere.

## Source map

```
src/ballbrawlla/
  config.py            Tuning dataclass (all gameplay numbers)
  input.py             Keyboard -> Intent
  game.py              Game: level, players, ball, step(), pickup resolution
  main.py              Window, fixed-timestep loop, --host / --join
  physics/             body, shapes, collision (AABB sweep, circle bounce), vec
  world/level.py       Level, Platform, JSON load/save
  entities/            player, player_states, ball
  net/                 protocol, host, client, snapshot
  render/renderer.py   Primitive drawing and debug overlay
levels/arena_01.json   The bundled arena
tests/                 pytest suite
```

## What is not there

- No scoring, goals, rounds or win condition.
- No ball-vs-player collision. Players and the ball pass through each other, and players pass through each other. The ball only interacts with players through pickup and throw.
- No drop-through on thin platforms. Down means crouch or slide.
- No client-side prediction or interpolation in network play.
- No sound, art or menus. Everything is drawn with rectangles and circles.
