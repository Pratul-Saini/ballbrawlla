"""Find games on the local network without typing an IP address.

A host runs a `Beacon`, which sends a small UDP broadcast about once a second while it has a free seat.
The join screen runs a `Finder`, which listens for those broadcasts and keeps the list of games heard
recently. Both are non-blocking and are driven from the caller's loop, with no threads.

Broadcasts only travel within the local network, and some Wi-Fi networks block them. Typing the address
always still works. The address of a game is the sender of its packet, never a value the packet claims.
"""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass

from ballbrawlla.net.protocol import PROTOCOL_VERSION

DISCOVERY_PORT = 50556
MAGIC = "ballbrawlla-game"
BEACON_INTERVAL = 1.0
GAME_TIMEOUT = 3.5         # a game not heard from for this long is dropped from the list
MAX_TEXT = 40


@dataclass(frozen=True)
class FoundGame:
    address: str
    port: int
    name: str
    level: str


def _clean(value: object) -> str:
    return "".join(c for c in str(value) if c.isprintable())[:MAX_TEXT].strip()


def encode(name: str, level: str, port: int) -> bytes:
    return json.dumps({"magic": MAGIC, "v": PROTOCOL_VERSION, "name": name, "level": level, "port": port},
                      separators=(",", ":")).encode()


def decode(data: bytes, sender: str) -> FoundGame | None:
    """A FoundGame for a valid beacon packet, else None. Never raises on garbage."""
    try:
        msg = json.loads(data.decode())
        if not isinstance(msg, dict) or msg.get("magic") != MAGIC or msg.get("v") != PROTOCOL_VERSION:
            return None
        port = msg.get("port")
        if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
            return None
        return FoundGame(sender, port, _clean(msg.get("name", "")) or sender, _clean(msg.get("level", "")))
    except (ValueError, UnicodeDecodeError):
        return None


class Beacon:
    """Advertises a hosted game. Call tick() every frame; it sends at most once per BEACON_INTERVAL."""

    def __init__(self, name: str, level: str, port: int, discovery_port: int = DISCOVERY_PORT) -> None:
        self.packet = encode(_clean(name), _clean(level), port)
        self.discovery_port = discovery_port
        self._last = -BEACON_INTERVAL
        try:
            self.sock: socket.socket | None = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.setblocking(False)
        except OSError:
            self.sock = None

    def tick(self, open_seat: bool = True, now: float | None = None) -> bool:
        """Send a beacon if one is due and a seat is open. Returns True if a packet went out."""
        now = time.monotonic() if now is None else now
        if self.sock is None or not open_seat or now - self._last < BEACON_INTERVAL:
            return False
        self._last = now
        # The broadcast address reaches other machines; loopback lets a second copy on this machine see it.
        for target in ("255.255.255.255", "127.0.0.1"):
            try:
                self.sock.sendto(self.packet, (target, self.discovery_port))
            except OSError:
                pass            # no route, firewall, or offline: discovery is best-effort
        return True

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class Finder:
    """Listens for beacons. Call poll() every frame to read what arrived and get the current list."""

    def __init__(self, discovery_port: int = DISCOVERY_PORT) -> None:
        self._seen: dict[tuple[str, int], tuple[FoundGame, float]] = {}
        self.sock: socket.socket | None = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            s.bind(("0.0.0.0", discovery_port))
            s.setblocking(False)
            self.sock = s
        except OSError:
            self.sock = None

    @property
    def available(self) -> bool:
        return self.sock is not None

    def poll(self, now: float | None = None) -> list[FoundGame]:
        now = time.monotonic() if now is None else now
        while self.sock is not None:
            try:
                data, (sender, _) = self.sock.recvfrom(2048)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            game = decode(data, sender)
            if game is not None:
                self._seen[(game.address, game.port)] = (game, now)
        self._seen = {k: v for k, v in self._seen.items() if now - v[1] <= GAME_TIMEOUT}
        games = [g for g, _ in self._seen.values()]
        # On the host's own machine the same beacon arrives twice, from its LAN address and from loopback. Show it once.
        real = {(g.name, g.level, g.port) for g in games if not g.address.startswith("127.")}
        games = [g for g in games if not (g.address.startswith("127.") and (g.name, g.level, g.port) in real)]
        return sorted(games, key=lambda g: (g.name.lower(), g.address, g.port))

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None
