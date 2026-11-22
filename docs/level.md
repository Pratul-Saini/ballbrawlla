# Levels

Source: `world/level.py`, `levels/arena_01.json`. Rendering colors are in [input-and-rendering.md](input-and-rendering.md).

A level is a rectangular arena, a list of platforms, spawn points for players and a spawn point for the ball. Levels are JSON files loaded with `load_level`.

## File format

```json
{
  "name": "Arena 01",
  "width": 1280,
  "height": 720,
  "wall_thickness": 32,
  "player_spawns": [[200, 650], [1080, 650]],
  "ball_spawn": [640, 120],
  "platforms": [
    {"x": 200, "y": 550, "w": 220, "h": 20, "type": "thin"},
    {"x": 600, "y": 600, "w": 80,  "h": 88}
  ]
}
```

| Field | Meaning |
|---|---|
| `name` | display name. If missing, the file name is used |
| `width`, `height` | arena size in px |
| `wall_thickness` | thickness of the generated boundary walls (default 32) |
| `player_spawns` | list of player **centers**, one per player slot. Slot `i` uses entry `i % len`, so a short list is reused |
| `player_spawn` | older single-spawn form, used only if `player_spawns` is missing |
| `ball_spawn` | the ball's **center** |
| `platforms` | list of rectangles, each `{x, y, w, h}` with `(x, y)` the top-left corner |
| `type` (per platform) | optional, `"thin"` or `"solid"` |

Unknown keys are ignored. Any `type` other than exactly `"thin"` or `"solid"` raises a `ValueError`. A level with a bad type does not load.

## Boundaries

You do not list the floor, ceiling and side walls. `Level` generates them from `width`, `height` and `wall_thickness`, so every level is enclosed. They are always solid, are drawn in a darker color, and come first in the platform list (floor, ceiling, left wall, right wall). The playable area is `width - 2 * wall_thickness` by `height - 2 * wall_thickness`. In the bundled arena that is 1216 by 656 px, with the floor top at y = 688.

## Platform types

| Type | Behavior | Look |
|---|---|---|
| **solid** (default) | blocks players and the ball from all four sides. You cannot jump through it. You can land on it, wall-cling on its sides, and bump your head on it | gray rectangle |
| **thin** | one-way. You and the ball pass through it from below and from the sides, and land on it from above | teal rectangle with a light 3 px top edge |

Details for thin platforms (the full rules are in [physics.md](physics.md)):
- A thin platform never gives a ceiling or wall contact, so you cannot wall cling on it or hit your head on it.
- Standing up from a crouch ignores thin platforms.
- There is no way to drop through one on purpose yet. Down still crouches.
- A thin platform is "landed on" based on where your feet were when you started moving down. If your feet are already below its top edge, you fall through.

Use solid platforms for walls, pillars and floors you want to be hard. Use thin platforms for walkways and ledges players should be able to reach by jumping from underneath.

## Spawns

- Players spawn at their slot's center point and fall to the floor if it is above it. In the bundled arena the spawn centers are at y = 650, 14 px above where the box bottom rests, so players drop a few pixels at the start.
- The ball starts at `ball_spawn` and falls. In the bundled arena it starts high at (640, 120).
- Respawn on `Game.reset()` (key R on the host) uses the same points.

## The bundled arena (`arena_01.json`)

1280 by 720, walls 32 px thick, floor top at y = 688.

```
y=160  |      |                 ___ (560..720, y=200 thin)      |      |
       |  wall 330..354         (520..760, y=400 thin)      wall 926..950
y=300  |__ (32..142 thin)                           (1138..1248 thin) __|
y=550       (200..420 thin)                         (860..1080 thin)
y=600                       [block 600..680 solid, up to floor]
y=688  ================================ floor ============================
```

| Platform | x | y | w | h | Type |
|---|---|---|---|---|---|
| Left walkway | 200 | 550 | 220 | 20 | thin |
| Right walkway | 860 | 550 | 220 | 20 | thin |
| Center walkway | 520 | 400 | 240 | 20 | thin |
| Top walkway | 560 | 200 | 160 | 20 | thin |
| Left side ledge | 32 | 300 | 110 | 20 | thin |
| Right side ledge | 1138 | 300 | 110 | 20 | thin |
| Center block | 600 | 600 | 80 | 88 | solid |
| Left pillar | 330 | 160 | 24 | 240 | solid |
| Right pillar | 926 | 160 | 24 | 240 | solid |

The sketch is not to scale. The layout is mirrored left to right. The two pillars are solid on purpose so you can wall cling and wall jump on them. The block in the middle sits on the floor and can be run around or jumped over.

## Designing levels: numbers to use

These come from the player's movement numbers in [player.md](player.md).

| What | Number |
|---|---|
| Single jump height | about 153 px |
| Single jump plus double jump (best case) | about 258 px |
| Horizontal distance of a full single jump | about 240 px |
| Wall jump rise | about 118 px |
| Player box | 28 wide, 48 tall (30 crouched) |
| Ball | 24 px across |

Guidelines:
- A ledge up to about 150 px above where you stand is reachable with a normal jump. Up to about 255 px needs a double jump. Higher needs walls or a chain of ledges.
- Horizontal speed is fixed at 320 px/s, so a single jump crosses a gap of about 240 px. A double jump extends that. Wider gaps need a wall or a stepping platform.
- Leave at least 42 px of headroom under a solid platform if you want players to stand under it, or 26 px if they should only crouch under it.
- Platform thickness: any value of 1 px or more is safe from tunnelling, even at the maximum throw speed. 20 px reads well.
- Keep platforms from overlapping each other. The collision code resolves them one by one and assumes separate rectangles.
- Solid walls are the only thing players can cling to. Put some in if you want wall play.
- The ball bounces with 75% restitution, so a ball dropped from a platform will bounce several times. Floors that are too close to platforms above can make it hard to retrieve.

## Making a new level

1. Copy `levels/arena_01.json`.
2. Edit the size, spawns and platforms. Keep spawns inside the playable area.
3. Run it: `python -m ballbrawlla --level levels/my_level.json`.

There is no level editor. In network play, only the host's level matters: the host sends it to the client when they join.

## In code

- `Level.platforms`: every platform including the four boundaries, in order.
- `Level.solids`: the rectangles that block from all sides (boundaries first, then solid platforms in file order).
- `Level.thin`: the one-way rectangles, in file order.
- `level_from_dict` / `level_to_dict`: convert to and from the file format. `level_to_dict` omits the boundaries, writes `"type": "thin"` only for thin platforms, and leaves solid platforms with just `x, y, w, h`.
