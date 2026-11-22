# Packaging: sending the game to a friend

## Make a build

```
pip install -e ".[build]"
python tools/build_app.py
```

Output in `dist/`: `GridironScramble-<version>-macos.zip` (or `-windows.zip`). PyInstaller does not cross-compile, so
each OS is built on that OS. The GitHub Actions workflow (`.github/workflows/build.yml`) builds both; run it from the
Actions tab or push a tag such as `v0.2.0`. That workflow has not been run yet.

Bump `src/ballbrawlla/version.py` for every build you hand out. If the rules or network messages changed, also bump
`PROTOCOL_VERSION` in `net/protocol.py`, so an older build is refused with a message naming both versions.

## What your friend does

**Mac:** unzip, then right-click `Gridiron Scramble.app` > Open > Open. The app is not signed, so a plain double-click
is blocked the first time. If macOS says the app is damaged, run `xattr -dr com.apple.quarantine "Gridiron Scramble.app"`.
The build is Apple Silicon only when made by the GitHub runner.

**Windows:** unzip, open the folder, run `Gridiron Scramble.exe`. SmartScreen says "Windows protected your PC": click
More info > Run anyway.

**Playing online:** the first time you host, the OS asks whether to allow incoming connections. Allow it. If someone
clicks Block, hosting appears to work but nobody can connect. Both players need the same version, shown at the
bottom right of the menu.

## Where files go

| What | Source checkout | Packaged app |
|---|---|---|
| Levels | `levels/` | inside the app (read-only) |
| Logs, session notes | `logs/` in the repo | macOS `~/Library/Application Support/Gridiron Scramble/logs`, Windows `%APPDATA%\Gridiron Scramble\logs` |

`BALLBRAWLLA_HOME=/some/folder` moves the writable folder in either case. `logs/latest.log` holds the path of the newest
run's log, which is the first thing to ask a friend for if something goes wrong.

## Your own art for the menu

Put PNGs with a transparent background in `assets/menu/` named `football_1.png`, `football_2.png`, and so on, in
order. They are scaled to the ball size and replace the drawn football. A file that can't be read is skipped, and with no
files the menu draws its own ball. The build bundles `assets/` when it exists. If the art is not yours to share, keep it
out of git (add `assets/` to `.gitignore`); the build still bundles it from your disk.

## What each mode needs

| Mode | Notes |
|---|---|
| Explore, Catch practice, Practice, Two players | Offline. Nothing to configure. |
| Host / Join | Same network. Firewall must allow the app. Discovery uses UDP broadcast on port 50556, the game uses TCP on 50555. Some Wi-Fi (guest, school) blocks broadcast; typing the address still works. |
| Online match | Not built. Needs a server that stays running. |
| Controllers | Included in the build; the log line `controller support: True` confirms it. |
