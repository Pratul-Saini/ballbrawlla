# The big field

Built by `tools/build_field_05_layout.py` (the design lives there as code). 96 platforms in the whole level: 65 thin, 31 solid.

## Idea
One shared space with two jobs:
- **The football layer (floor):** open, so players can run routes and throw. Only low blocks (140 px), ramps, and slide slots.
- **The chase network (above the floor):** a mid deck and a sky deck of thin ledges, and **pipes** (the solid walls) that gate the routes behind two skill moves.

A **pipe** is a solid wall, 24 px wide.

## The two skill moves

### Pipe hop (sky deck)
The sky deck is deliberately broken. To keep going you must land on the 24 px top of a pipe and jump on to the next ledge.

| | Pixels |
|---|---|
| Each hop leg (ledge edge to pipe, pipe to ledge) | 190 to 198 |
| Longest single jump across a flat gap (measured) | 220 |
| Ledge to ledge past the pipe | 404 to 412 |
| Longest single plus double jump across a flat gap (measured) | 340 |

So each leg is a single jump with a tight take-off, and the pipe cannot be skipped, because the total is over 340. `tools/skill_check.py` verifies this for every pipe with real physics.

### Slide under a pipe (ground, mid deck)
A low roof leaves a 32 px gap (a crouched player is 30 px tall). Tunnels are 100 to 124 px long.

| Tunnel length | Window to start the slide | A bad start costs |
|---|---|---|
| 100 px | about 65 px (203 ms) | about +1.1 s (crawl through) |
| 114 to 154 px | about 50 px (156 ms) | about +1.2 s |

A longer tunnel does not tighten the window past 50 px, it only adds time. So tunnels stay at 114 to 124 px.

## Layers
| Layer | Height above floor | Contents |
|---|---|---|
| Ground | 0 to ~150 | Floor, 140 px blocks, slide slots under pipes, ramps up to the deck |
| Mid deck | 280 | A chain of thin ledges that runs through the window of each gate; a tunnel roof on the deck |
| Ladders | 420 to 700 | Zig-zag ledges between the deck and the sky |
| Sky deck | 840 | Ledges broken by pipes: the pipe hops |

## Gates (pipes with three doors)
There is a gate at each goal line and at the 10, 20 and 40 yard marks of each half. (The old 30 yard gate is now the Great Slab.) Each gate is a pipe with three doors:
| Door | Layer | Skill |
|---|---|---|
| Slot | ground | slide under the 32 px gap, often through a short tunnel |
| Window | mid deck | walk through the 140 px opening (280 to 420) |
| Top | sky | the pipe top at 840 is a hop target |

At the goal line these are the three **end zone entries**. The pipe top there counts as scoring (standing on a platform inside the end zone).

## Slabs: big masses for variance
Not everything is a thin ledge or a 24 px pipe. Three kinds of mass break up the scale and force routes apart:

| Slab | Size | What it does |
|---|---|---|
| **Bulwark** (segment 2) | a pipe 120 px thick, 420 px tall | Its slot is a 120 px slide tunnel, its window is a 120 px corridor, and its top is a 120 px wide landing between two sky hops |
| **Great Slab** (segments 3 and 4) | 700 x 200 px, top at 700 | Underneath is a covered corridor (deck and ground, 220 px of headroom) with a slide tunnel. On top is a 700 px wide plateau. Above it is the sky, with a pipe standing on the slab |
| **Hub slab** (segment 5) | 600 x 100 px, top at 560, centered on midfield | The stage. Ladders on each side end flush with its faces, and an apex hops up from its top |

Under, over, or through is a real choice, and a route cannot be switched mid-way except at a ladder or a ramp.

Reaching a slab top: the last ladder step is flush with the slab's face at the same height as its top. You hop across a 10 px gap. For the Great Slab the last step sits 140 px below the top, so you jump up along the face.

## Segments (480 px = 10 yd each)
| Segment | Yards | What's in it |
|---|---|---|
| End zone | -10 to 0 | The pocket, a shelf at deck height, gate g0 with a slide tunnel |
| 1 | 0 to 10 | QB ledge (the first 10 yd), deck, a ladder, a sky hop from g0 to g1 |
| 2 | 10 to 20 | The bulwark, a ramp, a ladder, gate g2 at the 20 with a slide tunnel |
| 3 and 4 | 20 to 40 | The Great Slab, a covered deck corridor with a tunnel, a pipe on the slab, gate g4 at the 40 |
| 5 | 40 to 50 | The hub slab, ladders to it, an apex, a deck |

## Status
Third draft. The skill moves and the slabs are in and checked. Nobody has played this version yet.
