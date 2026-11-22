# ballbrawlla - notes for a new session

2-player football platformer (Python 3.14, pygame-ce). Read first: `README.md` (run/controls), `gameplay-rules.md` (rules + every level), `docs/README.md` (how each subsystem works).

## Run and test (Windows, repo root)

```
.venv\Scripts\python -m ballbrawlla [--local | --host | --join IP | --sandbox] [--level field_09]
.venv\Scripts\python -m pytest -q              # ~25 s, 386 tests
.venv\Scripts\python -m pytest -q -m "not slow" # ~9 s, skips 3 vault sweeps
python tools/gen_levels.py [field_NN ...]       # regenerate levels from code
```

- **Test-time budget:** keep the full suite close to main's (~25 s). Mark long sweeps `@pytest.mark.slow`.
- Headless checks: set `SDL_VIDEODRIVER=dummy`; render with `MatchRenderer`/`Renderer` to a surface and `pygame.image.save` to inspect.
- The venv has an editable install of the main checkout. In another worktree, set `PYTHONPATH=<worktree>/src`.

## Architecture (src/ballbrawlla)

- `game.py` **Game**: physics world (players, ball, pickups). No rules.
- `session.py` **Session**: a match (phases WAITING / PLAY_CALL / PRE_THROW / LIVE / DEAD / GAME_OVER). It drives `rules/` and a `Game` for the WR and Defender.
- `rules/`: pure rules: `field.py` (yards, end zones, spawn surfaces), `down.py` (Down, spawn rules, `next_down`), `play_call.py` (QB/DEF players moved with normal movement, lock-in only standing on a platform in zone), `match.py`, `teams.py`.
- `entities/`: Player (state machine in `player_states.py`) and Ball.
  - Carrier ground speed is scaled by `carry_speed_multiplier`.
  - `last_wall`: one cling per wall until landing.
  - Ledge assist: `will_clear_wall`.
- `net/`: host/client JSON over TCP. `view.py` builds per-player views with hidden information.
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
  - Wall climbing is unlimited, so a wall only works as a skill check if it dead-ends.
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

- Merged into `main` on 2026-11-22: PRs #22-#27 (local two-player, one cling per wall, slower carrier, play-call movement, F2 session notes, F3 controls HUD). Issues #20, #15, #7 closed by them.
- This docs update is PR branch `pr/7-docs` (= `tooly`).
- #7 note: the issue wanted mid-air confirm to drop the QB to the platform below; built as "confirm only while standing" (user's instruction).
- Open issues not started:
  - #8 turnover-on-downs spot rules
  - #9 anti-grief / forward progress
  - #10 crowding the QB at the throw
  - #16 slow/hanging tests
  - #17 death traps (new level copies with spikes, in a new folder)
  - #18 longer throws / ball physics
  - #19 choke points so defenders can catch up
  - stamina, if wanted (from #15)
- Unverified by a human: the new levels, local play, controllers (no pad was connected), network play across two machines.
