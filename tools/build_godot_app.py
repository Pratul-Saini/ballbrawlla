"""Build the Godot version of the game into zips you can send to a friend.

    .venv/bin/python tools/build_godot_app.py [--godot /path/to/Godot] [--only macos|windows]

Needs the export templates: run tools/install_godot_templates.py once. Output is in dist/godot/:
    GridironScramble-godot-<version>-macos.zip      the .app (macOS, Intel and Apple Silicon)
    GridironScramble-godot-<version>-windows.zip    the .exe and its .pck, which must stay together

Neither build is signed: macOS needs right-click > Open the first time, and Windows shows a SmartScreen warning.
Drop music files into godot/assets/music/ before building and they are included.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "godot"
GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"
VERSION = "0.2.0"
for line in (ROOT / "godot" / "scripts" / "version.gd").read_text().splitlines():
    if line.startswith("const VERSION"):
        VERSION = line.split('"')[1]


def export(godot: str, preset: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([godot, "--headless", "--path", "godot", "--export-release", preset, str(target)],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    text = r.stdout + r.stderr
    errors = [l for l in text.splitlines() if l.startswith("ERROR") and "leaked" not in l and "still in use" not in l]
    if r.returncode != 0 or not target.exists():
        print(text[-1500:])
        raise SystemExit(f"Exporting '{preset}' failed")
    if errors:
        print("\n".join(errors))


def zip_macos() -> Path:
    zip_path = OUT / f"GridironScramble-godot-{VERSION}-macos.zip"
    zip_path.unlink(missing_ok=True)
    if platform.system() == "Darwin":
        # ditto keeps the .app's symlinks and permissions, which a plain zip can break.
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(OUT / "Gridiron Scramble.app"), str(zip_path)], check=True)
    else:
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", OUT, "Gridiron Scramble.app")
    return zip_path


def zip_windows() -> Path:
    folder = OUT / "windows" / "Gridiron Scramble"
    shutil.rmtree(OUT / "windows", ignore_errors=True)
    folder.mkdir(parents=True)
    for f in OUT.glob("Gridiron Scramble.*"):
        if f.suffix in (".exe", ".pck"):
            shutil.copy2(f, folder / f.name)
    for f in OUT.glob("Gridiron Scramble*.console.exe"):
        shutil.copy2(f, folder / f.name)
    zip_path = OUT / f"GridironScramble-godot-{VERSION}-windows.zip"
    zip_path.unlink(missing_ok=True)
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", OUT / "windows", "Gridiron Scramble")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--godot", default=GODOT)
    ap.add_argument("--only", choices=["macos", "windows"])
    args = ap.parse_args()
    built = []
    if args.only in (None, "macos"):
        shutil.rmtree(OUT / "Gridiron Scramble.app", ignore_errors=True)
        export(args.godot, "macOS", OUT / "Gridiron Scramble.app")
        built.append(zip_macos())
    if args.only in (None, "windows"):
        for f in OUT.glob("Gridiron Scramble.*"):
            if f.is_file():
                f.unlink()
        export(args.godot, "Windows Desktop", OUT / "Gridiron Scramble.exe")
        built.append(zip_windows())
    for z in built:
        print(f"Built {z} ({z.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
