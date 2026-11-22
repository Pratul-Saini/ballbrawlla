# Networking (host and join)

Source: `net/protocol.py`, `net/host.py`, `net/client.py`, `net/view.py`, and the loops in `main.py`.

```
python -m ballbrawlla --host               # prints "Hosting on 192.168.x.y:50555"
python -m ballbrawlla --join 192.168.x.y   # --port N on both sides to change it
```

To test on one machine, host in one terminal and join `127.0.0.1` in another. Both sides must run the same code (`PROTOCOL_VERSION` is checked).

## Who does what

- **The host runs the only `Session`** (rules + physics). Human 0 is Blue (the host), human 1 is Red (the joiner). The match waits until both are connected and restarts if one leaves.
- **The client never simulates.** It sends Intents and draws the latest **view** the host sent.
- Level and tuning come from the host in the welcome message.

## Messages (JSON, one per line, TCP with Nagle off, non-blocking, no threads)

```
client -> host   {"t": "hello", "v": PROTOCOL_VERSION}
host   -> client {"t": "welcome", "id": 1, "level": {...}, "tuning": {...}}
                 {"t": "reject", "reason": "version mismatch" | "game is full"}
client -> host   {"t": "in", "mx", "v", "j", "z", "x",          # held / press edges
                  "m": [x, y] | null, "mh", "mp", "b",          # mouse (world coords), held, pressed, HUD button
                  "jh", "as": [x, y] | null}                    # controller: jump held, right-stick aim
host   -> client {"t": "snap", ...}                             # that client's view
```

- `RemoteInput` (host) keeps the latest held values and **latches** press edges until a tick consumes them.
- A peer whose outgoing buffer passes 1 MiB is dropped.

## Views and hidden information (`net/view.py`)

`make_view(session, pid, local=False)` builds what one human may see. The host draws view 0 itself and sends each client only its own view, so hidden data never leaves the host:
- the defense never receives the offense's throw aim;
- the offense never receives the Defender's position during the play call.

`local=True` (one shared screen, `--local`) includes everything. The renderer draws any view the same way.

## Latency

No client-side prediction or interpolation: the joiner sees the world one round trip behind. Catches are judged on the host; the catch grace window (see [catching-and-throwing.md](catching-and-throwing.md)) makes this playable on a LAN. Internet play needs a VPN (e.g. Tailscale) or port forwarding.
