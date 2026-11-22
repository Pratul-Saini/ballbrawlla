extends RefCounted
## The game's version, shown in the menu and exchanged when joining a game (src/ballbrawlla/version.py).
## Bump it when you hand out a new build. If the rules or the network messages change, also bump
## protocol.gd PROTOCOL_VERSION so older builds are refused with a clear message instead of desyncing.
const VERSION := "0.2.0"
