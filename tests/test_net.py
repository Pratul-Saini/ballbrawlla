import json
import time
from dataclasses import asdict

from conftest import make_game, run

from ballbrawlla.config import Tuning
from ballbrawlla.game import Game
from ballbrawlla.input import Intent
from ballbrawlla.net.client import Client
from ballbrawlla.net.host import Host
from ballbrawlla.net.snapshot import apply_snapshot, make_snapshot
from ballbrawlla.world.level import level_from_dict, level_to_dict


def test_level_dict_roundtrip():
    g = make_game(platforms=[(100, 200, 50, 20)], players=[(200, 650), (1000, 650)])
    d = level_to_dict(g.level)
    lv = level_from_dict(json.loads(json.dumps(d)))
    assert len(lv.platforms) == len(g.level.platforms)
    assert lv.player_spawns == g.level.player_spawns


def test_snapshot_roundtrip_matches_host_state():
    host = make_game(players=[(620, 650), (900, 650)], ball=(640, 670))
    run(host, ticks=60)
    run(host, [Intent(z_pressed=True), Intent(move_x=1)], ticks=1)
    run(host, [Intent(), Intent(move_x=1)], ticks=5)

    replica = Game(host.level, host.t, num_players=2)
    apply_snapshot(replica, json.loads(json.dumps(make_snapshot(host, 66))))

    for a, b in zip(host.players, replica.players):
        assert abs(a.box.x - b.box.x) < 0.01 and abs(a.box.y - b.box.y) < 0.01
        assert a.state.name == b.state.name
        assert a.facing == b.facing
    assert replica.ball.held_by is replica.players[0]
    assert replica.players[0].held_ball is replica.ball


def _pump(host: Host, until, timeout=2.0):
    deadline = time.monotonic() + timeout
    events = ([], [])
    while time.monotonic() < deadline:
        j, l = host.poll()
        events[0].extend(j)
        events[1].extend(l)
        if until(events):
            return events
        time.sleep(0.005)
    raise AssertionError("timed out")


def test_host_client_over_loopback():
    t = Tuning()
    g = make_game(players=[(200, 650), (1000, 650)])
    host = Host({"level": level_to_dict(g.level), "tuning": asdict(t)}, max_players=2,
                port=0, bind="127.0.0.1")
    try:
        # Client handshake blocks, so let the host answer from a helper thread.
        import threading
        stop = threading.Event()
        joined = []

        def serve():
            while not stop.is_set() and not joined:
                joined.extend(host.poll()[0])
                time.sleep(0.005)

        th = threading.Thread(target=serve)
        th.start()
        client = Client("127.0.0.1", host.port, timeout=2.0)
        stop.set()
        th.join()

        assert client.pid == 1 and joined == [1]
        assert Tuning(**client.tuning_data) == t
        assert level_from_dict(client.level_data).player_spawns == g.level.player_spawns

        # Press edge from client survives to the host's next consumed Intent, once.
        client.send_intent(Intent(move_x=-1, jump_pressed=True))
        deadline = time.monotonic() + 2
        while host._inputs[1].move_x != -1 and time.monotonic() < deadline:
            host.poll()
        first = host.intent_for(1)
        assert first.move_x == -1 and first.jump_pressed
        second = host.intent_for(1)
        assert second.move_x == -1 and not second.jump_pressed

        # Snapshot reaches the client.
        host.broadcast(make_snapshot(g, 7))
        deadline = time.monotonic() + 2
        snap = None
        while snap is None and time.monotonic() < deadline:
            snap = client.latest_snapshot()
            time.sleep(0.005)
        assert snap is not None and snap["tick"] == 7

        # Disconnect is noticed.
        client.close()
        _pump(host, lambda ev: 1 in ev[1])
        assert 1 not in host.clients
    finally:
        host.close()


def test_host_rejects_when_full():
    g = make_game()
    host = Host({"level": level_to_dict(g.level), "tuning": asdict(Tuning())}, max_players=1,
                port=0, bind="127.0.0.1")
    import threading
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            host.poll()
            time.sleep(0.005)

    th = threading.Thread(target=serve)
    th.start()
    try:
        try:
            Client("127.0.0.1", host.port, timeout=2.0)
            raise AssertionError("expected rejection")
        except ConnectionError as e:
            assert "full" in str(e)
    finally:
        stop.set()
        th.join()
        host.close()
