"""Game state <-> snapshot dicts. The host sends one per frame; clients apply
the latest to a local Game that is only ever drawn, never stepped."""

from ballbrawlla.entities.player_states import State
from ballbrawlla.game import Game
from ballbrawlla.physics.collision import Contacts
from ballbrawlla.physics.vec import Vector2


class ReplicaState(State):
    """Stand-in for a host-side state on a client: carries the name for rendering."""

    def __init__(self, name: str) -> None:
        self.name = name

    def update(self, p, intent, dt):  # pragma: no cover - clients never step
        return None


def _r(v: float) -> float:
    return round(v, 2)


def make_snapshot(game: Game, tick: int) -> dict:
    b = game.ball
    return {
        "t": "snap",
        "tick": tick,
        "players": [
            {
                "id": p.pid,
                "on": p.connected,
                "x": _r(p.body.pos.x),
                "y": _r(p.body.pos.y),
                "h": p.h,
                "vx": _r(p.vel.x),
                "vy": _r(p.vel.y),
                "s": p.state.name,
                "f": p.facing,
                "a": _r(p.aim_angle),
                "p": _r(p.aim_power),
                "j": p.jumps_left,
                "c": [p.contacts.on_ground, p.contacts.on_ceiling,
                      p.contacts.wall_left, p.contacts.wall_right],
            }
            for p in game.players
        ],
        "ball": {
            "x": _r(b.pos.x),
            "y": _r(b.pos.y),
            "vx": _r(b.vel.x),
            "vy": _r(b.vel.y),
            "held": b.held_by.pid if b.held_by is not None else None,
            "rest": b.resting,
        },
    }


def apply_snapshot(game: Game, snap: dict) -> None:
    b = game.ball
    for d in snap["players"]:
        p = game.players[d["id"]]
        p.connected = d["on"]
        p.body.pos.update(d["x"], d["y"])
        p.h = d["h"]
        p.body.vel.update(d["vx"], d["vy"])
        if p.state.name != d["s"]:
            p.state = ReplicaState(d["s"])
        p.facing = d["f"]
        p.aim_angle = d["a"]
        p.aim_power = d["p"]
        p.jumps_left = d["j"]
        p.contacts = Contacts(*d["c"])
        p.ball = b
        p.held_ball = None

    bd = snap["ball"]
    b.body.pos = Vector2(bd["x"], bd["y"])
    b.body.vel = Vector2(bd["vx"], bd["vy"])
    b.resting = bd["rest"]
    b.held_by = game.players[bd["held"]] if bd["held"] is not None else None
    if b.held_by is not None:
        b.held_by.held_ball = b
