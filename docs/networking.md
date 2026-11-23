# Networking (host and join)

Source: `net/protocol.py`, `net/host.py`, `net/client.py`, `net/view.py`, `net/discovery.py`, `net/online.py`,
`net/upnp.py`, `net/invite.py`, `net/relay_server.py`, and the loops in `main.py`. The Godot port mirrors it in
`godot/scripts/` (`reach.gd` is `online.Reach` + `upnp.PortOpener`).

Players do everything from the menu: **Online → Host game** shows an invite code, **Online → Join game** takes it.
The command line does the same:

```
python -m ballbrawlla --host                  # shows the invite code on the waiting screen (and prints it)
python -m ballbrawlla --join-code 2JDH-GC8A   # join with it
python -m ballbrawlla --join 192.168.x.y      # or by address; --port N on both sides to change it
python -m ballbrawlla --host --no-router      # don't ask the router to open the port
```

To test on one machine, press **N** on the host's waiting screen: a second copy of the game opens and joins
(`main.open_test_window`). Both sides must run the same code (`PROTOCOL_VERSION` is checked).

## Invite codes and reachability (`net/online.py`, `net/upnp.py`)

One code per hosted game, decided by `online.Reach` in a thread while the waiting screen shows "getting your code":

| Situation | Code | "Internet" line |
|---|---|---|
| a relay server is set and answers | relay room code, 6 characters (`KQ7-M3X`) | ready (through the relay server) |
| no relay; the router opened the port (UPnP) | address code of the **public** IP, 8 characters (`2JDH-GC8A`) | ready |
| no relay; the router can't or won't | address code of the **LAN** IP | not available, with the reason and the fix |

- **Address codes** (`invite.address_code` / `code_address`): an IPv4 address `v` packed as `v * 198 + v % 197` in
  8 base-31 characters. A mistyped character is caught (about 99.7% of single typos) instead of dialling a stranger.
  Codes assume the standard port 50555; on another port there is no code and the LAN address is shown instead.
- **LAN first:** the host's beacon (`net/discovery.py`) lists its codes. A joiner who types a code connects straight
  to a game on the same network that advertises it (the menu checks the games it already heard; `--join-code`
  listens for 1.3 s). This also sidesteps routers that can't loop a public address back inside the network.
- **Opening the port** (`upnp.PortOpener`, standard library only): SSDP M-SEARCH for an Internet Gateway Device, read
  its description for the WANIPConnection/WANPPPConnection control URL, then SOAP `GetExternalIPAddress` and
  `AddPortMapping` (TCP 50555 -> this computer, 1 h lease renewed every 25 min; permanent if the router only
  allows that), and `DeletePortMapping` when the game ends. A router whose own public address is private or in
  100.64.0.0/10 sits behind another NAT (double NAT, carrier NAT): reported as not reachable. Godot uses its
  built-in `UPNP` class the same way.
- Every failure is a sentence a player can act on: router didn't answer (UPnP off), port taken by another computer
  (UPnP error 718), behind another router or carrier NAT, refused (error N). Each ends with "turn on UPnP, or
  forward TCP port 50555 to <LAN IP>. Players on the same Wi-Fi can join either way."

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

- **`RelayRoom`** (host side) is opened by `online.Reach` and handed to the `Host` (`host.room`), which polls it.
  Sockets it returns go into the same pending list as LAN connections, so hello/welcome, "game is full" and
  version checks are shared. The LAN listener stays open too. If the control connection drops, the running match continues but nobody new can join
  (the status line says so).
- **`dial()` / `Client.via_code()`** (joiner side, from `online.connect`) waits for `ok`, then runs the normal handshake.
- **Codes**: 6 characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, displayed `KQ7-M3X`. `normalize_code`
  ignores case, spaces and dashes. The `key` from `room` stops anyone else from claiming a joiner.
- **Relay address**: `--relay HOST[:PORT]` / `BALLBRAWLLA_RELAY` > `relay` in `settings.json` (`settings.py`) >
  `DEFAULT_RELAY`. The default port is 50600. With none set, hosts use address codes, and a typed 6-character
  code is explained ("that is a relay server code ... ask for the 8-character one"). If the relay is set but
  doesn't answer, the host falls back to the router.
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
