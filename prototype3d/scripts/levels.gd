extends RefCounted
## The prototype's own level format and its hand-built arenas.
##
## A level is { name, boxes: Array }. Each box is { pos (center), size, kind, mirror }:
##   kind  "ground" | "solid" | "wall" | "thin"   (thin = one-way: land on top, jump up through)
##   mirror  true  -> a matching box is also placed at mirrored X (fairness across midfield),
##           false -> the box is used as-is (use for pieces centered on the midfield plane).
## Coordinates are yards: X runs goal-to-goal (midfield at 0), Z sideline-to-sideline, Y up.
## This module has NO geometry logic; arena.gd turns these into colliders and meshes.

const Cfg = preload("res://scripts/config.gd")

static func _box(pos: Vector3, size: Vector3, kind: String, mirror: bool = true) -> Dictionary:
	return {"pos": pos, "size": size, "kind": kind, "mirror": mirror}

static func all() -> Array:
	return [_greybox(), _ledges()]

# A hull every arena shares: a floor the length of the field, sidelines, and back walls behind each end zone.
static func _shell(boxes: Array) -> void:
	var L := Cfg.HALF_LENGTH
	var W := Cfg.HALF_WIDTH
	boxes.append(_box(Vector3(0, -1, 0), Vector3(2 * L + 4, 2, 2 * W + 4), "ground", false))   # floor, top at y=0
	boxes.append(_box(Vector3(0, 5, W + 0.5), Vector3(2 * L + 4, 10, 1), "wall", false))        # far sideline
	boxes.append(_box(Vector3(0, 5, -W - 0.5), Vector3(2 * L + 4, 10, 1), "wall", false))       # near sideline
	boxes.append(_box(Vector3(-L - 0.5, 5, 0), Vector3(1, 10, 2 * W + 4), "wall", true))         # back walls (both ends)

# Greybox: the headline level. Stairs + a mid tier, a wall-jump chimney up to a high perch, cover, a thin catwalk.
static func _greybox() -> Dictionary:
	var b: Array = []
	_shell(b)
	# steps up to a mid tier (an easy route; the tier is also within a jump of the floor)
	b.append(_box(Vector3(-17, 1.0, -8), Vector3(4, 2, 8), "solid"))
	b.append(_box(Vector3(-21, 2.5, -8), Vector3(4, 3, 8), "solid"))
	b.append(_box(Vector3(-26, 4.0, -8), Vector3(10, 1, 10), "solid"))     # the mid tier platform (top y = 4.5)
	# a thin catwalk reached by a jump off the tier (you can also jump up through it from below)
	b.append(_box(Vector3(-20, 7.5, 6), Vector3(12, 0.3, 4), "thin"))
	# a two-wall chimney up to a high perch (the only way up to the perch)
	b.append(_box(Vector3(-6, 6, 11), Vector3(1, 12, 5), "wall"))
	b.append(_box(Vector3(-2, 6, 11), Vector3(1, 12, 5), "wall"))
	b.append(_box(Vector3(-4, 12, 11), Vector3(6, 1, 7), "solid"))         # the perch (top y = 12.5)
	# cover to dodge around near midfield
	b.append(_box(Vector3(-12, 2, 4), Vector3(3, 4, 3), "solid"))
	b.append(_box(Vector3(-30, 1.5, 7), Vector3(4, 3, 4), "solid"))
	b.append(_box(Vector3(-40, 2, -5), Vector3(5, 4, 5), "solid"))
	return {"name": "Greybox", "boxes": b}

# Ledges: a calmer second level (proves the level system is data-driven), mostly flat with scattered perches.
static func _ledges() -> Dictionary:
	var b: Array = []
	_shell(b)
	b.append(_box(Vector3(-30, 2, -6), Vector3(8, 1, 8), "solid"))
	b.append(_box(Vector3(-18, 4, 4), Vector3(8, 1, 8), "thin"))
	b.append(_box(Vector3(-8, 6, -4), Vector3(8, 1, 8), "thin"))
	b.append(_box(Vector3(-22, 1.5, 10), Vector3(4, 3, 4), "solid"))
	b.append(_box(Vector3(-40, 2.5, 8), Vector3(5, 5, 5), "solid"))
	return {"name": "Ledges", "boxes": b}
