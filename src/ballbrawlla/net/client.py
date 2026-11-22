"""Client side: connects to a host, sends Intents, receives snapshots."""

import socket
import time

from ballbrawlla.input import Intent
from ballbrawlla.net.protocol import DEFAULT_PORT, PROTOCOL_VERSION, Connection, intent_to_msg
from ballbrawlla.version import __version__


class Client:
    def __init__(self, address: str = "", port: int = DEFAULT_PORT, timeout: float = 5.0,
                 sock: socket.socket | None = None) -> None:
        """Connects (or uses `sock`, already connected to the host) and completes the handshake, blocking
        up to `timeout`. Raises ConnectionError if the host refuses or doesn't answer."""
        if sock is None:
            try:
                sock = socket.create_connection((address, port), timeout=timeout)
            except OSError as e:
                raise ConnectionError(f"could not reach {address}:{port} ({e})") from e
        self.conn = Connection(sock)
        self.conn.send({"t": "hello", "v": PROTOCOL_VERSION, "game": __version__})
        self._latest: dict | None = None

        deadline = time.monotonic() + timeout
        while True:
            for msg in self.conn.receive():
                kind = msg.get("t")
                if kind == "reject":
                    self.conn.close()
                    raise ConnectionError(f"host refused: {msg.get('reason')}")
                if kind == "welcome":
                    self.pid: int = msg["id"]
                    self.level_data: dict = msg["level"]
                    self.tuning_data: dict = msg["tuning"]
                elif kind == "snap":
                    self._latest = msg
            if hasattr(self, "pid"):
                return
            if self.conn.closed:
                raise ConnectionError("host closed the connection during handshake")
            if time.monotonic() > deadline:
                self.conn.close()
                raise ConnectionError("timed out waiting for host")
            time.sleep(0.01)

    @classmethod
    def via_code(cls, relay: tuple[str, int], code: str, timeout: float = 10.0) -> "Client":
        """Join through the relay server with an invite code (net/invite.py)."""
        from ballbrawlla.net.invite import dial
        return cls(sock=dial(relay, code, timeout), timeout=timeout)

    @property
    def closed(self) -> bool:
        return self.conn.closed

    def send_intent(self, intent: Intent) -> None:
        self.conn.send(intent_to_msg(intent))

    def latest_snapshot(self) -> dict | None:
        """Newest snapshot received since the last call (older ones are skipped)."""
        for msg in self.conn.receive():
            if msg.get("t") == "snap":
                self._latest = msg
        snap, self._latest = self._latest, None
        return snap

    def close(self) -> None:
        self.conn.close()
