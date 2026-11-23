# 3-D prototype design

> **A first prototype now exists** in [`prototype3d/`](prototype3d/) — a standalone Godot 4 project
> built from this brief (isolated from the Python game and the 2-D Godot port; the 2-D game is
> unaffected). It implements the vertical slice in §11: one human on offense vs. an AI defender, the
> full down loop, 3-D aiming, the faithful movement set, and its own levels. See
> [`prototype3d/README.md`](prototype3d/README.md). This document remains the design reference for
> extending it.

A design brief for a 3-D version of this game, written for the agent who will build the first
prototype. It mirrors [`prototype-design.md`](prototype-design.md) (the original 2-D brief) but aims
one level higher: it says what the 3-D game **is**, which parts of today's game must stay faithful,
how each 2-D idea translates, and what the **first prototype** (a vertical slice) should and should
not include. Where the 2-D design left a choice, this doc makes the call and says why; a short list
of genuinely open questions is at the end.

Read these first to ground yourself, in order: [`gameplay-rules.md`](gameplay-rules.md) (the rules as
built, every number in brackets), [`docs/README.md`](docs/README.md) (how each subsystem works),
[`docs/player.md`](docs/player.md) and [`docs/physics.md`](docs/physics.md) (the movement and the
hand-rolled kinematics), [`docs/catching-and-throwing.md`](docs/catching-and-throwing.md) and
[`docs/networking.md`](docs/networking.md). The numbers cited below come from those docs and
`config.py` (`Tuning`).

---

## 1. What this game is (the identity to keep)

It is **not** 3-D football. It is a **1-v-1, asymmetric, platformer-football duel**. Strip away the
sport dressing and the core is: one player runs an obstacle course carrying (or chasing) a ball while
the other tries to cut them off, and before every play both sides commit to a hidden plan. The
football skin — downs, end zones, a quarterback, interceptions — is the scoring and pacing layer on
top of a movement game.

The non-negotiables, the things that make it this game and not a generic sports title:

- **Three roles, two humans.** Offense is a **Quarterback** (placed during the play call, throws
  automatically, can't move or be tagged during the play) and a **Wide Receiver** (the human's avatar
  during the play: runs, catches, can't throw). Defense is a single **Defender** (runs, catches, tags
  the ball-carrier). See [`rules/teams.py`]. There is no AI opponent in the core game.
- **Two phases per down: a hidden-information play call, then an execution.** In the play call both
  sides place their player and lock in, and the offense aims the throw. **The throw's direction and
  power are hidden from the defense; the Defender's chosen spot is hidden from the offense** until the
  play starts. This mutual guessing is the heart of the strategy layer. [`rules/play_call.py`,
  `net/view.py`]
- **Movement is the game.** Fixed-speed running (no acceleration), a jump and one air jump, wall
  clinging and wall jumping with the rule that **one cling only buys one jump per wall** (so a single
  wall is a dead end and going up needs stairs, ledges or a two-wall chimney), sliding, and crawling
  under low gaps. The levels are obstacle courses built around exactly these abilities. [`docs/player.md`]
- **The carrier is slower, so you escape with the terrain, not footspeed.** Holding the ball scales
  ground speed to 78% (`carry_speed_multiplier`); a free defender wins a flat-ground race, so the
  carrier has to use jumps, walls and skill routes to get away. This is why the platforming has to be
  good — it is the only way to beat a tag.
- **Fairness by symmetry.** Every level is a designed half **mirrored across midfield**, so neither
  end is easier, and a reachability test proves every surface can be reached from the floor.
- **One deterministic simulation, host-authoritative, with per-screen hidden information.** The sim is
  a fixed 120 Hz kinematic model that takes `Intent`s in and produces `view` dicts out; one machine
  (the host) runs the only `Session`, and each player is sent only what they're allowed to see. The
  renderer is a pure reader of a view. This architecture is why the game is testable, why catches are
  judged fairly over the network, and why the Godot port can match the Python version tick-for-tick.
  Keep it. [`docs/networking.md`, `game.py`, `session.py`]

If the 3-D prototype keeps those six, it is faithful, whatever else changes.

---

## 2. What the third dimension adds (the design pillars)

Today's game is a **side view**: movement lives in two axes — **along the field** (goal to goal) and
**up** (the platforming). The field has no width; you can't move toward or away from the camera.

The 3-D version keeps both of those axes and promotes the missing one to first class:

- **Length** — goal line to goal line (the old horizontal axis). Yards, downs and end zones live here.
- **Width** — sideline to sideline (brand new). Lateral freedom: routes now have breadth, you can
  juke sideways, and the Defender has to cover an area, not a line.
- **Height** — the platforming volume (the old vertical axis). Multi-level structures, towers,
  catwalks, chimneys.

**Design pillar: verticality stays central.** The temptation in 3-D is to flatten into a field with
scenery and become ordinary 3-D football. Resist it. The platforming — climbing, wall jumping,
dropping between tiers, reading a skill route — is the identity. A good 3-D level is a **climbable
piece of architecture laid over a football field**, not a field with props. The width axis makes the
chase richer; it does not replace the up axis.

**Design pillar: the hidden-information duel is unchanged.** The play call is still two blind choices
resolved at once. In 3-D the throw is aimed in a full 3-D direction and the Defender is placed on a
surface somewhere in a 3-D volume, but the *structure* — place, lock in, reveal on the snap — is the
same, and the view-hiding rules port directly.

**Design pillar: readable over simulationist.** The 2-D game rolls its own kinematics precisely so it
feels tuned and arcade-y, not physical — a 6-yard jump, a 13-yard/second sprint, instant stops. Keep
that hand-authored feel in 3-D. Do **not** reach for an engine's rigid-body physics for the
characters (more on this in §9).

---

## 3. The core loop in 3-D (mostly reused)

The phase machine, the down rules, scoring and spawn logic are **dimension-light** and should be
reused almost verbatim from [`rules/`](src/ballbrawlla/rules) and `session.py`. The flow is unchanged:

```
PLAY_CALL ──both locked──> PRE_THROW ──(free run, then QB auto-throws)──> LIVE ──play ends──> DEAD
    ^  │                                                                                        │
    │  └── 15 s timeout: restart the same play call (keep choices) ──┐                          │
    └───────────────────── next down, or GAME_OVER ─────────────────────────────────────────────┘
```

- **A possession is 4 downs**; a touchdown is 1 point; first to **5** wins. [`rules/match.py`]
- **Play call (15 s):** the offense moves the QB into place and confirms it (only while standing on a
  walkable surface in the allowed zone), then aims the throw and locks it; the defense moves the
  Defender into place and locks in (only while standing on a surface in its zone). Both locked →
  execution starts. Timeout → restart the same down, keeping any choice already made.
- **Execution:** QB, WR and Defender spawn (WR beside the QB, toward the defense's end zone). **10 s
  of free running**, then the **QB throws automatically** at the locked aim. Either player can catch
  (press the catch button within reach; the catch window is forgiving — see §6). If the ball comes to
  rest, there are **3 s** to pick it up or the play is dead.
- **Endings** [`rules/down.py` `next_down`]: WR reaches the defense's end zone = **touchdown**;
  Defender tags the WR = **tackle**, next down from the WR's last surface (turnover on downs after the
  4th); ball not recovered in time = **dead ball**; Defender catches it = **interception**, then the
  WR tries to tag them; Defender reaches the offense's end zone = **pick six**.
- **Reaching the end zone means standing on a surface inside it.** Flying through it does not count —
  the same rule as 2-D, now a surface in a 3-D end-zone volume.

What becomes 3-D-aware inside the rules:

- **`rules/field.py`** keeps measuring **yards along the length axis**. `x_at`, `yards_from_goal`,
  goal lines and end zones all project onto that one axis; the width and height of a position are
  carried along but don't affect the yard count. A **`Spot`** gains the width coordinate (and the
  height is determined by the surface it sits on). "Spawn on a surface, never floating" becomes "spawn
  on a **walkable surface** (floor-like, not a steep wall)."
- **The Defender's spawn zone** is still "at least `defender_gap_yards` (10) past the furthest the QB
  could be, toward the defense's end zone; the defense's own end zone is always allowed." That's a
  constraint on the **length** coordinate only; width and height are free. Same math.
- **The safe zone** (recently added, [`rules/play_call.py` `clamp_to_safe_zone`]) was "the Defender
  can't cross the QB's yard line until the throw." In 3-D it's a **plane perpendicular to the length
  axis at the QB's yard line**; the Defender's body is held on the defense side of it through the play
  call and the pre-throw window, and it lifts the instant the ball is thrown. One-axis clamp again.
- **Tagging** stays proximity-based: the tagger is within `tag_radius` of the carrier and presses the
  catch/tag button. In 3-D that's a sphere, not a circle. Players still **do not physically collide**
  (they pass through each other) — keep that; it keeps the chase about positioning, not shoving, and
  it's much simpler.

---

## 4. Roles and control in 3-D

| Role | Team | Controlled… | Can |
|---|---|---|---|
| **QB** | Offense | during the play call only (placed, then aims) | throw automatically on the snap; can't move, be tagged, or be stripped during the play |
| **WR** | Offense | during execution | run, jump, wall-jump, slide, catch/pick up, tag the Defender after an interception |
| **Defender** | Defense | play call + execution | run, jump, wall-jump, slide, catch/pick up, tag the WR when the WR has the ball |

- **The catch/tag button does whatever applies** (the old "Z"): it catches a loose ball in reach, or
  tags an opponent carrying the ball within `tag_radius`, otherwise nothing. One button.
- **Camera-relative movement.** The left stick points a direction on the ground plane relative to the
  camera; the avatar runs that way at fixed speed and turns to face it. "Facing" — a single sign in
  2-D — becomes a **yaw heading** that drives the slide direction and where a held ball sits.

---

## 5. Movement in 3-D (the heart — translate it carefully)

Keep the **state machine** from [`entities/player_states.py`]: `Grounded → Airborne → WallCling`,
plus `Crouch`/`Slide`, plus `Aiming`. Each state reads the Intent and the contact flags, sets
velocity, and may hand off to another state. Port it, don't redesign it. The translations:

- **Run (Grounded).** Fixed speed, no acceleration; a held direction sets horizontal velocity
  directly and releasing stops you at once (except mid-slide). Now the direction is a 2-D vector on
  the ground plane instead of ±1. Start at the 2-D value: **≈13 yards/second** (see §13).
- **Jump / double jump (Airborne).** Unchanged in spirit: a jump, then one air jump that **replaces**
  vertical velocity (so double-jumping near the apex gains the most), and a **jump cut** (releasing
  the button while rising shortens the hop once). Air steering is full-speed horizontal control,
  briefly locked out after a wall jump (`control_lock`). Keep the numbers (jump rises ≈6.4 yd; the
  double jump adds ≈4.4 yd).
- **Walls (WallCling / wall jump).** This is the mechanic most worth getting right, because the levels
  depend on it. Faithful rules to keep:
  - You stick to a wall by **moving into its face** while airborne, *unless* the current jump will
    already carry your feet above its top (**ledge assist** — running up steps you can clear never
    sticks you).
  - A cling gives exactly **one jump** (a straight hop up, a wall jump out-and-up, or an air jump
    after dropping off). **A single wall is a dead end** — you can't re-grab the wall you just left
    until you've touched a different wall or landed. Going up needs **stairs, ledges, or a two-wall
    chimney** (bounce between two facing walls).
  - Wall jump = press **away** from the wall (plus up): a kick out-and-up with a short air-control
    lock. Drop off = away without up (let go, keep the jump). Hop = up alone (one short climb, then
    you can't climb further).
  - In 3-D, "into the wall / away from the wall" is **relative to the wall's surface normal** (the
    horizontal component of your input vs. the face you're touching), not a left/right sign. A
    **wall-run** (moving laterally along a wall face while clinging) is a natural 3-D extension and
    would feel great — but treat it as a **stretch goal**, not prototype scope. Ship the faithful
    cling-and-jump first.
- **Slide / Crouch.** Down (or a dedicated button — the game just added a controller **Circle** slide
  that also cancels a slide back to running, see [`entities/player_states.py`]) starts a **slide** in
  the facing direction: a burst to `slide_speed` that decays over ≈0.45 s (covering ≈6 yd), used to
  pass under low gaps and to carry momentum. If there's no room to stand, you **crawl** (slow,
  short-height) so a slide never traps you under an overhang. Keep both; they're how levels gate
  routes by height.
- **Carrying the ball.** Ground speed ×0.78 while holding it; jumps and air speed unchanged. Keep this
  exactly — it is the balance lever that makes platforming the escape.

Everything above is **hand-rolled kinematics**, not engine physics (§9). Start from the 2-D numbers
converted to yards (§13) and tune for feel in the 3-D space — the extra axis changes how far a jump
"feels," so expect to re-tune, but keep the *relationships* (a double jump ≈1.6× a single; the carrier
clearly slower than a free runner; a wall jump a real commitment).

---

## 6. Ball, throwing, aiming, catching in 3-D

- **The ball** is a sphere with its own gravity, bouncing off geometry with restitution ≈0.75 and a
  little surface friction, and **coming to rest** when a bounce is gentle enough (then the 3-s
  recovery window starts). The 2-D bounce model — reflect the velocity about the contact **normal**,
  drop the normal component below a rest speed — generalizes directly to a sphere vs. 3-D surfaces.
  No spin. [`docs/ball.md`, `docs/physics.md`]
- **Throwing.** The QB is **fixed in place** during the throw window and throws automatically on the
  snap at the **locked-in aim**: `velocity = direction × power`, released from the player's center,
  then a parabola under gravity until it hits something. Keep the power range (≈12.5–58 yd/s).
- **Aiming (the 3-D change).** In 2-D the aim is an **angle in the vertical plane** (full circle) plus
  **power**. In 3-D it's a **full 3-D direction** — a yaw *and* a pitch — plus power. The natural
  control: point with the right stick / mouse to swing a **predicted-trajectory arc** around the QB
  (yaw with horizontal, pitch with vertical, a modifier or the triggers for power), and lock it. Show
  the **dotted parabola preview** (gravity only, ignoring bounces, as 2-D does) so the thrower reads
  the arc — this is even more important in 3-D. **The aim is hidden from the defense**, so it lives
  only in the offense's view. This is the single biggest new UX problem in the game; budget iteration
  for it (§11).
- **Catching / pickup.** Keep the forgiving, host-judged pickup from
  [`docs/catching-and-throwing.md`] — it exists for network fairness and it's worth every line:
  - **In reach** = ball free, you hold nothing, your center within `pickup_radius` (≈2.3 yd) of the
    ball. Draw the reach sphere around the local player.
  - **Early-press buffer**: a catch press when the ball isn't in reach arms a short retry window.
  - **Late-press grace**: the host keeps the ball's recent positions (a short trail) and a press
    counts if you're near **any** recent position — this absorbs the joiner's round-trip lag.
  - Contested balls go to the **closest** requester; the host resolves it after everyone has moved.
  Port this whole flow; the only change is circle→sphere distance.

---

## 7. The field and levels in 3-D

**Units.** Pick a world unit and a yards-per-unit scale up front and put it in one config, the way
`yard_px` lives in `config.py` today. The cleanest choice: **1 world unit = 1 yard** (so the field is
120 units long end to end), and scale the movement numbers from §13 directly. A player is roughly a
**capsule ~0.9 yd across and ~1.8 yd tall** (from the 2-D 24×42 px box at 24 px/yd), shrinking to
~1.1 yd for crouch/slide.

**The arena.** A finite box: **100 yards of field + a 10-yard end zone at each end** along the length
axis, a **bounded width** (sidelines are walls — out-of-bounds can come later), and a **generous
height** for the platforming. End zones are volumes tinted in the defending team's color, with a
goal structure the carrier must stand on to score.

**Fairness.** Mirror the designed geometry **across midfield** (the 50), exactly as 2-D does, so both
ends are identical. The width axis is symmetric by construction (design one side of the centerline and
mirror, or just design it symmetric). Keep a **reachability check** — every walkable surface must be
reachable from the floor with the real movement set — as a test; it's caught real bugs in 2-D.

**Platform vocabulary**, translated:

- **Solid blocks / floors / ramps** (walkable if their top is flat enough), **walls** (clingable
  faces), **thin / one-way platforms** (land on from above, pass up through) — all have direct 3-D
  analogues. Thin platforms matter: they're how you build layered catwalks you can jump up through.
- **Chimneys** (two facing walls), **stair towers**, **ledges** — the vertical-travel kit.
- The 2-D **skill elements** — kick hatches (a timed air-jump through a floor slot), vaults (a precise
  double-jump onto a balcony then a slide through), slide gauntlets — are the game's expert flavor.
  Build **one** of them in the prototype as a proof that the 3-D movement supports timed skill routes;
  don't port the whole catalog.

**Do not build the level generator for the prototype.** Today `tools/gen_levels.py` builds every level
from mirrored halves with physics route tests; that's a mature subsystem. For the prototype, **hand-
build one blockout arena** (greyboxed) with: a ground lane, one or two raised tiers reached by stairs
and a chimney, a wall or two to cling, some cover to break sightlines, a thin-platform catwalk, one
skill route, and scoreable end-zone structures. Prove the loop is fun on one good level before
investing in generation. When you do generalize, keep the discipline: **design a mirrored half,
generate, and gate every geometry change behind a physics route test.**

---

## 8. Camera and HUD

- **Camera.** A **third-person follow camera** behind the player you control (over-the-shoulder, with
  the aim camera swinging around the QB during the throw). This is new work with no 2-D equivalent
  (2-D used a side-on zoom camera). Controls are **camera-relative**. Expect to iterate on distance,
  height, and how the camera handles the player going behind geometry.
- **Hidden information per screen is sacred.** Each player's camera and HUD are built from **their
  own view only**. The offense never sees the Defender's placement during the play call; the defense
  never sees the aim. On one shared screen (local 2-player) everything shows — fine for early
  iteration, but keep the per-view split in the data so split-screen / network play stays honest.
- **HUD**, ported from the 2-D match HUD: a **game clock** (the play-call / pre-throw / loose-ball
  countdown), the **score and down**, and the asymmetric awareness aids the 2-D game settled on — the
  **offense gets a radial "where's the defender and how close" indicator** rather than a map, and the
  **defense gets a minimap that never shows the ball**. Those translate to 3-D as a compass/radar and
  a top-down map; keep the asymmetry, it's a deliberate design choice.

---

## 9. Architecture — the most important faithful decision

**Keep the 2-D architecture. It is the reason the game is testable, fair over the network, and
portable. The 3-D version is a new *renderer and physics shape*, not a new *design*.**

Concretely, preserve these seams:

- **A deterministic, fixed-tick simulation** (keep 120 Hz, or choose one fixed rate) that is **pure**:
  it takes a list of `Intent`s and advances the world; it does no rendering and reads no devices.
  `Game.step(intents, dt)` and the `Session` phase machine stay the model.
- **Intent in, view out.** Input devices (now including a 3-D-aware aim) are mapped to the same small
  `Intent`. The renderer consumes a `view` dict and draws it. Hidden information is **left out of the
  view entirely**, never hidden only in the UI. This is what makes the net code safe and the game
  testable headless.
- **Host-authoritative networking.** One machine runs the only `Session`; clients send Intents and
  draw their own view; catches are judged on the host with the grace window. The whole invite-code /
  LAN-beacon / relay stack ([`docs/networking.md`]) is transport and can be reused wholesale later —
  the game protocol runs over it unchanged.
- **Roll your own character kinematics; do not use rigid-body physics for the players or the ball.**
  The 2-D game deliberately hand-writes semi-implicit Euler + swept collision in small substeps
  ([`docs/physics.md`]) so movement is deterministic and tunable and the Godot port matches Python
  tick-for-tick. For 3-D, do the same: a **kinematic character controller** (a capsule swept against
  static level colliders, pushed out along the contact normal, with substeps small enough not to
  tunnel) and a **custom ball integrator** (parabola + swept-sphere raycasts + the reflect-and-rest
  bounce). Engine rigid-body solvers are non-deterministic across platforms and would break both the
  feel and the host-authoritative model. (If you must lean on an engine helper to move fast, a
  **kinematic** `move_and_slide`-style call is acceptable for a first blockout, but plan to own the
  collision so you can keep determinism and parity.)

**Reuse map.** What ports nearly as-is vs. what is genuinely new:

| Layer | 2-D source | In 3-D |
|---|---|---|
| Rules: downs, spawn regions, scoring, phase flow | `rules/down.py`, `rules/match.py`, `rules/teams.py`, `session.py` | **Reuse** (dimension-light) |
| Field math (yards, goal lines, end zones, spots) | `rules/field.py` | **Reuse, extend** a `Spot` to carry width; surfaces instead of platform tops |
| Play call (place, lock, aim, safe-zone clamp, hidden views) | `rules/play_call.py`, `net/view.py` | **Reuse structure**; aim becomes 3-D; clamp is a plane on one axis |
| Movement state machine | `entities/player_states.py` | **Port** (walls/aim become direction-relative) |
| Kinematics (integration, swept AABB, contacts) | `physics/` | **Rewrite in 3-D** (capsule/box vs. mesh), same philosophy |
| Ball (gravity, bounce, rest, held, trail) | `entities/ball.py`, `game.py` | **Port** circle→sphere |
| Catching (reach, buffer, grace, contested) | `game.py`, `entities/player.py` | **Reuse** (circle→sphere distance) |
| Networking (host-auth, views, invite/relay) | `net/` | **Reuse model and transport** |
| Rendering + camera | `render/` | **New** (3-D follow camera, HUD ported in spirit) |
| Levels | `world/level.py`, `tools/gen_levels.py` | **New format**; prototype hand-builds one, generator later |

**Engine recommendation.** The project already has a **Godot 4** port of the whole game
([`docs/godot.md`], `godot/`), and Godot 4 is a strong 3-D engine with the team already familiar with
it. **Build the 3-D prototype in Godot 4**, reusing the GDScript `rules/`/`session` port as the
starting point for the dimension-light layer, and writing the 3-D kinematics and renderer fresh —
**kinematic bodies, not rigid bodies**, for the reasons above. (If the team would rather keep the
Python sim as the source of truth and parity-test against it, that's viable too, but it's more work;
for a *prototype*, Godot-first is the faster honest path. Don't start a brand-new third engine.)

---

## 10. Networking for the prototype

Start **local, two players, one machine** (hotseat is fine; split-screen is nicer and forces the
per-view discipline early). That's enough to find the fun and to validate the camera and the 3-D aim.
Because the sim/presentation seam is preserved, **host/join drops in later without touching the
rules**: the host runs the `Session`, clients send Intents and render their own view, and the
existing invite-code/relay transport can carry it. Do **not** build prediction/interpolation for the
prototype — the 2-D game ships none and relies on the catch grace window; match that and revisit only
if 3-D speed demands it.

---

## 11. Prototype scope — the vertical slice

**In (the slice must prove the loop is fun and faithful):**

1. One greyboxed 3-D arena: field + two end zones, bounded width, two height tiers, a chimney and a
   cling wall, some cover, a thin-platform catwalk, one skill route, scoreable end-zone structures.
2. The three roles and **both phases** end to end: play call (place QB, place Defender, aim the throw,
   with the hidden-info split and the safe-zone plane), then execution (spawn, 10-s free run, auto-
   throw, catch, tag, and all five endings), on a loop with the clock, score and 4 downs, first to N.
3. Core movement ported and tuned: run, jump, double jump, slide/crawl, wall cling + wall jump
   (one-jump-per-wall, chimney). Carrier slowdown.
4. 3-D aiming with the live trajectory preview; the forgiving catch/pickup flow.
5. A third-person follow camera and a basic HUD (clock, down/score, the asymmetric radar/map).
6. The deterministic fixed-tick sim with the Intent-in / view-out seam, so networking can follow.
7. Local 2-player (hotseat or split-screen).

**Out (deliberately deferred — note them so no one gilds the prototype):**

- The level generator, mirrored-half tooling, level families, and more than one skill element.
- Wall-running, out-of-bounds/sidelines-as-rules, moving platforms, player-vs-player collision.
- Online host/join, invite codes, UPnP, the relay (keep the seam; don't build the transport yet).
- Art, music, menus, settings, packaging — greybox and placeholder audio only.

**Suggested phasing** (each phase should be playable):

1. **Movement toy.** One flat arena + a few blocks and one wall. Nail run / jump / double jump /
   slide / wall cling + wall jump feel in 3-D with the follow camera. No football yet. This is where
   you earn the identity; don't rush it.
2. **Ball + aim.** Add the ball, the 3-D aim with trajectory preview, throwing, and the forgiving
   catch. Two players can throw and catch in the toy arena.
3. **The down.** Wire in the reused `rules/`/`session`: play call (placement, lock-in, hidden views,
   safe-zone plane) → execution → the five endings → next down → scoring. First to N, 4 downs.
4. **The real blockout.** Replace the toy arena with the designed greybox (tiers, chimney, cover,
   catwalk, one skill route) and tune the level + numbers against actual chases.
5. **Harden the seam.** Confirm the sim is deterministic and headless-testable and the views carry no
   hidden data, so a future agent can add host/join on top.

---

## 12. Open questions (iterate on these; everything else above is a decision)

- **Camera + 3-D aim feel.** The hardest unknowns. How the follow camera frames a vertical chase, and
  how a player points a throw in 3-D and reads the arc, will make or break the game. Prototype them
  early and expect to redo them.
- **How much lateral freedom vs. verticality.** Width makes the chase richer but can dilute the
  platforming. Tune arena proportions (how wide vs. how tall) until the fastest route to escape a tag
  still usually goes **up**, not just sideways. If it doesn't, narrow the field or raise the walls.
- **Re-tuning movement for the extra axis.** The 2-D numbers (§13) are the start, not the answer; a
  jump's reach reads differently in 3-D. Keep the *ratios*, retune the magnitudes against real chases.
- **Defender placement UX in a volume.** Placing on a surface in a 3-D zone, with the length-axis
  constraint and the safe-zone plane, needs a clear way to pick and preview a spot. A ghost/marker the
  defense drives around (as 2-D moves a real player into place) likely still works; validate it.
- **Wall interaction in 3-D** (cling vs. run vs. mantle). Ship faithful cling-and-jump first; decide
  whether wall-running earns its place only after the core feels right.

---

## 13. Starting numbers (2-D values in yards, to seed the 3-D tuning)

From `config.py` at the default 24 px/yard. Use these to set initial 3-D units, then tune for feel.

| Thing | 2-D value | ≈ in yards / seconds |
|---|---|---|
| Run speed (fixed) | 320 px/s | **13.3 yd/s** |
| Air steering speed | 320 px/s | 13.3 yd/s |
| Gravity (player & ball) | 2200 px/s² | **91.7 yd/s²** |
| Jump | 820 px/s up | rises **≈6.4 yd**, ≈0.75 s airborne |
| Full-jump horizontal reach | — | **≈10 yd** |
| Double jump (from apex) | 680 px/s | adds ≈4.4 yd (≈10.75 yd total) |
| Wall jump | 380 away / 720 up | away ≈ run speed; rises ≈4.9 yd |
| Wall hop (climb) | 520 px/s up | rises ≈2.5 yd |
| Max fall speed | 1200 px/s | 50 yd/s |
| Slide | 560 px/s, 0.45 s | covers **≈6.25 yd**, decaying |
| Carry speed multiplier | ×0.78 | carrier ≈10.4 yd/s on the ground |
| Throw power range | 300–1400 px/s | **12.5–58 yd/s** |
| Aim rotate / power rates | 180°/s, 900/s | (angle & power while aiming) |
| Pickup radius | 55 px | **≈2.3 yd** |
| Tag radius | 40 px | **≈1.7 yd** |
| Player box | 24 × 42 px (26 crouch) | ≈0.9 × 1.75 yd (≈1.1 crouch) |
| Ball radius | 12 px | ≈0.5 yd |
| Play-call timer | 15 s | — |
| Pre-throw (free run) | 10 s | — |
| Loose-ball recovery | 3 s | — |
| Downs / win | 4 downs, first to 5 | — |

---

### One-line brief for the builder

*Build a 1-v-1 platformer-football duel in a climbable 3-D arena: keep the three roles, the two-phase
hidden-information play call, the fixed-speed wall-jumping movement, the slower carrier, and the
deterministic Intent-in/view-out host-authoritative sim; make the third dimension add lateral chase
room without flattening the verticality; and ship a one-arena vertical slice (local 2-player, Godot 4,
kinematic — not rigid-body — characters) before building generators, art, or netcode.*
