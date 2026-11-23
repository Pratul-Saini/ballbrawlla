extends RefCounted
## Turns a level dict (levels.gd) into 3-D geometry: one StaticBody3D of box colliders + meshes, plus
## cosmetic end-zone tints and a midfield line. Also holds the field math (yards, goal lines, end zones).
##
## Teams: 0 = LEFT (defends -X, attacks +X), 1 = RIGHT (defends +X, attacks -X), like the 2-D game.
## NOTE: "thin" one-way platforms are approximated as thin solids here (Godot 3-D has no built-in
## one-way collision); you land on them but can't jump up through them yet. See README.

const Cfg = preload("res://scripts/config.gd")
const Levels = preload("res://scripts/levels.gd")

var level: Dictionary

func _mat(c: Color, rough := 0.95) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	return m

func _kind_color(kind: String) -> Color:
	match kind:
		"ground": return Color(0.24, 0.45, 0.28)   # turf green
		"wall":   return Color(0.42, 0.44, 0.50)
		"thin":   return Color(0.62, 0.78, 0.82)
		_:        return Color(0.55, 0.58, 0.66)    # solid
	return Color(0.55, 0.58, 0.66)

func build(parent: Node3D, lvl: Dictionary) -> void:
	level = lvl
	var body := StaticBody3D.new()
	body.name = "Arena"
	body.collision_layer = 1
	body.collision_mask = 0
	parent.add_child(body)
	for box in lvl["boxes"]:
		_add_box(body, box["pos"], box["size"], box["kind"])
		if box.get("mirror", false):
			var p: Vector3 = box["pos"]
			_add_box(body, Vector3(-p.x, p.y, p.z), box["size"], box["kind"])
	_add_markings(parent)

func _add_box(body: StaticBody3D, center: Vector3, size: Vector3, kind: String) -> void:
	var shape := BoxShape3D.new()
	shape.size = size
	var col := CollisionShape3D.new()
	col.shape = shape
	col.transform.origin = center
	body.add_child(col)
	var mesh := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mesh.mesh = bm
	mesh.material_override = _mat(_kind_color(kind))
	mesh.transform.origin = center
	body.add_child(mesh)

func _add_markings(parent: Node3D) -> void:
	# End-zone tint slabs just above the floor (cosmetic), and a midfield stripe.
	var ez := Cfg.END_ZONE_YARDS
	_slab(parent, Vector3(-(Cfg.GOAL_X + ez / 2.0), 0.02, 0), Vector3(ez, 0.02, Cfg.FIELD_WIDTH),
		Color(0.25, 0.55, 1.0, 1.0))                                   # LEFT end zone (blue)
	_slab(parent, Vector3(Cfg.GOAL_X + ez / 2.0, 0.02, 0), Vector3(ez, 0.02, Cfg.FIELD_WIDTH),
		Color(1.0, 0.35, 0.35, 1.0))                                   # RIGHT end zone (red = the target)
	_slab(parent, Vector3(0, 0.03, 0), Vector3(0.6, 0.02, Cfg.FIELD_WIDTH), Color(1, 1, 1))  # midfield
	for yards in [-50, -40, -30, -20, -10, 10, 20, 30, 40, 50]:
		_slab(parent, Vector3(float(yards), 0.025, 0), Vector3(0.3, 0.02, Cfg.FIELD_WIDTH),
			Color(1, 1, 1, 0.5))

func _slab(parent: Node3D, center: Vector3, size: Vector3, c: Color) -> void:
	var mesh := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mesh.mesh = bm
	var m := _mat(c)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA if c.a < 1.0 else BaseMaterial3D.TRANSPARENCY_DISABLED
	mesh.material_override = m
	mesh.transform.origin = center
	parent.add_child(mesh)

# ------------------------------------------------------------ field math (static)

static func attack_dir(team: int) -> int:
	return 1 if team == 0 else -1

static func goal_line_x(team: int) -> float:
	return -Cfg.GOAL_X if team == 0 else Cfg.GOAL_X

static func in_end_zone(team: int, x: float) -> bool:
	# True if x is inside `team`'s own end zone.
	return x <= -Cfg.GOAL_X if team == 0 else x >= Cfg.GOAL_X

static func yards_from_goal(team: int, x: float) -> float:
	return (x - goal_line_x(team)) * attack_dir(team)
