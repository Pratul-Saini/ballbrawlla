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

## Round 2 (feet, arms, jump poses, clock key)

User feedback: "the feet look weird, need the front foot planted and the back foot out and alternate", plus the other changes I had listed. Images to look at:
- `run-cycle-closeup.png`: navy right-facing run, 8 frames, 4x, ground row 85 drawn (grey and yellow line).
- `contact-sheet.png`: all four sets, run row plus idle/jump/apex/fall/land.
- `idle-air-closeup.png`: navy idle, jump, apex, fall, land at 4x.
- `ingame-run-sequence.png`: sandbox screenshots with the ball held. Top two rows: running left (left-facing set). Bottom two rows: running right.

### What changed in the art
- `rig.lua` no longer flips legs. Each leg is built from the user's own leg pixels as one of two parts: `N` (the drawn front leg: shin, optionally stretched or squashed by row duplication or removal, plus the flat shoe, moved as a unit) and `F` (the drawn back leg: horizontal leg with the toe-down shoe, lifted by an offset and a 1 to 2 px column shear). There is no mirroring, so the shading keeps its light direction. This removes the thigh slab and the reversed shading.
- The 2 px outline stub at the left of the pelvis (row 64, x <= 39) moved from the torso layer into `leg_far` (`common.lua`). This was the stray seam pixel in run 3/4/7. The layers still flatten back to the source.
- Cycle: in half 1 `leg_far` is planted in front (frames 8, 1, 2, 3: flat shoe on row 85, sliding back 6 px per frame under the body) while `leg_near` trails (frames 1, 2: foot 7 to 8 rows above the ground, toe down) and swings forward with the knee up (frame 3: foot 11 rows up). Frame 4 plants `leg_near` in front and lifts `leg_far`. Frames 5 to 8 repeat with the roles swapped. Each leg is planted for 4 frames and in the air for 4.
- Torso: forward lean by shearing rows (head 1 px, chest 0 or 1 px in contact and down frames), 0/1 px bob (lowest at the down frame, highest at passing and up). Arms counter-swing: the far arm swings in toward the body (up to 8 px) when the near leg is forward; the near arm only moves 0 to 2 px right, 2 px up and down, so "23" stays uncovered.
- Idle is a relaxed stance: both flat shoes side by side on row 85, legs shorter, arms hanging, 1 px breathing dip.
- Jump: take-off is a squash with both legs compressed 3 rows; rise has the front knee up and the back leg trailing; apex tucks both knees (feet 10 and 14 rows up); fall extends and stretches the legs apart with arms up and back; land is a deep crouch (legs compressed 4 rows, torso 6 px lower than standing relative to the feet) then recovery. Frame counts and tag names are unchanged (idle 2, run 8, jump 2, apex 1, fall 2, land 2), so `player_anim.json` and the engine mapping stay valid. Hand anchors are recomputed per frame (arm offset + half the lean + the grounding shift).

### Engine and test changes
- `match_renderer.gd`: the animation clock key is now `"<team>:<role>"` (was the role label). `_age_clocks` runs once per `draw()`: a clock not drawn for 1 s is dropped with `sprites.forget(key)`, and all clocks are dropped when the view tick counter goes backwards (a new match). Match-screen position interpolation is not implemented; this is a known limit (needs a snapshot buffer in `match_screen.gd`).
- `test_player_anim.gd`: one new test (a role on the other team gets its own clock, `forget()` restarts it).
- `check_frames.py`: new gait assertions (per set, from per-leg data that `rig.lua` writes): idle both feet on row 85; every run frame has exactly one foot on row 85 and the other at least 4 rows higher; the planted foot is the front one in the contact and down frames; the planted leg changes exactly twice per loop (and so alternates between the halves and at the loop point). Holes are now counted on rows <= 66 only (the gap between two legs is real negative space). The pure black and white allowance is the source count plus the count in the source leg rows, because a leg part is now used twice in some frames (e.g. two shoes in idle).
- `make_run_cycle.sh`: `KEEP_TMP=1` keeps the intermediate files; per-leg info goes to the temp dir.

### Commands run and results
```
tools/make_run_cycle.sh      # exit 0
  [navy|navy_left|red|red_left] layers flatten back to the source: ok
  [each set] gait: planted foot per run frame = ['far','far','far','near','near','near','near','far'] -> ok
  [each set] failures: palette=0, foot=0, bounds=0, orphans=0, holes=0, black=0, white=0, hand=0
  lowest row per tag (all sets): idle=[85,85]; run=[85 x8]; jump=[85,81]; apex=[75]; fall=[83,85]; land=[85,85]
  all checks passed (68 frame checks over 4 sets)
Godot --headless --path godot --import     # new PNGs imported, .import files committed
godot/run_tests.sh                         # 105 passed, 0 failed (script still ends FAILED from the pre-existing relay !is_open() error)
```
In-game: a throwaway probe in /tmp (not committed) ran the sandbox with a scripted left and right run, a held ball, and a scripted jump. I looked at `ingame-run-sequence.png` and the jump sequence: feet on the floor line while running, the planted foot is on the floor and the other foot is lifted, the ball is in the near hand in all frames. I did not look at the match screen again in this round.

### Frame-by-frame verdict (navy right-facing, I looked at the 4x close-up; red and the left sets I judged from the 2x contact sheet and the left-facing in-game run)
| Frame | Verdict | Notes |
|---|---|---|
| run 1 (contact) | good | Front foot flat on row 85 in front, back leg behind with the foot 7 rows up, toe down. |
| run 2 (down) | good | Same, body lower and leaning, planted foot has slid back 6 px. |
| run 3 (passing) | acceptable | Planted foot under the body, other knee up with its shoe 11 rows up. The lifted shoe overlaps the planted shin, which looks stacked. |
| run 4 (up) | acceptable | Planted foot in front again, the other leg tucked behind with the foot 4 rows up. The tucked back leg is a flat horizontal slab at the hip. |
| run 5 to 8 | acceptable | The silhouette of the legs is the same as 1 to 4 because the same two leg parts trade layers. The alternation shows in the arms and in which layer is planted, not in a different leg shape. |
| idle 1/2 | acceptable | Feet together and planted, reads as standing. The pants edge is a little ragged where the two shin parts meet the pelvis. |
| jump 1 (take-off) | acceptable | Legs visibly compressed, torso down. |
| jump 2 (rise) | acceptable | Front knee forward, back leg trailing, arms up. Reads as a stride in the air. |
| apex | acceptable | Both knees tucked. A pointed shin corner sticks out at the hip. |
| fall 1/2 | weak | Legs straight down and slightly apart, arms up. Reads as "standing with arms up", clearly different from run but not dramatic. |
| land 1/2 | acceptable | Crouch is readable. Jagged pants edge at the hip. |

### Still wrong or not verified
- The cycle is effectively a 4-pose loop played twice. The two halves differ in arms and layer roles only, since both legs use the same two drawn leg parts. Making half 2 differ would need new drawn art.
- Foot sliding: the planted foot moves back 12 art px (about 8 screen px) during its 3 planted frames, but at 320 px/s the ground moves about 100 screen px per step. The planted foot therefore slides on the ground in game. Fixing that needs a longer stride in the art or a slower run clock (`run_rate` in `player_sprites.gd`), which I did not change.
- Hip seams: small pointed corners remain at the hip in apex and some passing frames. The rig layers are kept for hand polishing.
- Red and left-facing sets were not inspected at 4x. The match screen, wall cling, crouch, slide and aiming were not re-checked after this round. The ball stays large and covers most of the "23" while held (unchanged, existing size).
- The match screen still draws actors at the latest sim tick (no interpolation). Motion smoothness was judged from stills only.
