"""Invite codes and the relay server, end to end over loopback."""

import threading
import time
from dataclasses import asdict

import pytest
from conftest import make_game

from ballbrawlla.config import Tuning
from ballbrawlla.input import Intent
from ballbrawlla.net import invite
from ballbrawlla.net.client import Client
from ballbrawlla.net.host import Host
from ballbrawlla.net.invite import (
    RelayRoom, check_code, check_relay, dial, format_code, new_code, normalize_code, relay_address,
)
from ballbrawlla.net.relay_server import BackgroundRelay
from ballbrawlla.world.level import level_to_dict


# ---------------------------------------------------------------- codes and addresses

def test_codes_normalize_format_and_validate():
    code = new_code()
    assert len(code) == 6 and check_code(code) is None
    assert normalize_code(" kq7-m3x ") == "KQ7M3X"
    assert format_code("kq7m3x") == "KQ7-M3X"
    assert check_code("kq7 m3x") is None
    assert "6 characters" in check_code("KQ7M3")
    assert "never use 0, O, 1, I or L" in check_code("KQ7M30")
    assert "Type the invite code" in check_code("  ")


def test_relay_address_sources(monkeypatch):
    monkeypatch.setattr(invite, "DEFAULT_RELAY", "")
    monkeypatch.delenv(invite.RELAY_ENV, raising=False)
    assert relay_address() is None and "No relay server" in check_relay()
    monkeypatch.setenv(invite.RELAY_ENV, "relay.example.com")
    assert relay_address() == ("relay.example.com", invite.RELAY_PORT)
    assert relay_address("10.0.0.5:6000") == ("10.0.0.5", 6000)        # --relay wins over the environment
    assert relay_address("[::1]:6000") == ("::1", 6000)
    assert check_relay() is None


# ---------------------------------------------------------------- relay

@pytest.fixture
def relay():
    r = BackgroundRelay(failed_joins_per_minute=3)
    yield r
    r.close()


def _host(room: RelayRoom) -> Host:
    g = make_game(players=[(200, 650), (1000, 650)])
    return Host({"level": level_to_dict(g.level), "tuning": asdict(Tuning())}, max_players=2,
                port=0, bind="127.0.0.1", room=room)


def _serve(host: Host, stop: threading.Event, joined: list, left: list) -> threading.Thread:
    """The host's game loop stand-in: poll and answer while a Client's blocking handshake runs."""
    def loop():
        while not stop.is_set():
            j, l = host.poll()
            joined.extend(j)
            left.extend(l)
            time.sleep(0.003)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


def _wait(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.005)
    raise AssertionError("timed out")


def test_join_by_code_plays_through_relay(relay):
    room = RelayRoom(relay.address)
    assert check_code(room.code) is None and room.display_code[3] == "-"
    host = _host(room)
    stop, joined, left = threading.Event(), [], []
    t = _serve(host, stop, joined, left)
    try:
        client = Client.via_code(relay.address, room.display_code.lower(), timeout=3)
        assert client.pid == 1 and "platforms" in client.level_data
        _wait(lambda: joined == [1])

        client.send_intent(Intent(move_x=1, z_pressed=True))
        _wait(lambda: host._inputs[1].move_x == 1)          # input crossed the relay
        host.send_to(1, {"t": "snap", "tick": 7})
        snap = None

        def got():
            nonlocal snap
            snap = snap or client.latest_snapshot()
            return snap is not None
        _wait(got)
        assert snap["tick"] == 7

        client.close()
        _wait(lambda: left == [1])                          # leaving reaches the host
    finally:
        stop.set()
        t.join()
        host.close()


def test_second_joiner_is_told_the_game_is_full(relay):
    room = RelayRoom(relay.address)
    host = _host(room)
    stop, joined, left = threading.Event(), [], []
    t = _serve(host, stop, joined, left)
    try:
        first = Client.via_code(relay.address, room.code, timeout=3)
        with pytest.raises(ConnectionError, match="game is full"):
            Client.via_code(relay.address, room.code, timeout=3)
        first.close()
    finally:
        stop.set()
        t.join()
        host.close()


def test_wrong_code_and_closed_room_are_refused(relay):
    with pytest.raises(ConnectionError, match="no game is open with that code"):
        dial(relay.address, "ABCDEF", timeout=3)
    room = RelayRoom(relay.address)
    room.close()
    _wait(lambda: room.code not in relay.relay.rooms)
    with pytest.raises(ConnectionError, match="no game is open"):
        dial(relay.address, room.code, timeout=3)


def test_too_many_wrong_codes_are_blocked(relay):
    for _ in range(3):
        with pytest.raises(ConnectionError, match="no game is open"):
            dial(relay.address, "ABCDEF", timeout=3)
    room = RelayRoom(relay.address)
    with pytest.raises(ConnectionError, match="too many wrong codes"):
        dial(relay.address, room.code, timeout=3)           # even a right code, for a while
    room.close()


def test_unreachable_relay_gives_a_readable_error():
    with pytest.raises(ConnectionError, match="Could not reach the relay server"):
        RelayRoom(("127.0.0.1", 1), timeout=1)
