# Input, main loop and rendering

Source: `input.py`, `gamepad.py`, `main.py`, `notes.py`, `render/`.

## Intent

The simulation never reads devices; it only sees one `Intent` per human per tick: `move_x`, `vertical` (held), `jump_pressed`, `z_pressed`, `x_pressed` (one-tick edges), mouse fields (`mouse` in world coords, `mouse_held`, `mouse_pressed`, `button_pressed` for the HUD button) and controller extras (`jump_held`, `aim_stick`). `up_held` is `vertical > 0 or jump_held`.

## Devices

- `KeyboardInput(keys=KeyBindings, shared_pads=None, pad_slot=None)`: keys (layout `DEFAULT_KEYS` = arrows/Z/X; `BLUE_KEYS` = WASD/F/G and `RED_KEYS` = arrows/period/slash for `--local`), mouse, and controllers. Edges are collected from events and cleared when an Intent is built. `consume(camera, zoom, use_mouse)`.
- `Gamepads` (SDL game-controller API; PS5/PS4/Xbox): Cross jump, Square grab/tag/confirm, Circle/R1/R2 throw/lock, sticks/D-pad move, right stick aims, Options restart, Create/touchpad debug. Pads are addressed by slot (0 = first connected) for local play.

## Main loop (`main.py`)

Modes: `run_match` (practice, `--host`), `run_couch` (`--local`), `run_client` (`--join`), `run_sandbox` (`--sandbox`). Each frame: accumulate time (capped at 0.25 s), handle events, step the 120 Hz simulation while a tick is owed, draw, flip.

Every loop has:
- **F1** debug overlay, **F3** show/hide the controls HUD, **Esc** quit.
- **F2** session notes (`notes.py`): an in-game text panel saved to `logs/sessions/<date_time>_<mode>_<level>/notes.md`. One file per run, rewritten on every save. While open, input goes only to the notes; practice/local/sandbox pause.
- Restart: R (practice/host/sandbox), F5 (local, since R sits next to Blue's keys), controller Options.

## Rendering

- `render/match_renderer.py` (`MatchRenderer`) draws a **view dict** for every match mode: field markings, platforms, play-call markers (green bar = can lock in, red outline = can't), actors, ball, aim arc, HUD (minimap, score line, phase hint, bottom status/controls line), lock-in button (top-right), result banners. `Camera.follow` for one player; `Camera.frame` zooms (down to `MIN_ZOOM` 0.4) to keep both players in view in local play. `show_controls` (F3) hides key instructions but keeps game state.
- `render/field_markers.py`: end zones, yard lines and numbers, scaled by camera zoom.
- `render/renderer.py` (`Renderer`): the sandbox's drawing of a raw physics `Game`, with an optional camera and field markings.
