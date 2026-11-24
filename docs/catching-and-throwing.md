# Catching, aiming and throwing

> **Throwing is switched off in this version.** `Tuning.throw_enabled` defaults to `False`: nobody aims, the QB does not throw
> (the QB only marks the ball spot), and the WR carries the ball from the snap through a `route_window_seconds` route window.
> This page describes the code path that stays in the game behind the switch. Set `throw_enabled = True` in `config.py` (and run
> `tools/export_parity.py`) to bring it back; `pre_throw_seconds` then sets the free-running time before the automatic throw.

Source: `entities/player.py` (pickup logic, `throw`), `entities/player_states.py` (Aiming), `game.py` (`_resolve_pickups`, `ball_trail`). Tuning values are in `config.py`.

"Catching" is picking the ball up with **Z**. There is no separate catch mechanic. Because the host judges every pickup, the rules are built to forgive timing errors and network lag.

## The pickup flow

1. **Input.** Z arrives as a one-tick press edge (`Intent.z_pressed`). Holding Z does nothing extra.
2. **Attempt.** `Player._pickup_step` runs once per tick at the start of `Player.update`, for every state except Aiming. It does nothing if the player already holds the ball.
3. **Request.** If the ball is within reach, the player files a pickup request.
4. **Resolution.** After all players have updated, `Game._resolve_pickups` gives the ball to exactly one requester and ends the tick's pickup logic.
5. **Held.** The winner has `held_ball` set and the ball's `held_by` points to them. The ball now follows their hand. See [ball.md](ball.md).

Because the attempt happens in one place, no state can swallow a Z press. A press on the tick you land, leave the ground, enter a wall cling, or slide still counts.

## Reach

- **In reach:** the ball is free, you hold nothing, and the distance from **your center** to the **ball's center** is at most `pickup_radius` (55 px).
- The renderer draws a green circle of that radius around the local player while the ball is in reach.

## Three ways the window is widened

### 1. Bigger radius
`pickup_radius` is 55 px. A ball passing near you is catchable from further away than the old 40 px.

### 2. Early-press buffer
A Z press when the ball is **not** in reach arms a countdown of `pickup_buffer_time` (0.1 s, 12 ticks). On each following tick the player retries. If the ball comes into reach before the countdown ends, the pickup request is filed then. A new Z press restarts the countdown.

The buffer is cleared when: the player catches the ball, enters Aiming, holds the ball, or is respawned (`reset_player`). A buffer never takes a ball that someone else is holding. If the ball becomes free again within the window (for example a teammate throws it back) a buffered player can catch it.

### 3. Late-press grace (judged on the host)
The game remembers the ball's recent positions in `Game.ball_trail`, a short queue holding the last `pickup_grace_time` (0.1 s, 12 ticks) plus the current position. Positions are recorded after the ball moves, only while it is free.

A pickup attempt succeeds if **your current center** is within `pickup_radius` of **any** position in that trail. So pressing Z up to 0.1 s after the ball left your reach still catches it.

This exists for network play. A joining player presses Z based on what their screen shows, which is slightly behind the host. The Z message then takes another trip to the host. By the time it arrives, a fast ball has moved on. The grace window absorbs that delay. The host's own player uses the same code, so grace is not a client-only advantage.

The trail is cleared whenever the ball is held, so positions from before a catch never count after it. Player positions are not recorded: only the ball's history is used.

## Who wins a contested ball

If several players request on the same tick, the one with the **smallest pickup distance** wins. Pickup distance is the shortest distance from the player's center to any ball position in the trail (including the current one). Ties go to the lowest player id. When the ball is granted:
- all players' buffers are cleared,
- the trail is cleared,
- the ball stays with the winner until they throw it.

## Aiming

From Grounded or Crouch, Z while holding the ball enters **Aiming** (if `throw_enabled`). You stand still while aiming.

| Input | Effect |
|---|---|
| Left / Right | rotate the aim at 180 degrees/s, full circle (right is clockwise) |
| Up / Down | power up or down at 900 per second, clamped 300..1400 |
| X | throw |
| Z | cancel, keep the ball |

The aim starts at 45 degrees (facing right) or 135 degrees (facing left), with power 850. The aim direction is `(cos a, -sin a)` in screen coordinates, so 0 degrees is right and 90 degrees is up.

The renderer shows an aim ring, a line whose length shows power, and a dotted arc of the predicted flight. The arc uses gravity only. It **ignores platforms**, so it shows where the ball would go in open space, not where it will bounce.

## Throwing

`Player.throw()` releases the ball from the **player's center** (not the hand) with velocity `direction * aim_power`. The player turns to face the throw direction if it is mostly horizontal. State returns to Grounded.

Details:
- The ball starts inside the thrower's reach, so a fresh Z press right after a throw can catch it again. Nothing is buffered while you hold the ball, and the trail is empty after a throw, so a throw is never re-caught without a new Z press.
- The throw speed range is 300 to 1400 px/s. At the maximum the ball covers 11.7 px per tick.
- Throws cannot happen in the air: Aiming only starts from Grounded or Crouch, and leaving the ground cancels it.

## Edge cases worth knowing

- Z while sliding catches the ball but cannot start aiming.
- Z while aiming always cancels aiming. It never picks anything up.
- A player who disconnects while holding the ball drops it where they stood.
- `throw_enabled = False` (the default) disables aiming entirely, the QB's automatic throw and the play-call aim step. `Player.throw()` also does nothing. You can still pick up a ball that is on the ground (sandbox).
