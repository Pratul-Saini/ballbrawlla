"""Relay server for internet play: lets two players on different networks meet through an invite code.

    python -m ballbrawlla.net.relay_server [--bind 0.0.0.0] [--port 50600]

Run it on any machine both players can reach (a small VPS, for example) and open that TCP port.
It needs only Python 3.11+, with no dependencies and no game files.

How it works (the messages are in net/invite.py):
- A host connects and asks for a room. The relay picks an unused code and keeps that control connection.
- A joiner connects with the code. The relay tells the host, the host opens a new connection for that
  joiner, and from then on the relay copies bytes between the two without reading them.
- The relay only ever links a joiner to the host of the room they named, so it can't be used to reach
  anything else. Traffic is not encrypted: whoever runs the relay could read the game messages.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from ballbrawlla.net.invite import MAX_LINE, RELAY_PORT, RELAY_VERSION, format_code, new_code, normalize_code

log = logging.getLogger("ballbrawlla.relay")

MAX_ROOMS = 500
ROOMS_PER_IP = 4
FAILED_JOINS_PER_MINUTE = 20
HANDSHAKE_TIMEOUT = 10.0     # to send the first line
HOST_IDLE_TIMEOUT = 45.0     # the host pings every 10 s; silence this long means it's gone
JOIN_TIMEOUT = 10.0          # the host must answer a joiner this fast
CHUNK = 65536


@dataclass
class Room:
    code: str
    key: str
    ip: str
    ctrl: asyncio.StreamWriter
    pending: dict[int, asyncio.Future] = field(default_factory=dict)
    next_n: int = 1


def _line(msg: dict) -> bytes:
    return json.dumps(msg, separators=(",", ":")).encode() + b"\n"


async def _send(writer: asyncio.StreamWriter, msg: dict) -> None:
    writer.write(_line(msg))
    await writer.drain()


async def _close(writer: asyncio.StreamWriter) -> None:
    writer.close()
    try:
        await writer.wait_closed()
    except (OSError, asyncio.CancelledError):
        pass


async def _read_msg(reader: asyncio.StreamReader, timeout: float) -> dict | None:
    """One JSON line, or None on timeout, EOF, an oversized line or garbage."""
    try:
        line = await asyncio.wait_for(reader.readline(), timeout)
    except (asyncio.TimeoutError, ValueError, OSError):
        return None
    if not line.endswith(b"\n") or len(line) > MAX_LINE:
        return None
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return None
    return msg if isinstance(msg, dict) else None


class Relay:
    def __init__(self, max_rooms: int = MAX_ROOMS, rooms_per_ip: int = ROOMS_PER_IP,
                 failed_joins_per_minute: int = FAILED_JOINS_PER_MINUTE,
                 host_idle_timeout: float = HOST_IDLE_TIMEOUT, join_timeout: float = JOIN_TIMEOUT) -> None:
        self.max_rooms = max_rooms
        self.rooms_per_ip = rooms_per_ip
        self.failed_joins_per_minute = failed_joins_per_minute
        self.host_idle_timeout = host_idle_timeout
        self.join_timeout = join_timeout
        self.rooms: dict[str, Room] = {}
        self._failures: dict[str, deque[float]] = {}

    # ---- entry
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        ip = (writer.get_extra_info("peername") or ("?",))[0]
        try:
            msg = await _read_msg(reader, HANDSHAKE_TIMEOUT)
            kind = msg.get("t") if msg else None
            if kind == "open":
                await self._open(msg, ip, reader, writer)
            elif kind == "join":
                await self._join(msg, ip, reader, writer)
            elif kind == "accept":
                await self._accept(msg, reader, writer)
        except (OSError, asyncio.IncompleteReadError):
            pass
        finally:
            await _close(writer)

    # ---- host control connection
    async def _open(self, msg: dict, ip: str, reader, writer) -> None:
        if msg.get("v") != RELAY_VERSION:
            await _send(writer, {"t": "error", "reason": "the relay server runs a different version of the game"})
            return
        if len(self.rooms) >= self.max_rooms:
            await _send(writer, {"t": "error", "reason": "the relay server is full, try again later"})
            return
        if sum(1 for r in self.rooms.values() if r.ip == ip) >= self.rooms_per_ip:
            await _send(writer, {"t": "error", "reason": "too many games hosted from your address"})
            return
        code = new_code()
        while code in self.rooms:
            code = new_code()
        room = Room(code, secrets.token_hex(16), ip, writer)
        self.rooms[code] = room
        log.info("room %s opened by %s (%d rooms)", format_code(code), ip, len(self.rooms))
        try:
            await _send(writer, {"t": "room", "code": code, "key": room.key})
            while True:              # pings keep the room; anything else is ignored
                if await _read_msg(reader, self.host_idle_timeout) is None:
                    break
        finally:
            del self.rooms[code]
            for fut in room.pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("the host left"))
            log.info("room %s closed (%d rooms)", format_code(code), len(self.rooms))

    # ---- joiner
    def _failed(self, ip: str) -> bool:
        """Record a failed join; True when this address has failed too often in the last minute."""
        now = time.monotonic()
        q = self._failures.setdefault(ip, deque())
        while q and now - q[0] > 60:
            q.popleft()
        q.append(now)
        return len(q) > self.failed_joins_per_minute

    def _blocked(self, ip: str) -> bool:
        now = time.monotonic()
        q = self._failures.get(ip)
        return bool(q) and sum(1 for t in q if now - t <= 60) >= self.failed_joins_per_minute

    async def _join(self, msg: dict, ip: str, reader, writer) -> None:
        if msg.get("v") != RELAY_VERSION:
            await _send(writer, {"t": "error", "reason": "the relay server runs a different version of the game"})
            return
        if self._blocked(ip):
            await _send(writer, {"t": "error", "reason": "too many wrong codes, wait a minute and try again"})
            return
        code = normalize_code(str(msg.get("code", "")))
        room = self.rooms.get(code)
        if room is None:
            self._failed(ip)
            await _send(writer, {"t": "error", "reason": "no game is open with that code"})
            return
        n, room.next_n = room.next_n, room.next_n + 1
        fut = asyncio.get_running_loop().create_future()
        room.pending[n] = fut
        try:
            await _send(room.ctrl, {"t": "incoming", "n": n})
            host_reader, host_writer, done = await asyncio.wait_for(fut, self.join_timeout)
        except (asyncio.TimeoutError, ConnectionError, OSError) as e:
            reason = str(e) if isinstance(e, ConnectionError) else "the host didn't answer"
            await _send(writer, {"t": "error", "reason": reason})
            return
        finally:
            room.pending.pop(n, None)
        log.info("room %s: player %d joined from %s", format_code(code), n, ip)
        try:
            await _send(writer, {"t": "ok"})
            await self._splice(reader, writer, host_reader, host_writer)
        finally:
            if not done.done():
                done.set_result(None)

    # ---- host data connection for one joiner
    async def _accept(self, msg: dict, reader, writer) -> None:
        room = self.rooms.get(normalize_code(str(msg.get("code", ""))))
        if room is None or not secrets.compare_digest(str(msg.get("key", "")), room.key):
            return
        fut = room.pending.get(msg.get("n"))
        if fut is None or fut.done():
            return
        done = asyncio.get_running_loop().create_future()
        fut.set_result((reader, writer, done))
        await done                       # the joiner's handler runs the splice; keep this socket until it ends

    @staticmethod
    async def _splice(r1, w1, r2, w2) -> None:
        async def pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
            while data := await r.read(CHUNK):
                w.write(data)
                await w.drain()

        tasks = [asyncio.create_task(pipe(r1, w2)), asyncio.create_task(pipe(r2, w1))]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)   # either side leaving ends both
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await _close(w1)
            await _close(w2)

    # ---- serving
    async def start(self, bind: str = "0.0.0.0", port: int = RELAY_PORT) -> asyncio.base_events.Server:
        return await asyncio.start_server(self.handle, bind, port)


class BackgroundRelay:
    """A relay on its own thread and event loop, for tests and for trying online play on one machine."""

    def __init__(self, bind: str = "127.0.0.1", port: int = 0, **kwargs) -> None:
        self.relay = Relay(**kwargs)
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        def run() -> None:
            asyncio.set_event_loop(self.loop)
            self.server = self.loop.run_until_complete(self.relay.start(bind, port))
            self.port = self.server.sockets[0].getsockname()[1]
            ready.set()
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, name="relay", daemon=True)
        self.thread.start()
        ready.wait(5)
        self.address = (bind, self.port)

    def close(self) -> None:
        async def stop() -> None:
            self.server.close()
            for room in list(self.relay.rooms.values()):
                room.ctrl.close()
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run_coroutine_threadsafe(stop(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.loop.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ballbrawlla-relay", description="Relay server for ballbrawlla invite codes.")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=RELAY_PORT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    async def serve() -> None:
        server = await Relay().start(args.bind, args.port)
        log.info("relay listening on %s:%d", args.bind, args.port)
        async with server:
            await server.serve_forever()

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
