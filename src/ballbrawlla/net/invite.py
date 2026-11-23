"""Invite codes, and the game's side of the relay server (see net/relay_server.py).

Every hosted game shows one invite code. There are two kinds:

* An address code (8 characters, KQ7M-3XPA) is the host's IP address plus a check value, so a typo is
  caught instead of dialling a stranger. It is the host's public address when its router opened the game's
  port (net/upnp.py), else its address on the local network. The joiner connects straight to it.
* A relay code (6 characters, KQ7-M3X) names a room on a relay server, used when one is set. The relay joins
  the joiner's connection to a fresh connection from the host, then only passes bytes along, so the normal
  game protocol (net/protocol.py) runs over it unchanged.

Hosts also broadcast their codes on the local network (net/discovery.py), so a joiner on the same Wi-Fi
always connects directly, whatever kind of code they typed.

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
# The public relay everyone uses unless --relay, BALLBRAWLLA_RELAY or the menu's RELAY SERVER says otherwise.
# Fill this in once the relay is deployed, e.g. "relay.example.com" or "203.0.113.5:50600".
DEFAULT_RELAY = ""
RELAY_ENV = "BALLBRAWLLA_RELAY"

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L: easy to read out loud
CODE_LEN = 6         # relay room codes
DIRECT_LEN = 8       # address codes
_CHECK = 198         # 2**32 * 198 < 31**8, so an IPv4 address and a check value fit in 8 characters
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
    if len(code) == CODE_LEN:
        return f"{code[:3]}-{code[3:]}"
    if len(code) == DIRECT_LEN:
        return f"{code[:4]}-{code[4:]}"
    return code


def address_code(ip: str) -> str:
    """The address code for an IPv4 address: KQ7M3XPA (display it with format_code)."""
    v = int.from_bytes(socket.inet_aton(ip), "big")
    n = v * _CHECK + v % 197
    out = ""
    for _ in range(DIRECT_LEN):
        n, d = divmod(n, len(ALPHABET))
        out = ALPHABET[d] + out
    return out


def code_address(code: str) -> str | None:
    """The IPv4 address in an address code, or None if it isn't one (wrong length, or a typo)."""
    code = normalize_code(code)
    if len(code) != DIRECT_LEN or any(c not in ALPHABET for c in code):
        return None
    n = 0
    for c in code:
        n = n * len(ALPHABET) + ALPHABET.index(c)
    v, check = divmod(n, _CHECK)
    if v >= 1 << 32 or check != v % 197:
        return None
    return socket.inet_ntoa(v.to_bytes(4, "big"))


def is_relay_code(code: str) -> bool:
    return len(normalize_code(code)) == CODE_LEN


def check_code(text: str) -> str | None:
    """Why this isn't a valid invite code, or None."""
    code = normalize_code(text)
    if not code:
        return "Type the invite code from the host's screen (like KQ7M-3XPA)."
    bad = sorted({c for c in code if c not in ALPHABET})
    if bad:
        hint = " Codes never use 0, O, 1, I or L." if set(bad) & set("0O1IL") else ""
        return f"An invite code can't contain {', '.join(bad)}.{hint}"
    if len(code) not in (CODE_LEN, DIRECT_LEN):
        return f"An invite code has {DIRECT_LEN} characters (like KQ7M-3XPA); this one has {len(code)}."
    if len(code) == DIRECT_LEN and code_address(code) is None:
        return "That code has a typo. Check it against the host's screen, character by character."
    return None


# ---------------------------------------------------------------- relay address

def relay_text() -> str:
    """The relay setting in effect, as typed: --relay / BALLBRAWLLA_RELAY, else `relay` in settings.json,
    else DEFAULT_RELAY. "" when none is set (then hosts use address codes)."""
    from ballbrawlla import settings
    return (os.environ.get(RELAY_ENV, "") or str(settings.get("relay") or "") or DEFAULT_RELAY).strip()


def parse_relay(text: str) -> tuple[str, int] | None:
    """"host", "host:port" or "[v6]:port" -> (host, port); None for "". Raises ValueError if it can't be one."""
    text = (text or "").strip()
    if not text:
        return None
    if any(c.isspace() or c in "/\\@" for c in text):
        raise ValueError(f"'{text}' isn't a server address.")
    host, sep, port = text.rpartition(":")
    if sep and host and not host.endswith(":") and (host.startswith("[") or ":" not in host):
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError(f"'{port}' isn't a port number (1-65535).")
        addr = host.strip("[]"), int(port)
    else:
        addr = text.strip("[]"), RELAY_PORT
    if not addr[0]:
        raise ValueError(f"'{text}' isn't a server address.")
    return addr


def check_relay_text(text: str) -> str | None:
    """Why this can't be saved as the relay address, or None ("" is fine: it clears the setting)."""
    try:
        parse_relay(text)
    except ValueError as e:
        return f"{e} Type a name or IP address, optionally with :port (like 203.0.113.5:{RELAY_PORT})."
    return None


def relay_address(override: str | None = None) -> tuple[str, int] | None:
    """Where the relay runs (see relay_text; `override` wins over everything). None when none is set or
    the setting can't be read as an address."""
    try:
        return parse_relay(override or relay_text())
    except ValueError:
        return None


def set_relay(text: str) -> None:
    """Save a relay address in settings.json and use it from now on, in this run too (even over --relay).
    Raises OSError if the settings file can't be written."""
    from ballbrawlla import settings
    text = (text or "").strip()
    settings.save(relay=text)
    if RELAY_ENV in os.environ:
        if text:
            os.environ[RELAY_ENV] = text
        else:
            del os.environ[RELAY_ENV]


def check_relay(override: str | None = None) -> str | None:
    if relay_address(override) is None:
        return ("That is a relay server code (6 characters), and this copy of the game has no relay server "
                "set. Ask the host for the code on their screen now: it has 8 characters.")
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
