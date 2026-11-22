"""A level can set its own yard scale, so a bigger field does not change Tuning or other levels."""

import pytest

from ballbrawlla.config import Tuning
from ballbrawlla.rules.field import Field
from ballbrawlla.rules.teams import Team
from ballbrawlla.world.level import Level, level_from_dict, level_to_dict, load_level

T = Tuning()
BASE = {"width": 1280, "height": 720, "player_spawns": [[100, 600]], "ball_spawn": [600, 300], "platforms": []}


def test_default_has_no_yard_override_and_is_omitted_when_saved():
    lv = level_from_dict(dict(BASE))
    assert lv.yard_px is None
    assert "yard_px" not in level_to_dict(lv)


def test_yard_px_round_trips():
    lv = level_from_dict({**BASE, "yard_px": 48})
    assert lv.yard_px == 48.0
    assert level_to_dict(lv)["yard_px"] == 48.0
    assert level_from_dict(level_to_dict(lv)).yard_px == 48.0


@pytest.mark.parametrize("bad", [0, -5, "48", True, float("nan"), [48]])
def test_invalid_yard_px_is_rejected(bad):
    with pytest.raises(ValueError, match="yard_px"):
        level_from_dict({**BASE, "yard_px": bad})


def test_field_uses_the_level_scale():
    w = (T.field_yards + 2 * T.end_zone_yards) * 48 + 64
    lv = Level(w, 1200, yard_px=48, wall_thickness=32)
    f = Field(lv, T)
    assert f.yard_px == 48
    assert f.goal_line_x(Team.LEFT) == 32 + T.end_zone_yards * 48
    assert f.x_at(Team.LEFT, 10) - f.x_at(Team.LEFT, 0) == 480


def test_field_rejects_a_level_that_does_not_match_its_own_scale():
    lv = Level(2944, 1200, yard_px=48, wall_thickness=32)  # 24 px/yard width with a 48 px/yard claim
    with pytest.raises(ValueError, match="48px/yard"):
        Field(lv, T)


def test_existing_level_still_uses_tuning_scale():
    lv = load_level("levels/field_01.json")
    assert lv.yard_px is None
    assert Field(lv, T).yard_px == T.yard_px
