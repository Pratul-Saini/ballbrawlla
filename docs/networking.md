# Networking (host and join)

Source: `net/protocol.py`, `net/host.py`, `net/client.py`, `net/snapshot.py`, and the loops in `main.py`.

Two players play over a local network. One machine **hosts**, the other **joins**. There is no matchmaking, no invite system and no internet relay. The joiner needs the host's IP address.

## Running it

```
python -m ballbrawlla --host               # prints "Hosting on 192.168.x.y:50555"
python -m ballbrawlla --join 192.168.x.y
```

`--port N` on both sides changes the port (default 50555). To test on one machine, host in one terminal and join `127.0.0.1` in another. Both machines must run the same version of the code.

## Who does what

- **The host is the only simulation.** It runs `Game.step` with the host's own keyboard Intent for player 1 and the latest Intent received from the client for player 2. Pickup and catch decisions are made here.
- **The client does not simulate.** It sends its keyboard Intents to the host and draws the latest snapshot it received. Its local `Game` object exists only to hold the state to draw. It is never stepped.
- The level and tuning come from the host. The client's own `levels/` and `config.py` do not matter, with the exception that its code must understand the same fields.
- The host is P1 (blue). The joiner is P2 (red). The game holds 2 players (`max_players`).

## Connection

TCP with Nagle disabled (`TCP_NODELAY`), non-blocking sockets, no threads. Messages are one JSON object per line.

```
client -> host   {"t": "hello", "v": 1}
host   -> client {"t": "welcome", "id": 1, "level": {...}, "tuning": {...}}
                 {"t": "reject", "reason": "version mismatch" | "game is full"}
client -> host   {"t": "in", "mx": -1|0|1, "v": -1|0|1, "j": 0|1, "z": 0|1, "x": 0|1}
host   -> client {"t": "snap", ...}
```

- `PROTOCOL_VERSION` is 1. A hello with a different version is rejected.
- The welcome message carries the level (`level_to_dict`, including each thin platform's `type`) and the whole `Tuning` as a dict. The client builds its `Level` and `Tuning` from it.
- If a peer stops reading and its outgoing buffer passes 1 MiB, the connection is dropped.

## Input path

Keys become an `Intent` (see [input-and-rendering.md](input-and-rendering.md)). The client sends one `in` message per 120 Hz tick:
- `mx` is move left/right, `v` is vertical (+1 up, -1 down) and these are **held** values,
- `j`, `z`, `x` are **press edges** for that tick.

On the host, `RemoteInput` keeps the latest held values and **latches** any press edge until the next simulation tick consumes it. Two messages landing in one tick cannot lose a Z press.

## Snapshots

After each tick that stepped, the host sends one snapshot to every client:

```
{"t": "snap", "tick": N,
 "players": [{"id", "on", "x", "y", "h", "vx", "vy", "s" (state name),
              "f" (facing), "a" (aim angle), "p" (aim power), "j" (jumps left),
              "c": [on_ground, on_ceiling, wall_left, wall_right]}],
 "ball": {"x", "y", "vx", "vy", "held" (pid or null), "rest"}}
```

Numbers are rounded to 2 decimals. The client keeps only the newest snapshot it received since its last frame and applies it to its local `Game`: positions, velocities, state names (as stand-in states used only for display), facing, aim, contacts, and who holds the ball.

Not sent: the pickup buffer, the ball trail and pickup requests. Those are host-only simulation state.

## Joining and leaving

- When the host starts, the other slots are marked **not connected**: not simulated, drawn as dim outlines.
- When a client joins, `Game.reset_player` respawns that slot as connected. When one leaves, the slot is respawned as not connected, and a ball they were holding is dropped.
- The host process stays authoritative whether or not anyone is connected, so it can be played alone with `--host`.
- `R` (reset) works only on the host.

## Latency

- On loopback the code path from a Z press to the client seeing the catch is about one tick, 8 to 10 ms. Real networks add a round trip.
- The host judges every catch with the ball position at the time the client's message arrives, one round trip after the press. The catch grace (0.1 s) and the bigger radius are what make this playable. See [catching-and-throwing.md](catching-and-throwing.md).
- There is **no client-side prediction or interpolation.** The joiner sees the world one network trip behind, and its own movement is delayed by a round trip. Snapshots arriving unevenly make motion look slightly uneven.
- TCP keeps press edges reliable, but one lost packet can stall everything behind it for a moment. On Wi-Fi this shows as brief freezes.

## Compatibility

An older client talking to a newer host can fail on joining if the host sends tuning fields the client's `Tuning` does not know. Both sides must have the same code. A newer client with an older host works but would use default values for fields the host did not send.

## Over the internet

Not built in. Options: a VPN such as Tailscale and join with the host's VPN address, or forward TCP port 50555 on the host's router. The firewall on the host must allow incoming connections to Python.
