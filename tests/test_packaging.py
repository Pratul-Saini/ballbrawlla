"""What a packaged build depends on: file locations, the version handshake, and a frozen-app simulation."""

import socket
import sys
import time
from pathlib import Path

import pytest

from ballbrawlla import paths
from ballbrawlla.net.host import Host
from ballbrawlla.net.protocol import PROTOCOL_VERSION, Connection
from ballbrawlla.version import __version__


# ---------------------------------------------------------------- paths

def test_source_checkout_keeps_levels_and_logs_in_the_repo(monkeypatch):
    monkeypatch.delenv("BALLBRAWLLA_HOME", raising=False)          # conftest points it at a temp folder
    root = Path(__file__).resolve().parents[1]
    assert paths.levels_dir() == root / "levels" and paths.levels_dir().is_dir()
    assert paths.logs_dir() == root / "logs"
    assert not paths.is_frozen()


def test_home_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BALLBRAWLLA_HOME", str(tmp_path))
    assert paths.user_data_dir() == tmp_path and paths.logs_dir() == tmp_path / "logs"


@pytest.mark.parametrize("platform,expected", [
    ("darwin", ("Library", "Application Support", "Gridiron Scramble")),
    ("win32", ("AppData", "Roaming", "Gridiron Scramble")),
    ("linux", (".local", "share", "gridiron-scramble")),
])
def test_frozen_app_writes_to_a_per_user_folder_not_the_bundle(monkeypatch, tmp_path, platform, expected):
    bundle = tmp_path / "bundle"
    (bundle / "levels").mkdir(parents=True)
    monkeypatch.delenv("BALLBRAWLLA_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert paths.levels_dir() == bundle / "levels"                         # read-only data comes from the bundle
    assert paths.user_data_dir() == tmp_path / "home" / Path(*expected)    # writable data does not
    assert bundle not in paths.logs_dir().parents


def test_windows_prefers_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("BALLBRAWLLA_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    assert paths.user_data_dir() == tmp_path / "roaming" / "Gridiron Scramble"


def test_every_level_file_is_findable_from_the_bundle_folder():
    assert len(list(paths.levels_dir().glob("*.json"))) == 15


# ---------------------------------------------------------------- version handshake

def _hello(port: int, **fields) -> dict:
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    conn = Connection(sock)
    conn.send({"t": "hello", **fields})
    return conn


def _wait_for(host: Host, conn: Connection) -> dict:
    for _ in range(100):
        host.poll()
        msgs = conn.receive()
        if msgs:
            return msgs[0]
        time.sleep(0.01)
    raise AssertionError("no answer from the host")


def test_old_build_is_refused_with_both_versions_and_what_to_do():
    host = Host(welcome={"level": {}, "tuning": {}}, max_players=2, port=0)
    try:
        conn = _hello(host.port, v=PROTOCOL_VERSION - 1, game="0.0.9")
        reply = _wait_for(host, conn)
        assert reply["t"] == "reject"
        assert __version__ in reply["reason"] and "0.0.9" in reply["reason"] and "latest build" in reply["reason"]
        conn.close()
    finally:
        host.close()


def test_a_client_that_never_sent_a_version_is_called_an_older_version():
    host = Host(welcome={"level": {}, "tuning": {}}, max_players=2, port=0)
    try:
        conn = _hello(host.port, v=1)
        assert "an older version" in _wait_for(host, conn)["reason"]
        conn.close()
    finally:
        host.close()


def test_matching_build_is_welcomed():
    host = Host(welcome={"level": {}, "tuning": {}}, max_players=2, port=0)
    try:
        conn = _hello(host.port, v=PROTOCOL_VERSION, game=__version__)
        assert _wait_for(host, conn)["t"] == "welcome"
        conn.close()
    finally:
        host.close()


def test_version_is_a_plain_dotted_string():
    assert all(part.isdigit() for part in __version__.split("."))
