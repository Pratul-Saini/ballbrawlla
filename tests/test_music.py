"""Music: every file in the folder plays in order and loops; no files means silence; nothing takes the game down."""

import math
import struct
import wave

import pygame
import pytest

from ballbrawlla.music import VOLUME, Music, find_tracks


def write_wav(path, seconds=0.2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(int(22050 * seconds))))


@pytest.fixture
def silent_audio(monkeypatch):
    """Real mixer, dummy device: no sound, but the same code path as a real run."""
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("BALLBRAWLLA_MUSIC", "on")
    pygame.mixer.quit()
    yield
    pygame.mixer.quit()


@pytest.fixture
def playlist(tmp_path):
    for name in ("02_b.wav", "01_a.wav", "03_c.wav"):
        write_wav(tmp_path / name)
    return tmp_path


# ---------------------------------------------------------------- which files

def test_missing_or_empty_folder_means_no_tracks(tmp_path):
    assert find_tracks(tmp_path / "missing") == []
    assert find_tracks(tmp_path) == []


def test_every_audio_file_is_found_in_name_order_and_the_rest_ignored(tmp_path):
    for name in ("b_song.mp3", "A_song.ogg", "10_last.wav", "notes.txt", ".hidden.mp3", "cover.png"):
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in find_tracks(tmp_path)] == ["10_last.wav", "A_song.ogg", "b_song.mp3"]


def test_the_shipped_folder_has_no_audio_so_the_game_is_silent_by_default():
    assert all(p.suffix in (".mp3", ".ogg", ".wav") for p in find_tracks())
    # the README in that folder must never be mistaken for music
    assert "README.txt" not in [p.name for p in find_tracks()]


# ---------------------------------------------------------------- silence

def test_off_switch_means_nothing_loads(monkeypatch, playlist):
    monkeypatch.setenv("BALLBRAWLLA_MUSIC", "off")
    assert Music().start(playlist) is False


def test_empty_folder_stays_silent_and_quiet(silent_audio, tmp_path):
    m = Music()
    assert m.start(tmp_path) is False and not m.playing and m.current is None
    m.update()                                     # harmless with nothing playing
    m.toggle_mute()
    m.set_context("game")
    m.stop()


def test_no_audio_device_stays_silent(monkeypatch, playlist):
    monkeypatch.setenv("BALLBRAWLLA_MUSIC", "on")
    pygame.mixer.quit()
    monkeypatch.setattr(pygame.mixer, "init", lambda *a, **k: (_ for _ in ()).throw(pygame.error("no device")))
    assert Music().start(playlist) is False


def test_a_folder_of_unreadable_files_stays_silent(silent_audio, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"not audio")
    (tmp_path / "b.ogg").write_bytes(b"not audio either")
    m = Music()
    assert m.start(tmp_path) is False and not m.playing


def test_an_unreadable_file_is_skipped_and_the_rest_play(silent_audio, tmp_path):
    (tmp_path / "01_bad.mp3").write_bytes(b"not audio")
    write_wav(tmp_path / "02_good.wav")
    m = Music()
    assert m.start(tmp_path) is True and m.current.name == "02_good.wav"


# ---------------------------------------------------------------- the playlist

def test_plays_the_first_file_and_moves_through_the_list_then_wraps(silent_audio, playlist, monkeypatch):
    m = Music()
    assert m.start(playlist) is True and m.current.name == "01_a.wav"
    monkeypatch.setattr(pygame.mixer.music, "get_busy", lambda: True)
    m.update()
    assert m.current.name == "01_a.wav"                          # still playing: no change
    monkeypatch.setattr(pygame.mixer.music, "get_busy", lambda: False)
    seen = [m.current.name]
    for _ in range(4):
        m.update()                                               # each time a track has ended
        seen.append(m.current.name)
    assert seen == ["01_a.wav", "02_b.wav", "03_c.wav", "01_a.wav", "02_b.wav"]


def test_a_bad_file_in_the_middle_is_skipped_when_advancing(silent_audio, tmp_path, monkeypatch):
    write_wav(tmp_path / "01_a.wav")
    (tmp_path / "02_bad.mp3").write_bytes(b"not audio")
    write_wav(tmp_path / "03_c.wav")
    m = Music()
    m.start(tmp_path)
    monkeypatch.setattr(pygame.mixer.music, "get_busy", lambda: False)
    m.update()
    assert m.current.name == "03_c.wav"


def test_a_single_file_repeats_by_itself(silent_audio, tmp_path):
    import time
    write_wav(tmp_path / "only.wav", seconds=0.1)
    m = Music()
    m.start(tmp_path)
    time.sleep(0.45)                                             # several times the track length
    m.update()
    assert pygame.mixer.music.get_busy() and m.current.name == "only.wav"


def test_real_playback_moves_on_by_itself(silent_audio, tmp_path):
    import time
    write_wav(tmp_path / "01_a.wav", seconds=0.1)
    write_wav(tmp_path / "02_b.wav", seconds=0.1)
    m = Music()
    m.start(tmp_path)
    names = {m.current.name}
    deadline = time.time() + 3
    while time.time() < deadline and len(names) < 2:
        time.sleep(0.02)
        m.update()
        names.add(m.current.name)
    assert names == {"01_a.wav", "02_b.wav"}


# ---------------------------------------------------------------- volume and mute

def test_volume_follows_context_and_mute_survives_track_changes(silent_audio, playlist, monkeypatch):
    m = Music()
    m.start(playlist)
    assert pygame.mixer.music.get_volume() == pytest.approx(VOLUME["menu"], abs=0.02)
    m.set_context("game")
    assert pygame.mixer.music.get_volume() == pytest.approx(VOLUME["game"], abs=0.02)
    assert m.toggle_mute() is True and pygame.mixer.music.get_volume() == 0
    monkeypatch.setattr(pygame.mixer.music, "get_busy", lambda: False)
    m.update()                                                   # next track starts muted, not loud
    assert m.current.name == "02_b.wav" and pygame.mixer.music.get_volume() == 0
    assert m.toggle_mute() is False
    assert pygame.mixer.music.get_volume() == pytest.approx(VOLUME["game"], abs=0.02)
    assert m.start(playlist) is True                             # starting twice doesn't restart or stack
    m.stop()
    assert not m.playing


def test_m_key_mutes_but_ctrl_m_does_not():
    m = Music()
    press = lambda mod: pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, mod=mod, unicode="m")
    assert m.handle_event(press(0)) is True and m.muted
    assert m.handle_event(press(pygame.KMOD_CTRL)) is False and m.muted
    assert m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a")) is False


def test_menu_does_not_steal_m_while_typing_an_address():
    from ballbrawlla.menu import MenuState
    s = MenuState()
    for label in ("PLAY", "ONLINE", "JOIN GAME"):
        s.cursor = [i.label.split(":")[0] for i in s.items()].index(label)
        s.select()
    s.close()
    assert s.editing                                       # the code box is focused: the loop must skip the M hotkey
