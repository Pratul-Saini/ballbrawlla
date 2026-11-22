import json
from pathlib import Path

import pytest

from ballbrawlla.physics.shapes import AABB
from ballbrawlla.world.level import (
    Level,
    Platform,
    level_from_dict,
    level_to_dict,
    load_level,
)

INVALID_TYPES = ["Thin", " thin", "", None, 1, True, ["thin"]]


def rect(a: AABB) -> tuple:
    return (a.x, a.y, a.w, a.h)


def level_dict(platforms, **extra) -> dict:
    d = {
        "width": 1280,
        "height": 720,
        "player_spawns": [[100, 600]],
        "ball_spawn": [600, 300],
        "platforms": platforms,
    }
    d.update(extra)
    return d


MIXED = [
    {"x": 10, "y": 100, "w": 50, "h": 20, "type": "thin"},
    {"x": 20, "y": 200, "w": 60, "h": 30},
    {"x": 30, "y": 300, "w": 70, "h": 20, "type": "solid"},
    {"x": 40, "y": 400, "w": 80, "h": 20, "type": "thin"},
    {"x": 50, "y": 500, "w": 90, "h": 40},
]


# --- Platform types partition the level (Req 1.x, 2.1-2.3, 2.5) ---


def test_platform_defaults_to_solid():
    p = Platform(AABB(0, 0, 10, 10))
    assert p.platform_type == "solid"
    assert not p.is_thin


def test_thin_platform_is_thin():
    assert Platform(AABB(0, 0, 10, 10), platform_type="thin").is_thin


def test_mixed_entries_get_right_types_in_order():
    level = level_from_dict(level_dict(MIXED))
    entries = level.platforms[4:]
    assert [p.platform_type for p in entries] == ["thin", "solid", "solid", "thin", "solid"]
    assert [rect(p.rect) for p in entries] == [(d["x"], d["y"], d["w"], d["h"]) for d in MIXED]
    assert all(p.kind == "platform" for p in entries)


def test_boundaries_are_solid_bound_platforms():
    level = level_from_dict(level_dict(MIXED))
    bounds = level.platforms[:4]
    assert all(p.kind == "bound" and p.platform_type == "solid" for p in bounds)
    assert [p.rect for p in bounds] == level.solids[:4]


def test_solids_and_thin_lists():
    level = level_from_dict(level_dict(MIXED))
    t, w, h = level.wall_thickness, level.width, level.height
    expected_bounds = [(0, h - t, w, t), (0, 0, w, t), (0, 0, t, h), (w - t, 0, t, h)]
    assert [rect(r) for r in level.solids] == expected_bounds + [
        (20, 200, 60, 30),
        (30, 300, 70, 20),
        (50, 500, 90, 40),
    ]
    assert [rect(r) for r in level.thin] == [(10, 100, 50, 20), (40, 400, 80, 20)]


def test_each_platform_in_exactly_one_list():
    level = level_from_dict(level_dict(MIXED))
    assert len(level.solids) + len(level.thin) == len(level.platforms)
    assert not any(any(s is t for t in level.thin) for s in level.solids)


def test_level_without_platforms_has_only_boundaries():
    level = Level(width=800, height=600)
    assert len(level.solids) == 4
    assert level.thin == []


# --- Invalid types are rejected (Req 2.4) ---


@pytest.mark.parametrize("bad", INVALID_TYPES)
def test_platform_rejects_invalid_type(bad):
    with pytest.raises(ValueError) as exc:
        Platform(AABB(0, 0, 10, 10), platform_type=bad)
    assert repr(bad) in str(exc.value)


@pytest.mark.parametrize("bad", INVALID_TYPES)
def test_level_from_dict_rejects_invalid_type(bad):
    entries = [{"x": 1, "y": 2, "w": 3, "h": 4}, {"x": 5, "y": 6, "w": 7, "h": 8, "type": bad}]
    result = None
    with pytest.raises(ValueError) as exc:
        result = level_from_dict(level_dict(entries))
    assert repr(bad) in str(exc.value)
    assert result is None


# --- Serialization keeps the type (Req 3.x) ---


def test_to_dict_thin_and_solid_keys():
    d = level_to_dict(level_from_dict(level_dict(MIXED)))
    plats = d["platforms"]
    assert plats[0] == {"x": 10, "y": 100, "w": 50, "h": 20, "type": "thin"}
    assert set(plats[0]) == {"x", "y", "w", "h", "type"}
    assert set(plats[1]) == {"x", "y", "w", "h"}  # untyped
    assert set(plats[2]) == {"x", "y", "w", "h"}  # explicit solid written without type
    assert plats[3]["type"] == "thin"


def test_to_dict_omits_boundaries_and_keeps_order():
    d = level_to_dict(level_from_dict(level_dict(MIXED)))
    assert [(p["x"], p["y"], p["w"], p["h"]) for p in d["platforms"]] == [
        (e["x"], e["y"], e["w"], e["h"]) for e in MIXED
    ]


def test_json_round_trip_preserves_types_and_rects():
    original = level_from_dict(level_dict(MIXED))
    restored = level_from_dict(json.loads(json.dumps(level_to_dict(original))))
    assert [p.platform_type for p in restored.platforms] == [
        p.platform_type for p in original.platforms
    ]
    assert [rect(p.rect) for p in restored.platforms] == [rect(p.rect) for p in original.platforms]
    assert [rect(r) for r in restored.thin] == [rect(r) for r in original.thin]


def test_load_level_reads_file_and_uses_stem_as_name(tmp_path):
    path = tmp_path / "my_arena.json"
    path.write_text(json.dumps(level_dict(MIXED)))
    level = load_level(path)
    assert level.name == "my_arena"
    assert len(level.thin) == 2
    assert len(level.solids) == 4 + 3


def test_load_level_keeps_explicit_name(tmp_path):
    path = tmp_path / "file.json"
    path.write_text(json.dumps(level_dict(MIXED, name="Custom")))
    assert load_level(path).name == "Custom"


def test_load_level_invalid_type_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(level_dict([{"x": 1, "y": 2, "w": 3, "h": 4, "type": "Thin"}])))
    with pytest.raises(ValueError, match="Thin"):
        load_level(path)


# --- Bundled level smoke test (Req 10.1-10.4) ---

ARENA_PATH = Path(__file__).resolve().parents[1] / "levels" / "arena_01.json"

ARENA_THIN = [
    (200, 550, 220, 20),
    (860, 550, 220, 20),
    (520, 400, 240, 20),
    (560, 200, 160, 20),
    (32, 300, 110, 20),
    (1138, 300, 110, 20),
]
ARENA_SOLID = [(600, 600, 80, 88), (330, 160, 24, 240), (926, 160, 24, 240)]


def test_arena_01_platform_types():
    level = load_level(ARENA_PATH)
    assert [rect(r) for r in level.thin] == ARENA_THIN
    assert len(level.thin) == 6
    assert len(level.solids) == 4 + 3
    assert [rect(r) for r in level.solids[4:]] == ARENA_SOLID


def test_arena_01_untyped_entries_have_no_type_key_and_are_solid():
    data = json.loads(ARENA_PATH.read_text())
    untyped = [(p["x"], p["y"], p["w"], p["h"]) for p in data["platforms"] if "type" not in p]
    assert untyped == ARENA_SOLID
    typed = [p for p in data["platforms"] if "type" in p]
    assert all(p["type"] == "thin" for p in typed)
    assert len(typed) == 6


def test_arena_01_other_values_unchanged():
    level = load_level(ARENA_PATH)
    assert level.name == "Arena 01"
    assert (level.width, level.height, level.wall_thickness) == (1280, 720, 32)
    assert [(s.x, s.y) for s in level.player_spawns] == [(200, 650), (1080, 650)]
    assert (level.ball_spawn.x, level.ball_spawn.y) == (640, 120)
    assert [rect(p.rect) for p in level.platforms[4:]] == [
        (200, 550, 220, 20),
        (860, 550, 220, 20),
        (520, 400, 240, 20),
        (560, 200, 160, 20),
        (600, 600, 80, 88),
        (32, 300, 110, 20),
        (1138, 300, 110, 20),
        (330, 160, 24, 240),
        (926, 160, 24, 240),
    ]
