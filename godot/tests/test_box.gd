extends "res://tests/test_case.gd"

const Box = preload("res://scripts/box.gd")

func test_touching_boxes_do_not_overlap() -> void:
	check(not Box.new(0, 0, 10, 10).overlaps(Box.new(10, 0, 10, 10)), "side by side")
	check(not Box.new(0, 0, 10, 10).overlaps(Box.new(0, 10, 10, 10)), "stacked")

func test_overlapping_boxes_overlap_both_ways() -> void:
	var a := Box.new(0, 0, 10, 10)
	var b := Box.new(9.99, 9.99, 10, 10)
	check(a.overlaps(b) and b.overlaps(a), "corner overlap")

func test_edges_center_and_shift() -> void:
	var a := Box.new(5, 7, 10, 20)
	check_near(a.right(), 15.0)
	check_near(a.bottom(), 27.0)
	check_near(a.center_x(), 10.0)
	check_near(a.center_y(), 17.0)
	check_eq(a.shifted(1, -2).to_array(), [6.0, 5.0, 10.0, 20.0], "shifted")
	check_eq(a.to_array(), [5.0, 7.0, 10.0, 20.0], "original untouched")
