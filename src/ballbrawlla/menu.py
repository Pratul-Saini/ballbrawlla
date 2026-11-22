"""Launcher menu. `MenuState` holds all the logic and knows nothing about drawing, so it can be tested
without a window; `run_menu` is the pygame loop around it.

Every option that starts a game asks `launch.check_launch`. If the answer is a reason, the option is
greyed out and the reason is shown, so a player can only start things that will run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import time

import pygame

from ballbrawlla import diag
from ballbrawlla.launch import (
    MODE_LABELS, LevelInfo, check_launch, check_level, check_port, list_levels,
)
from ballbrawlla.net.discovery import Finder, FoundGame
from ballbrawlla.net.invite import ALPHABET, CODE_LEN, check_relay, format_code, normalize_code
from ballbrawlla.net.protocol import DEFAULT_PORT, lan_ip
from ballbrawlla.world.level import load_level

TITLE = "GRIDIRON SCRAMBLE"
TAGLINE = "Catch it. Run it. Don't get tagged."
DEFAULT_KEY = "field_01"

BG = (30, 104, 52)         # turf green
PANEL = (20, 72, 36)       # darker green behind the selected row and dialogs
FG = (255, 255, 255)       # options
DIM = (160, 196, 168)      # unavailable options and small print
ACCENT = (150, 92, 44)     # title and tagline: leather brown
BAD = (255, 170, 160)


@dataclass(frozen=True)
class Launch:
    """What the menu hands back when the player starts something."""
    mode: str
    level: Path | None = None
    port: int = DEFAULT_PORT
    address: str = ""
    code: str = ""             # invite code, for "join_code"


@dataclass
class Item:
    label: str
    action: str
    reason: str | None = None   # why it is unavailable; None = available
    hint: str = ""              # right-aligned note, e.g. the current level
    soon: bool = False          # a planned feature: shown greyed, and `reason` describes it instead of an error

    @property
    def enabled(self) -> bool:
        return self.reason is None


@dataclass
class MenuState:
    levels: list[LevelInfo] = field(default_factory=list)
    level_key: str = DEFAULT_KEY      # last level picked; the picker opens on it
    mode: str = ""                    # the mode waiting for a level
    port: int = DEFAULT_PORT
    address: str = ""
    code: str = ""                    # invite code being typed (bare, without the dash)
    screen: str = "main"
    cursor: int = 0
    error: str | None = None          # message dialog; any key dismisses it
    pad_names: list[str] = field(default_factory=list)
    result: Launch | None = None
    quit: bool = False
    _stack: list[str] = field(default_factory=list)
    _port_cache: tuple | None = None
    finder: Finder | None = None     # listens for hosted games while the Join screen is open
    games: list[FoundGame] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.levels:
            self.levels = list_levels()
        if self.level_key not in {i.key for i in self.levels} and self.levels:
            self.level_key = self.levels[0].key

    # ---- queries
    def items(self) -> list[Item]:
        if self.screen == "main":
            return [Item("PLAY", "go:play"), Item("QUIT", "quit")]
        if self.screen == "play":
            return [
                Item("FREE PLAY", "go:freeplay", hint="explore or catch practice"),
                Item("TWO PLAYERS", "mode:local", hint="one screen"),
                Item("ONLINE", "go:online"),
            ]
        if self.screen == "freeplay":
            return [
                Item("EXPLORE", "mode:sandbox", hint="no rules, any level"),
                Item("CATCH PRACTICE", "mode:catch", hint="QB throws, you catch and score, no defender"),
            ]
        if self.screen == "online":
            return [
                Item("HOST ONLINE GAME", "mode:host_online", check_relay() or self._port_reason(),
                     hint="get an invite code to share"),
                Item("JOIN WITH CODE", "go:code", check_relay(), hint="type the host's invite code"),
                Item("HOST ON THIS NETWORK", "mode:host", self._port_reason(), hint=f"you are Blue, port {self.port}"),
                Item("JOIN ON THIS NETWORK", "go:join", hint="you are Red"),
            ]
        if self.screen == "code":
            return [
                Item(f"CODE: {format_code(self.code)}_", "edit", hint="Ctrl+V pastes"),
                Item("CONNECT", "launch:join_code", check_launch("join_code", code=self.code)),
            ]
        if self.screen == "join":
            if self.games:
                found = [Item(g.name, f"found:{n}", hint=g.level or g.address) for n, g in enumerate(self.games)]
            elif self.finder is not None and self.finder.available:
                found = [Item("Looking for games on your network...", "none", hint="or type an address below")]
            else:
                found = [Item("Can't search this network automatically", "none", hint="type an address below")]
            return found + [
                Item(f"ADDRESS: {self.address}_", "edit"),
                Item("CONNECT", "launch:join", check_launch("join", None, self.port, self.address)),
            ]
        if self.screen == "level":
            return [Item(i.name, f"pick:{i.key}", self._level_reason(i),
                         hint=i.summary() if i.usable else "") for i in self.shown_levels()]
        return []

    def shown_levels(self) -> list[LevelInfo]:
        """Levels for the waiting mode: Free play shows everything, match modes only football fields."""
        if self.mode == "sandbox":
            return self.levels
        return [i for i in self.levels if i.football or not i.usable]

    def _level_reason(self, info: LevelInfo) -> str | None:
        # Cheap: uses what list_levels already read. The full check (load the file, build the field,
        # bind the port) runs once, when the player actually launches, in main.start().
        return check_level(self.mode, info)

    def _port_reason(self) -> str | None:
        """Binding the port is a system call, so look at most once a second instead of every frame."""
        now = time.monotonic()
        if self._port_cache is None or self._port_cache[0] != self.port or now - self._port_cache[1] > 1.0:
            self._port_cache = (self.port, now, check_port(self.port))
        return self._port_cache[2]

    def title(self) -> str:
        if self.screen == "level":
            return f"{MODE_LABELS[self.mode].upper()}: CHOOSE A LEVEL"
        return {"main": "", "play": "PLAY", "freeplay": "FREE PLAY", "online": "ONLINE", "join": "JOIN ON THIS NETWORK",
                "code": "JOIN WITH CODE"}[self.screen]

    # ---- navigation
    def _go(self, screen: str) -> None:
        self._stack.append(self.screen)
        self.screen, self.cursor = screen, 0
        diag.log.info("menu: -> %s", screen)
        if screen == "join":
            self.finder = Finder()
            self.games = []
            self.cursor = 1                  # the address row; games found later appear above it
        if screen == "level":
            self.cursor = next((n for n, i in enumerate(self.shown_levels()) if i.key == self.level_key), 0)

    def back(self) -> None:
        if self.error:
            self.error = None
        elif self._stack:
            if self.screen == "join":
                self.close()
            self.screen, self.cursor = self._stack.pop(), 0

    def close(self) -> None:
        if self.finder is not None:
            self.finder.close()
        self.finder, self.games = None, []

    def update(self) -> None:
        """Once per frame: read broadcasts, and keep the cursor on the same row when the games list changes size."""
        if self.screen != "join" or self.finder is None:
            return
        before = max(1, len(self.games))
        self.games = self.finder.poll()
        after = max(1, len(self.games))
        if after != before and self.cursor >= before:
            self.cursor += after - before

    def move(self, step: int) -> None:
        if self.error or not self.items():
            return
        self.cursor = (self.cursor + step) % len(self.items())

    def hover(self, index: int) -> None:
        if not self.error and 0 <= index < len(self.items()):
            self.cursor = index

    def select(self) -> None:
        if self.error:
            self.error = None
            return
        items = self.items()
        if not items:
            return
        item = items[self.cursor]
        diag.log.info("menu: select %r (%s)%s", item.label, item.action, "" if item.enabled else f" refused: {item.reason}")
        if not item.enabled:
            self.error = item.reason
            return
        kind, _, arg = item.action.partition(":")
        if kind == "go":
            self._go(arg)
        elif kind == "quit":
            self.quit = True
        elif kind == "found":
            g = self.games[int(arg)]
            self.result = Launch("join", None, g.port, g.address)
        elif kind == "mode":
            self.mode = arg
            self._go("level")
        elif kind == "pick":
            self.level_key = arg
            info = next(i for i in self.levels if i.key == arg)
            self.result = Launch(self.mode, info.path, self.port)
        elif kind == "launch":
            self.result = Launch(arg, None, self.port, self.address.strip(), self.code)

    # ---- text entry (join address, invite code)
    @property
    def editing(self) -> bool:
        items = self.items() if self.screen in ("join", "code") else []
        return bool(items) and not self.error and items[min(self.cursor, len(items) - 1)].action == "edit"

    def type_char(self, ch: str) -> None:
        if not self.editing:
            return
        if self.screen == "code":
            # Keep anything code-like (so a typo is shown and explained) but ignore dashes and spaces.
            ch = normalize_code(ch)
            if ch.isalnum() and len(self.code) < CODE_LEN + 2:
                self.code += ch
        elif (ch.isdigit() or ch in ".:-" or ch.isalpha()) and len(self.address) < 40:
            self.address += ch

    def backspace(self) -> None:
        if not self.editing:
            return
        if self.screen == "code":
            self.code = self.code[:-1]
        else:
            self.address = self.address[:-1]

    def paste(self, text: str | None) -> None:
        """Ctrl+V: a pasted code (or address) replaces what was typed. Pasting "Code: kq7-m3x" works too."""
        if not self.editing or not text:
            return
        if self.screen == "code":
            words = [normalize_code(w) for w in text.replace(":", " ").split()]
            exact = [w for w in words if len(w) == CODE_LEN and all(c in ALPHABET for c in w)]
            self.code = (exact[-1] if exact else normalize_code(text))[:CODE_LEN + 2]
        else:
            self.address = ""
            for ch in text.strip():
                self.type_char(ch)


# ---------------------------------------------------------------- drawing

_minimaps: dict[tuple, pygame.Surface] = {}


def _minimap(surface: pygame.Surface, info: LevelInfo, box: pygame.Rect) -> None:
    """Drawn once per level and size, then reused: loading a level every frame made the picker crawl."""
    key = (info.key, box.size)
    if key not in _minimaps:
        img = pygame.Surface(box.size)
        img.fill(PANEL)
        try:
            level = load_level(info.path)
        except Exception:
            level = None
        if level is not None:
            s = min(box.w / level.width, box.h / level.height)
            ox = (box.w - level.width * s) / 2
            oy = (box.h - level.height * s) / 2
            for p in level.platforms:
                r = p.rect
                rect = pygame.Rect(ox + r.x * s, oy + r.y * s, max(1, r.w * s), max(1, r.h * s))
                pygame.draw.rect(img, DIM if p.kind == "bound" else ((210, 160, 100) if p.is_thin else FG), rect)
        _minimaps[key] = img
    surface.blit(_minimaps[key], box.topleft)


SELECT_BUTTONS = (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_X)   # Cross or Square
ROW_H = 44


def _rows(state: MenuState, size: tuple[int, int]) -> list[pygame.Rect]:
    w, h = size
    n = len(state.items())
    top = max(150, h // 2 - (min(n, 12) * ROW_H) // 2 + 30)
    first = max(0, state.cursor - 11) if n > 12 else 0
    return [pygame.Rect(w // 2 - 330, top + (k - first) * ROW_H, 660 if state.screen != "level" else 420, ROW_H - 6)
            for k in range(n)]


def _wrap(surface: pygame.Surface, font: pygame.font.Font, message: str, color, box: pygame.Rect) -> None:
    """Draw `message` word-wrapped inside `box`, centered."""
    line, y = "", box.y
    for word in message.split():
        if font.size((line + " " + word).strip())[0] > box.w:
            img = font.render(line, True, color)
            surface.blit(img, img.get_rect(midtop=(box.centerx, y)))
            line, y = word, y + font.get_linesize()
        else:
            line = (line + " " + word).strip()
    surface.blit(font.render(line, True, color), font.render(line, True, color).get_rect(midtop=(box.centerx, y)))


def draw(surface: pygame.Surface, state: MenuState, fonts: dict[str, pygame.font.Font]) -> list[pygame.Rect]:
    """Draw the current screen. Returns each item's rect (for mouse hit-testing)."""
    surface.fill(BG)
    w, h = surface.get_size()
    big, mid, small = fonts["big"], fonts["mid"], fonts["small"]

    def text(font, s, color, **pos):
        img = font.render(s, True, color)
        surface.blit(img, img.get_rect(**pos))

    if state.screen == "main":
        text(big, " ".join(TITLE), ACCENT, midtop=(w // 2, 40))
        text(small, TAGLINE, DIM, midtop=(w // 2, 100))
    else:
        text(big, state.title(), ACCENT, midtop=(w // 2, 40))

    items, rects = state.items(), _rows(state, (w, h))
    n = len(items)
    first = max(0, state.cursor - 11) if n > 12 else 0
    for k, (item, rect) in enumerate(zip(items, rects)):
        if k < first or k > first + 11:
            continue
        sel = k == state.cursor
        if sel:
            pygame.draw.rect(surface, PANEL, rect, border_radius=6)
            pygame.draw.rect(surface, FG, rect, 2, border_radius=6)
        text(mid, item.label, FG if item.enabled else DIM, midleft=(rect.x + 16, rect.centery))
        if item.soon and sel:
            _wrap(surface, small, item.reason, FG, pygame.Rect(w // 2 - 330, h - 200, 660, 90))
        if item.hint:
            text(small, item.hint, DIM, midright=(rect.right - 16, rect.centery))
        if not item.enabled and sel and not item.soon:
            text(small, item.reason, BAD, midtop=(w // 2, h - 110))

    shown = state.shown_levels() if state.screen == "level" else []
    if shown:
        info = shown[state.cursor]
        box = pygame.Rect(w // 2 + 110, 170, 260, 150)
        _minimap(surface, info, box)
        text(small, info.summary() if info.usable else info.error, FG, topleft=(box.x, box.bottom + 10))
    if state.screen == "main":
        pads = ", ".join(state.pad_names)
        text(small, f"controller: {pads}" if pads else "no controller found (keyboard and mouse work)", DIM,
             midbottom=(w // 2, h - 50))
    if state.screen == "online":
        text(small, f"your address: {lan_ip()}", DIM, midbottom=(w // 2, h - 50))
    if state.screen == "code":
        text(small, "The host sees the code on their waiting screen (Ctrl+C there copies it).", DIM,
             midbottom=(w // 2, h - 50))
    text(small, "Up/Down: move   Enter / click / Cross: select   Esc / Circle: back", DIM, midbottom=(w // 2, h - 20))

    if state.error:
        box = pygame.Rect(0, 0, 760, 170)
        box.center = (w // 2, h // 2)
        pygame.draw.rect(surface, PANEL, box, border_radius=8)
        pygame.draw.rect(surface, BAD, box, 2, border_radius=8)
        words, line, y = state.error.split(), "", box.y + 30
        for word in words:
            if small.size(line + " " + word)[0] > box.w - 60:
                text(small, line, FG, midtop=(w // 2, y))
                line, y = word, y + 24
            else:
                line = (line + " " + word).strip()
        text(small, line, FG, midtop=(w // 2, y))
        text(small, "press any key", DIM, midbottom=(w // 2, box.bottom - 12))
    return rects


def _clipboard() -> str | None:
    try:
        return pygame.scrap.get_text()
    except (pygame.error, AttributeError):
        return None


def handle_event(state: MenuState, event: pygame.event.Event, rects: list[pygame.Rect]) -> None:
    if event.type == pygame.QUIT:
        state.quit = True
    elif event.type == pygame.KEYDOWN:
        if state.error:
            state.error = None
        elif event.key == pygame.K_ESCAPE:
            state.back() if state._stack else setattr(state, "quit", True)
        elif event.key == pygame.K_v and event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META) and state.editing:
            state.paste(_clipboard())
        elif event.key == pygame.K_BACKSPACE:
            state.backspace() if state.editing else state.back()
        elif event.key in (pygame.K_UP, pygame.K_w) and not (state.editing and event.key == pygame.K_w):
            state.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s) and not (state.editing and event.key == pygame.K_s):
            state.move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) or (event.key == pygame.K_SPACE and not state.editing):
            if state.editing:
                state.move(1)
            else:
                state.select()
        elif event.unicode and event.unicode.isprintable():
            state.type_char(event.unicode)
    elif event.type == pygame.MOUSEMOTION:
        for k, r in enumerate(rects):
            if r.collidepoint(event.pos):
                state.hover(k)
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if state.error:
            state.error = None
            return
        for k, r in enumerate(rects):
            if r.collidepoint(event.pos):
                state.hover(k)
                state.select()
    elif event.type == pygame.CONTROLLERBUTTONDOWN:
        b = event.button
        if state.error:
            state.error = None
        elif b == pygame.CONTROLLER_BUTTON_DPAD_UP:
            state.move(-1)
        elif b == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            state.move(1)
        elif b in SELECT_BUTTONS:
            state.select()
        elif b == pygame.CONTROLLER_BUTTON_B:
            state.back()


def run_menu(screen: pygame.Surface, state: MenuState | None = None, pad_names: list[str] | None = None,
             pads=None) -> Launch | None:
    """Show the menu until the player starts something (returns the Launch) or quits (returns None)."""
    state = state or MenuState()
    state.pad_names = pad_names or []
    state.result = None
    diag.where("menu")
    diag.log.info("menu open on screen %r", state.screen)
    if state.screen == "join" and state.finder is None:
        state.finder = Finder()      # coming back after a failed join
    fonts = {"big": pygame.font.Font(None, 64), "mid": pygame.font.Font(None, 36), "small": pygame.font.Font(None, 24)}
    pygame.key.set_repeat(350, 40)
    clock = pygame.time.Clock()
    rects: list[pygame.Rect] = []
    try:
        while not state.quit and state.result is None:
            diag.beat()
            for event in pygame.event.get():
                diag.event(event)
                if pads is not None:
                    pads.handle_event(event)         # keeps pads plugged in later working
                handle_event(state, event, rects)
            if pads is not None:
                state.pad_names = pads.names
            state.update()
            rects = draw(screen, state, fonts)
            pygame.display.flip()
            clock.tick(60)
    finally:
        pygame.key.set_repeat()
        state.close()
    return None if state.quit else state.result
