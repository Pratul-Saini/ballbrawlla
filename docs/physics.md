# Physics

Shared rules used by the player, the ball and the level. Source: `physics/body.py`, `physics/shapes.py`, `physics/collision.py`.

## Coordinates and units

- Units are pixels, seconds and degrees.
- The origin is the top-left of the arena. **x grows right, y grows down.** Gravity is a positive y acceleration, and "up" is negative y.
- A player's `body.pos` is the **top-left of its box**. The ball's `body.pos` is its **center**.
- Platforms and the player are `AABB(x, y, w, h)` with `(x, y)` the top-left corner. The ball is a circle.
- `AABB.overlaps` is strict: boxes that only touch edges do not overlap. A player standing on a floor has its bottom exactly at the floor top and does not overlap it.

## Integration (`Body`)

Every moving thing has a `Body` with position, velocity, an extra acceleration `acc` (unused by default) and a `gravity` value in px/s².

Each tick is semi-implicit Euler, in two halves:
1. `integrate_velocity(dt, gravity_scale)` updates velocity: `vel.y += (gravity * gravity_scale + acc.y) * dt` and `vel.x += acc.x * dt`.
2. Position is then advanced by the new velocity inside the collision routine.

The player and the ball each have their own gravity. Both default to 2200 px/s². The player's gravity can be scaled by its state (wall cling uses 0.3 when falling).

## Player collision (`move_aabb`)

The player is a kinematic box. `move_aabb(box, vel, dt, solids, thin)` moves it and pushes it out of platforms:

1. The move is split into sub-steps of at most **8 px** (`MAX_AABB_STEP`), so a fast fall cannot skip over a platform.
2. In each sub-step the box moves along **X first**, then **Y**.
3. After the X move, any overlapping solid pushes the box flush against its near edge and sets `vel.x = 0`.
4. After the Y move, any overlapping solid does the same on Y: moving down snaps the box bottom to the solid's top, moving up snaps the box top to the solid's bottom. Either way `vel.y = 0`.
5. Then thin platforms are checked, only if the box was moving down (see below).

The box is pushed out of solids one at a time in list order. There is no corner-case handling beyond that, which is fine for rectangles that do not overlap each other.

## Thin (one-way) platforms

A thin platform stops the mover only when **both** are true:
- it is moving down (`vy > 0` at the start of the sub-step), and
- its bottom was at or above the platform's top edge at the start of the sub-step (within `1e-6` px, `ABOVE_TOP_TOL`).

Then the box snaps so its bottom sits on the top edge and `vel.y = 0`. In every other case it passes through: moving up, moving sideways, or already below the top edge.

Solids are resolved first. If a mover overlaps both a solid and a thin platform, the solid decides, and the thin platform can only stop the mover higher, never lower.

## Contacts (`probe_contacts`)

After each move the player probes by nudging its box 1 px in each direction and checking for overlap with solids. This yields four flags:

| Flag | Meaning |
|---|---|
| `on_ground` | a solid is within 1 px below, **or** the box bottom is on a thin platform's top edge (within `1e-6`) and overlaps it horizontally |
| `on_ceiling` | a solid is within 1 px above |
| `wall_left` / `wall_right` | a solid is within 1 px to that side |

Thin platforms only ever set `on_ground`. They never produce ceiling or wall contacts, so a player cannot wall cling on one and cannot bump its head on one.

The state machine reads these flags on the next tick.

## Standing up (`box_is_free`)

Crouch and slide shrink the box from 48 px to 30 px with the **feet kept planted**. Standing up needs the taller box to be free of **solids only**. Thin platforms are ignored, so you can stand up under a thin walkway.

## Ball collision (circle vs box)

See [ball.md](ball.md) for behavior. The geometry:

- `circle_vs_aabb` finds the closest point on the box to the circle's center. If the distance is under the radius, it returns a contact with the unit **normal** (from the box toward the circle) and a penetration **depth**.
- If the center is inside the box, the circle is pushed out along the shallowest axis.
- The ball is pushed out by `normal * depth` and its velocity is reflected by `bounce`.

### The bounce

`bounce(vel, normal, restitution, friction, rest_speed)`:

- If the ball is already moving away from the surface (`vel . normal >= 0`) nothing changes.
- Split `vel` into a part along the normal (`v_n`) and a part along the surface (`v_t`).
- If the impact speed `|v_n|` is below `rest_speed`, drop the normal part: result `v_t`. The ball settles.
- Otherwise the result is `v_t * (1 - friction) - v_n * restitution`. Defaults: restitution 0.75 (loses 25% of its normal speed), friction 0.1 (loses 10% of its sliding speed).

There is no spin. A ball hitting a surface at an angle keeps rolling in the same sense, minus the friction loss.

## Tunnelling

- Players move at most 8 px per sub-step. Their minimum box height is 30 px and their max fall speed is 1200 px/s, which is 10 px per tick, so two sub-steps per tick.
- The ball takes sub-steps of at most half its radius (6 px). Its diameter is 24 px, so a platform 1 px thick or more cannot be skipped, even at the maximum throw speed of 1400 px/s (11.7 px per tick).

## Not modeled

- Player-vs-player and player-vs-ball collision.
- Moving platforms.
- Slopes or any shape other than axis-aligned rectangles.
- Air drag.
