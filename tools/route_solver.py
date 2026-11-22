"""Finds routes through a layout and measures chases, using the real player physics.

    python tools/route_solver.py            solve routes and chases for docs/level-design/layout.json

Graph: nodes are standing spots (piece id or 'floor', x). Edges are runs along a surface, real jumps and walk-offs
(simulated), slides under low solids, and wall climbs (cost modelled from the measured ~280 px/s climb).
A chase: the carrier picks the route that survives longest against a Defender who is always on his best path.
"""

from __future__ import annotations

import heapq
import itertools
import os
import pickle
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from layout_tools import DT, T, Layout  # noqa: E402
from ballbrawlla.entities.player import Player  # noqa: E402
from ballbrawlla.input import Intent  # noqa: E402
from ballbrawlla.physics.vec import Vector2  # noqa: E402
from ballbrawlla.world.level import Level, Platform  # noqa: E402

CLIMB_SPEED = 280.0   # px/s up a solid wall (measured: 280 px in about 1 s)
TAG_SLACK = 0.12      # s: a 40 px tag radius at run speed
CACHE = Path("/tmp/route_graph.pkl")


class Solver:
    def __init__(self, lay: Layout, floor_step: int = 120, ledge_step: int = 70) -> None:
        self.lay = lay
        lay.level(mirror=True)
        self.pieces = {p["id"]: p for p in lay.all_pieces}
        self.rect = {pid: lay.rect(p) for pid, p in self.pieces.items()}
        self.W, self.floor = lay.W, lay.floor
        self.samples: dict[str, list[float]] = {"floor": list(range(lay.WALL + 40, lay.W - lay.WALL - 39, floor_step))}
        for pid, r in self.rect.items():
            n = max(2, int(r.w // ledge_step) + 1)
            self.samples[pid] = [r.left + 2 + (r.w - 4) * i / (n - 1) for i in range(n)]
        self.edges: dict[tuple, list[tuple]] = {}
        self.goal_left = lay.WALL + 10 * lay.yard      # left goal line x
        self.goal_right = lay.W - lay.WALL - 10 * lay.yard

    # ------------------------------------------------------------------ graph
    def add(self, a, b, cost, how):
        self.edges.setdefault(a, []).append((b, cost, how))

    def snap(self, name, x):
        xs = self.samples[name]
        return (name, min(xs, key=lambda v: abs(v - x)))

    def top_of(self, name):
        return 0 if name == "floor" else self.pieces[name]["top"]

    def build(self) -> None:
        for name, xs in self.samples.items():                       # runs
            for u, v in zip(xs, xs[1:]):
                c = (v - u) / T.run_speed
                self.add((name, u), (name, v), c, "run"); self.add((name, v), (name, u), c, "run")
        self._slides(); self._climbs(); self._jumps()

    def _slides(self):
        for wid, w in self.pieces.items():
            if w["type"] != "solid":
                continue
            wr = self.rect[wid]; gap_h = self.floor - wr.bottom
            for name in ["floor"] + list(self.pieces):
                if name == wid:
                    continue
                gap = gap_h - self.top_of(name)
                if not 30 <= gap <= 47:
                    continue
                if name != "floor":
                    sr = self.rect[name]
                    if not (sr.left < wr.right and sr.right > wr.left):
                        continue
                lo = [x for x in self.samples[name] if x < wr.left - 3]
                hi = [x for x in self.samples[name] if x > wr.right + 3]
                if lo and hi:
                    a, b = (name, max(lo)), (name, min(hi))
                    c = (b[1] - a[1]) / T.run_speed
                    self.add(a, b, c, "slide"); self.add(b, a, c, "slide")

    def _climbs(self):
        for wid, w in self.pieces.items():
            if w["type"] != "solid":
                continue
            wr = self.rect[wid]; top = w["top"]
            tops = self.samples[wid]
            for name, xs in self.samples.items():
                if name == wid or self.top_of(name) >= top:
                    continue
                if name != "floor" and self.pieces[name]["type"] == "solid" and False:
                    continue
                for x in xs:
                    if min(abs(x - wr.left), abs(x - wr.right)) <= 36 and (name == "floor" or self._on_height(name, x)):
                        rise = top - self.top_of(name)
                        t = rise / CLIMB_SPEED + 0.25
                        tgt = (wid, min(tops, key=lambda v: abs(v - x)))
                        self.add((name, x), tgt, t, "climb")

    def _on_height(self, name, x):
        r = self.rect[name]; return r.left - 40 <= x <= r.right + 40

    def _jumps(self):
        allp = list(self.pieces.items())
        for name, xs in self.samples.items():
            top = self.top_of(name)
            for x in xs:
                near = [(pid, p) for pid, p in allp if abs(self.rect[pid].center.x - x) < 900 or self.rect[pid].left < x < self.rect[pid].right]
                lv = Level(self.lay.W, self.lay.H, platforms=[Platform(self.rect[pid], platform_type=p["type"]) for pid, p in near],
                           wall_thickness=self.lay.WALL, yard_px=self.lay.yard)
                nm = {id(pl.rect): pid for pl, (pid, _) in zip(lv.platforms[4:], near)}
                for dst, lx, ticks, how in self._macros(lv, nm, name, x, self.floor - top):
                    if dst not in self.samples:
                        continue
                    a, b = (name, x), self.snap(dst, lx)
                    if abs(b[1] - lx) <= 45 and a != b:
                        self.add(a, b, ticks / 120, how)

    def _macros(self, lv, nm, start, x, top):
        out = {}
        def under(p):
            b = p.box
            for pl in lv.platforms:
                r = pl.rect
                if abs(b.bottom - r.top) < 1e-3 and b.left < r.right and b.right > r.left:
                    return nm.get(id(r), "floor" if pl.kind == "bound" else None)
        def mk():
            p = Player(Vector2(x, top - T.player_height / 2), T)
            for _ in range(20): p.update(Intent(), DT, lv.solids, None, lv.thin)
            return p
        for d in (-1, 1):                                            # walk off
            p = mk()
            for t in range(1, 500):
                p.update(Intent(move_x=d), DT, lv.solids, None, lv.thin)
                if t > 3 and p.contacts.on_ground:
                    g = under(p)
                    if g and not (g == start and abs(p.center.x - x) < 30):
                        out[(g, round(p.center.x / 20), "drop")] = (g, p.center.x, t, "drop")
                    break
        for d, hold, dj in itertools.product((-1, 0, 1), (6, 70), (None, 22, 40)):
            if d == 0 and dj is not None:
                continue
            p = mk()
            p.update(Intent(jump_pressed=True, vertical=1, move_x=d), DT, lv.solids, None, lv.thin)
            for t in range(1, 280):
                p.update(Intent(move_x=d, vertical=1 if t < hold else 0, jump_pressed=(dj == t)), DT, lv.solids, None, lv.thin)
                if t > 4 and p.contacts.on_ground and p.vel.y >= 0:
                    g = under(p)
                    if g and not (g == start and abs(p.center.x - x) < 30):
                        k = (g, round(p.center.x / 20), "jump")
                        if k not in out or t < out[k][2]:
                            out[k] = (g, p.center.x, t, "jump" if dj is None else "double jump")
                    break
        return list(out.values())

    # ------------------------------------------------------------------ search
    def dijkstra(self, starts, allowed=None, stop=None):
        dist = {s: 0.0 for s in starts}; prev = {}; pq = [(0.0, s) for s in starts]
        heapq.heapify(pq)
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e18):
                continue
            if stop and stop(u):
                return dist, prev, u
            for v, c, how in self.edges.get(u, ()):
                if allowed and not allowed(v):
                    continue
                nd = d + c
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = (u, how); heapq.heappush(pq, (nd, v))
        return dist, prev, None

    def path(self, prev, end):
        out = [(end, None)]
        while end in prev:
            end, how = prev[end]; out.append((end, how))
        return out[::-1]

    def is_goal(self, node, team="right"):
        return node[1] >= self.goal_right if team == "right" else node[1] <= self.goal_left


def chase(sol: Solver, carrier, defender, slack: float = TAG_SLACK):
    """Can the carrier reach the far end zone without the Defender arriving first at any spot?
    Returns (escaped, seconds): if he escapes, the time it takes; otherwise how long he stays safe."""
    dD, _, _ = sol.dijkstra([defender])
    safe = lambda n, c: dD.get(n, 1e18) > c + slack
    dist = {carrier: 0.0}; pq = [(0.0, carrier)]; last = 0.0
    while pq:
        c, u = heapq.heappop(pq)
        if c > dist.get(u, 1e18):
            continue
        last = max(last, c)
        if sol.is_goal(u):
            return True, c
        for v, cost, _how in sol.edges.get(u, ()):
            nc = c + cost
            if nc < dist.get(v, 1e18) and safe(v, nc):
                dist[v] = nc; heapq.heappush(pq, (nc, v))
    return False, last


def chase_report(sol: Solver, lay: Layout) -> None:
    yd = lay.yard; rows = []
    layers = {"floor": lambda x: sol.snap("floor", x), "deck": None, "sky": None}

    def spot(layer, x):
        want = {"floor": 0, "deck": 280, "sky": 840}[layer]
        best = None
        for name, xs in sol.samples.items():
            if name != "floor" and sol.pieces[name]["top"] != want:
                continue
            if name == "floor" and want != 0:
                continue
            for v in xs:
                d = abs(v - x)
                if best is None or d < best[0]:
                    best = (d, (name, v))
        return best[1] if best and best[0] < 4 * yd else None

    catches = [sol.goal_left + yd * y for y in (10, 20, 30, 40)]
    print("\nchase test: carrier catches the ball and runs for the far end zone; the Defender stands 15 yd ahead on a layer.")
    print("(escape = reaches the goal; otherwise the number is how long he stays safe)")
    print(f"{'catch':>8} {'carrier':>8} | " + " | ".join(f"def on {l:5s}" for l in ("floor", "deck", "sky")))
    survive = []
    for cx in catches:
        for cl in ("floor", "deck", "sky"):
            c = spot(cl, cx)
            if not c:
                continue
            cells = []
            for dl in ("floor", "deck", "sky"):
                d = spot(dl, cx + 15 * yd)
                if not d:
                    cells.append("   n/a    "); continue
                esc, t = chase(sol, c, d)
                cells.append(f"escape {t:4.1f}s" if esc else f"tagged {t:4.1f}s")
                survive.append((esc, t))
            print(f"{(cx - sol.goal_left) / yd:5.0f} yd {cl:>8} | " + " | ".join(cells))
    n = len(survive); esc = sum(1 for e, _ in survive if e)
    ts = sorted(t for e, t in survive if not e)
    print(f"\n{n} chases: {esc} escapes, {n - esc} tags; median time before a tag: " + (f"{ts[len(ts)//2]:.1f}s" if ts else "n/a"))


def layer_filter(solver: Solver, layer: str):
    caps = {"ground": 150, "deck": 760, "sky": 10**9}
    cap = caps[layer]
    return lambda n: solver.top_of(n[0]) <= cap


def main() -> None:
    lay = Layout()
    lay.level(mirror=True)  # populates lay.all_pieces
    if CACHE.exists() and "--rebuild" not in sys.argv:
        sol = pickle.loads(CACHE.read_bytes())
    else:
        sol = Solver(lay)
        print("building the move graph with real jumps (takes a minute) ...", flush=True)
        sol.build()
        CACHE.write_bytes(pickle.dumps(sol))
    n_edges = sum(len(v) for v in sol.edges.values())
    print(f"graph: {sum(len(v) for v in sol.samples.values())} spots, {n_edges} moves")
    yd = lay.yard
    print(f"\nfastest route from a catch at the 20-yard line (x={sol.goal_left + 20*yd:.0f}) to the far end zone, by layer:")
    start = sol.snap("floor", sol.goal_left + 20 * yd)
    base = (sol.goal_right - start[1]) / T.run_speed
    print(f"  open-floor straight line would be {base:.1f}s")
    for layer in ("ground", "deck", "sky"):
        dist, prev, end = sol.dijkstra([start], allowed=layer_filter(sol, layer), stop=sol.is_goal)
        print(f"  {layer:6s} layers and below: " + (f"{dist[end]:.1f}s" if end else "no route"))
    chase_report(sol, lay)


if __name__ == "__main__":
    main()
