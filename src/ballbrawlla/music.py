"""Background music: every audio file in assets/music/ plays in name order, then the list starts over, forever.

No files means no music, and the game says nothing about it. One file loops on its own. The music plays at menu
volume in the menus and a little lower during a game; M mutes it, and - / + lower and raise the volume (a master
level in [0, 1] the HUD meter shows). The context volume is scaled by that master.

Any problem (no audio device, an unreadable file) is logged and the game carries on: a file that won't load is
skipped, and if none will load the game stays silent. Set BALLBRAWLLA_MUSIC=off to turn music off completely
(the tests do). Call `music.update()` once per frame so the next track starts when one ends.
"""

from __future__ import annotations

import os
from pathlib import Path

import pygame

from ballbrawlla import diag
from ballbrawlla.paths import assets_dir

EXTENSIONS = (".mp3", ".ogg", ".wav")
# Per-context base volume, scaled by the user's master level (Music.volume, 0..1).
VOLUME = {"menu": 0.7, "game": 0.45}
VOLUME_STEP = 0.1


def find_tracks(folder: Path | None = None) -> list[Path]:
    """Every audio file in the folder, in name order. Empty if the folder is missing or has none."""
    folder = folder if folder is not None else assets_dir() / "music"
    if not folder.is_dir():
        return []
    return sorted((p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS and not p.name.startswith(".")),
                  key=lambda p: p.name.lower())


class Music:
    def __init__(self) -> None:
        self.tracks: list[Path] = []
        self.index = 0
        self.playing = False
        self.muted = False
        self.context = "menu"
        self.volume = 1.0            # master level in [0, 1]; the HUD meter adjusts it

    @property
    def enabled(self) -> bool:
        return os.environ.get("BALLBRAWLLA_MUSIC", "").lower() not in ("off", "0", "no")

    @property
    def current(self) -> Path | None:
        return self.tracks[self.index] if self.playing and self.tracks else None

    def _target_volume(self) -> float:
        """The volume to hand pygame: the context base scaled by the master level, 0 when muted."""
        if self.muted:
            return 0.0
        return max(0.0, min(1.0, self.volume * VOLUME[self.context]))

    def start(self, folder: Path | None = None) -> bool:
        """Begin playing the list. Returns True if music is playing."""
        if self.playing or not self.enabled:
            return self.playing
        self.tracks = find_tracks(folder)
        if not self.tracks:
            diag.log.info("music: no audio files in assets/music, staying silent")
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error as e:
            diag.log.warning("music: no audio device (%s), staying silent", e)
            return False
        self.index = 0
        self.playing = self._play_from(0)
        return self.playing

    def _play_from(self, first: int) -> bool:
        """Play the first track that loads, starting at `first` and wrapping once around the list."""
        n = len(self.tracks)
        for step in range(n):
            i = (first + step) % n
            track = self.tracks[i]
            try:
                pygame.mixer.music.load(str(track))
                pygame.mixer.music.set_volume(self._target_volume())
                pygame.mixer.music.play(loops=-1 if n == 1 else 0)    # a single track repeats by itself
            except pygame.error as e:
                diag.log.warning("music: skipping %s: %s", track.name, e)
                continue
            self.index = i
            diag.log.info("music: playing %s (%d of %d)", track.name, i + 1, n)
            return True
        diag.log.warning("music: none of the %d files could be played, staying silent", n)
        return False

    def update(self) -> None:
        """Call every frame. When a track ends, start the next one (the first again after the last)."""
        if not self.playing or len(self.tracks) < 2:
            return
        try:
            busy = pygame.mixer.music.get_busy()
        except pygame.error:
            return
        if not busy:
            self.playing = self._play_from(self.index + 1)

    def set_context(self, context: str) -> None:
        """"menu" or "game": the game plays quieter so its own feedback stays clear."""
        self.context = context
        self._apply_volume()

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        self._apply_volume()
        diag.log.info("music: %s", "muted" if self.muted else "unmuted")
        return self.muted

    def set_volume(self, level: float) -> float:
        """Set the master level (clamped to [0, 1]) and apply it. Returns the new level."""
        self.volume = max(0.0, min(1.0, level))
        self._apply_volume()
        return self.volume

    def change_volume(self, delta: float) -> float:
        return self.set_volume(self.volume + delta)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """M toggles mute; - / + lower and raise the volume. Returns True if the event was
        used. Don't call this while text is being typed."""
        if event.type != pygame.KEYDOWN or (event.mod & pygame.KMOD_CTRL):
            return False
        if event.key == pygame.K_m:
            self.toggle_mute()
            return True
        if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.change_volume(-VOLUME_STEP)
            return True
        if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.change_volume(VOLUME_STEP)
            return True
        return False

    def _apply_volume(self) -> None:
        if self.playing:
            try:
                pygame.mixer.music.set_volume(self._target_volume())
            except pygame.error:
                pass

    def stop(self) -> None:
        if self.playing:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
            self.playing = False


music = Music()
