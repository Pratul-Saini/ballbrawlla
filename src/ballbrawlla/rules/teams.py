"""Teams and roles.

Each team defends the same end zone all match; only who is on offense changes.
"""

from enum import Enum, IntEnum


class Team(IntEnum):
    LEFT = 0   # defends the left end zone, attacks to the right
    RIGHT = 1  # defends the right end zone, attacks to the left

    @property
    def other(self) -> "Team":
        return Team.RIGHT if self is Team.LEFT else Team.LEFT

    @property
    def attack_dir(self) -> int:
        """+1 if this team scores by moving right, -1 if by moving left."""
        return 1 if self is Team.LEFT else -1

    @property
    def display(self) -> str:
        return "Blue" if self is Team.LEFT else "Red"


class Role(str, Enum):
    QB = "QB"    # offense: placed during the play call, throws automatically, can't be tagged
    WR = "WR"    # offense: runs, catches/picks up; tags the Defender after an interception
    DEF = "DEF"  # defense: runs, catches/picks up; tags the WR when the WR has the ball


CAN_THROW = {Role.QB: True, Role.WR: False, Role.DEF: False}
