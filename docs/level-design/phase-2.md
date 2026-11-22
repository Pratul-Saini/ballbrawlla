> **Superseded.** This describes the first, smaller layout (2944 x 1880, kept as `layout-v1.json`). The current design is in [big-field.md](big-field.md).

# Phase 2: 20 to 50 yards, up to midfield

Left half, x 752 to 1472. The right half mirrors it. Every number is in [layout.json](layout.json); this file explains the intent.

## Rules chosen for this zone
1. **Throw lanes stay open.** No solid piece taller than 140 px in the field of play. A pass should never be blocked by scenery, as in football. Thin ledges don't block a ball, so all cover and routes here are thin.
2. **Three layers, one job each.**
   | Layer | Height | Job |
   |---|---|---|
   | Low shelves | 140 | Quick hops off the floor, a safe landing when a higher jump fails |
   | Catch nests | 280 | Mid-level catches and interceptions |
   | Bridge | 420 | The fast top route |
3. **The floor lane stays open.** Past the Phase 1 block, nothing on the floor.
4. **The top route has one skill gate:** a 210 px gap. A miss drops you to the shelves or the floor.
5. **The hub is shared.** It straddles midfield and is its own mirror, so both teams fight over the same ground.

## Frames
### F4: 20 to 30 yd, catch nests (x 752 to 992)
The Defender's range starts here (20 yd past the QB's furthest spot). A low shelf (L1, x 790) and a nest (N1, x 850, 280 up) give a Defender somewhere to wait and a WR somewhere to catch. Both are reachable from the floor by single jumps, and a Defender on the nest sees the whole lane.

### F5: 30 to 40 yd, the gap (x 992 to 1232)
The bridge from Phase 1 ends at x=800 (T3). It resumes at T4 (x 1010): a **210 px gap**. A single jump crosses 240 px at best, so the gap needs a clean take-off, and it is the top route's one real risk. Past it the bridge continues (T4, T5) with a nest (N2) and a low shelf (L3) underneath, so a missed jump still lands somewhere useful.

### F6: 40 to 50 yd, the hub (x 1232 to 1472)
A Brawlhalla-style stage around midfield:
- **H0**, the main stage: 200 px wide at 280 up, centered on x = 1472.
- **H1L** (and its mirror), the wings: 420 up.
- **H2**, the apex: 560 up, centered.
- **HL** (and its mirror): a 140 px step so anyone can climb from the floor.

Contested catches and interceptions happen here. The ledges are thin, so a thrown ball passes through them and a defender can still reach a high catch.

## Decisions and reasons
| Decision | Why |
|---|---|
| Only thin pieces in the field of play | Keeps every throw lane open, which football treats as the basic fairness of the passing game |
| 140 px layer spacing | One tier is a single jump (153 px), so every layer is one hop from the next |
| 210 px gap rather than 240 | A single jump covers about 240 px, so 210 leaves a margin that rewards a clean take-off without being a coin flip |
| Hub centered on midfield | Mirror symmetry means neither team owns it |
| No floor obstacles beyond the Phase 1 block | The floor is the defender's fastest lane. Taxing it more would make the top route the only route |

## Checks (tools/layout_tools.py check)
- Everything inside the arena, under the 1000 px cap, no overlaps in either half.
- No solid taller than 140 px in the field of play.
- Pieces crossing midfield are symmetric about it.
- Every piece reachable from the floor with real jumps. The 210 px gap jump is confirmed by physics.
- Enough standable surfaces for each team's QB region and Defender range.

## Not tested yet
- Route timing across this zone (Phase 1 timed the fork only).
- Feel: this is a first draft and needs playing.
