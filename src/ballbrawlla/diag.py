"""Diagnostics: one log file per run in logs/, so a problem can be read instead of described.

    logs/run-<pid>.log      this run (the five newest are kept)
    logs/latest.log         a copy of the path to the newest run (plain text, one line)

What it records: the machine and library versions, the window (requested flags, where macOS put it, whether it
is active), window events, a heartbeat every two seconds with the frame rate, any frame that took over 100 ms,
menu and launch decisions, every exception with its traceback, and a stack dump of the main thread whenever
the loop stops beating for three seconds, which is what a hang looks like from the inside.

Set BALLBRAWLLA_LOG=debug for per-event detail.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import threading
import time
import traceback
from pathlib import Path

from ballbrawlla.paths import logs_dir

LOG_DIR = logs_dir()
KEEP = 5
STALL_SECONDS = 3.0
HEARTBEAT_SECONDS = 2.0
SLOW_FRAME_MS = 100.0

log = logging.getLogger("ballbrawlla")
log.addHandler(logging.NullHandler())   # silent until setup() adds the file
_cache: dict = {}
_state = {"path": None, "beat": time.monotonic(), "where": "startup", "frames": 0, "since": time.monotonic(),
          "worst": 0.0, "last": None, "watchdog": None}


def setup() -> Path | None:
    """Start logging to a new file. Never raises: a logging problem must not stop the game."""
    if _state["path"] is not None:
        return _state["path"]
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        old = sorted(LOG_DIR.glob("run-*.log"), key=lambda p: p.stat().st_mtime)
        for p in old[:-(KEEP - 1)] if len(old) >= KEEP else []:
            p.unlink(missing_ok=True)
        path = LOG_DIR / f"run-{os.getpid()}.log"
        handler = logging.FileHandler(path, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
        level = logging.DEBUG if os.environ.get("BALLBRAWLLA_LOG", "").lower() == "debug" else logging.INFO
        log.setLevel(level)
        log.addHandler(handler)
        log.propagate = False
        (LOG_DIR / "latest.log").write_text(str(path) + "\n")
        _state["path"] = path
    except OSError:
        return None
    log.info("start: python %s on %s, argv=%s", platform.python_version(), platform.platform(), sys.argv[1:])
    log.info("cwd=%s  SDL env=%s", os.getcwd(), {k: v for k, v in os.environ.items() if k.startswith("SDL")} or "none")
    sys.excepthook = _excepthook
    _start_watchdog()
    return path


def _excepthook(kind, value, tb) -> None:
    log.error("unhandled exception:\n%s", "".join(traceback.format_exception(kind, value, tb)))
    sys.__excepthook__(kind, value, tb)


def describe_pygame() -> None:
    """Versions and the display, after pygame.init()."""
    import pygame
    log.info("pygame-ce %s, SDL %s", pygame.version.ver, ".".join(map(str, pygame.get_sdl_version())))
    try:
        log.info("video driver=%s  desktops=%s", pygame.display.get_driver(), pygame.display.get_desktop_sizes())
    except pygame.error as e:
        log.warning("display info unavailable: %s", e)


def describe_window(label: str, requested_flags: str = "") -> None:
    """Where the window actually is. 'active: False' or an off-screen position explains 'nothing opened'."""
    import pygame
    try:
        info = f"position={tuple(pygame.display.get_window_position())} size={tuple(pygame.display.get_window_size())}"
    except Exception as e:  # noqa: BLE001 - diagnostics must never raise
        info = f"window query failed: {e}"
    surf = pygame.display.get_surface()
    log.info("window %r flags=[%s]: %s surface=%s active=%s desktops=%s", label, requested_flags, info,
             surf.get_size() if surf else None, pygame.display.get_active(), pygame.display.get_desktop_sizes())


def where(name: str) -> None:
    """Say what the main loop is doing (shown in stall dumps and heartbeats)."""
    if _state["where"] != name:
        log.info("now in: %s", name)
    _state["where"] = name


def beat(clock=None) -> None:
    """Call once per frame from every loop. Feeds the stall watchdog and writes the heartbeat."""
    now = time.monotonic()
    gap = (now - _state["beat"]) * 1000
    if gap > SLOW_FRAME_MS and _state["frames"] > 0:
        log.warning("slow frame: %.0f ms since the last frame (in %s)", gap, _state["where"])
    _state["worst"] = max(_state["worst"], gap if _state["frames"] else 0.0)
    _state["beat"] = now
    _state["frames"] += 1
    elapsed = now - _state["since"]
    if elapsed >= HEARTBEAT_SECONDS:
        import pygame
        try:
            active = pygame.display.get_active()
        except pygame.error:
            active = "?"
        log.info("heartbeat in %s: %.0f fps, worst frame %.0f ms, window active=%s",
                 _state["where"], _state["frames"] / elapsed, _state["worst"], active)
        _state.update(frames=0, since=now, worst=0.0)


def event(ev) -> None:
    """Window and focus events matter when a window 'doesn't show up'; everything else is debug noise."""
    import pygame
    if "names" not in _cache:       # build once; this runs for every event
        _cache["names"] = {getattr(pygame, n): n for n in dir(pygame)
                           if n.startswith("WINDOW") and isinstance(getattr(pygame, n), int)}
        _cache["input"] = _INPUT_EVENTS(pygame)
    names = _cache["names"]
    if ev.type in names:
        log.info("window event: %s %s", names[ev.type], {k: v for k, v in ev.dict.items() if k != "window"})
    elif ev.type in _cache["input"]:
        log.info("input: %s %s", pygame.event.event_name(ev.type), {k: v for k, v in ev.dict.items() if k != "window"})
    elif log.isEnabledFor(logging.DEBUG) and ev.type != pygame.MOUSEMOTION:
        log.debug("event: %s", ev)


def _INPUT_EVENTS(pygame) -> set[int]:
    """Clicks, pad buttons and device changes: rare enough to log always, and what you need to see whether input arrives."""
    return {pygame.MOUSEBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERDEVICEADDED,
            pygame.CONTROLLERDEVICEREMOVED, pygame.JOYBUTTONDOWN, pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED}


def _start_watchdog() -> None:
    if _state["watchdog"] is not None:
        return
    main_id = threading.main_thread().ident

    def watch() -> None:
        reported = False
        while True:
            time.sleep(1.0)
            stalled = time.monotonic() - _state["beat"]
            if stalled > STALL_SECONDS and not reported:
                frame = sys._current_frames().get(main_id)
                stack = "".join(traceback.format_stack(frame)) if frame else "(no stack)"
                log.error("STALL: no frame for %.1f s, last in %s. Main thread is at:\n%s", stalled, _state["where"], stack)
                reported = True
            elif stalled <= STALL_SECONDS and reported:
                log.warning("recovered after a stall")
                reported = False

    t = threading.Thread(target=watch, name="ballbrawlla-watchdog", daemon=True)
    t.start()
    _state["watchdog"] = t
