"""Choices the player makes in the menu that should survive a restart, in settings.json in the writable
folder (paths.user_data_dir: the repository in a source checkout, the per-user folder in the packaged app).

Stdlib only, like net/invite.py, which reads the relay address from here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ballbrawlla.paths import user_data_dir

FILE_NAME = "settings.json"


def settings_path() -> Path:
    return user_data_dir() / FILE_NAME


def load() -> dict:
    """The saved settings; {} if there are none or the file can't be read."""
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(key: str, default=None):
    return load().get(key, default)


def save(**changes) -> None:
    """Update some settings. A value of None or "" removes the key. Raises OSError if the file can't be written."""
    data = load()
    for key, value in changes.items():
        if value is None or value == "":
            data.pop(key, None)
        else:
            data[key] = value
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
