"""Launch checks: every way a mode can fail to start gives a plain reason instead of a traceback."""

import socket

import pytest

from ballbrawlla.launch import (
    ALL_MODES,
    LEVELS, check_address, check_launch, check_port, inspect_level, list_levels, resolve_level,
)


def test_lists_all_levels_football_first():
    infos = list_levels()
    assert len(infos) == 15
    assert all(i.usable for i in infos)
    football = [i for i in infos if i.football]
    assert len(football) == 14 and infos[-1].key == "arena_01" and not infos[-1].football


def test_resolve_bare_name():
    assert resolve_level("field_05") == LEVELS / "field_05.json"


@pytest.mark.parametrize("mode", ["practice", "local", "host"])
def test_arena_refused_for_match_modes(mode):
    why = check_launch(mode, LEVELS / "arena_01.json", port=0 + 49321)
    assert why and "football field" in why


def test_arena_ok_for_free_play():
    assert check_launch("sandbox", LEVELS / "arena_01.json") is None


@pytest.mark.parametrize("mode", ["practice", "local", "sandbox"])
def test_field_launches(mode):
    assert check_launch(mode, LEVELS / "field_01.json") is None


def test_missing_level():
    why = check_launch("practice", LEVELS / "field_99.json")
    assert why and "field_99" in why and "not found" in why


def test_broken_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope")
    assert "not valid JSON" in check_launch("practice", p)
    assert inspect_level(p).error


def test_bad_platform_type(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text((LEVELS / "field_01.json").read_text().replace('"type": "thin"', '"type": "Thin"', 1))
    why = check_launch("practice", p)
    assert why and "invalid platform type" in why


def test_busy_port():
    s = socket.create_server(("0.0.0.0", 0))
    try:
        port = s.getsockname()[1]
        assert "already in use" in check_port(port)
        assert "already in use" in check_launch("host", LEVELS / "field_01.json", port=port)
    finally:
        s.close()


def test_free_port_ok():
    s = socket.create_server(("0.0.0.0", 0))
    port = s.getsockname()[1]
    s.close()
    assert check_port(port) is None


@pytest.mark.parametrize("port", [0, 80, 70000])
def test_port_out_of_range(port):
    assert "isn't valid" in check_port(port)
    assert "isn't valid" in check_launch("join", address="1.2.3.4", port=port)


@pytest.mark.parametrize("addr,ok", [("", False), ("  ", False), ("1.2 .3", False), ("192.168.1.5", True)])
def test_address(addr, ok):
    assert (check_address(addr) is None) is ok


def _relay(monkeypatch, value):
    from ballbrawlla.net import invite
    monkeypatch.setattr(invite, "DEFAULT_RELAY", "")
    if value:
        monkeypatch.setenv(invite.RELAY_ENV, value)
    else:
        monkeypatch.delenv(invite.RELAY_ENV, raising=False)


def test_join_code_checks(monkeypatch):
    from ballbrawlla.net.invite import address_code
    _relay(monkeypatch, "")
    assert check_launch("join_code", code=address_code("203.0.113.5")) is None     # no relay needed
    assert "relay server code" in check_launch("join_code", code="KQ7-M3X")
    assert "8 characters" in check_launch("join_code", code="KQ7")
    _relay(monkeypatch, "relay.example.com")
    assert check_launch("join_code", code="kq7 m3x") is None
    assert "host_online" not in ALL_MODES
