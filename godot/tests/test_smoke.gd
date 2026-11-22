extends "res://tests/test_case.gd"

func test_runner_works() -> void:
	check_eq(1 + 1, 2, "arithmetic")

func test_floats_are_64_bit() -> void:
	# The simulation must use plain floats (64-bit), not Vector2 (32-bit), to match Python.
	check_near(0.1 + 0.2, 0.30000000000000004, 1e-18, "double precision")
