"""Session notes (F2): one notes file per session, edited in place."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from datetime import datetime

import pygame
import pytest

from ballbrawlla.input import Intent
from ballbrawlla.notes import NotesEditor, SessionLog, SessionNotes

T0 = datetime(2026, 11, 22, 9, 30, 5)


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


def text(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


# ---------------------------------------------------------------- the log file

def test_saves_go_to_one_file_per_session(tmp_path):
    log = SessionLog("local", "Fortress", root=tmp_path, now=T0)
    assert log.notes_path == tmp_path / "2026-11-22_09-30-05_local_fortress" / "notes.md"
    log.save("first thought", "Blue 0 - 0 Red", now=T0)
    log.save("first thought\nsecond thought", "Blue 1 - 0 Red", now=T0.replace(minute=45))
    files = list(tmp_path.rglob("*.md"))
    assert files == [log.notes_path]                         # edited in place, not a new file
    body = log.notes_path.read_text(encoding="utf-8")
    assert "second thought" in body and body.count("first thought") == 1
    assert "- Last saved: 2026-11-22 09:45:05" in body
    assert "- At last save: Blue 1 - 0 Red" in body
    assert "- Mode: local" in body and "- Level: Fortress" in body


def test_a_new_session_gets_a_new_file(tmp_path):
    a = SessionLog("practice", "Field 01", root=tmp_path, now=T0)
    a.save("a", now=T0)
    b = SessionLog("practice", "Field 01", root=tmp_path, now=T0)   # started the same second
    b.save("b", now=T0)
    assert a.notes_path != b.notes_path
    assert b.id.endswith("-2")
    assert len(list(tmp_path.rglob("notes.md"))) == 2


# ---------------------------------------------------------------- editing

def test_editor_typing_and_cursor_keys():
    e = NotesEditor()
    for ev in (text("helo"), key(pygame.K_LEFT), text("l"), key(pygame.K_END), key(pygame.K_RETURN),
               text("wall jump too floaty"), key(pygame.K_HOME), key(pygame.K_DELETE), text("W"),
               key(pygame.K_END), key(pygame.K_BACKSPACE)):
        e.handle(ev)
    assert e.text == "hello\nWall jump too float"


# ---------------------------------------------------------------- F2 panel

def test_f2_opens_and_closes_and_saves(tmp_path):
    n = SessionNotes("practice", "Field 01", context=lambda: "Blue 2 - 1 Red", root=tmp_path)
    assert not n.handle(key(pygame.K_a))                    # closed: keys go to the game
    assert n.handle(key(pygame.K_F2)) and n.is_open
    assert n.handle(text("ball felt heavy"))
    assert n.handle(key(pygame.K_a))                        # open: keys don't reach the game
    assert n.gate(Intent(move_x=1, jump_pressed=True)) == Intent()
    assert n.handle(key(pygame.K_F2)) and not n.is_open     # close = save
    body = n.log.notes_path.read_text(encoding="utf-8")
    assert "ball felt heavy" in body and "Blue 2 - 1 Red" in body
    assert n.gate(Intent(move_x=1)) == Intent(move_x=1)


def test_reopening_in_the_same_session_edits_the_same_file(tmp_path):
    n = SessionNotes("local", "Canopy", root=tmp_path)
    n.handle(key(pygame.K_F2)); n.handle(text("one")); n.handle(key(pygame.K_ESCAPE))   # Esc closes too
    assert not n.is_open
    n.handle(key(pygame.K_F2))
    assert n.editor.text == "one"                           # what you wrote is still there
    n.handle(key(pygame.K_RETURN)); n.handle(text("two"))
    n.handle(key(pygame.K_s, pygame.KMOD_LCTRL))             # Ctrl+S saves and stays open
    assert n.is_open
    assert list(tmp_path.rglob("notes.md")) == [n.log.notes_path]
    assert n.log.notes_path.read_text(encoding="utf-8").rstrip().endswith("one\ntwo")


def test_nothing_is_written_for_empty_notes_and_context_errors_are_ignored(tmp_path):
    def broken():
        raise RuntimeError("no view yet")

    n = SessionNotes("join", "Harbor", context=broken, root=tmp_path)
    n.handle(key(pygame.K_F2)); n.handle(key(pygame.K_F2))
    assert not list(tmp_path.rglob("*"))                    # opened and closed with nothing typed
    n.handle(key(pygame.K_F2)); n.handle(text("lag on join")); n.handle(key(pygame.K_F2))
    assert "lag on join" in n.log.notes_path.read_text(encoding="utf-8")


def test_panel_draws_long_and_multiline_notes():
    n = SessionNotes("sandbox", "Arena 01", root=None or __import__("pathlib").Path("unused"))
    n.open()
    for i in range(40):
        n.editor.handle(text(f"line {i} " + "word " * 30))
        n.editor.handle(key(pygame.K_RETURN))
    n.draw(pygame.Surface((1280, 720)))                     # wraps and scrolls without errors
    n.is_open = False


def test_wrap_always_fits_and_keeps_every_character():
    from ballbrawlla.notes import wrap

    font = pygame.font.Font(None, 24)
    para = "short words then averyveryverylongwordwithnospacesatall " * 6
    lines = wrap(font, para, 200)
    assert "".join(t for t, _ in lines) == para
    assert all(font.size(t)[0] <= 200 or len(t) == 1 for t, _ in lines)
    assert [off for _, off in lines] == sorted({off for _, off in lines})
