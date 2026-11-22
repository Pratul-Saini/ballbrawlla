"""Check and draw the tall-field layout in docs/level-design/layout.json.

    python tools/layout_tools.py check      validate with the real physics
    python tools/route_solver.py            routes and chase measurements (uses this layout)

The layout file describes the LEFT half. The right half mirrors it (x' = width - x - w).
Everything here is a design aid: it does not change the game.
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ballbrawlla.config import Tuning
from ballbrawlla.entities.player import Player
from ballbrawlla.input import Intent
from ballbrawlla.physics.shapes import AABB
from ballbrawlla.physics.vec import Vector2
from ballbrawlla.rules.down import defender_x_range, possession_start, qb_x_range
from ballbrawlla.rules.field import Field
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import Level, Platform

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "docs" / "level-design" / "layout.json"
OUT = ROOT / "docs" / "level-design"
T = Tuning()
DT = T.dt



class Layout:
    def __init__(self, path: Path = LAYOUT) -> None:
        d = json.loads(path.read_text())
        a = d["arena"]
        self.W, self.H, self.WALL = a["width"], a["height"], a["wall"]
        self.yard = a.get("yard_px", 24)
        self.floor = self.H - self.WALL
        self.thick = d["thin_thickness"]
        self.frames, self.zones, self.moves = d["frames"], d["zones"], d["moves"]
        self.pieces = d["pieces"]

    def rect(self, p: dict) -> AABB:
        h = p.get("h", self.thick)
        return AABB(p["x"], self.floor - p["top"], p["w"], h)

    def mirrored(self, p: dict) -> dict:
        q = dict(p)
        q["x"] = self.W - p["x"] - p["w"]
        q["id"] = p["id"] + "'"
        return q

    def level(self, mirror: bool = True, only: set[str] | None = None) -> tuple[Level, dict[int, str]]:
        ps = [p for p in self.pieces if only is None or p["id"] in only]
        mid = self.W / 2
        twins = [self.mirrored(p) for p in ps if abs(p["x"] + p["w"] / 2 - mid) > 1e-6]  # centred pieces are their own twin
        allp = ps + (twins if mirror else [])
        self.all_pieces = allp
        plats = [Platform(self.rect(p), platform_type=p["type"]) for p in allp]
        lv = Level(self.W, self.H, platforms=plats, wall_thickness=self.WALL, yard_px=self.yard)
        names = {id(pl.rect): p["id"] for pl, p in zip(lv.platforms[4:], allp)}
        return lv, names

    def frame_of(self, p: dict) -> dict:
        cx = p["x"] + p["w"] / 2
        return next((f for f in self.frames if f["x0"] <= cx < f["x1"]), self.frames[-1])


# ------------------------------------------------------------------ physics probes

def _settle(lv: Level, x: float, top: float) -> Player:
    p = Player(Vector2(x, top - T.player_height / 2), T)
    for _ in range(30):
        p.update(Intent(), DT, lv.solids, None, lv.thin)
    return p


def _name_under(lv: Level, names: dict[int, str], p: Player) -> str | None:
    b = p.box
    for pl in lv.platforms:
        r = pl.rect
        if abs(b.bottom - r.top) < 1e-3 and b.left < r.right and b.right > r.left:
            return names.get(id(r), "floor" if pl.kind == "bound" else None)
    return None


def _label(lv, names, p: Player, pocket_x1: float | None) -> str | None:
    """Name of what the player stands on; the floor inside the end zone pocket is called 'pocket'."""
    g = _name_under(lv, names, p)
    if g == "floor" and pocket_x1 is not None and p.center.x < pocket_x1:
        return "pocket"
    return g


def landings(lv, names, start: str, x: float, top: float, pocket_x1: float | None = None):
    """Where real jumps and walk-offs from (start, x) land: {(name, how): ticks}."""
    out: dict[tuple[str, str], int] = {}

    def record(g, how, ticks):
        if g and g != start:
            k = (g, how)
            out[k] = min(ticks, out.get(k, 10**9))

    for d in (-1, 1):
        p = _settle(lv, x, top)  # walk off the edge
        for t in range(1, 400):
            p.update(Intent(move_x=d), DT, lv.solids, None, lv.thin)
            if t > 3 and p.contacts.on_ground and _label(lv, names, p, pocket_x1) not in (None, start):
                record(_label(lv, names, p, pocket_x1), "drop", t)
                break
    for d, hold, dj in itertools.product((-1, 0, 1), (6, 70), (None, 14, 28, 42)):
        if d == 0 and dj is not None:
            continue
        p = _settle(lv, x, top)
        p.update(Intent(jump_pressed=True, vertical=1, move_x=d), DT, lv.solids, None, lv.thin)
        for t in range(1, 260):
            p.update(Intent(move_x=d, vertical=1 if t < hold else 0, jump_pressed=(dj == t)),
                     DT, lv.solids, None, lv.thin)
            if t > 4 and p.contacts.on_ground and p.vel.y >= 0:
                record(_label(lv, names, p, pocket_x1), "jump" if dj is None else "double jump", t)
                break
    return out


def move_graph(lay: Layout):
    """Edges between platforms (and the floor) from real physics, plus the declared special moves."""
    lv, names = lay.level(mirror=False)
    nodes = {p["id"]: p for p in lay.pieces}
    pocket_x1 = next((z["x1"] for z in lay.zones if z["id"] == "pocket"), None)
    edges: dict[tuple[str, str], tuple[str, int]] = {}
    rank = {"drop": 0, "jump": 1, "double jump": 2}
    for src in ["floor"] + [p["id"] for p in lay.pieces]:
        if src == "floor":
            top, xs = 0, range(60, int(lay.W / 2 + 200), 40)
        else:
            p = nodes[src]
            top = p["top"]
            xs = sorted({p["x"] + 2, p["x"] + p["w"] / 2, p["x"] + p["w"] - 2})
        for x in xs:
            for (dst, how), ticks in landings(lv, names, src, x, lay.floor - top, pocket_x1).items():
                if dst in ("floor", "pocket") or dst in nodes:
                    k = (src, dst)
                    if k not in edges or (rank[how], ticks) < (rank[edges[k][0]], edges[k][1]):
                        edges[k] = (how, ticks)
    return edges


def with_declared_moves(lay: Layout, edges):
    """Physics edges plus the hand-checked special moves (the macros cannot cling or slide)."""
    out = dict(edges)
    for m in lay.moves:
        key = (m["from"], m["to"])
        if m["how"] in ("wall climb", "slide") or key not in out:
            out[key] = (m["how"], 0)
        elif key in out:
            out[key] = (m["how"], out[key][1])  # physics confirmed it: keep the declared name
    return out


# ------------------------------------------------------------------ check

def check(lay: Layout) -> int:
    bad = 0

    def report(ok, msg):
        nonlocal bad
        print(("  ok   " if ok else "  FAIL ") + msg)
        bad += 0 if ok else 1

    rects = {p["id"]: lay.rect(p) for p in lay.pieces}
    inside = all(r.left >= lay.WALL and r.right <= lay.W - lay.WALL and r.top >= lay.WALL and r.bottom <= lay.floor
                 for r in rects.values())
    report(inside, "every piece inside the playable area")
    cap = lay.floor - 1000
    report(all(r.top >= cap for r in rects.values()), f"platform tops at or below the 1000 px cap (y >= {cap})")
    lv, names = lay.level()
    allr = [(names[id(pl.rect)], pl.rect) for pl in lv.platforms[4:]]
    clash = [(a, b) for (a, ra), (b, rb) in itertools.combinations(allr, 2) if ra.overlaps(rb)]
    report(not clash, f"no overlaps (both halves){'' if not clash else ': ' + str(clash)}")
    mid = lay.W / 2
    straddle = [k for k, r in rects.items() if r.left < mid < r.right]
    sym = all(abs((lay.W - r.right) - r.left) < 1e-6 for k, r in rects.items() if k in straddle)
    report(sym, f"pieces crossing midfield are symmetric about it: {straddle or 'none'}")

    f = Field(lv, T)
    for team in (Team.LEFT, Team.RIGHT):
        d = possession_start(team, T)
        lo, hi = qb_x_range(d, f)
        dlo, dhi = defender_x_range(d, f, T)
        nq = sum(1 for s in f.surfaces if s.x1 >= lo and s.x0 <= hi)
        nd = sum(1 for s in f.surfaces if s.x1 >= dlo and s.x0 <= dhi)
        report(nq >= 2 and nd >= 3, f"{team.display}: {nq} QB-region surfaces, {nd} Defender-range surfaces")

    print("  ...running physics reachability (a few seconds)")
    phys = move_graph(lay)
    usable = dict(phys)
    for m in lay.moves:
        if m["how"] in ("wall climb", "slide"):
            usable[(m["from"], m["to"])] = (m["how"], 0)
    seen, queue = {"floor"}, ["floor"]
    while queue:
        a = queue.pop()
        for (s, d), _ in usable.items():
            if s == a and d not in seen and d != "floor":
                seen.add(d)
                queue.append(d)
    missing = [p["id"] for p in lay.pieces if p["id"] not in seen]
    report(not missing, f"every piece reachable from the floor{'' if not missing else ': missing ' + str(missing)}")
    for m in lay.moves:
        if m["how"] in ("wall climb", "slide"):
            print(f"  note  '{m['how']}' {m['from']} -> {m['to']} is taken from the earlier hand tests (the search cannot cling or slide)")
        else:
            ok = (m["from"], m["to"]) in phys
            report(ok, f"declared {m['how']} {m['from']} -> {m['to']} confirmed by real jumps ({m['note']})")
    return bad


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    lay = Layout()
    if cmd == "check":
        print("layout check:")
        sys.exit(1 if check(lay) else 0)
    else:
        sys.exit(f"unknown command {cmd!r}: use check (routes: python tools/route_solver.py)")
