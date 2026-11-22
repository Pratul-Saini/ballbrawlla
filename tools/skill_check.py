"""Verifies the two skill moves in the big field with the real physics.

    python tools/skill_check.py

PIPE HOP   For each sky-deck gap that has a pipe in it: the hop onto the pipe top and off again must be doable,
           and a straight jump (single or double) over the whole span must be impossible.
SLIDE      For each low tunnel: a slide through must work, and a bad start must cost time.
"""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from layout_tools import DT, T, Layout  # noqa: E402
from ballbrawlla.entities.player import Player  # noqa: E402
from ballbrawlla.input import Intent  # noqa: E402
from ballbrawlla.physics.vec import Vector2  # noqa: E402
from ballbrawlla.world.level import Level, Platform  # noqa: E402


def build(lay: Layout):
    lv, names = lay.level(mirror=True)
    return lv, {v: k for k, v in names.items()}, names


def _player(lv, cx, top_y):
    p = Player(Vector2(cx, top_y - T.player_height / 2), T)
    for _ in range(20):
        p.update(Intent(), DT, lv.solids, None, lv.thin)
    return p


def hop(lv, names, a_rect, direction, dst_rect, allow_double):
    """Best-effort hop from the edge of a_rect toward dst_rect. True if the player lands on dst_rect."""
    edge = a_rect.right if direction > 0 else a_rect.left
    for off in range(0, 40, 4):
        for hold, dj in itertools.product((6, 70), ((None, 14, 22, 30, 38, 46, 56) if allow_double else (None,))):
            start_x = edge - direction * (14 + off)
            p = _player(lv, start_x, a_rect.top)
            p.update(Intent(move_x=direction, jump_pressed=True, vertical=1), DT, lv.solids, None, lv.thin)
            for t in range(1, 320):
                p.update(Intent(move_x=direction, vertical=1 if t < hold else 0, jump_pressed=(dj == t)),
                         DT, lv.solids, None, lv.thin)
                if t > 4 and p.contacts.on_ground and p.vel.y >= 0:
                    b = p.box
                    if abs(b.bottom - dst_rect.top) < 1.0 and b.left < dst_rect.right and b.right > dst_rect.left:
                        return True
                    break
    return False


def check_hops(lay: Layout, lv, byname):
    """Every consecutive pair of sky-level tops (ledges and pipes alike) is a hop that must be doable, and every
    pipe or slab in the chain must be unskippable: its neighbours are more than a double jump apart."""
    sky_top = lay.floor - 840
    tops = sorted(((n, r) for n, r in byname.items() if abs(r.top - sky_top) < 1 and not n.endswith("'")),
                  key=lambda kv: kv[1].left)
    tops += sorted(((n, r) for n, r in byname.items() if abs(r.top - sky_top) < 1 and n.endswith("'")), key=lambda kv: kv[1].left)
    tops.sort(key=lambda kv: kv[1].left)
    ok = True
    print("SKY HOPS (everything with its top at 840, left to right, both halves):")
    for (na, a), (nb, b) in zip(tops, tops[1:]):
        gap = b.left - a.right
        if gap <= 0:
            continue
        if gap > 230:
            print(f"  {na} -> {nb}: gap {gap:.0f} px   (a break: the chain does not continue here)")
            continue
        doable = hop(lv, None, a, +1, b, allow_double=False)
        ok &= doable
        print(f"  {na} -> {nb}: gap {gap:.0f} px, {'single jump works' if doable else 'NOT reachable'}")
    print("\nCAN A PIPE BE SKIPPED? (neighbour to neighbour across a solid, double jump allowed)")
    for i in range(1, len(tops) - 1):
        (np_, pp), (na, a), (nb, b) = tops[i], tops[i - 1], tops[i + 1]
        if pp.h <= 13:
            continue
        span = b.left - a.right
        if span > 230 and span <= 700 and a.right <= pp.left and b.left >= pp.right:
            skipped = hop(lv, None, a, +1, b, allow_double=True)
            ok &= not skipped
            print(f"  {np_}: {na} to {nb} is {span:.0f} px -> {'SKIPPABLE with a double jump' if skipped else 'forced'}")
    return ok


def slide_window(length: int, d_values=range(0, 200, 10)):
    """Isolated test: run right on a floor toward a roof `length` px long with a 32 px gap.
    Returns (best_time, window_px, worst_extra_seconds). The window is how many px before the mouth a slide may start
    and still finish within 0.15 s of the best."""
    from ballbrawlla.physics.shapes import AABB
    mouth, floor = 1400, 2368
    res = {}
    for d in d_values:
        lv = Level(5824, 2400, platforms=[Platform(AABB(mouth, floor - 32 - 24, length, 24))], wall_thickness=32)
        p = Player(Vector2(mouth - 700, floor - 24), T)
        for _ in range(30):
            p.update(Intent(), DT, lv.solids, None, lv.thin)
        t = 0
        while t < 1500:
            x = p.center.x
            down = (mouth - x) <= max(d, 16) and x < mouth + length + 20  # pressing Down at the roof edge also slides
            p.update(Intent(move_x=1, vertical=-1 if down else 0), DT, lv.solids, None, lv.thin)
            t += 1
            if p.center.x > mouth + length + 20 and p.state.name == "grounded":
                break
        res[d] = t / 120
    best = min(res.values())
    good = [d for d, v in res.items() if v <= best + 0.15]
    return best, max(good) - min(good) + 10, max(res.values()) - best


def check_tunnels(lay: Layout, lv, byname):
    print("\nSLIDE TUNNELS (32 px gap; the window is how far before the mouth a slide may start):")
    seen = {}
    for n, r in sorted(byname.items(), key=lambda kv: kv[1].left):
        if n.endswith("'"):
            continue
        if n.endswith("_tun") or n in ("T3", "TR"):
            gate = n[:-4] if n.endswith("_tun") else None
            sill = byname.get(f"{gate}_lo") if gate else None
            length = int(r.w + (sill.w if sill else 0))
            seen[n] = length
    ok = True
    for n, length in seen.items():
        best, window, worst = slide_window(length)
        verdict = "tight" if window <= 40 else "forgiving"
        print(f"  {n}: {length} px long -> start window about {window} px ({window / 320 * 1000:.0f} ms), {verdict}; "
              f"a bad start costs up to +{worst:.1f}s")
    return ok


if __name__ == "__main__":
    lay = Layout()
    lv, rects, names = build(lay)
    byname = {names[id(pl.rect)]: pl.rect for pl in lv.platforms[4:]}
    good = check_hops(lay, lv, byname)
    check_tunnels(lay, lv, byname)
    print("\nresult:", "all pipe hops forced and doable" if good else "PROBLEMS above (see the hops list)")
