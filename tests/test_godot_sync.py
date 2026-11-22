"""The Godot port must not drift from this Python game. If one of these fails, run:
    .venv/bin/python tools/export_parity.py
and commit the result (then run godot/run_tests.sh to see what the port no longer matches)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import export_parity  # noqa: E402


def test_godot_has_a_copy_of_every_level_and_it_is_identical():
    names = sorted(p.name for p in (ROOT / "levels").glob("*.json"))
    copies = sorted(p.name for p in (ROOT / "godot" / "levels").glob("*.json"))
    assert names == copies
    for name in names:
        assert (ROOT / "levels" / name).read_bytes() == (ROOT / "godot" / "levels" / name).read_bytes(), name


def test_tuning_parity_data_is_current():
    saved = json.loads((ROOT / "godot" / "tests" / "data" / "tuning.json").read_text())
    assert saved == export_parity.tuning_json()


def test_generated_tuning_script_is_current():
    assert (ROOT / "godot" / "scripts" / "tuning.gd").read_text() == export_parity.tuning_gd()


def test_level_parity_data_is_current():
    saved = json.loads((ROOT / "godot" / "tests" / "data" / "levels.json").read_text())
    assert saved == json.loads(json.dumps(export_parity.levels_json()))
