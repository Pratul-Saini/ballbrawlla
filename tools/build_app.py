"""Build a double-clickable app and a zip to send to friends.

    .venv/bin/python tools/build_app.py          (macOS / Linux)
    .venv\Scripts\python tools\build_app.py      (Windows)

Needs PyInstaller:  pip install -e ".[build]"

PyInstaller does not cross-compile, so the Mac build is made on a Mac and the Windows build on Windows
(or by the GitHub Actions workflow in .github/workflows/build.yml). Output is in dist/:

    macOS    Gridiron Scramble.app            and  GridironScramble-<version>-macos.zip
    Windows  Gridiron Scramble/ (with .exe)   and  GridironScramble-<version>-windows.zip
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballbrawlla.paths import APP_NAME  # noqa: E402
from ballbrawlla.version import __version__  # noqa: E402

# pygame's controller support is imported inside a try/except at run time, so PyInstaller cannot see it.
# Without these the packaged app would silently have no gamepad support.
HIDDEN = ["pygame._sdl2", "pygame._sdl2.controller", "pygame._sdl2.video", "pygame._sdl2.audio"]


def data_args() -> list[str]:
    sep = os.pathsep
    args = ["--add-data", f"{ROOT / 'levels'}{sep}levels"]
    if (ROOT / "assets").is_dir():
        args += ["--add-data", f"{ROOT / 'assets'}{sep}assets"]
    return args


def system_name() -> str:
    return {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system().lower())


def build() -> Path:
    dist, work = ROOT / "dist", ROOT / "build"
    for folder in (dist, work):
        shutil.rmtree(folder, ignore_errors=True)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", APP_NAME, "--paths", str(ROOT / "src"),
        "--distpath", str(dist), "--workpath", str(work), "--specpath", str(work),
        *data_args(),
        *[arg for mod in HIDDEN for arg in ("--hidden-import", mod)],
        str(ROOT / "packaging" / "entry.py"),
    ]
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    return dist


def make_zip(dist: Path) -> Path:
    name = f"GridironScramble-{__version__}-{system_name()}.zip"
    out = dist / name
    if platform.system() == "Darwin":
        # ditto keeps the .app's symlinks and permissions, which a plain zip can break.
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(dist / f"{APP_NAME}.app"), str(out)], check=True)
    else:
        base = shutil.make_archive(str(dist / out.stem), "zip", dist, APP_NAME)
        out = Path(base)
    return out


if __name__ == "__main__":
    dist = build()
    zip_path = make_zip(dist)
    print(f"\nBuilt {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")
