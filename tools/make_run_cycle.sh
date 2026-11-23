#!/usr/bin/env bash
# Rebuilds every player animation from the hand-drawn fball sprites. Sources are never edited.
#   tools/make_run_cycle.sh
# Env: ASEPRITE (aseprite binary), PY (python with Pillow, default the repo venv).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASEPRITE="${ASEPRITE:-/Users/kris/deps/aseprite/build/bin/Aseprite.app/Contents/MacOS/aseprite}"
if [ -z "${PY:-}" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"
  else PY="$(git -C "$ROOT" rev-parse --git-common-dir)/../.venv/bin/python"; fi
fi
SRC="$ROOT/godot/assets/sprites/player"
OUT="$SRC/anim"
LUA="$ROOT/tools/aseprite"
TMP="$(mktemp -d)"
trap '[ -n "${KEEP_TMP:-}" ] || rm -rf "$TMP"' EXIT   # KEEP_TMP=1 keeps the intermediate files

[ -x "$ASEPRITE" ] || { echo "aseprite not found: $ASEPRITE (set ASEPRITE)"; exit 1; }
[ -x "$PY" ] || { echo "python not found: $PY (set PY)"; exit 1; }
mkdir -p "$OUT"
rm -f "$OUT"/*.png "$OUT"/*.json "$OUT"/*.aseprite

# set name | source file | mirrored?
SETS=("navy fball_navy false" "navy_left fball_navy_left true" "red fball_red false" "red_left fball_red_left true")

for entry in "${SETS[@]}"; do
  read -r name file mirror <<<"$entry"
  echo "== $name"
  "$ASEPRITE" -b --script-param root="$ROOT" --script-param src="$SRC/$file.aseprite" \
    --script-param out="$TMP/${name}_split.aseprite" --script-param mirror="$mirror" \
    --script "$LUA/split_layers.lua"
  "$ASEPRITE" -b "$TMP/${name}_split.aseprite" --save-as "$TMP/${name}_split_flat.png"
  "$ASEPRITE" -b --script-param root="$ROOT" --script-param split="$TMP/${name}_split.aseprite" \
    --script-param out="$OUT/${name}_rig.aseprite" --script-param hands="$OUT/${name}_hands.json" \
    --script-param legs="$TMP/${name}_legs.json" \
    --script-param mirror="$mirror" --script "$LUA/rig.lua"
  "$ASEPRITE" -b "$OUT/${name}_rig.aseprite" --sheet "$OUT/$name.png" --sheet-type horizontal \
    --data "$OUT/$name.json" --format json-array --list-tags
done

"$PY" "$LUA/sheet_to_godot.py"
"$PY" "$LUA/check_frames.py" --split-dir "$TMP"
"$PY" "$LUA/contact_sheet.py"
