extends RefCounted
## Teams and roles (src/ballbrawlla/rules/teams.py). Each team defends the same end zone all match; only who is on
## offense changes. Team ids are ints so they can be used as dictionary keys and array indexes.

const LEFT := 0    # defends the left end zone, attacks to the right (Blue)
const RIGHT := 1   # defends the right end zone, attacks to the left (Red)

const ROLE_QB := "QB"    # offense: placed during the play call, throws automatically, can't be tagged
const ROLE_WR := "WR"    # offense: runs, catches/picks up; tags the Defender after an interception
const ROLE_DEF := "DEF"  # defense: runs, catches/picks up; tags the WR when the WR has the ball

static func other(team: int) -> int:
	return RIGHT if team == LEFT else LEFT

## +1 if this team scores by moving right, -1 if by moving left.
static func attack_dir(team: int) -> int:
	return 1 if team == LEFT else -1

static func display(team: int) -> String:
	return "Blue" if team == LEFT else "Red"

static func can_throw(role: String) -> bool:
	return role == ROLE_QB
