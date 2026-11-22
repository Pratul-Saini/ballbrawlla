extends SceneTree
const Tuning = preload("res://scripts/tuning.gd")
const Level = preload("res://scripts/level.gd")
const Session = preload("res://scripts/session.gd")
const Intent = preload("res://scripts/intent.gd")
func _process(_d: float) -> bool:
	var t = Tuning.new()
	var lv = Level.load_file("res://levels/field_03.json")["level"]
	var s = Session.create(lv, t, 2, [1, 1])["session"]      # coin flips: RIGHT (Red) on offense
	s.set_connected(1, true)
	var c = s.call
	print("PROBE offense=%d range=[%.1f, %.1f] spot=%s start center=(%.1f, %.1f) ok=%s" % [s.down().offense, c.qb_lo, c.qb_hi, str(c.qb_spot), c.qb_player.center_x(), c.qb_player.center_y(), str(c.qb_ok)])
	for i in 240:
		s.step([Intent.new(), Intent.new()], t.dt())
	print("PROBE after 2s idle: center=(%.1f, %.1f) ok=%s placing=%s" % [c.qb_player.center_x(), c.qb_player.center_y(), str(c.qb_ok), str(c.placing)])
	quit(0)
	return true
