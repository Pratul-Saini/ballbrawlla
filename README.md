# ballbrawlla

Prototype of a 2D ball-throwing platformer: a 2-player football match played across platforms.

- [prototype-design.md](prototype-design.md): movement, world and physics requirements
- [further-gameplay-features.md](further-gameplay-features.md): teams, roles, downs, play call
- [gameplay-rules.md](gameplay-rules.md): **the rules as built**, including edge cases

## Run

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows (source .venv/bin/activate elsewhere)
pip install -e .[dev]
python -m ballbrawlla           # practice: you on offense vs a defender that stands still
python -m ballbrawlla --sandbox # free play in the small arena, no rules (movement tuning)
python -m ballbrawlla --sandbox --level field_02   # free play on a match field (field_01..field_14)
python -m ballbrawlla --level field_03             # a match on another field (also works with --host)
pytest                          # physics, player, rules, match, network and level-route tests (~2 min;
                                #   the skill-route sweeps are most of it)
```

## Godot version

The game is also ported to Godot 4 (`godot/`), with the same rules, levels, menus and network play. See
[docs/godot.md](docs/godot.md) for how to run it, how it was checked against this Python version, and how to build
apps for Mac and Windows.

## Menu and packaged builds

`python -m ballbrawlla` with no flags opens the menu (Play > Free play, Two players, Online). Flags such as
`--level field_05`, `--catch`, `--local`, `--host`, `--join ADDR` still work. To build an app you can send to a friend
(Mac or Windows) and for first-run notes, see [docs/packaging.md](docs/packaging.md).

## Session notes

Press **F2** in any mode to write notes about the session you're playing (playtest feedback,
bugs, ideas). Enter starts a new line, Ctrl+S saves, Esc or F2 saves and closes. While the panel is
open your keys only go to the notes; practice, local and sandbox pause, and network games keep
running with your player standing still.

Notes are saved to `logs/sessions/<date_time>_<mode>_<level>/notes.md`. A session is one run of the
game: every save in the same run rewrites that same file (reopening the panel brings your notes
back to keep editing), and the next run starts a new file. The header records the mode, level, start
time, last save and the score at that moment. Notes are also saved when the game quits.
`logs/` is git-ignored.

## Two players on one screen

```sh
python -m ballbrawlla --local                    # any level: --local --level field_09
```

Both players share one window and see everything, including the throw aim and the Defender's
spawn. The camera zooms out (down to 40%) to keep both players in view, and the ball while it's in the air.

| | Blue | Red |
|---|---|---|
| Move / jump / down | W A S D | Arrow keys |
| Catch, pick up, tag, confirm | F | . (period) |
| Lock in, throw | G | / (slash) |
| Controller | first one connected | second one connected |

During the play call the **mouse belongs to whichever side is on offense** (aiming the throw and
the on-screen button). **F5** or a controller's **Options** starts a new match. R is not used here,
because it sits next to Blue's keys. F1 toggles the debug overlay, F3 hides or shows the controls HUD,
and Esc quits.

## Local network play (2 players)

Both machines need this repo installed as above and on the same network.

```sh
python -m ballbrawlla --host               # machine A: prints "Hosting on 192.168.x.y:50555"
python -m ballbrawlla --join 192.168.x.y   # machine B
```

- The host is **Blue** and runs the only simulation; the joining player is **Red**. A coin flip
  picks who starts on offense. The match starts once both are connected.
- The client sends its input and draws the view the host sends back. Each player is sent only
  what they're allowed to see (the defense never receives the throw aim, and the offense never
  receives the Defender's spawn during the play call).
- The level and tuning come from the host, so the client's `config.py` and `levels/` don't matter.
- Players pass through each other. If both press Z on the same tick, the one closer to the ball gets it.
- Windows Firewall will ask to allow Python the first time you host. Allow it on private networks.
- Use `--port N` on both sides to change the port (default 50555). R (reset) works on the host only.
- You can test on one machine with two terminals: `--host`, then `--join 127.0.0.1`.

## Online play with an invite code (different networks)

The host gets a short **invite code** and the other player, on any network, types it in. Both connect
out to a **relay server**, so there's no port forwarding or IP address to share.

```sh
python -m ballbrawlla --host --online             # prints and shows "Invite code: KQ7-M3X"
python -m ballbrawlla --join-code KQ7-M3X         # the other player, anywhere
```

In the menu: **Play → Online → Host online game / Join with code** (Ctrl+V pastes a code). The host's
waiting screen shows the code, and **Ctrl+C** copies it. Codes never use 0, O, 1, I or L, and dashes,
spaces and case don't matter. A friend on the same network can still join the same game by address.

**Relay server.** Someone has to run one where both players can reach it (any small VPS, open TCP 50600):

```sh
pip install -e .                     # or just copy the repo: the relay needs only Python 3.11+
ballbrawlla-relay --port 50600       # = python -m ballbrawlla.net.relay_server
```

Players find it via `--relay HOST[:PORT]`, the `BALLBRAWLLA_RELAY` environment variable, or `DEFAULT_RELAY`
in `src/ballbrawlla/net/invite.py` (set that once it's deployed so nobody has to configure anything).
To try it on one machine, run the relay, then `--host --online --relay 127.0.0.1` and
`--join-code CODE --relay 127.0.0.1` in two more terminals.

The relay only passes bytes along and can't read the game's rules, but traffic is **not encrypted**. The
joiner plays one internet round trip behind the host (there's no client-side prediction yet).

## Controls

**Play call** (15s; see [gameplay-rules.md](gameplay-rules.md)):

| Input | Offense | Defense |
|---|---|---|
| Arrows / stick (normal movement: run, jump, wall-jump, slide) | Move the QB (1st down only); it can only be confirmed standing on a platform in the yellow zone | Move the Defender; it can only lock in standing on a platform in your zone |
| Z / on-screen button | Confirm the QB spot | Lock in |
| Hold mouse and point, or ←/→ and ↑/↓ | Aim: direction = angle, distance = power | |
| X / on-screen button | Lock in the throw | Lock in |

**Execution** (you are the WR on offense, the Defender on defense):

| Key | Action |
|---|---|
| ← / → | Run (fixed speed) |
| ↑ | Jump / double jump / hop up a wall |
| ↓ | Crouch (standing) / slide (running); hold ←/→ while crouched to crawl |
| Z | Catch / pick up the ball · tag the opponent carrying the ball |
| R / F1 / F2 / F3 / Esc | New match (practice / host only) · debug overlay · session notes · show / hide the controls HUD · quit |

In `--sandbox` mode the original controls apply: Z with the ball enters aim, X throws.

**PS5 controller (DualSense)**: plug in over USB or pair over Bluetooth, before or during play.
DualShock 4 and Xbox pads work too (same layout). Every controller on a machine drives that
machine's player, alongside the keyboard and mouse.

| DualSense | Action | Keyboard |
|---|---|---|
| Left stick / D-pad | Run, crouch/slide (down), move the spawn cursor, aim angle/power while aiming | Arrows |
| Cross | Jump (hold for full height) | ↑ |
| Square | Catch / pick up / tag · confirm QB spot · lock in Defender | Z |
| Circle, R1 or R2 | Lock in the throw / Defender · throw (sandbox) | X |
| Right stick | Point the aim (play call and sandbox) | Mouse |
| Options | New match (practice / host) · reset (sandbox) | R |
| Create or touchpad click | Debug overlay | F1 |

If Steam is running it may take over the controller; close Steam or turn off its
PlayStation controller support if the pad isn't detected. The status line at the bottom
shows the controller's name once it's connected.

Catching is forgiving: pressing Z shortly before the ball arrives, or shortly after it passes, still catches it.

Wall cling: jump into a wall while holding toward it. With no input you slide slowly down.
A wall gives you one jump: ↑ hops up it (then you slide down), ↑ + away wall-jumps, or
press away to drop off and jump once in the air. Walls can't be climbed.

## Structure

```
src/ballbrawlla/
  config.py            Tuning: every gameplay number (movement, ball, field, downs, timers)
  input.py             Keyboard + mouse + controllers -> Intent (the sim only ever sees Intents)
  gamepad.py           PS5 DualSense / SDL game controllers: button and stick mapping
  game.py              Game: physics world (players, ball, pickups), step(intents, dt). No rules.
  session.py           Session: a match in progress - phases of each down, driving Game for the WR/Defender
  main.py              Window + fixed-timestep loop (120 Hz); practice / --host / --join / --sandbox
  rules/               Pure rules, no pygame (see gameplay-rules.md)
    teams.py           Team (LEFT/Blue, RIGHT/Red), Role (QB, WR, DEF)
    field.py           Yards <-> px, goal lines, end zones, valid spawn spots on platform tops
    down.py            Down, SpawnRule (ChooseInRegion | FixedSpot), spawn ranges, PlayResult, next_down
    play_call.py       PlayCall: QB drag/confirm, aim, Defender placement, locks, timeout restart
    match.py           Match: score, coin flip, first to 5
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
    host.py            Accepts clients, turns their messages into Intents, sends each its view
    client.py          Connects, sends Intents, receives the latest view
    view.py            Session -> one human's view (hidden info left out)
  render/
    match_renderer.py  Draws a match from a view: camera, field markings, play call, HUD, minimap
    renderer.py        Sandbox drawing of a raw Game (camera optional)
    field_markers.py   Yard lines, end zones and numbers, shared by both renderers
levels/field_NN.json   Match fields 01-14 (100 yd + end zones; bigger levels set their own yard_px)
tools/gen_levels.py    Generates every field level (python tools/gen_levels.py)
levels/arena_01.json   Small sandbox arena. Platforms are {x, y, w, h[, type]}; bounds are implicit.
tests/                 Collision, player, catching, platforms, rules, match session and network tests
```

### Model

- **Physics**: fixed 120 Hz step. Player and ball each have their own gravity (equal by default).
  The player is moved one axis at a time and pushed out of solids. Its contacts (ground/ceiling/left/right)
  come from 1px probes. The ball reflects off platforms as `v' = v_t(1-friction) - e·v_n`
  and comes to rest when an impact is slower than `ball_rest_speed`.
- **World**: a rectangle with boundary walls generated automatically, plus any number of
  rectangular platforms (horizontal or vertical, floating or connected).
- **Platform types**: a platform entry accepts an optional `type` of `"thin"` or `"solid"`.
  An entry without `type` is solid. Any other value raises a `ValueError`. Players and the ball
  land on a thin platform only when moving downward from at or above its top edge. They pass through
  it moving upward or sideways. Solid platforms block from all sides. Dropping down through a thin
  platform is not supported.
- **Player**: a state machine. Each state sets velocity from the Intent, scales or caps gravity
  (wall friction), and returns the next state.
- **Rules**: `Session` runs each down as play call -> execution. Downs differ only in how the QB
  spawn is decided (`ChooseInRegion` on a fresh possession, `FixedSpot` otherwise); see
  [gameplay-rules.md](gameplay-rules.md).
- **Network**: the host is the authority. Clients send Intents at 120 Hz; the host steps
  the `Session` with every player's Intent and sends each player their own view every frame. There is no
  client-side prediction, which is fine on a LAN (a few ms round trip).

- **Catching**: three values in `config.py` set how forgiving a catch is.
  - `pickup_radius` (55 px): player-center to ball-center distance that counts as in reach.
  - `pickup_buffer_time` (0.1 s): a Z press stays armed this long, waiting for the ball.
  - `pickup_grace_time` (0.1 s): a Z press still counts this long after the ball left reach.

  The host judges the late-press grace against the ball's recent positions, so it applies
  equally to the host's local player and to joining players.

Tune game feel in `config.py`. Change the arena in `levels/*.json`.
