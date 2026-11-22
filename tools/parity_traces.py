"""Record simulation traces from the Python game for the Godot port to replay.

A scenario is: a level, a number of players, optional starting positions, and a list of per-tick inputs. Python runs
it with the real Game and writes the state every SAMPLE_EVERY ticks. The Godot test replays the same inputs and
compares. Inputs are stored (run-length encoded), never re-generated in GDScript, so there is no random-number
generator to keep in sync.

Used by tools/export_parity.py; writes godot/tests/data/traces.json.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballbrawlla.config import Tuning  # noqa: E402
from ballbrawlla.game import Game  # noqa: E402
from ballbrawlla.input import Intent  # noqa: E402
from ballbrawlla.world.level import load_level  # noqa: E402

SAMPLE_EVERY = 4


def intent_array(i: Intent) -> list:
    stick = None if i.aim_stick is None else [i.aim_stick[0], i.aim_stick[1]]
    mouse = None if i.mouse is None else [i.mouse[0], i.mouse[1]]
    return [i.move_x, i.vertical, int(i.jump_pressed), int(i.z_pressed), int(i.x_pressed), int(i.jump_held), stick,
            mouse, int(i.mouse_held), int(i.mouse_pressed), int(i.button_pressed)]


def intent_from_array(r: list) -> Intent:
    """Inverse of intent_array; rows shorter than 11 (the physics scenarios) have no mouse."""
    mouse = tuple(r[7]) if len(r) >= 11 and r[7] is not None else None
    return Intent(r[0], r[1], bool(r[2]), bool(r[3]), bool(r[4]), mouse=mouse,
                  mouse_held=bool(r[8]) if len(r) >= 11 else False,
                  mouse_pressed=bool(r[9]) if len(r) >= 11 else False,
                  button_pressed=bool(r[10]) if len(r) >= 11 else False,
                  jump_held=bool(r[5]), aim_stick=None if r[6] is None else tuple(r[6]))


def rle(rows: list) -> list:
    out: list = []
    for row in rows:
        if out and out[-1][1] == row:
            out[-1][0] += 1
        else:
            out.append([1, row])
    return out


def unrle(runs: list) -> list:
    return [row for n, row in runs for _ in range(n)]


def fuzz_inputs(seed: int, ticks: int, players: int) -> list:
    """Per tick, one intent per player. Holds change slowly (like a person) and presses are single-tick edges."""
    rng = random.Random(seed)
    state = [{"mx": 0, "down": 0, "jump_for": 0, "stick": None} for _ in range(players)]
    frames = []
    for _ in range(ticks):
        row = []
        for s in state:
            if rng.random() < 1 / 35:
                s["mx"] = rng.choice([-1, 0, 1, 1, -1])
            if rng.random() < 1 / 55:
                s["down"] = 0 if s["down"] else rng.choice([1, 1, 0])
            jump = rng.random() < 1 / 40
            if jump:
                s["jump_for"] = rng.choice([0, 5, 20, 60])
            held = s["jump_for"] > 0
            s["jump_for"] = max(0, s["jump_for"] - 1)
            if rng.random() < 1 / 120:
                s["stick"] = None if s["stick"] else [rng.uniform(-1, 1), rng.uniform(-1, 1)]
            row.append([s["mx"], -1 if s["down"] else (1 if held else 0), int(jump), int(rng.random() < 1 / 45),
                        int(rng.random() < 1 / 70), int(held), s["stick"]])
        frames.append(row)
    return frames


def script_inputs(segments: list, players: int) -> list:
    """segments: [(ticks, {field: value}) ...] applied to every player; fields: mx, v, jump (tick 0 only), z, x."""
    frames = []
    for ticks, f in segments:
        for k in range(ticks):
            row = []
            for _ in range(players):
                row.append([f.get("mx", 0), f.get("v", 0), int(f.get("jump", 0) and k == 0), int(f.get("z", 0) and k == 0),
                            int(f.get("x", 0) and k == 0), int(f.get("held", 0)), f.get("stick")])
            frames.append(row)
    return frames


SCENARIOS = [
    # name, level, players, setup, inputs
    ("fall_and_stand", "field_01", 1, {}, lambda: script_inputs([(240, {})], 1)),
    ("run_jump_slide_crawl", "field_01", 1, {}, lambda: script_inputs([
        (60, {"mx": 1}), (1, {"mx": 1, "jump": 1}), (30, {"mx": 1, "held": 1}), (60, {"mx": 1}),
        (20, {"mx": 1, "v": -1}), (40, {"v": -1}), (30, {"mx": 1, "v": -1}), (50, {}), (1, {"jump": 1}), (80, {})], 1)),
    ("double_jump_and_short_hop", "field_01", 1, {}, lambda: script_inputs([
        (50, {}), (1, {"jump": 1, "held": 1}), (12, {"held": 1}), (1, {"jump": 1, "mx": 1, "held": 1}), (40, {"mx": 1}),
        (60, {}), (1, {"jump": 1}), (6, {}), (90, {})], 1)),
    ("wall_cling_and_jump", "field_01", 1, {"players": [[60, 700]]}, lambda: script_inputs([
        (50, {"mx": -1}), (1, {"mx": -1, "jump": 1, "held": 1}), (60, {"mx": -1, "held": 1}), (40, {"mx": -1}),
        (1, {"mx": 1}), (50, {"mx": 1}), (60, {})], 1)),
    ("catch_aim_throw", "field_01", 1, {"players": [[420, 1000]], "ball": [[470, 1000], [0, 0]]}, lambda: script_inputs([
        (3, {}), (1, {"z": 1}), (20, {}), (1, {"z": 1}), (30, {"mx": 1}), (30, {"mx": -1, "v": 1}), (1, {"x": 1}),
        (200, {})], 1)),
    ("ball_bounces_and_rolls", "field_01", 1, {"players": [[100, 1000]], "ball": [[500, 400], [300, -200]]},
     lambda: script_inputs([(900, {})], 1)),
    ("two_players_one_ball", "field_01", 2, {"players": [[430, 1000], [520, 1000]], "ball": [[475, 960], [0, 0]]},
     lambda: script_inputs([(4, {}), (1, {"z": 1}), (150, {})], 2)),
]
for _seed, _level, _players, _ball in [
    (1, "field_01", 1, True), (2, "field_01", 2, True), (3, "field_03", 1, True), (4, "field_05", 1, True),
    (5, "field_05", 2, False), (6, "field_09", 1, True), (7, "field_14", 2, True), (8, "arena_01", 1, True),
    (9, "field_08", 1, False), (10, "field_12", 2, True), (11, "field_01", 1, False), (12, "field_10", 1, True),
]:
    SCENARIOS.append((f"fuzz_{_seed}_{_level}_{_players}p", _level, _players, {"near_ball": _ball},
                      (lambda s=_seed, p=_players: fuzz_inputs(s, 2400, p))))


def _corner_scenarios() -> None:
    """Drop the ball on the top corners of real solid platforms, at many horizontal offsets and speeds. Corner hits
    give surface normals at every angle, which is what the ball's 'resting' rule (normal pointing mostly up) and its
    bounce math depend on; flat-floor bounces alone never exercise that."""
    level = load_level(ROOT / "levels" / "field_01.json")
    solids = [p.rect for p in level.platforms if p.kind == "platform" and not p.is_thin and p.rect.w >= 40]
    rng = random.Random(77)
    for n in range(24):
        r = solids[rng.randrange(len(solids))]
        corner_x = r.x if rng.random() < 0.5 else r.right
        x = corner_x + rng.uniform(-16, 16)
        y = r.y - rng.uniform(40, 160)
        vx = rng.choice([0.0, rng.uniform(-260, 260)])
        SCENARIOS.append((f"corner_drop_{n}", "field_01", 1, {"players": [[100, 1000]], "ball": [[x, y], [vx, 0.0]]},
                          (lambda: script_inputs([(500, {})], 1))))


_corner_scenarios()


def _boundary_scenarios() -> None:
    """Straddle the thresholds the game cares about, so a number that is off by one cannot hide:
    the pickup radius (55 px) and the speed below which an impact stops the ball instead of bouncing (40 px/s).
    Placed on open floor of field_01 (x 704..1016 has no platform within 80 px above the floor)."""
    import math
    t = Tuning()
    level = load_level(ROOT / "levels" / "field_01.json")
    floor_y = level.height - 32
    center_y = floor_y - t.player_height / 2          # a player standing on the floor
    ball_y = floor_y - t.ball_radius                  # a ball resting on the floor
    dy = center_y - ball_y
    for r in level.solids[1:]:
        assert not (r.x < 1000 and r.right > 740 and r.bottom > floor_y - 80 and r.top < floor_y), "floor is not open"
    # The ball rests on the floor at a chosen straight-line distance from the player's center; Z is pressed at once.
    for dist in [50, 53, 54.5, 54.9, 55.1, 55.5, 56, 57, 60]:
        dx = math.sqrt(dist * dist - dy * dy)
        setup = {"players": [[760, center_y]], "ball": [[760 + dx, ball_y], [0, 0]], "expect_distance": dist}
        SCENARIOS.append((f"pickup_at_{str(dist).replace('.', '_')}px", "field_01", 1, setup,
                          (lambda: script_inputs([(2, {}), (1, {"z": 1}), (40, {})], 1))))
    # The ball drops onto the floor and hits at a chosen speed (gravity adds to the start speed before contact,
    # so start slower by exactly that amount). Speeds from clearly below to clearly above the 40 px/s rest speed.
    gain = t.ball_gravity * t.dt
    for v in [30, 36, 39, 39.9, 40.1, 41, 44, 52]:
        setup = {"players": [[200, center_y]], "ball": [[900, ball_y - 0.2], [0, v - gain]]}
        SCENARIOS.append((f"impact_at_{str(v).replace('.', '_')}pxs", "field_01", 1, setup,
                          (lambda: script_inputs([(240, {})], 1))))


_boundary_scenarios()


def snapshot(g: Game) -> dict:
    ps = []
    for p in g.players:
        c = p.contacts
        ps.append([p.body.pos.x, p.body.pos.y, p.body.vel.x, p.body.vel.y, p.h, p.facing, p.jumps_left,
                   p.control_lock, p.pickup_buffer, p.state.name,
                   int(c.on_ground) | int(c.on_ceiling) << 1 | int(c.wall_left) << 2 | int(c.wall_right) << 3,
                   int(p.held_ball is not None), p.aim_angle, p.aim_power, p.last_ground.x, p.last_ground.y])
    b = g.ball
    return {"p": ps, "b": [b.pos.x, b.pos.y, b.vel.x, b.vel.y, int(b.resting),
                           -1 if b.held_by is None else b.held_by.pid]}


def apply_setup(g: Game, setup: dict) -> None:
    for pid, (cx, cy) in enumerate(setup.get("players", [])):
        p = g.players[pid]
        p.body.pos.update(cx - p.w / 2, cy - p.h / 2)
        p.last_ground.update(cx, cy + p.h / 2)
    if "ball" in setup:
        (bx, by), (vx, vy) = setup["ball"]
        g.ball.body.pos.update(bx, by)
        g.ball.body.vel.update(vx, vy)
    elif setup.get("near_ball"):
        # Put the ball a short hop from the first player so pickups, aiming and throws actually happen.
        p = g.players[0]
        g.ball.body.pos.update(p.center.x + 60, p.center.y)


def run_scenario(name: str, level: str, players: int, setup: dict, inputs: list) -> dict:
    t = Tuning()
    g = Game(load_level(ROOT / "levels" / f"{level}.json"), t, players)
    apply_setup(g, setup)
    # What the GDScript side must reproduce: the final setup after apply_setup, written as plain positions.
    if "expect_distance" in setup:
        d = g.players[0].center.distance_to(g.ball.pos)
        assert abs(d - setup["expect_distance"]) < 1e-9, f"{name}: starts {d} px away, wanted {setup['expect_distance']}"
    start = {"players": [[p.body.pos.x, p.body.pos.y] for p in g.players],
             "ball": [g.ball.body.pos.x, g.ball.body.pos.y, g.ball.body.vel.x, g.ball.body.vel.y]}
    frames = []
    states_seen = set()
    for tick, row in enumerate(inputs):
        g.step([intent_from_array(r) for r in row], t.dt)
        for p in g.players:
            states_seen.add(p.state.name)
        if tick % SAMPLE_EVERY == 0 or tick == len(inputs) - 1:
            frames.append([tick, snapshot(g)])
    return {"level": level, "players": players, "start": start, "inputs": rle(inputs), "frames": frames,
            "states_seen": sorted(states_seen)}


def all_traces() -> dict:
    return {name: run_scenario(name, level, players, setup, make())
            for name, level, players, setup, make in SCENARIOS}


if __name__ == "__main__":
    traces = all_traces()
    seen = set()
    for name, tr in traces.items():
        seen |= set(tr["states_seen"])
        print(f"{name:34s} {len(tr['frames']):4d} frames  states: {', '.join(tr['states_seen'])}")
    print("all states exercised:", sorted(seen))
