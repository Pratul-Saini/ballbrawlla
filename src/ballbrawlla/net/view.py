"""What one human is allowed to see, as a JSON-able dict.

The host builds a view per human every frame: its own screen draws view 0,
and each client is sent only its own view. Hidden information is left out
of the dict entirely, so a client can't peek at it:

* the offense's throw angle/power is never in the defense's view
* the defense's Defender spot (during the play call) is never in the offense's view
"""

from __future__ import annotations

from ballbrawlla.entities.player import Player
from ballbrawlla.rules.teams import Team
from ballbrawlla.session import Phase, Session


def _r(v: float) -> float:
    return round(v, 2)


def _actor(p: Player) -> dict:
    c = p.contacts
    return {
        "role": p.role.value if hasattr(p.role, "value") else p.role,
        "team": int(p.team),
        "x": _r(p.body.pos.x),
        "y": _r(p.body.pos.y),
        "w": p.w,
        "h": p.h,
        "vx": _r(p.vel.x),
        "vy": _r(p.vel.y),
        "s": p.state.name,
        "f": p.facing,
        "c": [c.on_ground, c.on_ceiling, c.wall_left, c.wall_right],
    }


def make_view(s: Session, pid: int) -> dict:
    my_team = s.team_of_human[pid]
    d = s.down
    side = "offense" if my_team is d.offense else "defense"
    v: dict = {
        "t": "snap",
        "tick": s.tick,
        "phase": s.phase.value,
        "you": pid,
        "team": int(my_team),
        "side": side,
        "practice": s.practice,
        "connected": list(s.connected),
        "down": d.number,
        "offense": int(d.offense),
        "score": [s.match.score[Team.LEFT], s.match.score[Team.RIGHT]],
        "winner": None if s.match.winner is None else int(s.match.winner),
        "message": s.message,
        "timer": None,
    }

    if s.phase is Phase.PLAY_CALL:
        c = s.call
        call = {
            "qb": [_r(c.qb_spot.x), _r(c.qb_spot.y)],
            "picks": d.offense_picks_spawn,
            "placing": c.placing,
            "qb_range": [_r(c.qb_lo), _r(c.qb_hi)],
            "def_range": [_r(c.def_lo), _r(c.def_hi)],
            "off_locked": c.offense_locked,
            "def_locked": c.defense_locked,
            "restarts": c.restarts,
        }
        if side == "offense":
            call["aim"] = [_r(c.aim_angle), _r(c.aim_power)]
        else:
            call["def"] = [_r(c.def_spot.x), _r(c.def_spot.y)]
        v["call"] = call
        v["timer"] = _r(c.timer)

    if s.game is not None and s.phase in (Phase.PRE_THROW, Phase.LIVE, Phase.DEAD):
        wr, df = s.game.players
        b = s.game.ball
        v["actors"] = [_actor(s.qb), _actor(wr), _actor(df)]
        holder = b.held_by
        v["ball"] = {
            "x": _r(b.pos.x),
            "y": _r(b.pos.y),
            "vx": _r(b.vel.x),
            "vy": _r(b.vel.y),
            "holder": None if holder is None else _actor(holder)["role"],
        }
        if s.phase is Phase.PRE_THROW:
            v["timer"] = _r(s.timer)
            if side == "offense":  # your own locked-in throw
                v["aim"] = [_r(s.qb.aim_angle), _r(s.qb.aim_power)]
        elif s.phase is Phase.LIVE and s.loose_timer is not None:
            v["timer"] = _r(s.loose_timer)
    return v
