# The Godot version

`godot/` is a port of the whole game to Godot 4 and GDScript, with the same rules, levels, controls, menus and network
protocol. The Python version is untouched and stays as the reference. The Godot version is the one to hand to friends.

## Run it

```
/Applications/Godot.app/Contents/MacOS/Godot --path godot                       # the menu
/Applications/Godot.app/Contents/MacOS/Godot --path godot -- --level=field_05    # practice on a level
```

Options go after the double dash. A launch that cannot work prints one line and exits with status 2, like the Python game.

| Option | What it does |
|---|---|
| `--level=field_05` | practice on that level (alone) |
| `--catch` | catch practice: football rules, no defender |
| `--local` | two players on one screen |
| `--sandbox` | free play (the arena unless `--level` says otherwise) |
| `--host` | host a game on this network (`--port=N` changes the port) |
| `--host` `--online` `--relay=ADDR` | host with an invite code through a relay server |
| `--join=ADDRESS` | join a game |
| `--join-code=CODE` `--relay=ADDR` | join with an invite code |

Everything in the Python game is here: the launcher with the animated backdrop, the level picker, the in-game menu (Esc),
session notes (F2), music (M mutes), per-run logs, LAN discovery, hosting and joining, and invite codes.

## Where things are

| | |
|---|---|
| `godot/scripts/` | the game. The simulation (`game.gd`, `player*.gd`, `ball.gd`, `collision.gd`, `session.gd`, ...) has no engine types in it: plain 64-bit numbers, like the Python code. |
| `godot/levels/` | a copy of `levels/` (a symlink is unreliable on Windows). `tests/test_godot_sync.py` fails if they differ. |
| `godot/tests/` | the tests. `godot/run_tests.sh` runs them headless. |
| `godot/tests/data/` | what the Python game does, recorded: the tests check the port against it. About 10 MB. |
| `tools/` | `export_parity.py` records that data; `interop_test.py`, `godot_cli_check.py` and `menu_shots.py` are checks you can run. |

## How we know it matches the Python game

The Python game records what it does (`.venv/bin/python tools/export_parity.py`), and the Godot tests replay the same
inputs and compare:

- every tuning number, all 15 levels, every launch check and error message, invite-code handling
- the physics: 60+ scenarios, including random play on 9 levels, compared tick by tick
- the rules: field geometry, 120 down transitions, 14 whole matches
- 16 whole football sessions played by bots, compared every few ticks: phases, scores, messages, the play call, every player
- the "view" each player is sent over the network, including that the defense never sees the offense's throw

The tests were checked by breaking the code on purpose and seeing them fail (a number off by 0.1%, a rule one step
late, a hidden-information leak). After changing the Python game, run `tools/export_parity.py` and then
`godot/run_tests.sh`: whatever no longer matches is reported with the tick and the value.

Not covered by tests: how it looks and feels. `tools/menu_shots.py` and the screenshot option take pictures to look at.

## Test and build

```
godot/run_tests.sh                                   # the Godot tests
.venv/bin/python tools/interop_test.py               # real network: relay, discovery, and a Python/Godot protocol check
.venv/bin/python tools/godot_cli_check.py            # every command-line option, good and bad
.venv/bin/python tools/install_godot_templates.py    # once: 1.3 GB of export templates
.venv/bin/python tools/build_godot_app.py            # dist/godot/GridironScramble-godot-<version>-macos.zip and -windows.zip
```

`.github/workflows/godot.yml` does the same on GitHub (tests, then both builds). It has not been run yet.

## Sending it to a friend

Neither build is signed. **Mac:** unzip, then right-click the app, Open, Open (the first time). **Windows:** unzip, run
`Gridiron Scramble.exe` (keep the `.pck` next to it); SmartScreen says "Windows protected your PC", so More info, then
Run anyway. When hosting, the system asks whether to allow incoming connections: allow it. Both players need the same
version (bottom right of the menu).

Music: put `.mp3`, `.ogg` or `.wav` files in `godot/assets/music/` before building and they play, in name order, on a
loop. A friend can also put files in an `assets/music` folder next to the app. No files means no music.

Logs and notes go to `~/Library/Application Support/Gridiron Scramble/` (Windows: `%APPDATA%\Gridiron Scramble\`).
`logs/latest.log` there holds the path of the newest run's log, the first thing to ask for if something goes wrong.

## Known limits

- Online play through invite codes needs a relay server and none is deployed (`DEFAULT_RELAY` in `scripts/invite.gd` is
  empty). The relay itself is still the Python one (`python -m ballbrawlla.net.relay_server`).
- Nobody has played the Godot version with a keyboard, a mouse or a controller yet; it has been run, tested and looked at
  in screenshots.
- The Windows build has not been run on Windows. The exported Mac app has been run and tested.
- The exported builds are 40 to 60 MB zips because they contain the whole engine.
