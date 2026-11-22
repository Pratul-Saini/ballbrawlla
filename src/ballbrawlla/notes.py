"""Session notes: press F2 in any mode to write notes about this play session.

A session is one run of the game. Its notes live in
    logs/sessions/<YYYY-MM-DD_HH-MM-SS>_<mode>_<level>/notes.md
Every save in the same session rewrites that same file (reopening the panel
brings back what you wrote, so you keep editing it); the next run of the game
starts a new session and a new file. Notes are also saved when the game quits.

While the panel is open, keystrokes go to the notes, never to your player.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pygame

from ballbrawlla.input import Intent

LOGS = Path(__file__).resolve().parents[2] / "logs" / "sessions"
TOGGLE_KEY = pygame.K_F2


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower() or "level"


def wrap(font, para: str, max_w: int) -> list[tuple[str, int]]:
    """Split one paragraph into lines no wider than max_w, breaking at spaces where
    possible. Returns (line, offset in para). Always makes progress."""
    if not para:
        return [("", 0)]
    out, pos, n = [], 0, len(para)
    while pos < n:
        end = n
        if font.size(para[pos:end])[0] > max_w:
            lo, hi = pos + 1, n                    # longest prefix that fits (at least 1 char)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.size(para[pos:mid])[0] <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            end = lo
            space = para.rfind(" ", pos, end)
            if space > pos:
                end = space + 1                    # break after the last space that fits
        out.append((para[pos:end], pos))
        pos = end
    return out


class SessionLog:
    """Where this session's notes are written. The file is created on the first save."""

    def __init__(self, mode: str, level: str, root: Path = LOGS, now: datetime | None = None) -> None:
        self.mode = mode
        self.level = level
        self.started = now or datetime.now()
        base = f"{self.started:%Y-%m-%d_%H-%M-%S}_{_slug(mode)}_{_slug(level)}"
        self.id, n = base, 2
        while (root / self.id).exists():          # two runs started in the same second
            self.id, n = f"{base}-{n}", n + 1
        self.dir = root / self.id
        self.notes_path = self.dir / "notes.md"

    def save(self, text: str, context: str = "", now: datetime | None = None) -> Path:
        """Write the notes, replacing this session's previous save."""
        now = now or datetime.now()
        header = [
            "# Session notes",
            "",
            f"- Session: {self.id}",
            f"- Mode: {self.mode}",
            f"- Level: {self.level}",
            f"- Started: {self.started:%Y-%m-%d %H:%M:%S}",
            f"- Last saved: {now:%Y-%m-%d %H:%M:%S}",
        ]
        if context:
            header.append(f"- At last save: {context}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.notes_path.write_text("\n".join(header) + "\n\n" + text.rstrip() + "\n", encoding="utf-8")
        return self.notes_path


class NotesEditor:
    """A plain multi-line text box: typing, Enter, Backspace/Delete, arrows, Home/End."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.cursor = len(text)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.TEXTINPUT:
            self._insert(event.text)
        elif event.type == pygame.KEYDOWN:
            k = event.key
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._insert("\n")
            elif k == pygame.K_BACKSPACE and self.cursor > 0:
                self.text = self.text[: self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
            elif k == pygame.K_DELETE and self.cursor < len(self.text):
                self.text = self.text[: self.cursor] + self.text[self.cursor + 1:]
            elif k == pygame.K_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif k == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor + 1)
            elif k == pygame.K_HOME:
                self.cursor = self.text.rfind("\n", 0, self.cursor) + 1
            elif k == pygame.K_END:
                end = self.text.find("\n", self.cursor)
                self.cursor = len(self.text) if end < 0 else end

    def _insert(self, s: str) -> None:
        self.text = self.text[: self.cursor] + s + self.text[self.cursor:]
        self.cursor += len(s)


class SessionNotes:
    """F2 notes for one session: the editor, its log file, and the overlay."""

    def __init__(self, mode: str, level: str, context: Callable[[], str] | None = None,
                 root: Path = LOGS) -> None:
        self.log = SessionLog(mode, level, root=root)
        self.editor = NotesEditor()
        self.context = context or (lambda: "")
        self.is_open = False
        self.saved_text: str | None = None   # what's on disk (None = nothing saved yet)
        self.status = ""
        self._font: pygame.font.Font | None = None

    # ------------------------------------------------------------ control

    def open(self) -> None:
        self.is_open = True
        pygame.key.start_text_input()

    def close(self) -> None:
        self.save()
        self.is_open = False
        pygame.key.stop_text_input()

    def save(self) -> Path | None:
        """Save if there's anything new. Returns the file written, if any."""
        text = self.editor.text
        if not text.strip() or text == self.saved_text:
            return None
        path = self.log.save(text, self._context())
        self.saved_text = text
        self.status = f"saved at {datetime.now():%H:%M:%S}"
        return path

    def _context(self) -> str:
        try:
            return self.context()
        except Exception:      # notes must never crash the game
            return ""

    def handle(self, event: pygame.event.Event) -> bool:
        """Feed an event in. Returns True if the notes used it (don't pass it on)."""
        if event.type == pygame.KEYDOWN and event.key == TOGGLE_KEY:
            self.close() if self.is_open else self.open()
            return True
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
            elif event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
                self.save()
            else:
                self.editor.handle(event)
            return True
        if event.type in (pygame.TEXTINPUT, pygame.KEYUP, pygame.TEXTEDITING,
                          pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if event.type == pygame.TEXTINPUT:
                self.editor.handle(event)
            return True
        return False

    def gate(self, intent: Intent) -> Intent:
        """Your player's input, or nothing while you're typing notes."""
        return Intent() if self.is_open else intent

    # ------------------------------------------------------------ drawing

    def draw(self, screen: pygame.Surface) -> None:
        if not self.is_open:
            return
        if self._font is None:
            self._font = pygame.font.Font(None, 24)
        f = self._font
        sw, sh = screen.get_size()
        panel = pygame.Rect(0, 0, min(900, sw - 80), min(480, sh - 120))
        panel.center = (sw // 2, sh // 2 + 20)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((14, 15, 20, 235))
        screen.blit(shade, panel.topleft)
        pygame.draw.rect(screen, (150, 155, 170), panel, 1, border_radius=4)

        title = f.render(f"Session notes  -  logs/sessions/{self.log.id}/notes.md", True, (230, 230, 230))
        screen.blit(title, (panel.x + 14, panel.y + 10))
        footer = "Enter: new line   Ctrl+S: save   Esc / F2: save and close"
        if self.status:
            footer += f"   |   {self.status}"
        screen.blit(f.render(footer, True, (140, 145, 160)), (panel.x + 14, panel.bottom - 28))

        # wrap text into lines that fit, keeping track of where the cursor lands
        max_w = panel.w - 28
        lines: list[tuple[str, int]] = []   # (text, index in the full string where it starts)
        start = 0
        for para in self.editor.text.split("\n"):
            lines += [(t, start + off) for t, off in wrap(f, para, max_w)]
            start += len(para) + 1
        line_h = 24
        visible = max(1, (panel.h - 80) // line_h)
        cur = self.editor.cursor
        cur_line = max(i for i, (_, s) in enumerate(lines) if s <= cur)
        first = max(0, cur_line - visible + 1)
        y = panel.y + 44
        for i, (text, s) in enumerate(lines[first:first + visible], start=first):
            screen.blit(f.render(text, True, (220, 222, 228)), (panel.x + 14, y))
            if i == cur_line and (pygame.time.get_ticks() // 500) % 2 == 0:
                cx = panel.x + 14 + f.size(text[: cur - s])[0]
                pygame.draw.line(screen, (255, 230, 120), (cx, y), (cx, y + 18), 2)
            y += line_h
