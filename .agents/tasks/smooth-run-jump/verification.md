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

## Engine side

Not part of this step. To be filled in by the `engine` step.
