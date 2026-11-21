# ballbrawlla

Prototype of a 2D ball-throwing platformer. See [prototype-design.md](prototype-design.md) for requirements.

## Run

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows (source .venv/bin/activate elsewhere)
pip install -e .[dev]
python -m ballbrawlla           # or: ballbrawlla --level levels/arena_01.json
pytest                          # physics + player state tests
```

## Controls

| Key | Action |
|---|---|
| ← / → | Run (fixed speed). While aiming: rotate aim (full circle) |
| ↑ | Jump / double jump / hop up a wall. While aiming: more power |
| ↓ | Crouch (standing) / slide (running). While aiming: less power |
| Z | Pick up ball when near · enter aim when holding (on ground) · cancel aim |
| X | Throw (while aiming) |
| R / F1 / Esc | Reset · toggle debug overlay · quit |

Wall cling: jump into a wall while holding toward it. With no input you slide slowly down;
press away to wall-jump, press ↑ to climb.

## Structure

```
src/ballbrawlla/
  config.py            Tuning: every gameplay number (speeds, gravity, restitution, aim...)
  input.py             Keyboard -> Intent (the sim only ever sees Intents)
  game.py              Game: owns level/player/ball, step(intent, dt). No rendering.
  main.py              Window + fixed-timestep loop (physics at 120 Hz)
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
  render/
    renderer.py        Primitive drawing, aim ring + predicted arc, debug overlay
levels/arena_01.json   Platforms as {x, y, w, h}; spawns are centers. Bounds are implicit.
tests/                 Collision math and player behaviour, driven through Game.step
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

Tune game feel in `config.py`. Change the arena in `levels/*.json`.
