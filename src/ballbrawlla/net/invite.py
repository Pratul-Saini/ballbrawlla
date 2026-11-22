"""Invite codes and the game's side of the relay server (see net/relay_server.py).

A host opens a room on the relay and gets a short code such as KQ7-M3X. A friend on any network types the
code in, and the relay joins their connection to a fresh connection from the host. From then on the relay
only passes bytes along, so the normal game protocol (net/protocol.py) runs over it unchanged.

    host control  -> {"t":"open","v":1}
                  <- {"t":"room","code":"KQ7M3X","key":hex}  |  {"t":"error","reason":str}
                  <- {"t":"incoming","n":7}       a joiner is waiting for slot n
                  -> {"t":"ping"}                 every PING_INTERVAL, so the relay and NATs keep the room
    host data     -> {"t":"accept","code":..,"key":..,"n":7}   then raw bytes
    joiner        -> {"t":"join","v":1,"code":"KQ7M3X"}
                  <- {"t":"ok"} then raw bytes  |  {"t":"error","reason":str}
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import time

from ballbrawlla.net.protocol import Connection

RELAY_VERSION = 1
RELAY_PORT = 50600
# The public relay everyone uses unless --relay or BALLBRAWLLA_RELAY says otherwise.
# Fill this in once the relay is deployed, e.g. "relay.example.com" or "203.0.113.5:50600".
DEFAULT_RELAY = ""
RELAY_ENV = "BALLBRAWLLA_RELAY"

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L: easy to read out loud
CODE_LEN = 6
PING_INTERVAL = 10.0
MAX_LINE = 1024


# ---------------------------------------------------------------- codes

def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))


def normalize_code(text: str) -> str:
    """What a player typed -> the bare code: uppercase, without spaces or dashes."""
    return "".join(c for c in (text or "").upper() if c not in " -\t")


def format_code(code: str) -> str:
    code = normalize_code(code)
    return f"{code[:3]}-{code[3:]}" if len(code) == CODE_LEN else code


def check_code(text: str) -> str | None:
    """Why this isn't a valid invite code, or None."""
    code = normalize_code(text)
    if not code:
        return "Type the invite code the host gave you (like KQ7-M3X)."
    bad = sorted({c for c in code if c not in ALPHABET})
    if bad:
        hint = " Codes never use 0, O, 1, I or L." if set(bad) & set("0O1IL") else ""
        return f"An invite code can't contain {', '.join(bad)}.{hint}"
    if len(code) != CODE_LEN:
        return f"An invite code has {CODE_LEN} characters (like KQ7-M3X); this one has {len(code)}."
    return None


# ---------------------------------------------------------------- relay address

def relay_address(override: str | None = None) -> tuple[str, int] | None:
    """Where the relay runs: --relay, else the BALLBRAWLLA_RELAY environment variable, else DEFAULT_RELAY.
    None when none is set."""
    text = (override or os.environ.get(RELAY_ENV, "") or DEFAULT_RELAY).strip()
    if not text:
        return None
    host, sep, port = text.rpartition(":")
    if sep and port.isdigit() and host and not host.endswith(":"):
        return host.strip("[]"), int(port)
    return text.strip("[]"), RELAY_PORT


def check_relay(override: str | None = None) -> str | None:
    if relay_address(override) is None:
        return (f"No relay server is set, so invite codes can't work yet. Start one (python -m "
                f"ballbrawlla.net.relay_server) and pass --relay HOST, set {RELAY_ENV}, or fill in "
                "DEFAULT_RELAY in net/invite.py.")
    return None


def _describe(relay: tuple[str, int]) -> str:
    return f"{relay[0]}:{relay[1]}"


def _line(msg: dict) -> bytes:
    return json.dumps(msg, separators=(",", ":")).encode() + b"\n"


def _read_line(sock: socket.socket, deadline: float) -> dict:
    """Blocking read of one JSON line, byte by byte so nothing after it is consumed: the game protocol's
    first bytes may follow straight away on the same socket."""
    buf = b""
    while not buf.endswith(b"\n"):
        sock.settimeout(max(0.01, deadline - time.monotonic()))
        try:
            ch = sock.recv(1)
        except socket.timeout:
            raise ConnectionError("the relay server didn't answer in time") from None
        except OSError as e:
            raise ConnectionError(f"lost the connection to the relay server ({e})") from e
        if not ch:
            raise ConnectionError("the relay server closed the connection")
        buf += ch
        if len(buf) > MAX_LINE:
            raise ConnectionError("the relay server sent something unexpected")
    try:
        msg = json.loads(buf)
    except json.JSONDecodeError:
        raise ConnectionError("the relay server sent something unexpected") from None
    if not isinstance(msg, dict):
        raise ConnectionError("the relay server sent something unexpected")
    return msg


def _connect(relay: tuple[str, int], timeout: float) -> socket.socket:
    try:
        sock = socket.create_connection(relay, timeout=timeout)
    except OSError as e:
        raise ConnectionError(f"Could not reach the relay server at {_describe(relay)} ({e}).") from e
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


# ---------------------------------------------------------------- host side

class RelayRoom:
    """A room on the relay, held open by a control connection. Call poll() every frame: it returns
    sockets to new joiners, already joined through the relay, ready for the game handshake."""

    def __init__(self, relay: tuple[str, int], timeout: float = 5.0) -> None:
        self.relay = relay
        sock = _connect(relay, timeout)
        try:
            sock.sendall(_line({"t": "open", "v": RELAY_VERSION}))
            msg = _read_line(sock, time.monotonic() + timeout)
        except (ConnectionError, OSError) as e:
            sock.close()
            raise ConnectionError(f"Could not open a game on the relay server: {e}") from e
        if msg.get("t") != "room":
            sock.close()
            raise ConnectionError(f"The relay server refused: {msg.get('reason', 'unknown reason')}.")
        self.code: str = str(msg["code"])
        self._key: str = str(msg["key"])
        self.ctrl = Connection(sock)
        self._last_ping = time.monotonic()

    @property
    def display_code(self) -> str:
        return format_code(self.code)

    @property
    def lost(self) -> bool:
        """The relay dropped the room: the current game goes on, but nobody new can join."""
        return self.ctrl.closed

    def poll(self, now: float | None = None) -> list[socket.socket]:
        now = time.monotonic() if now is None else now
        if not self.ctrl.closed and now - self._last_ping >= PING_INTERVAL:
            self._last_ping = now
            self.ctrl.send({"t": "ping"})
        socks = []
        for msg in self.ctrl.receive():
            if msg.get("t") == "incoming" and isinstance(msg.get("n"), int):
                sock = self._accept(msg["n"])
                if sock is not None:
                    socks.append(sock)
        return socks

    def _accept(self, n: int) -> socket.socket | None:
        """Open the data connection for joiner n. Blocking, but short, and joins only happen while the
        match waits for a player."""
        try:
            sock = _connect(self.relay, 3.0)
            sock.sendall(_line({"t": "accept", "code": self.code, "key": self._key, "n": n}))
            return sock
        except (ConnectionError, OSError):
            return None

    def close(self) -> None:
        self.ctrl.close()


# ---------------------------------------------------------------- joiner side

def dial(relay: tuple[str, int], code: str, timeout: float = 10.0) -> socket.socket:
    """Join the room with this code. Returns a socket that now leads to the host (blocking until then)."""
    code = normalize_code(code)
    sock = _connect(relay, timeout)
    try:
        sock.sendall(_line({"t": "join", "v": RELAY_VERSION, "code": code}))
        msg = _read_line(sock, time.monotonic() + timeout)
    except (ConnectionError, OSError) as e:
        sock.close()
        raise ConnectionError(f"Could not join {format_code(code)}: {e}.") from e
    if msg.get("t") != "ok":
        sock.close()
        raise ConnectionError(f"Could not join {format_code(code)}: {msg.get('reason', 'unknown reason')}.")
    return sock
