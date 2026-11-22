# Networking (host and join)

Source: `net/protocol.py`, `net/host.py`, `net/client.py`, `net/view.py`, `net/invite.py`, `net/relay_server.py`,
and the loops in `main.py`.

```
python -m ballbrawlla --host               # prints "Hosting on 192.168.x.y:50555"
python -m ballbrawlla --join 192.168.x.y   # --port N on both sides to change it
python -m ballbrawlla --host --online      # also opens the game on the relay: prints an invite code
python -m ballbrawlla --join-code KQ7-M3X  # join through the relay, from any network
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

No client-side prediction or interpolation: the joiner sees the world one round trip behind. Catches are judged on the host; the catch grace window (see [catching-and-throwing.md](catching-and-throwing.md)) makes this playable on a LAN. Over the internet the joiner is one internet round trip behind.

## Internet play: invite codes and the relay (`net/invite.py`, `net/relay_server.py`)

Home routers block incoming connections, so for players on different networks **both** sides connect out
to a relay server. The relay is a byte pipe: after a short relay handshake it joins the joiner's socket to
a socket the host opened, and the game protocol above runs over it **unchanged** (the host still runs the
only `Session`, and hidden information still never leaves the host except in the joiner's own view).

```
host control conn -> {"t":"open","v":1}
                  <- {"t":"room","code":"KQ7M3X","key":hex}  | {"t":"error","reason":..}
                  <- {"t":"incoming","n":7}        a joiner is waiting
                  -> {"t":"ping"}                  every 10 s; 45 s of silence closes the room
host data conn    -> {"t":"accept","code":..,"key":..,"n":7}   then raw bytes (one new connection per joiner)
joiner            -> {"t":"join","v":1,"code":"KQ7M3X"}
                  <- {"t":"ok"} then raw bytes  | {"t":"error","reason":..}
```

- **`RelayRoom`** (host side) is polled by `Host.poll()`. Sockets it returns go into the same pending list
  as LAN connections, so hello/welcome, "game is full" and version checks are shared. The LAN listener stays
  open too. If the control connection drops, the running match continues but nobody new can join
  (the status line says so).
- **`dial()` / `Client.via_code()`** (joiner side) waits for `ok`, then runs the normal handshake.
- **Codes**: 6 characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, displayed `KQ7-M3X`. `normalize_code`
  ignores case, spaces and dashes. The `key` from `room` stops anyone else from claiming a joiner.
- **Relay address**: `--relay HOST[:PORT]` > `BALLBRAWLLA_RELAY` > `DEFAULT_RELAY`. The default port is 50600.
  The menu greys out the online options when none is set.
- **Limits** (constants in `relay_server.py`): 500 rooms, 4 rooms per IP, 20 wrong codes per IP per minute,
  10 s to send the first line, 10 s for the host to answer a joiner, 1 KiB handshake lines.
- **Not encrypted.** The relay operator could read game messages. The relay only ever connects a joiner
  to the host of the room they named, so it can't be used as an open proxy.
- Tests use `BackgroundRelay` (the relay on a thread, on loopback): `tests/test_relay.py`.

### Deploying the relay

It needs Python 3.11+ and nothing else. On a Linux VPS, for example:

```
git clone <repo> /opt/ballbrawlla
# /etc/systemd/system/ballbrawlla-relay.service
[Service]
ExecStart=/usr/bin/python3 -m ballbrawlla.net.relay_server --port 50600
Environment=PYTHONPATH=/opt/ballbrawlla/src
Restart=always
DynamicUser=yes
[Install]
WantedBy=multi-user.target
```

Open TCP 50600 in the firewall (`ufw allow 50600/tcp`), then set `DEFAULT_RELAY` in `net/invite.py` to the
server's name or IP.
