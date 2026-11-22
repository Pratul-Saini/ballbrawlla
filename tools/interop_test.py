"""Do the Python game and the Godot port really speak the same network protocol? Run them against each other.

    .venv/bin/python tools/interop_test.py            # all checks
    .venv/bin/python tools/interop_test.py --godot /path/to/Godot

Checks (each starts real processes on loopback ports and always cleans them up):
  1. a Godot client joins a Python host            (handshake, level + tuning, snapshots, version, who you are)
  2. a Python client joins a Godot host            (and the Godot host sees the Python client's inputs)
  3. a Godot host opens a room on the relay, and another Godot game joins with the invite code
  4. one Godot game's LAN beacon is heard by another Godot game's finder

Checks 1 and 2 show the two games happen to speak the same protocol; the port does not depend on it. The relay
server is the Python one (it is only a pipe), and the port keeps using it.

Exit status 0 if every check passes. Not part of pytest: it needs the Godot binary and takes about a minute.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")
ENV = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "BALLBRAWLLA_MUSIC": "off"}
ENV.pop("BALLBRAWLLA_RELAY", None)
GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"
_children: list[subprocess.Popen] = []


def start(cmd: list[str], **kw) -> subprocess.Popen:
    p = subprocess.Popen(cmd, cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
    _children.append(p)
    return p


def stop_all() -> None:
    for p in _children:
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
    time.sleep(0.8)
    for p in _children:
        if p.poll() is None:
            p.kill()
    _children.clear()


def probe(*args: str, timeout: float = 60) -> list[str]:
    """Run the Godot probe script; return its PROBE lines (or a note saying what went wrong)."""
    p = start([GODOT, "--headless", "--path", "godot", "-s", "res://tools/net_probe.gd", "--", *args])
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return ["TIMED OUT"]
    lines = [l for l in out.splitlines() if l.startswith("PROBE")]
    errs = [l for l in out.splitlines() if "SCRIPT ERROR" in l or "Parse Error" in l]
    return lines + errs


def wait_listening(port: int, timeout: float = 20) -> bool:
    import socket
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
            return True
        except OSError:
            time.sleep(0.25)
    return False


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        {detail}")
    return ok


def godot_joins_python_host() -> bool:
    start([PY, "-u", "-m", "ballbrawlla", "--host", "--level", "field_03", "--port", "50961"])
    if not wait_listening(50961):
        return check("Godot client -> Python host", False, "the Python host never started listening")
    lines = probe("join", "127.0.0.1", "50961")
    text = " | ".join(lines)
    ok = any("joined pid=1" in l and "level_ok=true" in l and "phase=play_call" in l and "side=defense" in l or
             ("joined pid=1" in l and "level_ok=true" in l and "snaps=" in l and "snaps=0" not in l) for l in lines)
    ok = ok and any("jump_speed=820" in l and "hz=120" in l for l in lines)
    return check("Godot client -> Python host", ok, text)


def python_client_joins_godot_host() -> bool:
    host = start([GODOT, "--headless", "--path", "godot", "-s", "res://tools/net_probe.gd", "--", "host", "50962", "field_03", "9"])
    if not wait_listening(50962):
        return check("Python client -> Godot host", False, "the Godot host never started listening")
    code = (
        "import sys, time\nsys.path.insert(0, 'src')\n"
        "from ballbrawlla.net.client import Client\nfrom ballbrawlla.input import Intent\n"
        "c = Client('127.0.0.1', 50962)\n"
        "print('PYCLIENT joined pid', c.pid, 'level', c.level_data.get('name'), 'tuning keys', len(c.tuning_data))\n"
        "snaps = 0; last = None\n"
        "end = time.time() + 4\n"
        "while time.time() < end:\n"
        "    c.send_intent(Intent(move_x=1)); s = c.latest_snapshot()\n"
        "    if s is not None: snaps += 1; last = s\n"
        "    time.sleep(0.02)\n"
        "print('PYCLIENT snaps', snaps, 'phase', last and last['phase'], 'you', last and last['you'], 'side', last and last['side'])\n"
        "c.close()\n")
    r = subprocess.run([PY, "-c", code], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=40)
    try:
        out, _ = host.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        host.kill()
        out = ""
    probe_lines = [l for l in out.splitlines() if l.startswith("PROBE")]
    detail = " | ".join([l for l in r.stdout.splitlines() if l.startswith("PYCLIENT")] + probe_lines + ([r.stderr[-300:]] if r.returncode else []))
    ok = ("PYCLIENT joined pid 1" in r.stdout and "tuning keys 56" in r.stdout
          and any("client joined as 1" in l for l in probe_lines)
          and any("remote_inputs_with_movement=" in l and "remote_inputs_with_movement=0" not in l for l in probe_lines)
          and "snaps 0 " not in r.stdout)
    return check("Python client -> Godot host", ok, detail)


def godot_to_godot_through_the_relay() -> bool:
    relay = start([PY, "-u", "-m", "ballbrawlla.net.relay_server", "--bind", "127.0.0.1", "--port", "50970"])
    if not wait_listening(50970):
        return check("Godot host + Godot joiner through the relay", False, "the relay never started listening")
    host = start([GODOT, "--headless", "--path", "godot", "-s", "res://tools/net_probe.gd", "--", "host", "50963", "field_03", "11",
                  "127.0.0.1:50970"])
    code = ""
    end = time.time() + 15
    buf = ""
    import select
    while time.time() < end and not code:
        if select.select([host.stdout], [], [], 0.5)[0]:
            line = host.stdout.readline()
            buf += line
            if line.startswith("PROBE invite code "):
                code = line.split()[-1].strip()
            if "room-error" in line:
                break
    if not code:
        return check("Godot host + Godot joiner through the relay", False, "no invite code was printed: " + buf[-300:])
    lines = probe("joincode", "127.0.0.1:50970", code, timeout=40)
    try:
        out, _ = host.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        host.kill()
        out = ""
    host_lines = [l for l in (buf + out).splitlines() if l.startswith("PROBE")]
    detail = f"code {code} | " + " | ".join(lines + host_lines)
    ok = (any("joined pid=1" in l and "level_ok=true" in l and "snaps=" in l and "snaps=0" not in l for l in lines)
          and any("client joined as 1" in l for l in host_lines))
    ok = ok and relay.poll() is None
    return check("Godot host + Godot joiner through the relay", ok, detail)


def godot_discovery() -> bool:
    finder = start([GODOT, "--headless", "--path", "godot", "-s", "res://tools/net_probe.gd", "--", "discover", "6"])
    time.sleep(1.5)
    beacon = start([GODOT, "--headless", "--path", "godot", "-s", "res://tools/net_probe.gd", "--", "beacon", "4", "Test Game", "50964"])
    out, _ = finder.communicate(timeout=40)
    beacon.communicate(timeout=20)
    lines = [l for l in out.splitlines() if l.startswith("PROBE")]
    ok = any("name=Test Game" in l and "port=50964" in l and "level=Caverns" in l and "version=0.2.0" in l for l in lines)
    return check("Godot beacon -> Godot finder", ok, " | ".join(lines))


def main() -> int:
    global GODOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--godot", default=GODOT)
    GODOT = ap.parse_args().godot
    results = []
    try:
        for fn in (godot_joins_python_host, python_client_joins_godot_host, godot_to_godot_through_the_relay, godot_discovery):
            results.append(fn())
            stop_all()
    finally:
        stop_all()
    print(f"\n{sum(results)}/{len(results)} interop checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
