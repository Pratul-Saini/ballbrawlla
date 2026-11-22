"""Can this mode run with this level and port? One answer, shared by the command line and the menu.

Every check returns a plain-language reason when it fails, or None when the launch is fine, so the caller
decides how to show it: the menu greys the option out, the command line prints one line and exits.

Modes: "practice", "catch", "local", "host", "join", "host_online", "join_code", "sandbox".
"host_online" / "join_code" are internet play through the relay server with an invite code (net/invite.py).
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path

from ballbrawlla.config import TUNING
from ballbrawlla.net.invite import check_code, check_relay
from ballbrawlla.net.protocol import DEFAULT_PORT
from ballbrawlla.paths import levels_dir
from ballbrawlla.rules.field import Field
from ballbrawlla.world.level import Level, level_from_dict, load_level

LEVELS = levels_dir()
MATCH_MODES = ("practice", "catch", "local", "host", "host_online")  # football rules: need a football field
ALL_MODES = ("practice", "catch", "local", "host", "join", "host_online", "join_code", "sandbox")
MODE_LABELS = {
    "practice": "Practice", "catch": "Catch practice", "local": "Two players", "host": "Host a game",
    "join": "Join a game", "host_online": "Host online", "join_code": "Join with code", "sandbox": "Explore",
}


class LaunchError(Exception):
    """A launch that cannot work, with a message fit to show a player."""


@dataclass(frozen=True)
class LevelInfo:
    key: str                  # file stem, e.g. "field_05"
    path: Path
    name: str = ""
    width: float = 0
    height: float = 0
    yard_px: float = 0
    platforms: int = 0
    thin: int = 0
    football: bool = False    # satisfies the football field width rule
    error: str | None = None  # the file could not be read as a level

    @property
    def usable(self) -> bool:
        return self.error is None

    @property
    def crossing_seconds(self) -> float:
        return (self.width - 64) / 320.0

    def summary(self) -> str:
        if not self.usable:
            return "unreadable"
        return f"{self.width:g} x {self.height:g} px, {self.platforms} platforms"


# ---------------------------------------------------------------- levels

def expected_field_width(yard_px: float | None) -> float:
    """Inner width a football field needs, between the side walls."""
    return (TUNING.field_yards + 2 * TUNING.end_zone_yards) * (yard_px or TUNING.yard_px)


def resolve_level(arg: str | Path) -> Path:
    """`field_05`, `field_05.json` or a path to a file -> the file. (Does not check that it exists.)"""
    p = Path(arg)
    if p.exists():
        return p
    named = LEVELS / f"{p.stem}.json"
    return named if named.exists() else p


def read_level(path: Path) -> Level:
    """Load a level file, turning every way it can go wrong into a LaunchError with a clear message."""
    if not path.exists():
        raise LaunchError(f'Level "{path.stem}" was not found. Levels live in the levels folder (for example field_01).')
    try:
        return load_level(path)
    except json.JSONDecodeError as e:
        raise LaunchError(f'"{path.name}" is not valid JSON ({e.msg}, line {e.lineno}).') from e
    except (ValueError, KeyError, TypeError) as e:
        why = f"missing {e}" if isinstance(e, KeyError) else str(e)
        raise LaunchError(f'"{path.name}" can\'t be loaded: {why}') from e


def inspect_level(path: Path) -> LevelInfo:
    try:
        data = json.loads(path.read_text())
        level = level_from_dict(data)
    except FileNotFoundError:
        return LevelInfo(path.stem, path, error="file not found")
    except json.JSONDecodeError as e:
        return LevelInfo(path.stem, path, name=path.stem, error=f"not valid JSON ({e.msg}, line {e.lineno})")
    except (ValueError, KeyError, TypeError) as e:
        return LevelInfo(path.stem, path, name=path.stem, error=f"missing {e}" if isinstance(e, KeyError) else str(e))
    inner = level.width - 2 * level.wall_thickness
    football = abs(inner - expected_field_width(level.yard_px)) <= 0.5
    plats = [p for p in level.platforms if p.kind == "platform"]
    return LevelInfo(
        key=path.stem, path=path, name=level.name if level.name != "untitled" else path.stem,
        width=level.width, height=level.height, yard_px=level.yard_px or TUNING.yard_px,
        platforms=len(plats), thin=sum(1 for p in plats if p.is_thin), football=football,
    )


def list_levels(directory: Path = LEVELS) -> list[LevelInfo]:
    """Every level file in the folder, football fields first (in name order), then the rest."""
    infos = [inspect_level(p) for p in sorted(directory.glob("*.json"))]
    return sorted(infos, key=lambda i: (not i.football, i.key))


# ---------------------------------------------------------------- checks

def check_level(mode: str, info: LevelInfo | None) -> str | None:
    """Why `mode` can't use this level, or None."""
    if info is None:
        return "No level selected."
    if not info.usable:
        return f'"{info.key}" can\'t be loaded: {info.error}.'
    if mode in MATCH_MODES and not info.football:
        return (f'"{info.name}" isn\'t a football field: it is {info.width - 64:g} px wide inside the walls and a match '
                f"needs {expected_field_width(None if info.yard_px == TUNING.yard_px else info.yard_px):g} px. "
                "Use Free play for it, or pick a Field level.")
    return None


def check_port(port: int) -> str | None:
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        return f"Port {port} isn't valid. Use a number from 1024 to 65535."
    try:
        socket.create_server(("0.0.0.0", port)).close()
    except OSError:
        return f"Port {port} is already in use. Close the other game, or pick a different port."
    return None


def check_address(address: str) -> str | None:
    address = (address or "").strip()
    if not address:
        return "Type the host's IP address first."
    if any(c.isspace() for c in address):
        return "An IP address can't contain spaces."
    return None


def check_launch(mode: str, level: Path | None = None, port: int = DEFAULT_PORT, address: str = "",
                 code: str = "") -> str | None:
    """Everything that must be true before `mode` can start, checked against the real files and the real port."""
    if mode not in ALL_MODES:
        return f"Unknown mode {mode!r}."
    if mode == "join":
        return check_address(address) or check_port_number(port)
    if mode == "join_code":
        return check_code(code) or check_relay()
    try:
        lv = read_level(level)
    except LaunchError as e:
        return str(e)
    if mode in MATCH_MODES:
        try:
            Field(lv, TUNING)
        except ValueError:
            return check_level(mode, inspect_level(level))
    if mode == "host":
        return check_port(port)
    if mode == "host_online":
        return check_relay() or check_port(port)
    return None


def check_port_number(port: int) -> str | None:
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        return f"Port {port} isn't valid. Use a number from 1024 to 65535."
    return None
