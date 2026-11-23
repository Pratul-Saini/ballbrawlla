"""What one human is allowed to see, as a JSON-able dict.

The host builds a view per human every frame: its own screen draws view 0,
and each client is sent only its own view. Hidden information is left out
of the dict entirely, so a client can't peek at it:

* the offense's throw angle/power is never in the defense's view
* the defense's Defender spot (during the play call) is never in the offense's view

Local play (both players at one screen) uses `local=True`, which shows both.
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


def make_view(s: Session, pid: int, local: bool = False) -> dict:
    """The view for human `pid`. `local=True`: one shared screen, nothing hidden."""
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
        "defender": s.defender,
        "connected": list(s.connected),
        "down": d.number,
        "offense": int(d.offense),
        "score": [s.match.score[Team.LEFT], s.match.score[Team.RIGHT]],
        "winner": None if s.match.winner is None else int(s.match.winner),
        "message": s.message,
        "timer": None,
        "local": local,
    }

    if s.phase is Phase.PLAY_CALL:
        c = s.call
        qf = c.feet(c.qb_player)
        call = {
            "qb": [_r(qf.x), _r(qf.y)],                          # where the QB is (feet)
            "qb_h": c.qb_player.h,
            "qb_spot": [_r(c.qb_spot.x), _r(c.qb_spot.y)],       # the spawn it would take
            "qb_ok": c.qb_ok,                                    # standing on a platform in its zone
            "picks": d.offense_picks_spawn,
            "placing": c.placing,
            "qb_range": [_r(c.qb_lo), _r(c.qb_hi)],
            "def_range": [_r(c.def_lo), _r(c.def_hi)],
            "off_locked": c.offense_locked,
            "def_locked": c.defense_locked,
            "restarts": c.restarts,
        }
        if local or side == "offense":
            call["aim"] = [_r(c.aim_angle), _r(c.aim_power)]
        if local or side == "defense":
            df = c.feet(c.def_player)
            call["def"] = [_r(df.x), _r(df.y)]
            call["def_h"] = c.def_player.h
            call["def_spot"] = [_r(c.def_spot.x), _r(c.def_spot.y)]
            call["def_ok"] = c.def_ok
        v["call"] = call
        v["timer"] = _r(c.timer)
        if s.defender:  # QB's line: the Defender can't cross it into the offense's half yet
            v["safe_zone_x"] = _r(c.safe_zone_x)

    if s.game is not None and s.phase in (Phase.PRE_THROW, Phase.LIVE, Phase.DEAD):
        wr, *others = s.game.players          # the defender is absent in catch practice
        b = s.game.ball
        v["actors"] = [_actor(s.qb), _actor(wr), *(_actor(p) for p in others)]
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
            if s.defender:  # the QB's line stays a safe zone until the throw
                v["safe_zone_x"] = _r(s.qb.center.x)
            if local or side == "offense":  # your own locked-in throw
                v["aim"] = [_r(s.qb.aim_angle), _r(s.qb.aim_power)]
        elif s.phase is Phase.LIVE and s.loose_timer is not None:
            v["timer"] = _r(s.loose_timer)
    return v
