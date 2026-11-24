# ballbrawlla - notes for a new session

2-player football platformer (Python 3.14, pygame-ce). Read first: `README.md` (run/controls), `gameplay-rules.md` (rules + every level), `docs/README.md` (how each subsystem works).

## Run and test (Windows, repo root)

```
.venv\Scripts\python -m ballbrawlla [--local | --host [--no-router] | --join IP | --join-code CODE | --sandbox] [--level field_09]
.venv\Scripts\python -m ballbrawlla.net.relay_server   # optional standalone relay (players never need it)
.venv\Scripts\python -m pytest -q              # ~25 s, 386 tests
.venv\Scripts\python -m pytest -q -m "not slow" # ~9 s, skips 3 vault sweeps
python tools/gen_levels.py [field_NN ...]       # regenerate levels from code
```

- **Test-time budget:** keep the full suite close to main's (~25 s). Mark long sweeps `@pytest.mark.slow`.
- Headless checks: set `SDL_VIDEODRIVER=dummy`; render with `MatchRenderer`/`Renderer` to a surface and `pygame.image.save` to inspect.
- The venv has an editable install of the main checkout. In another worktree, set `PYTHONPATH=<worktree>/src`.

## Architecture (src/ballbrawlla)

- `game.py` **Game**: physics world (players, ball, pickups). No rules.
- `session.py` **Session**: a match (phases WAITING / PLAY_CALL / PRE_THROW / LIVE / DEAD / GAME_OVER). It drives `rules/` and a `Game` for the WR and Defender. `PRE_THROW` is the route window: with `throw_enabled` False (the default) the WR already carries the ball and `Game.barriers` wall both players off the line of scrimmage for `route_window_seconds`; with it True it is the old 10 s run before the QB's automatic throw.
- `rules/`: pure rules: `field.py` (yards, end zones, spawn surfaces), `down.py` (Down, spawn rules, `next_down`), `play_call.py` (QB/DEF players moved with normal movement, lock-in only standing on a platform in zone), `match.py`, `teams.py`.
- `entities/`: Player (state machine in `player_states.py`) and Ball.
  - Carrier ground speed is scaled by `carry_speed_multiplier`.
  - `last_wall`: one cling per wall until landing.
  - Ledge assist: `will_clear_wall`.
- `net/`: host/client JSON over TCP. `view.py` builds per-player views with hidden information.
  - Host/join is all in the menu (Online -> Host game / Join game) with one invite code. `online.py` (`Reach`: picks the code, says "Same Wi-Fi / Internet: ready / not available because ..."; `connect`: LAN beacon first, then address or relay), `upnp.py` (router port opening, stdlib), `invite.py` (8-char address codes with a check value, 6-char relay codes, `RelayRoom`, `dial`), `relay_server.py` (optional byte-pipe relay). N on the host's waiting screen opens a second game window that joins (testing alone).
  - `DEFAULT_RELAY` stays empty until a relay is deployed; `--relay` / `BALLBRAWLLA_RELAY` / `relay` in `settings.json` set one. Godot mirrors all of it (`reach.gd`, `invite.gd`, `discovery.gd`); `tools/export_parity.py` records codes and checks for its tests.
  - Tests get an empty `BALLBRAWLLA_HOME` (autouse fixture in `conftest.py`), so a real `settings.json` can't leak in.
- `render/`: `match_renderer.py` (views, zoom camera, HUD, F3 toggle), `renderer.py` (sandbox), `field_markers.py`.
- `input.py` / `gamepad.py` (key layouts, controller slots), `notes.py` (F2 session notes in `logs/sessions/`, git-ignored), `config.py` (`Tuning`: every number).

## Levels

- `tools/gen_levels.py` builds every field level from mirrored left halves.
- **Never hand-edit level JSON.**
- The teammate's `field_05` comes from `tools/gen_field_05.py` and its own tools.
- Families:
  - 01-04: originals.
  - 06-08: lane levels.
  - 09-11: three-lane maps.
  - 12-14: skill maps with kick hatches, vaults and gauntlets.
- Tests:
  - `tests/test_levels.py`: structure, symmetry, reachability.
  - `tests/test_level_routes.py`: routes with real physics.
  - `tests/test_skill_routes.py`: timing windows.
- Geometry rules learned the hard way, enforced in the generator and its tests:
  - Walls can't be climbed: a cling gives one jump (`wall_jumps`): a hop, a wall jump, or an air jump after dropping off. A single tall wall is a dead end; going up needs stairs, ledges or a two-wall chimney.
  - Kick hatches need a solid 24 px floor and a 2.5 yd opening.
  - Vault balconies need 6+ yd of clear runway, with no step within a single jump.
  - A level-design change should come with a physics route test.

## Workflow

- Work on branch `tooly`; teammate (kriskashh) works on `kriskashh`; both merge into `main` via PRs. Before committing, `git fetch` and rebase onto `origin/main` if it moved (their changes have overlapped ours before: check for duplicated features and level-number collisions).
- Commits: one per feature. Reference GitHub issues ("Closes #N" only if fully done; it auto-closes on merge). End messages with the `Co-Authored-By` line.
- **No `gh` CLI.** Read issues/PRs via `curl https://api.github.com/repos/Pratul-Saini/ballbrawlla/...`. Create PRs by pushing a branch and giving the user a pre-filled compare URL (`/compare/main...<branch>?expand=1&title=..&body=..`).
- Stacked PRs (later ones contain earlier commits): merge in order with normal merge commits.
- Bash tool quirk: heredocs containing Python `'''` strings sometimes fail to parse ("unexpected EOF"). Write edit scripts to a scratch file and run them instead.

## State at end of last session (2026-11-22)

- `main` has PRs up to #33 (packaging, invite codes/relay, music, the Godot port).
- Open from `tooly`, as stacked PRs (merge in order):
  1. `pr/34-35-wall-jump` - one jump per wall, chimneys and the new kick hatch (refs #34, #35; not closed).
  2. `pr/online-menu` (= `tooly`) - host/join from the menu with one invite code, router port opening, N test window.
- `godot/project.godot` has an uncommitted rewrite by the Godot 4.7 editor (version bump, `window/stretch/aspect` dropped): left out on purpose.
- Godot 4.7.2 on this machine: `GODOT=C:/Users/pratu/Downloads/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe bash godot/run_tests.sh 300`.
- This machine's router didn't answer UPnP, so "Internet: ready" has only been tested against a fake router.
- Open issues not started: #8 turnover-on-downs spots, #9 anti-grief / forward progress, #10 crowding the QB,
  #16 slow tests, #17 death traps, #18 longer throws, #19 choke points.
- Unverified by a human: the redesigned levels, the new wall moves, the online menu across two real networks, the N test window.
