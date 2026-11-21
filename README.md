# ballbrawlla

Prototype of a 2D ball-throwing platformer. See [prototype-design.md](prototype-design.md) for requirements.

## Run

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows (source .venv/bin/activate elsewhere)
pip install -e .[dev]
python -m ballbrawlla           # or: ballbrawlla --level levels/arena_01.json
pytest                          # physics, player, multiplayer and network tests
```

## Local network play (2 players)

Both machines need this repo installed as above and on the same network.

```sh
python -m ballbrawlla --host               # machine A: prints "Hosting on 192.168.x.y:50555"
python -m ballbrawlla --join 192.168.x.y   # machine B
```

- The host is P1 (blue) and runs the only simulation. The client sends its key input and
  draws the snapshots the host sends back. The level and tuning come from the host, so the
  client's `config.py` and `levels/` don't matter.
- Players pass through each other. If both press Z on the same tick, the one closer to the ball gets it.
- Windows Firewall will ask to allow Python the first time you host. Allow it on private networks.
- Use `--port N` on both sides to change the port (default 50555). R (reset) works on the host only.
- You can test on one machine with two terminals: `--host`, then `--join 127.0.0.1`.

## Controls

| Key | Action |
|---|---|
| ← / → | Run (fixed speed). While aiming: rotate aim (full circle) |
| ↑ | Jump / double jump / hop up a wall. While aiming: more power |
| ↓ | Crouch (standing) / slide (running). While aiming: less power |
| Z | Pick up ball when near · enter aim when holding (on ground) · cancel aim |
| X | Throw (while aiming) |
| R / F1 / Esc | Reset (single player / host only) · toggle debug overlay · quit |

Wall cling: jump into a wall while holding toward it. With no input you slide slowly down;
press away to wall-jump, press ↑ to climb.

## Structure

```
src/ballbrawlla/
  config.py            Tuning: every gameplay number (speeds, gravity, restitution, aim...)
  input.py             Keyboard -> Intent (the sim only ever sees Intents)
  game.py              Game: owns level/players/ball, step(intents, dt), pickup resolution. No rendering.
  main.py              Window + fixed-timestep loop (physics at 120 Hz); single player / --host / --join
  physics/
    body.py            Body: pos, vel, acc, gravity; semi-implicit Euler
    shapes.py          AABB (player, platforms), Circle
    collision.py       AABB sweep-and-push + contact probes; circle-vs-AABB + bounce
  world/
    level.py           Level/Platform, auto-generated floor/ceiling/walls, JSON loader
  entities/
    player.py          Player: kinematic AABB + state machine + pickup/throw
    player_states.py   Grounded, Airborne, WallCling, Crouch, Slide, Aiming
    ball.py            Ball: gravity, sub-stepped collision, restitution, held_by
  net/
    protocol.py        Non-blocking newline-JSON TCP connection, message formats
    host.py            Accepts clients, turns their messages into Intents, broadcasts snapshots
    client.py          Connects, sends Intents, receives the latest snapshot
    snapshot.py        Game state <-> snapshot dict
  render/
    renderer.py        Primitive drawing (players colored per slot), aim ring + arc, debug overlay
levels/arena_01.json   Platforms as {x, y, w, h}; player_spawns / ball_spawn are centers. Bounds are implicit.
tests/                 Collision, player, multiplayer and loopback network tests
```

### Model

- **Physics**: fixed 120 Hz step. Player and ball each have their own gravity (equal by default).
  The player is moved one axis at a time and pushed out of solids. Its contacts (ground/ceiling/left/right)
  come from 1px probes. The ball reflects off platforms as `v' = v_t(1-friction) - e·v_n`
  and comes to rest when an impact is slower than `ball_rest_speed`.
- **World**: a rectangle with boundary walls generated automatically, plus any number of
  rectangular platforms (horizontal or vertical, floating or connected).
- **Player**: a state machine. Each state sets velocity from the Intent, scales or caps gravity
  (wall friction), and returns the next state.
- **Network**: the host is the authority. Clients send Intents at 120 Hz; the host steps
  `Game` with every player's Intent and broadcasts a snapshot each frame. There is no
  client-side prediction, which is fine on a LAN (a few ms round trip).

Tune game feel in `config.py`. Change the arena in `levels/*.json`.
