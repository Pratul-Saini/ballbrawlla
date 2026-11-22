# Ball

Source: `entities/ball.py`. Collision math is in `physics/collision.py` (see [physics.md](physics.md)).

## What the ball is

A circle of radius 12 px with its own `Body`: position (its center), velocity, and gravity of 2200 px/s² (equal to the player's by default). There is one ball in the game. It has no spin and no mass: nothing pushes it except gravity, bounces, and throws.

## Two modes

### Free
Free means `held_by is None`. Each tick:

1. **Gravity.** `vel.y += gravity * dt`.
2. **Sub-steps.** The move is split so the ball never travels more than half its radius (6 px) in one step: `steps = ceil(speed * dt / 6)`. The max throw speed of 1400 px/s is 11.7 px per tick, which is 2 steps.
3. **For each sub-step:** move by `vel * sub_dt`, then:
   - for each **solid** platform, if the circle overlaps it, push the ball out along the contact normal by the penetration depth and apply `bounce` to its velocity;
   - for each **thin** platform, apply the one-way rule below.
4. **Resting.** After the sub-steps, if the ball is resting (see below), its horizontal speed is damped by `1 - 1.5 * dt` per tick, so it rolls to a stop.

### Held
Held means `held_by` is a player. The ball ignores physics. Each tick its position is set to the holder's hand and its velocity to zero. The hand is at the player's center plus `(facing * 0.6 * width, -0.15 * height)`: in front of the player and a little above center.

A ball becomes held through pickup and free again through a throw (or if its holder leaves the game). See [catching-and-throwing.md](catching-and-throwing.md).

## Bouncing

Contact with a solid reflects the velocity (details in [physics.md](physics.md)):

- Normal speed after the bounce is the incoming normal speed times **restitution 0.75**.
- Sliding speed along the surface is multiplied by **1 - bounce friction (0.1)**.
- An impact with normal speed under **rest speed 40 px/s** does not bounce at all: the normal part is removed and the ball settles.

So a ball dropped from rest bounces lower each time: each bounce keeps 75% of the speed, which is about 56% of the height. The bounces die out once the impact speed falls under 40 px/s.

The ball bounces off all four sides of a solid platform and off the arena boundaries. It hits corners as circle-to-point contacts, so a corner hit sends it away along the line from the corner to the ball's center.

## Resting and rolling

The ball is **resting** when it has just bounced off a surface whose normal points mostly up (`normal.y < -0.7`) and the resulting vertical speed is zero. While resting:
- `resting` is true (the debug overlay shows "rest"),
- horizontal speed decays at 1.5 per second.

`resting` is recomputed every tick. A ball that is not touching a floor on a tick is not resting.

## Thin platforms

A thin platform acts as a solid floor for the ball, but only from above:

- On a sub-step where the ball is moving down **and** its bottom was at or above the platform's top at the start of that sub-step, an overlap pushes the ball up so it sits exactly on top (`pos.y = top - radius`) and bounces with an **upward normal**. This works the same for hits on the flat top and for hits on a top corner.
- Moving up, sideways, or coming from below the top edge: the ball passes through untouched.
- Because the contact normal is forced upward, resting and rolling work on a thin platform exactly as on a floor.

## What the ball does not do

- It does not collide with players. A player standing in the ball's path does not stop it. The only ways a player affects the ball are pickup and throw.
- It does not collide with anything while held.
- It is not removed or reset by leaving the arena, because the arena is enclosed by boundary walls.
- It never scores. There are no goals yet.

## Reset

`Game.reset()` (key R on the host) puts the ball back at the level's `ball_spawn` and respawns the players. `Game.reset_player` releases the ball from a player who leaves.

## Useful numbers

| Thing | Value |
|---|---|
| Radius | 12 px |
| Gravity | 2200 px/s² |
| Restitution | 0.75 |
| Bounce friction | 0.1 |
| Rest speed | 40 px/s |
| Rolling drag | 1.5 per second |
| Throw speed range | 300 to 1400 px/s |
