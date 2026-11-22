> **Superseded.** This describes the first, smaller layout (2944 x 1880, kept as `layout-v1.json`). The current design is in [big-field.md](big-field.md).

# Phase 3: joining the halves

`levels/field_02.json` is generated from [layout.json](layout.json) by `python tools/gen_field_02.py levels/field_02.json`. The right half is the mirror of the left (x' = 2944 - x - w), and pieces centered on midfield are written once.

## The level
| | |
|---|---|
| Size | 2944 x 1880 px, 6.01x the original arena's area |
| Platforms | 34 total: 30 thin, 4 solid (2 gates, 2 floor blocks) |
| Field | Passes the football field check (inner width 2880 px) |
| Spawn surfaces | 39 standable surfaces. Each team has 5 in its QB region and 31 in its Defender range |

To play it: `python -m ballbrawlla --level levels/field_02.json` (practice), or add `--host`.
Note: the camera shows 1280 x 720 px at 1:1 for now. The zoomed-out view is a separate piece of work (the `tall-field` spec).

## Fairness checks (the right side is the mirror)
| Check | Result |
|---|---|
| Right end zone, slide slot | enters the pocket |
| Right end zone, gate climb | reaches the gate top in 0.98 s (left side: 0.97 s) |
| Right end zone, bridge drop | lands on the pocket floor |
| Floor run goal line to goal line, hopping both blocks | 7.32 s, the same as open floor (7.31 s) |
| Block clearance | single jump works from 110 to 155 px before the block, about a 0.14 s window |
| Random 10-minute 2-player matches | no crashes, all phases reached, frames render |

The pre-throw clock is 10 s, so a WR can cross the entire floor with 2.7 s to spare.

## Things I noticed
- A 140 px block against a 153 px jump leaves only 13 px of clearance. It is fair (the window above is wide enough), but a double jump is the forgiving option.
- Random inputs almost never score or tag, so the random matches only prove nothing crashes. They say nothing about balance.
- `field_02` replaces the level described in the `tall-field` spec, which planned its own `field_02.json` and generator. See the open question in [README.md](README.md).
