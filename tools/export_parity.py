"""Export data from the Python game so the Godot port can be checked against it.

    .venv/bin/python tools/export_parity.py

Writes godot/tests/data/*.json (parity data the GDScript tests compare against) and regenerates the field list of
godot/scripts/tuning.gd from src/ballbrawlla/config.py, so the two cannot drift by a typo. Run it again whenever the
Python game's numbers change; the Godot tests then say exactly what no longer matches.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballbrawlla.config import Tuning  # noqa: E402
from ballbrawlla.world.level import load_level  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import parity_launch  # noqa: E402
import parity_rules  # noqa: E402
import parity_sessions  # noqa: E402
import parity_traces  # noqa: E402

DATA = ROOT / "godot" / "tests" / "data"
GD_TYPES = {"int": "int", "float": "float", "bool": "bool"}


def tuning_json() -> dict:
    t = Tuning()
    out = {f.name: getattr(t, f.name) for f in dataclasses.fields(Tuning)}
    out["_derived"] = {"dt": t.dt, "pickup_buffer_ticks": t.pickup_buffer_ticks,
                       "pickup_grace_ticks": t.pickup_grace_ticks}
    return out


def tuning_gd() -> str:
    """Turn the Tuning dataclass body into GDScript `var` lines, keeping every comment."""
    src = (ROOT / "src" / "ballbrawlla" / "config.py").read_text().splitlines()
    start = next(i for i, l in enumerate(src) if l.startswith("class Tuning"))
    lines = ["# GENERATED from src/ballbrawlla/config.py by tools/export_parity.py. Edit the Python file and rerun",
             "# the tool; tests/test_tuning.gd checks every value against the Python game.",
             "extends RefCounted",
             "",
             "## Every tunable number in one place. Units: pixels, seconds, degrees. y is down, so \"up\" is -y.",
             ""]
    for line in src[start + 1:]:
        if line.startswith("    @property"):
            break
        m = re.match(r"^    (\w+): (int|float|bool) = ([^#]+?)\s*(#.*)?$", line)
        if m:
            name, typ, val, comment = m.groups()
            val = {"True": "true", "False": "false"}.get(val, val)
            lines.append(f"var {name}: {GD_TYPES[typ]} = {val}" + (f"  {comment}" if comment else ""))
        elif line.strip().startswith("#"):
            lines.append(line.strip())
        elif not line.strip():
            lines.append("")
    lines += [
        "",
        "func dt() -> float:",
        "\treturn 1.0 / physics_hz",
        "",
        "func pickup_buffer_ticks() -> int:",
        "\treturn maxi(0, int(ceil(pickup_buffer_time * physics_hz - 1e-9)))",
        "",
        "func pickup_grace_ticks() -> int:",
        "\treturn maxi(0, int(ceil(pickup_grace_time * physics_hz - 1e-9)))",
        "",
        "## Every value as a Dictionary, for the host to send to a joining player (the \"tuning\" in the welcome message).",
        "func to_dict() -> Dictionary:",
        "\tvar out := {}",
        "\tfor p in get_property_list():",
        "\t\tif p.usage & PROPERTY_USAGE_SCRIPT_VARIABLE:",
        "\t\t\tout[p.name] = get(p.name)",
        "\treturn out",
        "",
        "## Take the host's values (JSON turns every number into a float, so convert to each field's own type).",
        "func apply_dict(d: Dictionary) -> void:",
        "\tfor k in d:",
        "\t\tvar cur = get(k)",
        "\t\tif cur == null:",
        "\t\t\tcontinue",
        "\t\tif typeof(cur) == TYPE_BOOL:",
        "\t\t\tset(k, bool(d[k]))",
        "\t\telif typeof(cur) == TYPE_INT:",
        "\t\t\tset(k, int(d[k]))",
        "\t\telse:",
        "\t\t\tset(k, float(d[k]))",
        "",
    ]
    return "\n".join(lines)


def levels_json() -> dict:
    """What Python's Level looks like after loading, for every level file: the GDScript loader must match it."""
    out = {}
    for path in sorted((ROOT / "levels").glob("*.json")):
        lv = load_level(path)
        out[path.stem] = {
            "name": lv.name, "width": lv.width, "height": lv.height, "wall_thickness": lv.wall_thickness,
            "yard_px": lv.yard_px,
            "player_spawns": [[s.x, s.y] for s in lv.player_spawns],
            "ball_spawn": [lv.ball_spawn.x, lv.ball_spawn.y],
            "solids": [[r.x, r.y, r.w, r.h] for r in lv.solids],
            "thin": [[r.x, r.y, r.w, r.h] for r in lv.thin],
        }
    return out


def copy_levels() -> int:
    """The Godot project carries its own copy of the levels (a symlink is unreliable on Windows)."""
    dest = ROOT / "godot" / "levels"
    dest.mkdir(exist_ok=True)
    n = 0
    for path in sorted((ROOT / "levels").glob("*.json")):
        (dest / path.name).write_bytes(path.read_bytes())
        n += 1
    return n


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "tuning.json").write_text(json.dumps(tuning_json(), indent=1, sort_keys=True) + "\n")
    (ROOT / "godot" / "scripts" / "tuning.gd").write_text(tuning_gd())
    (DATA / "levels.json").write_text(json.dumps(levels_json(), sort_keys=True) + "\n")
    (DATA / "traces.json").write_text(json.dumps(parity_traces.all_traces(), separators=(",", ":")) + "\n")
    (DATA / "rules.json").write_text(json.dumps(parity_rules.all_rules(), separators=(",", ":")) + "\n")
    (DATA / "sessions.json").write_text(json.dumps(parity_sessions.all_sessions(), separators=(",", ":")) + "\n")
    (DATA / "launch.json").write_text(json.dumps(parity_launch.all_launch(), separators=(",", ":")) + "\n")
    n = copy_levels()
    print(f"wrote tuning.json, levels.json, traces.json, rules.json, sessions.json, launch.json, tuning.gd, and copied {n} levels into godot/levels/")


if __name__ == "__main__":
    main()
