"""The game's version, shown in the menu and exchanged when joining a game.

Bump it when you hand out a new build. If the rules or the network messages change, also bump
net.protocol.PROTOCOL_VERSION so older builds are refused with a clear message instead of desyncing.
"""

__version__ = "0.2.0"
