"""Turns the four Aseprite sheet exports (+ hands json) into the one file Godot loads at runtime:
godot/assets/sprites/player/anim/player_anim.json.

    .venv/bin/python tools/aseprite/sheet_to_godot.py

Every sheet is a horizontal strip of untrimmed 96x96 frames, so frame i is x = i * 96.
Loop flags are not stored by Aseprite, so they come from LOOPS here.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANIM = os.path.join(ROOT, "godot", "assets", "sprites", "player", "anim")
RES = "res://assets/sprites/player/anim/"
SETS = ["navy", "navy_left", "red", "red_left"]
LOOPS = {"idle": True, "run": True, "jump": False, "apex": False, "fall": True, "land": False}
SIZE = 96
GROUND_ROW = 85


def main():
    tags = None
    frames = None
    sheets = {}
    hands = {}
    for name in SETS:
        with open(os.path.join(ANIM, name + ".json")) as f:
            meta = json.load(f)
        fr = meta["frames"]
        t = {}
        for ft in meta["meta"]["frameTags"]:
            a, b = ft["from"], ft["to"]
            t[ft["name"]] = {
                "from": a,
                "to": b,
                "loop": LOOPS[ft["name"]],
                "durations_ms": [fr[i]["duration"] for i in range(a, b + 1)],
            }
        rects = []
        for i, item in enumerate(fr):
            r = item["frame"]
            assert (r["w"], r["h"]) == (SIZE, SIZE), (name, i, r)
            assert (r["x"], r["y"]) == (i * SIZE, 0), (name, i, r)
            rects.append([r["x"], r["y"], r["w"], r["h"]])
        if tags is None:
            tags, frames = t, rects
        assert t == tags and rects == frames, name + " differs from the first set"
        sheets[name] = RES + name + ".png"
        with open(os.path.join(ANIM, name + "_hands.json")) as f:
            hands[name] = json.load(f)
        assert len(hands[name]) == len(frames), name
    out = {
        "frame_size": SIZE,
        "ground_row": GROUND_ROW,
        "sheets": sheets,
        "tags": tags,
        "frames": frames,
        "hands": hands,
    }
    path = os.path.join(ANIM, "player_anim.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print("wrote", path, "tags:", ", ".join(f"{k}({v['from']}-{v['to']})" for k, v in tags.items()))


if __name__ == "__main__":
    main()
