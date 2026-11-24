"""Record whole football sessions from the Python game for the Godot port to replay.

Simple bots drive the humans so that real events happen (touchdowns, tags, interceptions, dead balls, game over,
play-call restarts, joins and leaves). The bots read the Python session to decide; what is recorded is only the
INPUTS they produced, so the Godot side replays them without any bot logic. Used by tools/export_parity.py; writes
godot/tests/data/sessions.json.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from ballbrawlla.config import Tuning  # noqa: E402
from ballbrawlla.input import Intent  # noqa: E402
from ballbrawlla.net.view import make_view  # noqa: E402
from ballbrawlla.session import Phase, Session  # noqa: E402
from ballbrawlla.world.level import load_level  # noqa: E402
from parity_traces import intent_array, intent_from_array, rle  # noqa: E402

SAMPLE_EVERY = 20


class _Rec:
    """Wraps the session RNG so every coin flip is recorded (the Godot side is told the results)."""

    def __init__(self, inner, log):
        self.inner, self.log = inner, log

    def choice(self, seq):
        v = self.inner.choice(seq)
        self.log.append(int(v))
        return v


class RecSession(Session):
    def __init__(self, *a, **k):
        self.flips: list = []
        super().__init__(*a, **k)

    def new_match(self):
        inner = self.rng
        self.rng = _Rec(inner, self.flips)
        try:
            super().new_match()
        finally:
            self.rng = inner


# ---------------------------------------------------------------- bots

def _sign(v: float, dead: float = 0.0) -> int:
    return 0 if abs(v) <= dead else (1 if v > 0 else -1)


def bot_intent(s: Session, pid: int, rng: random.Random, st: dict) -> Intent:
    team = s.team_of_human[pid]
    is_off = team == s.down.offense
    i = Intent()
    st["age"] = st.get("age", 0) + 1
    if rng.random() < 1 / 40:
        st["noise"] = rng.choice([-1, 0, 1])
    if s.phase is Phase.PLAY_CALL:
        c = s.call
        if is_off:
            if c.placing and st.get("wander"):
                if rng.random() < 1 / 12:
                    st["walk"] = rng.choice([-1, -1, 0, 1, 1])
                i.move_x = st.get("walk", 0)
                if rng.random() < 1 / 30:
                    i.jump_pressed = True
                    i.jump_held = rng.random() < 0.7
                i.vertical = -1 if rng.random() < 1 / 40 else (1 if i.jump_held else 0)
                i.z_pressed = c.qb_ok and rng.random() < 1 / 160
            elif c.placing:
                target = (c.qb_lo + c.qb_hi) / 2
                px = c.qb_player.center.x
                i.move_x = _sign(target - px, 25) or (st.get("noise", 0) if rng.random() < 0.3 else 0)
                if rng.random() < 1 / 50:
                    i.jump_pressed = True
                    i.jump_held = True
                i.z_pressed = c.qb_ok and st["age"] % 90 > 45 and rng.random() < 0.1
            else:
                r = rng.random()
                i.move_x = st.get("noise", 0) if r < 0.4 else 0
                i.vertical = rng.choice([-1, 0, 0, 1]) if r > 0.8 else 0
                if rng.random() < 1 / 60:
                    qx, qy = c.qb_center().x, c.qb_center().y
                    ang = rng.uniform(0.4, 1.2)
                    reach = rng.choice([22, 36, 39, 39.9, 40.1, 41, 43, 47, 60, rng.uniform(40, 220)])
                    i.mouse = (qx + math.cos(ang) * reach * team.attack_dir, qy - math.sin(ang) * reach)
                    i.mouse_pressed = True
                    i.mouse_held = True
                    st["mouse"] = (i.mouse, 20)
                elif st.get("mouse") and st["mouse"][1] > 0:
                    i.mouse, n = st["mouse"]
                    i.mouse_held = True
                    st["mouse"] = (i.mouse, n - 1)
                if rng.random() < 1 / 80:
                    i.aim_stick = (rng.uniform(-1, 1), rng.uniform(-1, 1))
                i.x_pressed = rng.random() < 0.025
                i.z_pressed = i.z_pressed or rng.random() < 0.004
                i.button_pressed = rng.random() < 0.004
        elif st.get("wander"):
            if rng.random() < 1 / 12:
                st["walk"] = rng.choice([-1, -1, 0, 1, 1])
            i.move_x = st.get("walk", 0)
            if rng.random() < 1 / 30:
                i.jump_pressed = True
                i.jump_held = rng.random() < 0.7
            i.vertical = -1 if rng.random() < 1 / 40 else (1 if i.jump_held else 0)
            i.z_pressed = c.def_ok and rng.random() < 1 / 160
        else:
            target = (c.def_lo + c.def_hi) / 2
            px = c.def_player.center.x
            i.move_x = _sign(target - px, 25) or (st.get("noise", 0) if rng.random() < 0.3 else 0)
            if rng.random() < 1 / 60:
                i.jump_pressed = True
                i.jump_held = True
            r = rng.random()
            i.z_pressed = c.def_ok and st["age"] % 90 > 40 and r < 0.1
            i.x_pressed = c.def_ok and 0.1 <= r < 0.103
            i.button_pressed = c.def_ok and 0.2 <= r < 0.203
    elif s.phase in (Phase.PRE_THROW, Phase.LIVE):
        g = s.game
        wr = g.players[0]
        df = g.players[1] if len(g.players) > 1 else None
        me = wr if is_off else df
        if me is None:
            return i
        ball = g.ball
        carrier = ball.held_by
        goal_dir = team.attack_dir
        if carrier is me:
            i.move_x = goal_dir if rng.random() > 0.05 else st.get("noise", 0)
            if rng.random() < 1 / 22 or (abs(me.body.vel.x) < 1 and rng.random() < 0.3):
                i.jump_pressed = True
                i.jump_held = True
        elif carrier is None or s.phase is Phase.PRE_THROW:
            tx = ball.pos.x if carrier is None else (s.qb.center.x + 120 * goal_dir)
            dx = tx - me.center.x
            i.move_x = _sign(dx, 8) or st.get("noise", 0)
            if (ball.pos.y < me.center.y - 20 and abs(dx) < 140 and rng.random() < 0.25) or rng.random() < 1 / 45:
                i.jump_pressed = True
                i.jump_held = True
            i.z_pressed = carrier is None and me.center.distance_to(ball.pos) < 85 and rng.random() < 0.5
        else:   # the other side has it: chase and tag
            dx = carrier.center.x - me.center.x
            i.move_x = _sign(dx, 8)
            if rng.random() < 1 / 28 or (carrier.center.y < me.center.y - 30 and rng.random() < 0.2):
                i.jump_pressed = True
                i.jump_held = True
            i.z_pressed = me.center.distance_to(carrier.center) < 55 and rng.random() < 0.6
        if rng.random() < 1 / 120:
            i.vertical = -1
        if me.state.name == "aiming" and rng.random() < 0.3:
            i.x_pressed = True
    return i


# ---------------------------------------------------------------- recording

def snapshot(s: Session) -> dict:
    out = {"ph": s.phase.value, "tick": s.tick, "down": [s.down.number, int(s.down.offense)],
           "spawn": ("region" if s.down.offense_picks_spawn else "fixed"),
           "score": [s.match.score[0], s.match.score[1]], "winner": -1 if s.match.winner is None else int(s.match.winner),
           "humans": [int(t) for t in s.team_of_human], "msg": s.message, "timer": s.timer, "los": s.los_x,
           "loose": s.loose_timer, "res": None if s.result is None else s.result.outcome.value,
           "conn": [int(c) for c in s.connected]}
    if s.phase is Phase.PLAY_CALL and s.call is not None:
        c = s.call
        out["call"] = [c.qb_spot.x, c.qb_spot.y, int(c.qb_ok), int(c.placing), c.aim_angle, c.aim_power,
                       int(c.offense_locked), int(c.defense_locked), c.restarts, c.timer, c.def_spot.x, c.def_spot.y,
                       int(c.def_ok), c.qb_lo, c.qb_hi, c.def_lo, c.def_hi,
                       c.qb_player.body.pos.x, c.qb_player.body.pos.y, c.qb_player.body.vel.x, c.qb_player.body.vel.y,
                       c.qb_player.state.name, c.def_player.body.pos.x, c.def_player.body.pos.y,
                       c.def_player.body.vel.x, c.def_player.body.vel.y, c.def_player.state.name]
    if s.game is not None and s.phase in (Phase.PRE_THROW, Phase.LIVE, Phase.DEAD):
        g = s.game
        rows = []
        for p in list(g.players) + [s.qb]:
            rows.append([p.body.pos.x, p.body.pos.y, p.body.vel.x, p.body.vel.y, p.h, p.facing, p.state.name,
                         int(p.held_ball is not None), p.last_ground.x, p.last_ground.y, p.pid])
        b = g.ball
        out["game"] = {"actors": rows, "ball": [b.pos.x, b.pos.y, b.vel.x, b.vel.y, int(b.resting),
                                                -1 if b.held_by is None else b.held_by.pid]}
    return out


def views(s: Session) -> dict:
    """The view every human would receive over the network, and the shared-screen view (what a client's screen draws)."""
    out = {str(pid): make_view(s, pid) for pid in range(s.humans)}
    out["L"] = make_view(s, 0, local=True)
    return out


def run(name: str, level: str, humans: int, seed: int, ticks: int, tuning: dict | None = None, defender: bool = True,
        events: dict | None = None, wander: bool = False) -> dict:
    t = Tuning(**(tuning or {}))
    s = RecSession(load_level(ROOT / "levels" / f"{level}.json"), t, humans=humans, seed=seed, defender=defender)
    events = events or {}
    rng = random.Random(seed * 7919 + 13)
    states = [{"wander": wander} for _ in range(humans)]
    frames, rows, evlog, outcomes, phases = [], [], [], set(), set()
    view_frames = []
    if humans == 2:
        evlog.append([-1, "connect", 1])   # before the first tick
        s.set_connected(1, True)
    for tick in range(ticks):
        for ev in events.get(tick, []):
            evlog.append([tick, ev[0], ev[1]])
            if ev[0] == "connect":
                s.set_connected(ev[1], True)
            elif ev[0] == "disconnect":
                s.set_connected(ev[1], False)
            elif ev[0] == "new_match":
                s.new_match()
        row = [intent_array(bot_intent(s, pid, rng, states[pid])) if s.phase is not Phase.WAITING else
               intent_array(Intent()) for pid in range(humans)]
        rows.append(row)
        s.step([intent_from_array(r) for r in row], t.dt)
        phases.add(s.phase.value)
        if s.result is not None:
            outcomes.add(s.result.outcome.value)
        every = (3 if wander else 12) if s.phase is Phase.PLAY_CALL else SAMPLE_EVERY
        if tick % every == 0 or tick == ticks - 1:
            frames.append([tick, snapshot(s)])
        if tick % 120 == 0 and not name.startswith("wander"):
            view_frames.append([tick, views(s)])
    return {"level": level, "humans": humans, "defender": defender, "tuning": tuning or {}, "events": evlog,
            "flips": [int(x) for x in s.flips], "inputs": rle(rows), "frames": frames, "views": view_frames,
            "outcomes": sorted(outcomes), "phases": sorted(phases)}


# The default game no longer throws; the legacy scenarios pin throwing on so the throw/catch code stays compared.
LEGACY = {"throw_enabled": True}
FAST = {**LEGACY, "pre_throw_seconds": 1.2, "play_call_seconds": 5.0, "result_pause_seconds": 0.4, "loose_ball_seconds": 1.2}
# No-throw scenarios: default tuning plus a short route window.
ROUTE = {"route_window_seconds": 1.2, "play_call_seconds": 5.0, "result_pause_seconds": 0.4}

SCENARIOS = [
    # name, level, humans, seed, ticks, tuning, defender, events
    ("practice_a", "field_01", 1, 1, 7000, {**FAST, "touchdowns_to_win": 3}, True, None),
    ("practice_b", "field_03", 1, 2, 7000, {**FAST}, True, None),
    ("catch_practice_a", "field_01", 1, 3, 7000, {**FAST, "touchdowns_to_win": 2}, False, None),
    ("catch_practice_b", "field_05", 1, 4, 8000, {**FAST}, False, None),
    ("versus_a", "field_01", 2, 5, 9000, {**FAST, "touchdowns_to_win": 2}, True, None),
    ("versus_b", "field_01", 2, 6, 9000, {**FAST}, True, None),
    ("versus_c", "field_09", 2, 7, 9000, {**FAST, "touchdowns_to_win": 2}, True, None),
    ("versus_d", "field_14", 2, 8, 9000, {**FAST, "downs_per_possession": 2}, True, None),
    ("versus_e", "field_01", 2, 9, 9000, {**LEGACY, "play_call_seconds": 3.0, "pre_throw_seconds": 2.0, "result_pause_seconds": 0.4}, True, None),
    ("versus_leave_and_rejoin", "field_01", 2, 10, 6000, {**FAST}, True,
     {1500: [("disconnect", 1)], 1800: [("connect", 1)], 3600: [("new_match", 0)]}),
    ("versus_f", "field_02", 2, 11, 9000, {**FAST, "touchdowns_to_win": 2}, True, None),
    ("versus_g", "field_12", 2, 12, 9000, {**FAST, "touchdowns_to_win": 2}, True, None),
    # Wanderers never settle quickly: they walk across platform edges and jump, so "standing on a platform edge"
    # and "is this spot acceptable" are decided at many positions. Long play calls give them time.
    # Seeds found by searching for a pick six (the defender catches and runs it back), which random play rarely produces.
    ("pick_six_a", "field_12", 2, 33, 7000, {**FAST, "touchdowns_to_win": 3}, True, None),
    ("pick_six_b", "field_01", 2, 30, 7000, {**FAST, "touchdowns_to_win": 3}, True, None),
    ("wander_a", "field_01", 2, 21, 3500, {**FAST, "play_call_seconds": 40.0}, True, None),
    ("wander_b", "field_05", 2, 22, 3500, {**FAST, "play_call_seconds": 40.0}, True, None),
    ("wander_c", "field_09", 1, 23, 3500, {**FAST, "play_call_seconds": 40.0}, True, None),
    ("wander_d", "field_14", 2, 24, 3500, {**FAST, "play_call_seconds": 40.0}, True, None),
    # No throwing: play call, route window (line of scrimmage locked), live run to the end zone.
    ("route_practice_a", "field_01", 1, 41, 7000, {**ROUTE, "touchdowns_to_win": 3}, True, None),
    ("route_catch_practice", "field_05", 1, 42, 7000, {**ROUTE}, False, None),
    ("route_versus_a", "field_01", 2, 43, 9000, {**ROUTE, "touchdowns_to_win": 2}, True, None),
    ("route_versus_b", "field_09", 2, 44, 9000, {**ROUTE, "touchdowns_to_win": 2}, True, None),
    ("route_versus_c", "field_14", 2, 45, 9000, {**ROUTE, "touchdowns_to_win": 2}, True, None),
]


def all_sessions() -> dict:
    return {n: run(n, lv, h, sd, tk, tu, df, ev, wander=n.startswith("wander")) for n, lv, h, sd, tk, tu, df, ev in SCENARIOS}


if __name__ == "__main__":
    allo, allp = set(), set()
    for name, tr in all_sessions().items():
        allo |= set(tr["outcomes"])
        allp |= set(tr["phases"])
        print(f"{name:26s} flips={tr['flips']!s:14s} outcomes: {', '.join(tr['outcomes']) or '-'}")
    print("ALL outcomes reached:", sorted(allo))
    print("ALL phases reached:  ", sorted(allp))
