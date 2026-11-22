extends RefCounted
## Base class for tests: collect failures instead of aborting, so one run shows every problem.

var failures: Array = []

func check(cond: bool, msg: String = "check failed") -> void:
	if not cond:
		failures.append(msg)

func check_eq(a, b, msg: String = "") -> void:
	if a != b:
		failures.append("%s expected %s, got %s" % [msg, str(b), str(a)])

func check_near(a: float, b: float, eps: float = 1e-6, msg: String = "") -> void:
	if absf(a - b) > eps:
		failures.append("%s expected %s +/- %s, got %s" % [msg, str(b), str(eps), str(a)])
