"""Wire format: newline-delimited JSON over TCP (Nagle disabled).

TCP keeps key-press edges (Z, X, jump) reliable without a resend layer, and on
a LAN its latency is a few ms. JSON keeps messages easy to inspect.

Messages
  (Over the internet the same messages pass through the relay server; see net/invite.py.)
  client -> host  {"t": "hello", "v": PROTOCOL_VERSION}
                  {"t": "in", "mx": -1|0|1, "v": -1|0|1, "j": 0|1, "z": 0|1, "x": 0|1,
                   "m": [x, y] | null (world coords), "mh": 0|1, "mp": 0|1, "b": 0|1,
                   "jh": 0|1 (jump held), "as": [x, y] | null (right stick aim, y up)}
  host -> client  {"t": "welcome", "id": pid, "level": {...}, "tuning": {...}}
                  {"t": "reject", "reason": str}
                  {"t": "snap", ...}   this client's view, see net/view.py
"""

import json
import socket

from ballbrawlla.input import Intent

PROTOCOL_VERSION = 4
DEFAULT_PORT = 50555
MAX_OUTBOX = 1 << 20  # drop a peer that stops reading rather than buffer forever


class Connection:
    """Non-blocking, line-framed JSON message socket. Call receive()/send()
    from the game loop; neither ever blocks."""

    def __init__(self, sock: socket.socket) -> None:
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = sock
        self._in = b""
        self._out = b""
        self.closed = False

    def send(self, msg: dict) -> None:
        if self.closed:
            return
        self._out += json.dumps(msg, separators=(",", ":")).encode() + b"\n"
        if len(self._out) > MAX_OUTBOX:
            self.close()
            return
        self.flush()

    def flush(self) -> None:
        while self._out and not self.closed:
            try:
                n = self.sock.send(self._out)
            except BlockingIOError:
                return
            except OSError:
                self.close()
                return
            self._out = self._out[n:]

    def receive(self) -> list[dict]:
        while not self.closed:
            try:
                data = self.sock.recv(65536)
            except BlockingIOError:
                break
            except OSError:
                self.close()
                break
            if not data:
                self.close()
                break
            self._in += data
        msgs = []
        while b"\n" in self._in:
            line, self._in = self._in.split(b"\n", 1)
            if line.strip():
                try:
                    msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return msgs

    def close(self) -> None:
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass


def intent_to_msg(intent: Intent) -> dict:
    return {
        "t": "in",
        "mx": intent.move_x,
        "v": intent.vertical,
        "j": int(intent.jump_pressed),
        "z": int(intent.z_pressed),
        "x": int(intent.x_pressed),
        "m": None if intent.mouse is None else [round(intent.mouse[0], 1), round(intent.mouse[1], 1)],
        "mh": int(intent.mouse_held),
        "mp": int(intent.mouse_pressed),
        "b": int(intent.button_pressed),
        "jh": int(intent.jump_held),
        "as": None if intent.aim_stick is None else [round(intent.aim_stick[0], 3), round(intent.aim_stick[1], 3)],
    }


def lan_ip() -> str:
    """Best guess at this machine's LAN address (connecting a UDP socket sends nothing)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
