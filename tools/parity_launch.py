"""Record what the launch checks and invite-code helpers say, for the Godot port to be checked against.

Used by tools/export_parity.py; writes godot/tests/data/launch.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballbrawlla import launch  # noqa: E402
from ballbrawlla.net import invite, upnp  # noqa: E402
from ballbrawlla import menu_anim  # noqa: E402

CODES = ["", "  ", "KQ7-M3X", "kq7m3x", "KQ7M3", "KQ7M3XA", "KQ1-M3X", "ABC-123", "OIL", "k q7 - m3x", "KQ7-M3X-", "0O1IL2", "abc", "ZZZ-ZZZ", "AB-CD-EF",
         "2JDH-GC8A", "2jdhgc8a", "2JDH-GC8B", "AAAA-AAAA", "97GD-SF99", "99999999", "KQ7M3XPAB"]
IPS = ["0.0.0.0", "10.0.0.5", "127.0.0.1", "192.168.1.20", "203.0.113.5", "93.184.216.34", "8.8.8.8", "255.255.255.255"]
PUBLIC = ["8.8.8.8", "93.184.216.34", "1.1.1.1", "10.0.0.1", "172.16.5.4", "172.32.0.1", "192.168.0.2", "100.64.0.1",
          "100.128.0.1", "127.0.0.1", "169.254.1.1", "0.0.0.0", "192.0.2.1", "198.51.100.7", "203.0.113.9", "198.18.0.1",
          "240.0.0.1", "255.255.255.255", "192.0.0.9", "192.0.0.8", "", "garbage", "1.2.3"]
RELAYS = ["", "relay.example.com", "relay.example.com:50601", "203.0.113.5:50600", "[::1]:50600", "host:abc", ":50600",
          "localhost", "127.0.0.1:1", "a:b:c", "  spaced.example.com  "]
ADDRESSES = ["", "  ", "10.0.0.5", "10.0.0 .5", "host name", "192.168.1.20:50555", "x"]
PORTS = [0, 80, 1023, 1024, 50555, 65535, 65536, -5]


def all_launch() -> dict:
    infos = launch.list_levels()
    levels = []
    for i in infos:
        levels.append({
            "key": i.key, "name": i.name, "width": i.width, "height": i.height, "yard_px": i.yard_px,
            "platforms": i.platforms, "thin": i.thin, "football": i.football, "error": i.error,
            "summary": i.summary(),
            "checks": {m: launch.check_level(m, i) for m in launch.ALL_MODES},
        })
    return {
        "levels": levels,
        "order": [i.key for i in infos],
        "codes": [{"in": c, "normal": invite.normalize_code(c), "format": invite.format_code(c),
                   "check": invite.check_code(c)} for c in CODES],
        "address_codes": [{"ip": ip, "code": invite.address_code(ip)} for ip in IPS],
        "code_addresses": [{"in": c, "ip": invite.code_address(c)} for c in CODES],
        "public": [{"ip": ip, "public": upnp.is_public(ip)} for ip in PUBLIC],
        "relays": [{"in": r, "addr": (list(invite.relay_address(r)) if invite.relay_address(r) else None)}
                   for r in RELAYS],
        "addresses": [{"in": a, "check": launch.check_address(a)} for a in ADDRESSES],
        "ports": [{"in": p, "check": launch.check_port_number(p)} for p in PORTS],
        "expected_width": launch.expected_field_width(None),
        "poses": [{"t": t / 40.0, "width": w, **{k: getattr(menu_anim.pose(t / 40.0, w), k) for k in
                  ("x", "y", "angle", "phase", "direction", "receiver_lift", "thrower_lean")}}
                  for w in (1280, 1000) for t in range(0, 300, 7)],
    }
