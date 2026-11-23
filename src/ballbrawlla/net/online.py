"""How a hosted game becomes reachable, and how a typed invite code becomes a connection.

Host side, `Reach`: started when a game is hosted, polled every frame. It works out the one invite code to
show and says, in words, who can join:

    relay server set        open a room on it          -> relay code, "Internet: ready"
    otherwise (or it fails)  ask the router to open the port (net/upnp.py)
        router opened it                               -> address code of the public IP, "Internet: ready"
        router can't                                   -> address code of the LAN IP, "Internet: not available
                                                          because ..." (same Wi-Fi still works)

Joiner side, `connect`: a game on this network that advertises the code wins (a direct LAN connection);
else an address code is dialled directly; else a relay code goes through the relay.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from ballbrawlla.net.client import Client
from ballbrawlla.net.discovery import FoundGame, Finder
from ballbrawlla.net.invite import (
    RelayRoom, address_code, check_code, check_relay, code_address, format_code, is_relay_code, normalize_code,
    relay_address,
)
from ballbrawlla.net.protocol import DEFAULT_PORT
from ballbrawlla.net.upnp import PortOpener

CHECKING, READY, UNAVAILABLE = "checking", "ready", "unavailable"


@dataclass
class Line:
    label: str
    text: str
    state: str            # CHECKING / READY / UNAVAILABLE: how to color it


class Reach:
    """The host's invite code and internet status. Nothing here blocks the caller: the relay and the
    router are asked in a thread. Poll `room` (hand it to Host) and `lines()` each frame."""

    def __init__(self, port: int, lan_ip: str, relay: tuple[str, int] | None = None, use_router: bool = True,
                 start: bool = True) -> None:
        self.port, self.lan_ip, self.relay = port, lan_ip, relay
        self.use_router = use_router
        self.room: RelayRoom | None = None
        self.opener: PortOpener | None = None
        self.relay_error = ""
        self.done = False                     # the relay/router question is settled
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="reach", daemon=True)
        if start:
            self._thread.start()

    # ---- background
    def _run(self) -> None:
        if self.relay is not None:
            try:
                room = RelayRoom(self.relay)
                if self._closed:
                    room.close()
                    return
                self.room = room
                self.done = True
                return
            except (ConnectionError, OSError) as e:
                self.relay_error = str(e)
        if self.use_router and self.port == DEFAULT_PORT:
            if self._closed:
                return
            self.opener = PortOpener(self.port, self.lan_ip)
            if self._closed:                     # close() ran while it was being created
                self.opener.close()
            while self.opener.state == "checking" and not self._closed:
                time.sleep(0.05)
        self.done = True

    # ---- what to show
    @property
    def code(self) -> str | None:
        """The invite code to share (bare), or None while it's still being worked out."""
        if self.room is not None:
            return self.room.code
        if not self.done:
            return None
        if self.port != DEFAULT_PORT:
            return None                      # codes assume the standard port; the status line shows the address
        if self.opener is not None and self.opener.state == "open":
            return address_code(self.opener.public_ip)
        return address_code(self.lan_ip)

    @property
    def codes(self) -> list[str]:
        """Every code that leads here, for the LAN beacon: the shown one, and the LAN address code."""
        out = [c for c in (self.code, address_code(self.lan_ip) if self.port == DEFAULT_PORT else None) if c]
        return list(dict.fromkeys(out))

    @property
    def internet(self) -> Line:
        if self.room is not None:
            if self.room.lost:
                return Line("Internet", "lost the relay server: only players on your Wi-Fi can join now", UNAVAILABLE)
            return Line("Internet", "ready (through the relay server)", READY)
        if not self.done:
            return Line("Internet", "asking your router to open the game's port...", CHECKING)
        if self.opener is not None and self.opener.state == "open":
            return Line("Internet", "ready: your router opened the game's port", READY)
        if self.opener is not None:
            return Line("Internet", f"not available. {self.opener.reason}", UNAVAILABLE)
        if self.port != DEFAULT_PORT:
            return Line("Internet", f"not set up (port {self.port} isn't the standard one)", UNAVAILABLE)
        return Line("Internet", "not available (automatic port opening is off)", UNAVAILABLE)

    def lines(self) -> list[Line]:
        if self.port == DEFAULT_PORT:
            lan = Line("Same Wi-Fi", "ready: they pick your game in Join game, or type the code", READY)
        else:
            lan = Line("Same Wi-Fi", f"ready: they join {self.lan_ip}:{self.port}", READY)
        return [lan, self.internet]

    def close(self) -> None:
        self._closed = True
        if self.room is not None:
            self.room.close()
        if self.opener is not None:
            self.opener.close()


# ---------------------------------------------------------------- joiner side

def find_on_lan(code: str, games: list[FoundGame] | None = None, listen: float = 1.3) -> FoundGame | None:
    """A game on this network advertising `code`: from `games` if given, else by listening briefly."""
    code = normalize_code(code)
    if games is None:
        finder = Finder()
        try:
            deadline = time.monotonic() + (listen if finder.available else 0)
            while True:
                games = finder.poll()
                hit = next((g for g in games if code in g.codes), None)
                if hit or time.monotonic() >= deadline:
                    return hit
                time.sleep(0.05)
        finally:
            finder.close()
    return next((g for g in games if code in g.codes), None)


def check_join_code(code: str) -> str | None:
    """Why this code can't be used to join from here, or None."""
    why = check_code(code)
    if why:
        return why
    return check_relay() if is_relay_code(code) else None


def connect(code: str, games: list[FoundGame] | None = None, timeout: float = 6.0) -> tuple[Client, str]:
    """Join the game with this invite code. Returns the client and a few words on how it connected.
    Raises ConnectionError with a message a player can act on."""
    why = check_join_code(code)
    if why:
        raise ConnectionError(why)
    shown = format_code(code)
    lan = find_on_lan(code, games)
    if lan is not None:
        try:
            return Client(lan.address, lan.port, timeout=timeout), "on your network"
        except ConnectionError:
            pass                                  # try the code's own route below
    if is_relay_code(code):
        try:
            return Client.via_code(relay_address(), code, timeout=timeout), "through the relay server"
        except ConnectionError as e:
            raise ConnectionError(f"{e} Check the code, and that the host's game is still waiting.") from e
    ip = code_address(code)
    try:
        return Client(ip, DEFAULT_PORT, timeout=timeout), "over the internet" if not _private(ip) else "on your network"
    except ConnectionError as e:
        raise ConnectionError(
            f"Couldn't reach the game with code {shown}. Check that the host's game is still waiting for a "
            "player, and that their screen says \"Internet: ready\" (or that you're both on the same Wi-Fi). "
            f"({e})") from e


def _private(ip: str) -> bool:
    import ipaddress
    try:
        return ipaddress.IPv4Address(ip).is_private
    except ValueError:
        return False
