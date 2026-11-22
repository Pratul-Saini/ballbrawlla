"""Download and install Godot's export templates (needed once, to build an app you can hand to someone).

    .venv/bin/python tools/install_godot_templates.py [--godot /path/to/Godot] [--version 4.7.2.stable]

The templates are about 1.3 GB. The file is downloaded to a temporary place (and resumed if interrupted), checked as a
zip, and unpacked into Godot's templates folder:
    macOS    ~/Library/Application Support/Godot/export_templates/<version>/
    Windows  %APPDATA%\\Godot\\export_templates\\<version>\\
    Linux    ~/.local/share/godot/export_templates/<version>/
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"


def templates_dir(version: str) -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Godot"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Godot"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "godot"
    return base / "export_templates" / version


def engine_version(godot: str) -> str:
    out = subprocess.run([godot, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    parts = out.split(".")           # 4.7.2.stable.official.<hash> -> 4.7.2.stable
    return ".".join(parts[:4])


def url_for(version: str) -> str:
    number, _, channel = version.rpartition(".")
    return (f"https://github.com/godotengine/godot/releases/download/{number}-{channel}/"
            f"Godot_v{number}-{channel}_export_templates.tpz")


def download(url: str, dest: Path) -> None:
    have = dest.stat().st_size if dest.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416:            # already complete
            return
        raise
    total = have + int(resp.headers.get("Content-Length", 0))
    mode = "ab" if have and resp.status == 206 else "wb"
    done = have if mode == "ab" else 0
    last = time.time()
    with open(dest, mode) as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if time.time() - last > 5:
                print(f"  {done / 1e6:7.0f} / {total / 1e6:.0f} MB", flush=True)
                last = time.time()
    print(f"  downloaded {done / 1e6:.0f} MB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--godot", default=GODOT)
    ap.add_argument("--version", default="")
    args = ap.parse_args()
    version = args.version or engine_version(args.godot)
    target = templates_dir(version)
    if (target / "version.txt").exists():
        print(f"Templates for {version} are already installed in {target}")
        return 0
    url = url_for(version)
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"godot_templates_{version}.tpz"
    print(f"Downloading templates for {version}\n  {url}")
    download(url, tmp)
    if not zipfile.is_zipfile(tmp):
        print("The download is not a valid zip file. Delete it and try again:", tmp)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(tmp) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        for n in names:
            dest = target / Path(n).name if n.startswith("templates/") else target / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(n) as src, open(dest, "wb") as out:
                out.write(src.read())
    tmp.unlink(missing_ok=True)
    print(f"Installed {len(names)} files into {target}")
    return 0 if (target / "version.txt").exists() else 1


if __name__ == "__main__":
    sys.exit(main())
