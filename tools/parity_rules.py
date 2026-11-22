"""Record the football rules (field, downs, match) from the Python game for the Godot port to be checked against.

Used by tools/export_parity.py; writes godot/tests/data/rules.json.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballbrawlla.config import Tuning  # noqa: E402
from ballbrawlla.rules.down import (  # noqa: E402
    ChooseInRegion, Down, FixedSpot, Outcome, PlayResult, defender_min_yards, defender_x_range, next_down,
    possession_start, qb_furthest_yards, qb_x_range,
)
from ballbrawlla.rules.field import Field, Spot  # noqa: E402
from ballbrawlla.rules.match import Match  # noqa: E402
from ballbrawlla.rules.teams import Team  # noqa: E402
from ballbrawlla.physics.vec import Vector2  # noqa: E402
from ballbrawlla.world.level import load_level  # noqa: E402


def _spot(s) -> list | None:
    return None if s is None else [s.x, s.y]


def field_data(t: Tuning) -> dict:
    """Per level: geometry, every standing surface, and many snap / spawn_spot / yard queries."""
    out = {}
    rng = random.Random(2024)
    for path in sorted((ROOT / "levels").glob("*.json")):
        lv = load_level(path)
        try:
            f = Field(lv, t)
        except ValueError as e:
            out[path.stem] = {"error": str(e)}
            continue
        queries = []
        for _ in range(60):
            px, py = rng.uniform(0, lv.width), rng.uniform(0, lv.height)
            lo = rng.uniform(0, lv.width)
            hi = lo + rng.choice([0, 30, 200, 900, lv.width])
            queries.append({
                "p": [px, py], "range": [lo, hi],
                "snap": _spot(f.snap(Vector2(px, py), lo, hi)),
                "spawn": _spot(f.spawn_spot(Spot(px, py), lo, hi)),
            })
        yards = []
        for team in (Team.LEFT, Team.RIGHT):
            for y in (-10, -3.5, 0, 1, 12.5, 50, 99, 100, 105):
                x = f.x_at(team, y)
                yards.append({"team": int(team), "yards": y, "x": x, "back": f.yards_from_goal(team, x),
                              "in_ez": f.in_end_zone(team, x), "range": list(f.x_range(team, y, y + 17))})
        out[path.stem] = {
            "yard_px": f.yard_px, "end_zone_px": f.end_zone_px, "inner_left": f.inner_left,
            "inner_right": f.inner_right, "floor_y": f.floor_y,
            "goal": {"0": f.goal_line_x(Team.LEFT), "1": f.goal_line_x(Team.RIGHT)},
            "surfaces": [[s.x0, s.x1, s.y] for s in f.surfaces], "queries": queries, "yards": yards,
        }
    return out


def _down_json(d: Down) -> dict:
    q = d.qb_spawn
    spawn = ({"kind": "region", "start": q.start_yards, "end": q.end_yards} if isinstance(q, ChooseInRegion)
             else {"kind": "fixed", "x": q.spot.x, "y": q.spot.y})
    return {"number": d.number, "offense": int(d.offense), "qb_spawn": spawn}


def down_data(t: Tuning) -> dict:
    lv = load_level(ROOT / "levels" / "field_01.json")
    f = Field(lv, t)
    spots = [Spot(f.x_at(Team.LEFT, 25), f.floor_y), Spot(f.x_at(Team.RIGHT, 3), f.floor_y),
             Spot(f.x_at(Team.LEFT, -4), f.floor_y)]       # the third one is inside an end zone
    transitions = []
    for number in range(1, t.downs_per_possession + 1):
        for offense in (Team.LEFT, Team.RIGHT):
            for spot in spots:
                down = Down(number, offense, FixedSpot(spot)) if number > 1 else possession_start(offense, t)
                for outcome in Outcome:
                    nxt, scorer = next_down(down, PlayResult(outcome, spot), t)
                    transitions.append({
                        "down": _down_json(down), "outcome": outcome.value, "spot": [spot.x, spot.y],
                        "next": _down_json(nxt), "scorer": -1 if scorer is None else int(scorer),
                    })
    ranges = []
    for number in (1, 2, 4):
        for offense in (Team.LEFT, Team.RIGHT):
            for spot in spots:
                down = Down(number, offense, FixedSpot(spot)) if number > 1 else possession_start(offense, t)
                ranges.append({
                    "down": _down_json(down), "qb_range": list(qb_x_range(down, f)),
                    "qb_furthest": qb_furthest_yards(down, f), "def_min": defender_min_yards(down, f, t),
                    "def_range": list(defender_x_range(down, f, t)),
                })
    return {"transitions": transitions, "ranges": ranges, "spots": [[s.x, s.y] for s in spots]}


def match_data(t: Tuning) -> list:
    """Scripted matches: a list of results applied in order, with the state after each one."""
    lv = load_level(ROOT / "levels" / "field_01.json")
    f = Field(lv, t)
    rng = random.Random(55)
    outcomes = list(Outcome)
    out = []
    for n in range(14):
        practice = n % 2 == 1
        first = Team.LEFT if n % 4 < 2 else Team.RIGHT
        m = Match.start(t, random.Random(0), practice=practice)
        if not practice:
            m.down = possession_start(first, t)          # the coin flip is injected, not replayed
        steps = []
        for _ in range(40):
            if m.winner is not None:
                break
            outcome = rng.choice(outcomes + [Outcome.TOUCHDOWN, Outcome.TAGGED, Outcome.TAGGED])
            spot = Spot(f.x_at(Team.LEFT, rng.uniform(0, 100)), f.floor_y)
            scorer = m.apply(PlayResult(outcome, spot))
            steps.append({"outcome": outcome.value, "spot": [spot.x, spot.y], "scorer": -1 if scorer is None else int(scorer),
                          "down": _down_json(m.down), "score": [m.score[Team.LEFT], m.score[Team.RIGHT]],
                          "winner": -1 if m.winner is None else int(m.winner), "human": int(m.human)})
        out.append({"practice": practice, "first": int(first), "steps": steps})
    return out


def all_rules() -> dict:
    t = Tuning()
    return {"field": field_data(t), "down": down_data(t), "match": match_data(t)}
