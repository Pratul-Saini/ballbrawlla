# Ball Brawl 3D — prototype

A **standalone Godot 4 project** that builds the first 3-D prototype described in
[`../3d-prototype.md`](../3d-prototype.md): the platformer-football duel in a climbable 3-D arena.

It lives entirely in this folder and is **independent of the rest of the repo** — it does not import
the Python package (`src/`) or the 2-D Godot port (`godot/`); it only *borrows ideas* from them. The
2-D game is completely unaffected: you still run it exactly as before. This is "a new 3-D option with
its own levels," built from the design, not wired into the old code.

## Run it

Open Godot 4 (4.4+; developed against 4.7), **Import** this `prototype3d/` folder as a project, and
press **Play** (F5). Or from a terminal:

```
<godot4> --path prototype3d
```

Everything — the arena, the characters, the ball, the camera, the HUD — is built in code
(`scripts/`), so there are no scenes to hand-edit beyond a one-line `scenes/main.tscn`.

## What it is

A **vertical slice**: **one human plays offense** (place the quarterback, aim the throw in 3-D, then
run the receiver) against a **simple AI defender**, on a greyboxed 3-D arena, through the full down
loop. This mirrors the 2-D game's *practice* mode. Local 2-player (split-screen) is a deliberate
next step for a future agent (see below).

The loop, per down:

1. **Place QB** — move the quarterback into your half and confirm the spawn.
2. **Aim** — swing a 3-D throw arc (look to aim, pitch and power), and lock it in. The dotted arc
   shows the predicted flight.
3. **Snap** — the receiver spawns, you take control of it, there's a short free-run window (the
   defender can't cross the QB's yard line yet — the *safe zone*), then the QB throws automatically.
4. **Live** — catch the ball (auto when you're under it) and reach the **red** end zone, while the
   AI defender chases and tags you. If the defender catches it, it's an **interception** and it runs
   the other way for a **pick six** — chase it down to stop it.

4 downs per possession; first to **5** wins. Touchdowns score for you; pick-sixes score for the AI.

## Controls

| | Keyboard / mouse | Controller |
|---|---|---|
| Move | **WASD** | left stick |
| Look / aim direction | **mouse** | right stick |
| Jump / double jump | **Space** | Cross (A) |
| Slide / cancel slide | **Shift** | Circle (B) |
| Confirm QB spot / catch | **E** | Square (X) |
| Aim: pitch | mouse up/down | right stick Y |
| Aim: power | **mouse wheel** | triggers |
| Lock in throw / throw now | **F** or **left-click** | R1 |
| Restart match | **R** | — |
| Cycle level | **L** | — |
| Release / grab mouse | **Esc** | — |

## Mechanics present (faithful to the 2-D game)

- **Movement:** camera-relative fixed-speed run, jump + one air jump (replace-velocity double jump,
  jump cut), **wall cling + wall jump** with *one jump per wall* (hop / wall-jump / drop-off), and a
  **slide** (with Circle-to-cancel, matching the 2-D addition). The **carrier is slower on the
  ground** (×0.78) — you escape a tag with the terrain, not footspeed.
- **3-D throwing & catching:** the QB is fixed while aiming; a full 3-D direction (look + pitch) and
  power; a live trajectory arc; parabola + reflect-and-settle bounces; a 3-s loose-ball recovery.
- **The rules:** downs, the safe-zone plane at the QB's yard line until the throw, end-zone scoring
  by *standing* in the zone, interceptions and pick-sixes, turnover on downs, first-to-5.
- **One kinematic world:** players and the ball are **CharacterBody3D** (kinematic, *not* rigid
  bodies), so the feel is hand-authored and the model stays deterministic-friendly and
  host-authoritative-ready — the same philosophy as the 2-D game's hand-rolled physics.

All tuning is in `scripts/config.gd`, seeded from the 2-D numbers in yards (see `3d-prototype.md` §13).

## Its own levels

`scripts/levels.gd` is a tiny data format (boxes with a kind and a mirror flag) and ships two
arenas — **Greybox** (stairs to a mid tier, a wall-jump chimney up to a perch, cover, a catwalk) and
**Ledges** — mirrored across midfield for fairness. Press **L** to cycle. `scripts/arena.gd` turns a
level into colliders, meshes and end-zone tints. Add a level by appending to `Levels.all()`.

## Deliberately out of scope (for the next agent)

Matching `3d-prototype.md` §11, these are intentionally *not* here yet:

- **Local 2-player split-screen** and online host/join (the sim already separates input→view, so a
  second human or a networked client can be added without touching the rules).
- **One-way (thin) platforms** — Godot 3-D has no built-in one-way collision, so "thin" platforms are
  currently thin *solids* (you land on them but can't jump up through them). `arena.gd` marks where.
- **Ledge assist**, **wall-running**, **crouch/crawl under low ceilings** (slide covers low gaps for
  now), and the full **skill-route catalog** (kick hatches / vaults / gauntlets) — one chimney stands
  in as the skill element.
- The **level generator** with physics route tests, and all **art / audio / menus** (greybox only).
- A smarter, fairer defender (the current one is a plain chaser).

## Architecture (so it stays clean)

- `config.gd` tuning · `intent.gd` the one input struct the sim sees · `levels.gd` + `arena.gd` the
  world · `player.gd` the kinematic character + state machine · `ball.gd` the kinematic ball ·
  `defender_ai.gd` the AI's Intent · `camera_rig.gd` the follow camera · `hud.gd` the overlay ·
  `main.gd` the "session" (phase machine, spawns, input mapping, scoring, camera/HUD).
- **Input in, world out.** Both the human and the AI produce an `Intent`; the sim never reads a
  device. This is the seam that lets a future agent add a second human or a network client.
- **No engine rigid-body physics** for characters or the ball — kinematic bodies + custom velocity,
  on purpose (determinism + feel + netcode model). See `3d-prototype.md` §9.

## Dev aid

`P3D_AUTO=1` runs a dumb autopilot (no human) so the loop can be smoke-tested headless:

```
P3D_AUTO=1 <godot4> --headless --path prototype3d --quit-after 2000
```

It drives place → aim → throw → live and prints each phase change, so CI or a future agent can check
the loop end-to-end without a window.
