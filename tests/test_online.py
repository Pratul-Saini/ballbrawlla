"""Invite codes end to end: address codes, LAN beacons that carry codes, joining by code (same network,
address code, relay code), the host's Reach status, and opening the router's port (UPnP) on a fake router."""

import re
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import make_game

from ballbrawlla.config import Tuning
from ballbrawlla.net import invite, online, upnp
from ballbrawlla.net.discovery import Beacon, Finder, FoundGame, decode, encode
from ballbrawlla.net.host import Host
from ballbrawlla.net.invite import address_code, check_code, code_address, format_code
from ballbrawlla.net.relay_server import BackgroundRelay
from ballbrawlla.world.level import level_to_dict


# ---------------------------------------------------------------- codes

@pytest.mark.parametrize("ip", ["0.0.0.0", "10.0.0.5", "192.168.1.20", "203.0.113.5", "255.255.255.255"])
def test_address_codes_round_trip(ip):
    code = address_code(ip)
    assert len(code) == 8 and all(c in invite.ALPHABET for c in code)
    assert code_address(code) == ip and code_address(format_code(code).lower()) == ip
    assert check_code(code) is None and format_code(code)[4] == "-"


def test_address_code_typos_are_caught():
    code = address_code("203.0.113.5")
    caught = 0
    for i in range(8):
        for c in invite.ALPHABET:
            if c != code[i]:
                caught += code_address(code[:i] + c + code[i + 1:]) is None
    assert caught / (8 * 30) > 0.97
    typo = next(code[:-1] + c for c in invite.ALPHABET if code_address(code[:-1] + c) is None)
    assert "typo" in check_code(typo)


def test_beacons_carry_codes():
    game = decode(encode("Kris's game", "Field 05", 50555, ["KQ7M3XPA", "AB2CD3"]), "10.0.0.7")
    assert game.codes == ("KQ7M3XPA", "AB2CD3") and game.address == "10.0.0.7"
    old = decode(encode("Old", "Field 01", 50555), "10.0.0.8")       # an older game's beacon: no codes
    assert old.codes == ()
    beacon = Beacon("Kris's game", "Field 05", 50555, discovery_port=1)
    beacon.set_codes(["KQ7M3XPA"])
    assert decode(beacon.packet, "10.0.0.7").codes == ("KQ7M3XPA",)
    beacon.close()


# ---------------------------------------------------------------- joining

def _host(port=0):
    g = make_game(players=[(200, 650), (1000, 650)])
    return Host({"level": level_to_dict(g.level), "tuning": asdict(Tuning())}, max_players=2, port=port,
                bind="127.0.0.1")


def _serve(host):
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            host.poll()
            time.sleep(0.003)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return stop, t


def test_a_game_on_this_network_with_the_code_is_joined_directly():
    host = _host()
    stop, t = _serve(host)
    code = address_code("203.0.113.5")           # the public code; the beacon says the game is right here
    try:
        lan = [FoundGame("127.0.0.1", host.port, "Kris's game", "Field 05", codes=(code,))]
        client, how = online.connect(format_code(code).lower(), games=lan, timeout=3)
        assert client.pid == 1 and how == "on your network"
        client.close()
    finally:
        stop.set()
        t.join()
        host.close()


def test_an_address_code_is_dialled(monkeypatch):
    host = _host()
    monkeypatch.setattr(online, "DEFAULT_PORT", host.port)
    stop, t = _serve(host)
    try:
        client, how = online.connect(address_code("127.0.0.1"), games=[], timeout=3)
        assert client.pid == 1
        client.close()
    finally:
        stop.set()
        t.join()
        host.close()


def test_unreachable_code_says_what_to_check(monkeypatch):
    with __import__("socket").socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    monkeypatch.setattr(online, "DEFAULT_PORT", free)
    with pytest.raises(ConnectionError, match='Internet: ready'):
        online.connect(address_code("127.0.0.1"), games=[], timeout=1)


def test_relay_code_joins_through_the_relay(monkeypatch):
    relay = BackgroundRelay()
    monkeypatch.setattr(invite, "DEFAULT_RELAY", "")
    monkeypatch.setenv(invite.RELAY_ENV, f"127.0.0.1:{relay.port}")
    reach = online.Reach(0, "127.0.0.1", invite.relay_address(), use_router=False)
    host = _host()
    stop, t = _serve(host)
    try:
        for _ in range(200):
            if reach.done:
                break
            time.sleep(0.01)
        assert reach.room is not None and len(reach.code) == 6
        assert reach.internet.state == online.READY and "relay" in reach.internet.text
        host.room = reach.room
        client, how = online.connect(reach.code, games=[], timeout=3)
        assert client.pid == 1 and how == "through the relay server"
        client.close()
    finally:
        stop.set()
        t.join()
        host.close()
        reach.close()
        relay.close()


def test_relay_code_without_a_relay(monkeypatch):
    monkeypatch.setattr(invite, "DEFAULT_RELAY", "")
    monkeypatch.delenv(invite.RELAY_ENV, raising=False)
    with pytest.raises(ConnectionError, match="relay server code"):
        online.connect("KQ7-M3X", games=[])


# ---------------------------------------------------------------- the host's status

class FakeOpener:
    def __init__(self, port, lan_ip, start=True, result=("open", "203.0.113.9", "")):
        self.state, self.public_ip, self.reason = result
        self.closed = False

    def close(self):
        self.closed = True


def _reach(monkeypatch, result, relay=None):
    monkeypatch.setattr(online, "PortOpener", lambda port, lan_ip: FakeOpener(port, lan_ip, result=result))
    r = online.Reach(online.DEFAULT_PORT, "192.168.1.20", relay)
    for _ in range(200):
        if r.done:
            break
        time.sleep(0.01)
    return r


def test_router_opened_the_port(monkeypatch):
    r = _reach(monkeypatch, ("open", "203.0.113.9", ""))
    assert r.code == address_code("203.0.113.9")
    assert set(r.codes) == {address_code("203.0.113.9"), address_code("192.168.1.20")}
    assert [ln.state for ln in r.lines()] == [online.READY, online.READY]
    r.close()
    assert r.opener.closed


def test_router_could_not_open_the_port(monkeypatch):
    r = _reach(monkeypatch, ("failed", "", "Your router didn't answer. To fix it, turn on UPnP."))
    assert r.code == address_code("192.168.1.20")           # same Wi-Fi still works with it
    lan, net = r.lines()
    assert lan.state == online.READY and net.state == online.UNAVAILABLE and "turn on UPnP" in net.text


def test_a_relay_that_is_down_falls_back_to_the_router(monkeypatch):
    r = _reach(monkeypatch, ("open", "203.0.113.9", ""), relay=("127.0.0.1", 1))
    assert r.room is None and r.relay_error and r.code == address_code("203.0.113.9")


def test_checking_shows_no_code_yet():
    r = online.Reach(online.DEFAULT_PORT, "192.168.1.20", None, start=False)
    assert r.code is None and r.internet.state == online.CHECKING


# ---------------------------------------------------------------- UPnP against a fake router

class FakeRouter:
    """Serves a gateway description and answers the three SOAP calls the game uses."""

    def __init__(self, external="93.184.216.34", add_error=None):
        self.external, self.add_error = external, add_error
        self.calls: list[tuple[str, str]] = []
        router = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = (
                    '<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><device>'
                    "<deviceType>urn:schemas-upnp-org:device:InternetGatewayDevice:1</deviceType><deviceList>"
                    "<device><serviceList><service>"
                    "<serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>"
                    "<controlURL>/ctl/IPConn</controlURL></service></serviceList></device>"
                    "</deviceList></device></root>").encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"])).decode()
                action = self.headers["SOAPAction"].strip('"').split("#")[1]
                router.calls.append((action, data))
                ns = 'xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"'
                if action == "AddPortMapping" and router.add_error:
                    code, inner = 500, (f"<s:Fault><detail><UPnPError><errorCode>{router.add_error}</errorCode>"
                                        "</UPnPError></detail></s:Fault>")
                elif action == "GetExternalIPAddress":
                    code, inner = 200, (f"<u:GetExternalIPAddressResponse {ns}><NewExternalIPAddress>"
                                        f"{router.external}</NewExternalIPAddress></u:GetExternalIPAddressResponse>")
                else:
                    code, inner = 200, f"<u:{action}Response {ns}/>"
                body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                        f"<s:Body>{inner}</s:Body></s:Envelope>").encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/desc.xml"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def router(monkeypatch):
    made = []

    def make(**kw):
        r = FakeRouter(**kw)
        made.append(r)
        monkeypatch.setattr(upnp, "discover", lambda lan_ip, wait=2.5: [r.url])
        return r
    yield make
    for r in made:
        r.close()


def _opened(port=50555, lan_ip="192.168.1.20"):
    op = upnp.PortOpener(port, lan_ip)
    for _ in range(300):
        if op.state != "checking":
            break
        time.sleep(0.01)
    return op


def test_router_opens_and_closes_the_port(router):
    r = router()
    op = _opened()
    assert op.state == "open" and op.public_ip == "93.184.216.34"
    add = next(d for a, d in r.calls if a == "AddPortMapping")
    assert "<NewExternalPort>50555</NewExternalPort>" in add and "<NewInternalClient>192.168.1.20<" in add
    op.close()
    assert [a for a, _ in r.calls][-1] == "DeletePortMapping"


def test_router_behind_another_router_is_reported(router):
    router(external="100.72.1.5")                            # carrier NAT range
    op = _opened()
    assert op.state == "failed" and "internet provider" in op.reason and "forward TCP port 50555" in op.reason


def test_router_port_taken_by_another_computer(router):
    router(add_error="718")
    op = _opened()
    assert op.state == "failed" and "another computer" in op.reason


def test_no_router_answers(monkeypatch):
    monkeypatch.setattr(upnp, "discover", lambda lan_ip, wait=2.5: [])
    op = _opened()
    assert op.state == "failed" and "UPnP" in op.reason and "same Wi-Fi" in op.reason


def test_public_address_check():
    assert upnp.is_public("8.8.8.8") and not upnp.is_public("192.168.0.2") and not upnp.is_public("100.64.0.1")
    assert not upnp.is_public("") and not upnp.is_public("garbage")


# ---------------------------------------------------------------- the test window

def test_n_opens_a_second_game_that_joins_this_one(monkeypatch):
    from ballbrawlla import main
    seen = {}

    class FakePopen:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
    monkeypatch.setattr(main.subprocess, "Popen", FakePopen)
    assert main.open_test_window(50601) is not None
    assert seen["cmd"][-4:] == ["--join", "127.0.0.1", "--port", "50601"]
    assert "ballbrawlla" in seen["cmd"] or main.is_frozen()
