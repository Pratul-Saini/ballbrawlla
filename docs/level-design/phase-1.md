> **Superseded.** This describes the first, smaller layout (2944 x 1880, kept as `layout-v1.json`). The current design is in [big-field.md](big-field.md).

# Phase 1: left end zone and the first 20 yards

Three modules of 240 px (10 yd). Heights are above the floor (floor top y = 1848). The right half mirrors this.

```
 y=1428 420 +   gate       T1===     T2===     T3===
        pocket | |
 y=1568 280 +   | |          S1==
 y=1708 140 +   | |==== QB ledge ====|                 block
        0   +-- floor -- slot -------------------------------------
            x=32      248/272         512      620      752 (yard 20)
            end zone  M1: 0-10 yd                M2: 10-20 yd
```

## Pieces (final coordinates)
| Piece | Type | x | y | w x h | Job |
|---|---|---|---|---|---|
| Gate | solid | 248 | 1428 | 24 x 388 | Closes the pocket (x 32 to 248). Bottom is 32 px above the floor: the slide slot |
| QB ledge | thin | 272 | 1708 | 240 x 12 | First 10 yd, 140 up. QB and WR spawn here |
| S1 | thin | 470 | 1568 | 80 x 12 | Step from the QB ledge to the bridge (280 up) |
| T1 | thin | 420 | 1428 | 100 x 12 | Sky bridge, 420 up |
| T2 | thin | 560 | 1428 | 100 x 12 | Sky bridge (40 px gap) |
| T3 | thin | 700 | 1428 | 100 x 12 | Sky bridge, continues past yard 20 |
| Floor block | solid | 720 | 1708 | 24 x 140 | One tier tall. Taxes the bottom route by about 0.37 s |

## Frames

### Frame 1: End zone pocket (x 32 to 272)
Open at the top, so the floor is the scoring surface. Scoring means standing on a platform inside the end zone, and the gate top counts too. Three ways in, on three layers:
| Entry | Layer | Skill | Measured |
|---|---|---|---|
| A. Slide slot | floor | slide | Works when the slide starts within about 110 px of the gate. Longer slides now crawl out |
| B. Gate climb | mid | wall-climb hops from the QB ledge | about 1 s, then you are on the gate top (a score) or drop in |
| C. Bridge drop | high | run and jump along the bridge | A jump from the bridge's west end drops into the pocket, or lands on the gate top |

A Defender in the pocket can tag a climber clinging to the gate (B), and can camp the slot (A). He can't cover all three.

### Frame 2: QB ledge (x 272 to 512)
- One thin ledge across the first 10 yards at 140 px up. The QB spawns here on 1st down, and the WR beside it.
- The floor beneath is open, so players can run under it.
- It is also the 10-yard line for the opposing team's offense: a tag here starts the next down 10 yd from scoring.

### Frame 3: Escape fork (x 512 to 752)
| Route | Path | Time from the QB ledge (x=300) to the ground at x=800 |
|---|---|---|
| Top | QB ledge, S1, T1, T2, T3 (sky bridge at 420 up) | 1.52 s |
| Bottom | step off the ledge, run the floor, clear the 140 px block at x=720 | 1.89 s (open floor would be 1.57 s) |

The top route leads by about 0.37 s, roughly 5 yards of separation, which is what football calls open. A missed hop drops you on the floor next to the block, which costs you the lead. The Defender on the floor can intercept at the rejoin, and one above can drop on the bridge.

Times are best case: a bot searches for the best take-off point, double-jump timing and hop rhythm, so a human will be slower on both routes.

**Why a 140 px block and not a tall wall.** An isolated 290 px wall costs 0.39 s. But the same wall placed 70 px from where a player lands after stepping off the QB ledge cost about 1.1 s, because there was no run-up. How much a block costs depends on how close it sits to the previous landing. Always measure on the real route. With a 140 px block, positions from x=680 to x=720 gave leads of 0.48 s, 0.30 s and 0.37 s.

## Checks run (throwaway scripts, real physics)
- No overlaps, all inside the playable area.
- All three entries work. Every platform is reachable from the floor.
- **Field surfaces:** with both halves built, each team's QB region (0 to 10 yd) has 5 standable surfaces (tops at 140, 280 and 420 up, plus the floor), and each Defender range has 11.
- **Route timing:** top 1.52 s, bottom 1.89 s with the block, 1.57 s on open floor. See Frame 3.

## To do
- Phase 2: 20 to 50 yards. The bridge (T3) continues past yard 20.
- Decide the ball gravity, since it sets how far a throw travels over these routes.
