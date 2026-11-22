#!/usr/bin/env bash
# Run the Godot tests headless:   godot/run_tests.sh [seconds-limit]
# - macOS has no `timeout`, so a watchdog loop kills a hung run.
# - Godot exits 0 even when a script crashes mid-test, so ANY "SCRIPT ERROR" / "ERROR:" line fails the run.
# Set GODOT=/path/to/Godot to use a different binary.
cd "$(dirname "$0")/.." || exit 1
GODOT_BIN="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"
OUT="${TMPDIR:-/tmp}/godot_test_out.txt"
"$GODOT_BIN" --headless --path godot -s res://tests/run_tests.gd >"$OUT" 2>&1 &
PID=$!
for _ in $(seq 1 "${1:-60}"); do
  kill -0 $PID 2>/dev/null || break
  sleep 1
done
TIMED_OUT=0
if kill -0 $PID 2>/dev/null; then kill $PID; TIMED_OUT=1; fi
wait $PID 2>/dev/null; CODE=$?
grep -v "^Godot Engine" "$OUT"
if [ $TIMED_OUT -eq 1 ]; then echo "FAILED: timed out"; exit 1; fi
# Godot prints "leaked at exit" notes when objects that reference each other (player <-> ball) are freed at
# shutdown. They are harmless, so they are ignored; every other error line fails the run.
if grep -vE "ObjectDB instances were leaked|resources still in use at exit|^\s+at: (cleanup|clear) " "$OUT" | grep -qE "SCRIPT ERROR|^ERROR:|Parse Error|Compile Error"; then echo "FAILED: the run printed script errors (see above)"; exit 1; fi
exit $CODE
