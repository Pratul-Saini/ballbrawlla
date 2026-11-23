# Verification: smooth run/jump

## Art pipeline (step `art`)

### Commands run

```
tools/make_run_cycle.sh        # exit 0, run twice, second run produced no file diffs (deterministic)
aseprite -b --list-layers --list-tags godot/assets/sprites/player/anim/navy_left_rig.aseprite
```

Result of `aseprite --list-layers --list-tags`: layers `leg_far leg_near fill head_torso arm_far arm_near`, tags `idle run jump apex fall land`. The layers stay separate, nothing is flattened.

### Automated checks (`tools/aseprite/check_frames.py`, 17 frames x 4 sets = 68 frame checks)

```
[navy]      layers flatten back to the source: ok | failures: palette=0, foot=0, bounds=0, orphans=0, holes=0, black=0, white=0, hand=0
[navy_left] layers flatten back to the source: ok | failures: all 0
[red]       layers flatten back to the source: ok | failures: all 0
[red_left]  layers flatten back to the source: ok | failures: all 0
lowest row per tag (all four sets identical): idle=[85,85]; run=[85 x8]; jump=[85,81]; apex=[79]; fall=[83,82]; land=[85,85]
all checks passed (68 frame checks over 4 sets)
```

What each check proves:

- palette: no opaque color outside the source palette (30 colors), alpha only 0 or 255.
- layers: the split layers flatten back to the source PNG pixel for pixel (each pixel in exactly one layer).
- foot line: lowest opaque row is 85 in idle, run, land and jump frame 1. Air frames are at or above 85.
- bounds: no opaque pixel on the outer border of any 96x96 frame.
- orphans: 0 single pixels (source has 0). holes: 0 enclosed transparent pixels (source has 0).
- black/white: pure `#000000` and `#FFFFFF` never exceed the source counts.
- hand: the ball-hand anchor of every frame is on or within 2 px of opaque pixels.

The checks do not prove the animation looks good. They do not check that the number stays readable or that limbs read as attached.

### Contact sheet

`.agents/tasks/smooth-run-jump/contact-sheet.png`: all 4 sets (navy, navy_left, red, red_left), run cycle row and one row for idle/jump/apex/fall/land, 2x nearest-neighbor, ground line drawn at row 85. I looked at it and at 4x zoomed crops of the navy frames while iterating. I judged red and the `_left` sets from the contact sheet at 2x only.

Choices made during iteration (first version failed visually):

- Moving the near arm left covered the "23". The near arm now never moves left. Arms only bob in y, and the far arm swings in toward the body.
- Translating a whole leg by 20 to 30 px left a detached horizontal thigh slab. The legs now trade places by a horizontal flip of both leg layers about the hips (frames 5 to 8 are mirrors of 1 to 4). The hip end of a moved thigh is kept inside the pelvis width.
- Left-facing: the `_left` .aseprite files are rigged with mirrored masks and negated offsets (flip axis 90 instead of 100), instead of mirroring the right-facing frames. Reason: the torso and number are never touched, so "23" stays readable in every frame.

### Frame verdicts (honest)

Same for all four sets unless noted. Source frame = the drawn pose. "Acceptable" means it reads as a football player and has no detached limbs or holes, but it is visibly built from cut-out parts.

| Frame | Verdict | Notes |
|---|---|---|
| run 1 (contact A) | good | The original hand-drawn pose, unchanged. |
| run 2 (down) | acceptable | Legs gather 5 to 6 px, torso dips 1 px. |
| run 3 (passing) | acceptable | Legs under the body, back leg lifted 3 px. A few stray dark outline pixels at the hip seam. |
| run 4 (up) | acceptable | Same seam artifacts, torso 1 px up leaves a small filled gap at the hips. |
| run 5 (contact B) | acceptable | Legs mirrored, front thigh is a long horizontal slab. Shading is lit from the other side on the flipped legs. |
| run 6 | acceptable | Like 2, mirrored legs. |
| run 7 (passing) | acceptable | Legs under body, wispy edge at the hip. |
| run 8 | acceptable | Like 4, mirrored legs. |
| idle 1/2 | acceptable | Legs gathered under the body, 1 px breathing dip. Still looks like a runner standing mid-stride, not a relaxed stance. |
| jump 1 (take-off squash) | acceptable | Torso and arms sink 2 px. |
| jump 2 (rise) | acceptable | Feet tucked up, arms raised. Close to the apex frame. |
| apex | acceptable | Legs tucked, arms 3 px up. |
| fall 1/2 | acceptable | Arms raised, feet apart. Differs from run 1 only by raised arms and lifted legs, so it reads weakly as "falling". |
| land 1/2 | acceptable | Squash is the torso sinking 3 px into the legs. The jersey does not compress. |

Overall quality verdict: run is acceptable, not good. The legs carry the whole stride read. The arms barely move (they must keep the number clear and the ball hand on the right), and a flipped leg has reversed shading. The frames hold up at game scale but a pixel artist would redraw the passing frames. The layers are kept in the `*_rig.aseprite` files so they can be hand-polished.

### Limits and what was not verified

- Red and left-facing sets were judged from the 2x contact sheet only. The red source has a light-blue shoulder trim, which is in the hand-drawn source.
- Source art colors are not hue-shifted: the source already uses pure black outline and pure white. The rule is "no more than the source".
- No engine work was done in this step. Godot import of `anim/*.png`, `godot/run_tests.sh`, and the in-game screenshot are for the `engine` step. The new PNGs have no `.import` files yet.
- Loop flags live in `tools/aseprite/sheet_to_godot.py` (Aseprite does not store them): idle, run, fall loop; jump, apex, land play once.
- The headless `aseprite` binary is a dev build (1.3.18.6-13-ge593180ee-dev).

### One-command regeneration

```
tools/make_run_cycle.sh
```

Env overrides: `ASEPRITE` (binary), `PY` (python with Pillow, defaults to the repo `.venv`, found through the git common dir when run from a worktree).

## Engine side (step `engine`)
Presentation only. No change to the simulation, rules, tuning, network view or `godot/tests/data`.
### What changed
- `godot/scripts/player_sprites.gd`: loads `anim/player_anim.json` and the four strips. New `get_frame(key, team, facing, state, vx, vy, dt)` keeps one animation clock per actor, driven by render `dt`. New `get_frame_at(team, facing, tag, seconds, hold)` is the stateless version (used by the menu). Pure statics: `pick_anim`, `run_rate`, `frame_at`, `art_scale`, `dest_rect`. `get_sprite`, the double-jump FX and `track_facing` are unchanged; if the JSON or a strip is missing, `get_frame` returns the old static pose.
- `match_renderer.gd`: `_draw_figure` takes `{state, vx, vy}` instead of `bob`. The sin-based bounce is gone. Play-call QB/DEF get a walking velocity from their x change per frame.
- `sandbox.gd`: same provider. The player is drawn (and the camera follows) between the previous and latest 120 Hz sim step, using the leftover accumulator time. Teleports (reset) are drawn as they are.
- `menu_anim.gd`: idle frames for both players (red half a second out of phase), jump then fall frames for the receiver's catch hop.
- `godot/tests/test_player_anim.gd` (new, 11 tests): state table, run speed, frame_at loop/hold, JSON completeness (tags, durations, 17 hand anchors per set), left/right same frame, feet line, jump/land sequence, no landing flash on a one-tick hop, speed vs. facing, fallback.
- `anim/*.png.import` generated by `Godot --headless --import` and committed, like the other sprites.
### State to animation
| Engine state | Animation |
|---|---|
| grounded, \|vx\| <= 20 | `idle` (2 frames, 500 ms) |
| grounded, \|vx\| > 20 | `run` (8 frames), clock rate = \|vx\|/320, clamped 0.35..1.6 (carrying at 250 px/s plays at 0.78x) |
| airborne, vy < -150 | `jump` (rise, plays once, holds last frame); a second jump restarts it |
| airborne, \|vy\| <= 150 | `apex` |
| airborne, vy > 150 | `fall` (loops) |
| grounded within 0.12 s after 0.08 s or more in the air | `land` once, then idle/run |
| wall_cling | `fall` frame 0 held |
| crouch, slide | `idle` frame 1 (the dip) held |
| aiming | `idle` frame 0 held |
Catch/tag (Z) has no state of its own, so it shows whatever the movement state is. Facing only chooses the `_left` or right strip at the same tag and frame index, so a turn does not pop.
Sizing is unchanged: scale `h / 84 * 1.35` (84 = old cropped art height), full 96x96 cell drawn so row 85 stands on the hitbox bottom and column 50.5 (45.5 left) is centred on it. The ball is drawn at the per-frame hand anchor from the JSON.
### Verified
- `godot/run_tests.sh`: 104 passed, 0 failed (93 before, plus 11 new). The script still ends with "FAILED: the run printed script errors" because of one `ERROR: Condition "!is_open()"` from `relay_client.gd` in `test_reach` (a relay that cannot be reached). The same line and verdict appear on an unmodified checkout of the previous commit (checked in a temporary worktree), so it is not caused by this change.
- Game screenshots: `.agents/tasks/smooth-run-jump/engine-screenshot.png` is 8 sandbox frames (`--smoke` run, taken with a throwaway probe script in /tmp, not committed). I looked at it: the blue player runs with changing leg poses across frames, feet on the floor line, a tucked pose in the air, "23" readable. The launcher menu (`shot.gd`) shows both players drawn from the new frames: blue idle, red in the jump pose during the catch hop, football in flight.
- Headless smoke runs of the sandbox and menu print no script errors.
### Not verified
- Held-ball placement in the near hand was not looked at in game (no screenshot had a held ball). It is covered only by the anchor tests (every frame has an anchor inside the cell), and the art step's check that each anchor is on or within 2 px of opaque pixels.
- Not seen in game: land, fall, wall cling, crouch, slide, aiming frames, red team in a match, left-facing sets in a match, and the match screen (`match_renderer.gd`) with real actors. The jump/land sequence is only tested through the clock logic.
- Smoothness in motion was not judged: I only looked at still frames. The 120 Hz interpolation was not measured on a high-refresh display.
- The thresholds (150 px/s apex band, 0.12 s landing, 0.08 s minimum air time, 0.35..1.6 rate clamp) are first guesses and not tuned by playing.
### Interpolation limit
The sandbox has the sim in-process, so it interpolates. `match_renderer.gd` only receives the latest view dictionary (host, client and local play alike), with no previous snapshot, so actors are drawn at the latest tick position. Only the animation clock is smooth there. Smoothing the match would need a snapshot buffer in `match_screen.gd` (a product-visible latency decision), so I left it.
### One-command regenerate
```
tools/make_run_cycle.sh      # then: Godot --headless --path godot --import   (once, for new PNGs)
godot/run_tests.sh
```

## Integration pass (step `integrate`, iteration 1)
No `review.json` existed, so this is the first integration pass. Nothing needed fixing. All commands were run from the worktree.

### Commands and results
```
tools/make_run_cycle.sh                         # exit 0, all four sets rebuilt; git status afterwards: no tracked file changed (deterministic)
  [navy|navy_left|red|red_left] layers flatten back to the source: ok
  failures: palette=0 foot=0 bounds=0 orphans=0 holes=0 black=0 white=0 hand=0  (each set)
  lowest row per tag, all four sets: idle 85,85; run 85 x8; jump 85,81; apex 79; fall 83,82; land 85,85
  all checks passed (68 frame checks over 4 sets)
godot/run_tests.sh                              # "104 passed, 0 failed"; script exit still FAILED (see below)
git worktree add /tmp/vr/base 3132b39 && godot/run_tests.sh   # base commit: "93 passed, 0 failed", same FAILED line (worktree removed again)
```
The `FAILED: the run printed script errors` verdict comes from `ERROR: Condition "!is_open()"` (relay_client.gd, `test_reach`, a relay that cannot be reached) and `ERROR: 5 resources still in use at exit`. Both lines also print on the untouched base commit 3132b39, so they are not caused by this branch. Every test passes (104/0).

### Engine loads the generated sheets (both teams, both facings), ball in hand
A throwaway probe (not committed, run from `godot/` and deleted) built a `PlayerSprites`, and for team 0/1 x facing right/left x every frame of idle, run, jump, apex, fall, land called `get_frame_at`, drew the frame with the engine's own `art_scale` and `dest_rect`, and drew the football at `spr["hand"]`. `animated=true available=true`. Result: `.agents/tasks/smooth-run-jump/held-ball-all-frames.png` (first 16 of 17 frames per set are visible; 4 rows: navy, navy_left, red, red_left). I looked at the rows at 3x. In every frame of all four sets the ball sits at the near fist, on the side the character faces: right of the torso for the right-facing sets, left for `_left`. The ball follows the hand through the run, jump, apex and fall frames.

Observation, not changed: the ball (radius x 1.5, the old size) is large against the 96 px art and covers most of the "23" while it is carried. The hand position and ball size are unchanged from before this branch (HAND_RIGHT 76.2/39.4, `ball radius * 1.5`), so this is the previous look, not a regression.

### Sandbox, ball held, real physics
Probe set `held_by` on the ball at start and ran the scripted `--smoke` input: stand, jump, run at 250 px/s (carrying speed), land, run at 320 after the jump, stop. `held-ball-sandbox-run.png` is 10 frames cropped around the ball. Seen: feet on the floor line while running, a different leg pose per frame, the tucked jump pose in the air, the ball stays in the near hand in all 10 frames. State/velocity printed with each frame matched the pose (grounded vx 250 shows run, airborne shows jump/fall frames).

### Match screen with both teams
`Godot --path godot res://scenes/match.tscn -- --mode=local --autoplay --shot=... --at=2.0` and `--at=4.0`. `.agents/tasks/smooth-run-jump/match-screenshot.png` (at 4.0): blue DEF and red WR/QB drawn from the new sheets through `match_renderer.gd`, red QB holds the ball in the hand, labels clear. No script errors besides the leak notes printed at exit.

### Still not verified
- Smoothness in motion was judged only from stills. No video, no high-refresh display.
- Left-facing sets were checked in the all-frames probe only, not in a running match (both actors in the screenshot face right).
- Land, wall cling, crouch, slide and aiming were not seen in game.
- The match screen still draws actors at the latest tick position (see "Interpolation limit" above).
- Thresholds (150 px/s apex band, 0.12 s landing, 0.08 s minimum air time, 0.35..1.6 rate clamp) remain untuned guesses.
