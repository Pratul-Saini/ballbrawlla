# Level design: field_05 (the big field)

Football is the reference for the rules, and SpeedRunners is the reference for movement. The field has two states in one space: a football state (run routes, throw, catch) and a chase state (the carrier escapes through a route network). See [big-field.md](big-field.md) for the current design and [findings.md](findings.md) for what the measurements say.

## Files
| File | What it is |
|---|---|
| `layout.json` | The left half of the level as data (generated). The right half mirrors it |
| `layout-v1.json` | The first, smaller layout (superseded) |
| `big-field.md` | The current design: scale, layers, gates, pieces |
| `findings.md` | Measurements and what they imply |
| `phase-1.md`, `phase-2.md`, `phase-3.md` | The superseded first layout |

Tools (in `tools/`):
| Tool | Use |
|---|---|
| `build_field_05_layout.py` | Writes `layout.json` (the design lives here as code) |
| `layout_tools.py check` | Bounds, overlaps, symmetry, spawn surfaces, reachability with real jumps |
| `skill_check.py` | Every pipe hop is forced and doable; slide tunnel windows |
| `route_solver.py` | Fastest routes by layer, and chase tests against a Defender |
| `gen_field_05.py levels/field_05.json` | Writes the playable level |

To change the level: edit `build_field_05_layout.py`, then run the builder, `layout_tools.py check`, `skill_check.py` and `gen_field_05.py` in order.

## Dimensions
| | |
|---|---|
| Arena | 5824 x 2400 px (15.2x the original 1280x720 area) |
| Yard | 48 px (a level setting, `yard_px`). Field 100 yd = 4800 px, end zones 480 px |
| Walls | 32 px. Floor top y = 2368 |
| Goal lines | x = 512 and x = 5312. Midfield x = 2912 |
| Symmetry | The right half mirrors the left: x' = width - x - w |

Crossing the field on the open floor takes about 18 s. The pre-throw clock is 10 s.

## Movement gates (what each height or gap requires)
| Gate | Requires |
|---|---|
| Any solid block, even 10 px | A jump (no step-up) |
| Rise up to about 150 px | Single jump |
| Rise up to about 258 px | Double jump with good timing |
| Rise above 258 px | A stepping ledge, or climbing a solid wall (about 280 px per second) |
| Gap of 30 to 47 px under a solid | A slide. A crouched player crawls (110 px/s), so it never traps |
| Horizontal gap up to about 220 px | Single jump (measured) |
| Horizontal gap up to about 340 px | Single plus double jump (measured) |

## The most important fact about this game's physics
Everyone runs at 320 px/s, **including in the air**. A jump or a drop costs no time. Only stops, reversals and wall climbs cost time. So a level makes routes differ by building **time sinks**, not by adding obstacles you can hop. A wall you can jump over costs nothing.

## Rules every piece must pass
1. Reachable from the floor with real jumps.
2. Both roles: each half works as a start area and as a scoring area.
3. No free yards: every platform top is a possible next-down spot.
4. The floor lane passes end to end.
5. No overlaps, everything inside the arena.
6. Spawns: the QB region and the Defender range contain standable surfaces.
