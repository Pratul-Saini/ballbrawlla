"""Where the game finds its files and where it may write.

Run from a source checkout, everything stays where it always was: levels/ and logs/ in the repository.
Run as a packaged app (PyInstaller), the levels ship inside the bundle (read-only) and logs and notes go to a
per-user folder, because the app's own folder may not be writable.

    macOS    ~/Library/Application Support/Gridiron Scramble
    Windows  %APPDATA%\\Gridiron Scramble
    Linux    $XDG_DATA_HOME/gridiron-scramble  (default ~/.local/share/gridiron-scramble)

BALLBRAWLLA_HOME overrides the writable folder in every case.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Gridiron Scramble"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """The folder holding read-only game data (levels, assets)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def levels_dir() -> Path:
    return bundle_dir() / "levels"


def assets_dir() -> Path:
    return bundle_dir() / "assets"


def user_data_dir() -> Path:
    """The folder the game may write to."""
    override = os.environ.get("BALLBRAWLLA_HOME")
    if override:
        return Path(override).expanduser()
    if not is_frozen():
        return bundle_dir()                      # source checkout: next to levels/, as before
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming") / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / "gridiron-scramble"


def logs_dir() -> Path:
    return user_data_dir() / "logs"
