# Input, main loop and rendering

Source: `input.py`, `main.py`, `render/renderer.py`.

## Intent

The simulation never reads keys. It only sees an `Intent` per player per tick:

| Field | Meaning |
|---|---|
| `move_x` | -1 left, 0, +1 right. **Held** |
| `vertical` | +1 up, 0, -1 down. **Held** (`up_held`, `down_held` are derived) |
| `jump_pressed` | Up was pressed this tick. **Edge** |
| `z_pressed` | Z was pressed this tick (pick up, aim, cancel). **Edge** |
| `x_pressed` | X was pressed this tick (throw). **Edge** |

Anything that produces Intents can drive a player: the keyboard, a network client, a test, or a future AI.

## Keyboard (`KeyboardInput`)

- Held keys (arrows) are read with `pygame.key.get_pressed()` when the simulation asks for an Intent.
- Press edges are collected from `KEYDOWN` events as they arrive, so a quick tap between two ticks is not lost. When an Intent is built, the edges are consumed and cleared.
- Z, X and Up are therefore **one-tick edges**. Holding Z does nothing after the first tick. The early-press buffer in [catching-and-throwing.md](catching-and-throwing.md) is what makes a slightly early Z still work.

Keys outside the simulation (handled in `main.py`): `R` reset (host or single player only), `F1` toggle debug overlay, `Esc` quit.

## The main loop (`main.py`)

Physics runs at a **fixed 120 Hz** whatever the frame rate. Each frame:

1. Add the frame's elapsed time to an accumulator. A frame is capped at 0.25 s so a stall does not cause a catch-up spiral. `Clock.tick(240)` caps rendering at about 240 fps.
2. Handle window events and pass them to `KeyboardInput`.
3. If hosting: accept and read clients (`server.poll()`).
4. While the accumulator holds at least one tick (1/120 s): build Intents, `game.step`, subtract a tick. If hosting, send a snapshot after stepping.
5. Draw the current state and flip the display.

Input is therefore sampled at tick granularity. The added delay between a key press and the simulation seeing it is at most about one frame (about 4 ms) plus up to one tick (about 8 ms).

Single player and `--host` share `run_local`. `--join` uses `run_client`, which sends Intents at the same tick rate instead of stepping, and applies snapshots (see [networking.md](networking.md)).

## Rendering (`Renderer`)

Everything is drawn with primitive shapes. The renderer reads state and never changes it.

| Thing | Look |
|---|---|
| Background | dark blue-gray |
| Boundaries | darker gray rectangles |
| Solid platforms | lighter gray rectangles |
| Thin platforms | teal fill with a 3 px light top edge |
| Players | colored boxes (P1 blue, P2 red, P3 green, P4 yellow), with an eye dot showing facing and a "P1" label |
| Disconnected player | a dim outline only |
| Ball | orange circle |
| Reach circle | green circle of radius `pickup_radius` around the local player, shown while the ball is in reach |
| Aim | a ring around the aiming player, a yellow line (length shows power) and a dotted predicted arc |

The predicted arc uses gravity only and ignores platforms, so it shows open-space flight, not bounces.

### Debug overlay (F1, on by default)

Top-left text: level name, fps, which player you are; your state, contact flags (`G` ground, `C` ceiling, `L`/`R` walls, `.` for none) and air jumps left; your velocity; the ball's velocity and whether it is held, resting or free; aim angle and power while aiming; and a controls reminder. Each player's label also shows their state name.

A status line (for example `hosting on ... players 2/2`) shows below it in host and join modes.

## Resizing

The window is `SCALED | RESIZABLE` at the level's pixel size, so it scales up on large screens while the game keeps working in level coordinates.
