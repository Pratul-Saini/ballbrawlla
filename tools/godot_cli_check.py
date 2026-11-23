"""Run the Godot app with command-line options, headless, and say what each one did.

    .venv/bin/python tools/godot_cli_check.py [--godot /path/to/Godot]

A launch that cannot work must print one line and exit with status 2 (like the Python game). A launch that can work
keeps running, so it is stopped after a few seconds and reported as "running". Exits 0 if every case behaves as expected.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"
ENV = {**os.environ, "BALLBRAWLLA_MUSIC": "off"}
ENV.pop("BALLBRAWLLA_RELAY", None)

# (options, expected exit status or None for "keeps running", text the one-line message must contain)
CASES = [
    (["--level=field_99"], 2, "not found"),
    (["--level=arena_01"], 2, "football field"),
    (["--catch", "--level=arena_01"], 2, "football field"),
    (["--local", "--level=arena_01"], 2, "football field"),
    (["--sandbox", "--level=field_99"], 2, "not found"),
    (["--join-code=ABC-123"], 2, "can't contain 1"),
    (["--join-code=KQ7-M3X"], 2, "relay server code"),
    (["--join-code=2JDH-GC8B"], 2, "typo"),
    (["--host", "--no-router", "--level=field_01", "--port=50977"], None, ""),
    (["--host", "--local"], 2, "only one"),
    (["--join=1.2.3.4", "--catch"], 2, "only one"),
    (["--level=field_01", "--port=abc"], 2, "number"),
    (["--join=has space"], 2, "spaces"),
    (["--level=field_01"], None, ""),
    (["--catch", "--level=field_05"], None, ""),
    (["--local", "--level=field_09"], None, ""),
    (["--sandbox"], None, ""),
    (["--sandbox", "--level=field_01"], None, ""),
    ([], None, ""),
]


def run_case(godot: str, opts: list[str], expect_exit, text: str) -> tuple[bool, str]:
    p = subprocess.Popen([godot, "--headless", "--path", "godot", "--", *opts], cwd=ROOT, env=ENV,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:      # read while waiting: on Windows Godot doesn't exit until its output is read
        out, _ = p.communicate(timeout=20 if expect_exit is not None else 7)
        running, code = False, p.returncode
    except subprocess.TimeoutExpired:
        running, code = True, None
        p.terminate()
        try:
            out, _ = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            out, _ = p.communicate()
    lines = [l for l in out.splitlines() if l.startswith("ballbrawlla:")]
    errors = [l for l in out.splitlines() if "SCRIPT ERROR" in l or "Parse Error" in l]
    detail = f"exit={code if code is not None else 'running'}  {(lines[0] if lines else '')[:110]}"
    if errors:
        return False, detail + "  SCRIPT ERROR: " + errors[0][:90]
    if expect_exit is None:
        return running and not lines, detail
    return (code == expect_exit and len(lines) == 1 and text in lines[0]), detail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--godot", default=GODOT)
    godot = ap.parse_args().godot
    bad = 0
    for opts, expect_exit, text in CASES:
        ok, detail = run_case(godot, opts, expect_exit, text)
        bad += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {' '.join(opts) or '(no options: the launcher)':44s} {detail}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} command-line cases behaved as expected")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
