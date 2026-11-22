"""LAN discovery: packets are validated, stale games expire, and a beacon is heard by a finder."""

import json
import socket
import time

import pytest

from ballbrawlla.net.discovery import (
    BEACON_INTERVAL, GAME_TIMEOUT, MAGIC, Beacon, Finder, FoundGame, decode, encode,
)
from ballbrawlla.net.protocol import PROTOCOL_VERSION


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_roundtrip_uses_sender_address():
    game = decode(encode("Kris", "Field 05", 50555), "10.0.0.9")
    assert game == FoundGame("10.0.0.9", 50555, "Kris", "Field 05")


@pytest.mark.parametrize("data", [
    b"", b"not json", b"[]", b"\xff\xfe",
    json.dumps({"magic": "other", "v": PROTOCOL_VERSION, "port": 50555}).encode(),
    json.dumps({"magic": MAGIC, "v": PROTOCOL_VERSION + 1, "port": 50555}).encode(),
    json.dumps({"magic": MAGIC, "v": PROTOCOL_VERSION, "port": 80}).encode(),
    json.dumps({"magic": MAGIC, "v": PROTOCOL_VERSION, "port": "50555"}).encode(),
    json.dumps({"magic": MAGIC, "v": PROTOCOL_VERSION, "port": True}).encode(),
])
def test_garbage_is_ignored(data):
    assert decode(data, "10.0.0.9") is None


def test_text_is_cleaned_and_limited():
    pkt = json.dumps({"magic": MAGIC, "v": PROTOCOL_VERSION, "port": 50555, "name": "A\x00" + "b" * 200, "level": 5}).encode()
    game = decode(pkt, "1.2.3.4")
    assert "\x00" not in game.name and len(game.name) <= 40 and game.level == "5"


def test_beacon_and_finder_on_one_machine():
    port = free_udp_port()
    finder = Finder(port)
    beacon = Beacon("Kris", "Field 05", 50555, discovery_port=port)
    try:
        assert beacon.tick(now=100.0)
        games = []
        for _ in range(50):
            games = finder.poll()
            if games:
                break
            time.sleep(0.02)
        assert games and games[0].port == 50555 and games[0].name == "Kris" and games[0].level == "Field 05"
    finally:
        beacon.close()
        finder.close()


def test_beacon_rate_and_open_seat():
    beacon = Beacon("x", "y", 50555, discovery_port=free_udp_port())
    assert beacon.tick(now=10.0)
    assert not beacon.tick(now=10.0 + BEACON_INTERVAL / 2)
    assert beacon.tick(now=10.0 + BEACON_INTERVAL + 0.01)
    assert not beacon.tick(open_seat=False, now=99.0)          # a full game stops advertising
    beacon.close()
    assert not beacon.tick(now=200.0)                          # closed beacons stay quiet


def test_games_expire():
    port = free_udp_port()
    finder = Finder(port)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.sendto(encode("A", "L", 50555), ("127.0.0.1", port))
    time.sleep(0.05)
    assert len(finder.poll(now=50.0)) == 1
    assert len(finder.poll(now=50.0 + GAME_TIMEOUT - 0.1)) == 1
    assert finder.poll(now=50.0 + GAME_TIMEOUT + 0.1) == []
    sender.close()
    finder.close()


def test_finder_survives_a_taken_port():
    blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # no reuse flags: a real conflict
    blocker.bind(("0.0.0.0", 0))
    finder = Finder(blocker.getsockname()[1])
    assert finder.poll() == []                                    # works either way, never raises
    finder.close()
    blocker.close()


def test_same_beacon_from_lan_and_loopback_is_listed_once():
    port = free_udp_port()
    finder = Finder(port)
    finder._seen[("10.0.0.5", 50555)] = (FoundGame("10.0.0.5", 50555, "K", "L"), 5.0)
    finder._seen[("127.0.0.1", 50555)] = (FoundGame("127.0.0.1", 50555, "K", "L"), 5.0)
    other = FoundGame("127.0.0.1", 50600, "Other", "L")
    finder._seen[("127.0.0.1", 50600)] = (other, 5.0)
    games = finder.poll(now=5.0)
    assert [(g.address, g.port) for g in games] == [("10.0.0.5", 50555), ("127.0.0.1", 50600)]
    finder.close()
