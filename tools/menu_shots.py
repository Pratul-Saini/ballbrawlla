"""Take screenshots of the Godot menu screens, to look at them.

    .venv/bin/python tools/menu_shots.py [--out /tmp]

Each shot opens the launcher in a real window, walks the given menu choices, and saves the picture. Needs a display.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"
ENV = {**os.environ, "BALLBRAWLLA_MUSIC": "off"}

SHOTS = [
    ("menu_play", "play"),
    ("menu_freeplay", "play,free"),
    ("menu_level_explore", "play,free,explore"),
    ("menu_level_two_players", "play,two"),
    ("menu_online", "play,online"),
    ("menu_join", "play,online,join on"),
    ("menu_code", "play,online,join with"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp")
    out = Path(ap.parse_args().out)
    for name, steps in SHOTS:
        target = out / f"g_{name}.png"
        target.unlink(missing_ok=True)
        p = subprocess.Popen([GODOT, "--path", "godot", "-s", "res://tools/shot.gd", "--", "res://scenes/launcher.tscn",
                              str(target), "2.2", steps], cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            p.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
        print(f"{name:26s} {'saved ' + str(target) if target.exists() else 'MISSING'}")


if __name__ == "__main__":
    main()
