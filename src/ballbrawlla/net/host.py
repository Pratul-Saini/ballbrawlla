"""Host side: accepts clients, turns their input messages into Intents, and
sends each client its view. The host's own player is slot 0; clients get 1..N-1.

Everything is non-blocking and driven from the game loop (no threads)."""

import socket

from ballbrawlla.input import Intent
from ballbrawlla.net.protocol import DEFAULT_PORT, PROTOCOL_VERSION, Connection


class RemoteInput:
    """Latest held keys from a client plus press edges accumulated since the
    last tick, so a press is never lost if two messages land in one tick."""

    def __init__(self) -> None:
        self.move_x = 0
        self.vertical = 0
        self.jump = self.z = self.x = False
        self.mouse: tuple[float, float] | None = None
        self.mouse_held = False
        self.mouse_pressed = self.button = False

    def feed(self, msg: dict) -> None:
        self.move_x = max(-1, min(1, int(msg.get("mx", 0))))
        self.vertical = max(-1, min(1, int(msg.get("v", 0))))
        self.jump |= bool(msg.get("j"))
        self.z |= bool(msg.get("z"))
        self.x |= bool(msg.get("x"))
        m = msg.get("m")
        self.mouse = (float(m[0]), float(m[1])) if isinstance(m, list) and len(m) == 2 else None
        self.mouse_held = bool(msg.get("mh"))
        self.mouse_pressed |= bool(msg.get("mp"))
        self.button |= bool(msg.get("b"))

    def consume(self) -> Intent:
        intent = Intent(
            self.move_x, self.vertical, self.jump, self.z, self.x,
            mouse=self.mouse,
            mouse_held=self.mouse_held,
            mouse_pressed=self.mouse_pressed,
            button_pressed=self.button,
        )
        self.jump = self.z = self.x = False
        self.mouse_pressed = self.button = False
        return intent


class Host:
    def __init__(self, welcome: dict, max_players: int, port: int = DEFAULT_PORT,
                 bind: str = "0.0.0.0") -> None:
        """`welcome` holds the level and tuning sent to every joining client."""
        self.welcome = welcome
        self.max_players = max_players
        self.listener = socket.create_server((bind, port))
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self._pending: list[Connection] = []
        self.clients: dict[int, Connection] = {}
        self._inputs: dict[int, RemoteInput] = {}

    def _free_slot(self) -> int | None:
        for pid in range(1, self.max_players):
            if pid not in self.clients:
                return pid
        return None

    def poll(self) -> tuple[list[int], list[int]]:
        """Accept/handshake/read. Returns (joined pids, left pids) since last poll."""
        joined: list[int] = []
        left: list[int] = []

        while True:
            try:
                sock, _ = self.listener.accept()
            except (BlockingIOError, OSError):
                break
            self._pending.append(Connection(sock))

        for conn in list(self._pending):
            for msg in conn.receive():
                if msg.get("t") != "hello":
                    continue
                self._pending.remove(conn)
                pid = self._free_slot()
                if msg.get("v") != PROTOCOL_VERSION:
                    conn.send({"t": "reject", "reason": "version mismatch"})
                    conn.close()
                elif pid is None:
                    conn.send({"t": "reject", "reason": "game is full"})
                    conn.close()
                else:
                    conn.send({"t": "welcome", "id": pid, **self.welcome})
                    self.clients[pid] = conn
                    self._inputs[pid] = RemoteInput()
                    joined.append(pid)
                break
            if conn.closed and conn in self._pending:
                self._pending.remove(conn)

        for pid, conn in list(self.clients.items()):
            for msg in conn.receive():
                if msg.get("t") == "in":
                    self._inputs[pid].feed(msg)
            if conn.closed:
                del self.clients[pid]
                del self._inputs[pid]
                left.append(pid)

        return joined, left

    def intent_for(self, pid: int) -> Intent:
        remote = self._inputs.get(pid)
        return remote.consume() if remote else Intent()

    def send_to(self, pid: int, msg: dict) -> None:
        conn = self.clients.get(pid)
        if conn is not None:
            conn.send(msg)

    def broadcast(self, msg: dict) -> None:
        for conn in self.clients.values():
            conn.send(msg)

    def close(self) -> None:
        for conn in [*self._pending, *self.clients.values()]:
            conn.close()
        self.listener.close()
