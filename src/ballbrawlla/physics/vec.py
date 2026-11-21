"""Single import point for the 2D vector type used throughout the simulation."""

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from pygame.math import Vector2  # noqa: E402

__all__ = ["Vector2"]
