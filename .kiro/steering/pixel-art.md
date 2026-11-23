# Pixel Art & Aseprite Steering Rules (ballbrawlla)

Adapted from section 5 of the AI sprite workflow doc. Applies to everything under `godot/assets/sprites/player/` and `tools/aseprite/`.

## Source art and regeneration

1. **Only two hand-drawn sources exist:** `fball_navy` (blue, team 0) and `fball_red` (red, team 1), plus their `_left` files (separate art so the jersey number "23" reads correctly facing left). Never draw characters from scratch, never replace them with generated sprites, never edit these four `.aseprite` files. Animations are built from copies.
2. **One command rebuilds everything:** `tools/make_run_cycle.sh` (env `ASEPRITE` = aseprite binary, `PY` = python with Pillow; defaults are the local paths). It splits layers, rigs the tagged timeline, exports sheets, writes `anim/player_anim.json`, runs the checks and writes the contact sheet. It exits non-zero when a check fails.
3. **Tune motion in `tools/aseprite/rig.lua`** (the `FRAMES` table of integer layer offsets) and region boundaries in `tools/aseprite/common.lua`. Do not hand-edit generated files in `godot/assets/sprites/player/anim/`.

## Frame geometry

4. Frames are **96x96**, untrimmed, one horizontal strip per set (`navy`, `navy_left`, `red`, `red_left`). Feet stand on **row 85** (lowest opaque row) in every grounded frame (idle, run, land, jump take-off). Air frames may be higher, never lower.
5. The hitbox is 24x42 px (26 crouching). The art is drawn at `VISUAL_SCALE` 1.35 times the hitbox height, bottom aligned to the hitbox bottom, so row 85 maps to the hitbox bottom. Do not change canvas size or ground row without changing `player_sprites.gd` too.
6. Nothing may touch the outer border of the 96x96 frame.

## Color and palette

7. **No new colors.** The palette is the 30 colors of `fball_navy.png` (`fball_red.png` for red). Only copy existing colors. The checker fails any frame with a color outside the source palette or partial alpha.
8. The source already contains pure black (`#000000`, the outline) and pure white (`#FFFFFF`, number and shoe stripes). Never add more of either than the source has (the checker compares counts). Do not use them for new shading. Use hue-shifted darks and creams from the existing palette.

## Pixel hygiene

9. **Nearest neighbor only.** No bilinear or bicubic, no anti-aliasing, no arbitrary-angle rotation. Moves are whole-pixel cel offsets. A horizontal flip is allowed (the run cycle mirrors the legs); keep the number and torso unflipped.
10. Keep the 1 px outline clean. No orphan single pixels beyond the source count (0), no enclosed transparent holes in the body (0).
11. The disocclusion fill may only copy a neighbor pixel color into a pixel that was opaque in the base pose and is now empty and inside the 2 px closing of the silhouette. It never grows the silhouette, and it never copies outline black or white.

## Non-destructive structure

12. **Never flatten layers automatically.** The rigged files keep `leg_far`, `leg_near`, `fill`, `head_torso`, `arm_far`, `arm_near` (bottom to top). Animated files are `anim/<set>_rig.aseprite`.
13. Wrap every multi-step Lua edit in `app.transaction()` so one undo reverts an AI pass.
14. Tags: `idle` (2), `run` (8, loop), `jump` (2), `apex` (1), `fall` (2), `land` (2). Per-frame durations live in the timeline. Loop flags live in `tools/aseprite/sheet_to_godot.py`.
15. The ball hand anchor of every frame is written to `anim/<set>_hands.json` from the `arm_near` offset. If the arm moves, the anchor moves with it. Keep `arm_near` from covering the jersey number (never offset it left in right-facing art).

## Review

16. After any change to the rig, run `tools/make_run_cycle.sh`, then open `.agents/tasks/smooth-run-jump/contact-sheet.png` and look at it. Passing checks do not prove the animation reads well.
