# Findings

## Measured jump and slide numbers (real physics)
| | Result |
|---|---|
| Longest flat gap crossable by a single jump | 220 px (I had assumed about 240) |
| Longest flat gap crossable with a double jump | 340 px |
| Slide start window, 114 px tunnel | about 50 px, 156 ms |
| Cost of a bad slide start | about 1.1 to 1.2 s |

A first measurement said a single jump crossed 450 px. It was wrong: the test counted a fall to the floor as a landing. The numbers above only count landings on the target ledge.

## Route solver findings (first draft)

`python tools/route_solver.py` builds a graph of 322 standing spots and 3,181 moves (real jumps, walk-offs, slides, wall climbs) and solves routes and chases.

## 1. All three layers take the same time
From the 20-yard line to the far end zone, ground, deck and sky all take **10.8 s** (open floor: 11.9 s). There is no route choice yet. A jump or a drop costs nothing, because everyone moves at 320 px/s in the air too. A route only gets slower when it forces a stop, a reversal or a wall climb.

## 2. Chases from behind: the carrier almost always escapes
With the Defender 4 to 15 yards behind the carrier, 47 of 51 chases end in an escape, lasting 9 to 12 s. The four tags happened only when the Defender stood on a different layer from a carrier on the deck. So the world is big enough for a long run. But a chaser who is simply behind can never catch up.

## 3. Chases head-on: the carrier is always tagged
With the Defender 15 yards ahead, 36 of 36 chases end in a tag after 3 to 8 s (median 5.8 s). That is the expected football situation.

## What this means
- **Length is solved, tension is not.** Runs last 9 to 12 s, which satisfies "run for a while". But the chase is decided by position, not by routes.
- **To make chases elaborate, the layers must differ in cost.** Add time sinks to the layer that is otherwise shortest, and shortcuts to the others:
  - the ground gets tall walls (400+ px) that force wall climbs
  - the deck gets forced detours (the slot walls cost about 0 s, so they do not count)
  - the sky gets gaps that need a double jump, and ladder zig-zags to reach it
- The target to aim for: the three layers within about 1 to 2 s of each other, so the right choice depends on where the Defender is.

## Caveats
- All times are best case (an optimal route). A human is slower.
- Wall climbs are modelled at 280 px/s plus 0.25 s, from one hand test.
- The Defender is modelled as always taking his best path. A real Defender has to guess.
- The graph samples a spot every 70 px, so routes are approximate.

## After the skill moves
The best-case solver still shows all three layers at the same time (10.1 s from the 20 yd line). That is by construction: it assumes a perfect run, and skill gates do not slow a perfect run. They punish mistakes.

So the routes now differ in **risk**, not in best-case time:
| Route | Gate | What a mistake costs |
|---|---|---|
| Ground | slide slots and tunnels (156 ms window) | about +1.2 s of crawling |
| Mid deck | tunnel roof, window doors | a fall to the ground, then a ramp back |
| Sky | pipe hops (190 to 198 px legs) | a fall to the deck or the floor |

Not measured yet: how large a lead a miss costs on each route, and how a Defender exploits it. That needs a chase model that includes mistakes.

## After the slabs
- 20 sky hops across both halves: each leg is a single jump (156 to 202 px) and every pipe or slab is unskippable (neighbours 370 to 448 px apart, past the 340 px double-jump limit).
- Best-case crossing time through the Great Slab stretch is about the same on every route (2.3 to 2.6 s for about 20 yd). That is expected: speed is constant, so route choice is about risk and position, not perfect-run time. I tried to measure each route separately, but the filters were too loose to separate them, so there is no per-route number yet.
- Not measured: how long a chase lasts through the slabs, and what a missed hop costs against a Defender.
