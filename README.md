# Bot Player macOS beta

This test package builds the current no-Xcode Bot Player companion for Apple
iPhone Mirroring. It contains no legacy Swift bridge, Replit cache, browser
server, or database.

## Requirements

- macOS 15 or later
- Python 3
- An internet connection for the first build so Python packages can be
  installed
- Apple iPhone Mirroring available on the Mac

## If macOS blocks the downloaded launcher

This beta package is not signed or notarized with an Apple Developer ID, so
Gatekeeper may show:

> Apple could not verify “Build Bot Player.command” is free of malware.

After reviewing the files in this archive, use the scoped Finder approval:

1. In Finder, Control-click **Build Bot Player.command**.
2. Choose **Open**, then choose **Open** again in the confirmation dialog.
3. If macOS still blocks it, open **System Settings → Privacy & Security**,
   scroll down, and choose **Open Anyway** for the blocked launcher.

Do not disable Gatekeeper globally. If the archive was downloaded from a
trusted source and you prefer to approve only this extracted folder from
Terminal, run this command from the folder that contains it:

```bash
xattr -dr com.apple.quarantine .
```

The generated **Bot Player.app** may require the same Control-click → Open
approval the first time it is launched. A fully warning-free download
requires an Apple Developer ID signature and notarization, which are not
available in this source beta package.

## Double-click and run

1. Extract this ZIP.
2. Double-click **DOUBLE-CLICK-TO-RUN (Mac).command**.
3. If macOS shows a security warning, Control-click the file, choose **Open**,
   and confirm **Open**. The launcher then remembers the approval for later
   launches.
4. The launcher finds Python, installs it through Homebrew if needed, creates a
   private `.bot-player-venv` beside the launcher, installs the required
   packages, builds a real **Bot Player.app**, installs it in `~/Applications`,
   and opens it. If Homebrew is missing, the launcher asks before using
   Homebrew's official installer.
5. In Bot Player, open **Mac setup & permissions** and approve **Bot Player.app**
   in Screen Recording and Accessibility. The checklist shows the exact app
   identity and opens one privacy pane at a time.
6. Once both permissions are ready, choose **Test iPhone connection** to confirm
   real input works. Place any app in the upper-left Home Screen app slot,
   approve the test prompt, and Bot Player will swipe Home, open that app,
   verify a visible change, then swipe Home again.
7. Later double-clicks open the installed app when its build revision matches.
   If this package has a newer revision, the launcher rebuilds and replaces the
   same `~/Applications/Bot Player.app` path so macOS evaluates the current
   signed app.
8. To force a replacement even when revisions match, double-click **Build Bot
   Player.command** and type `REBUILD`. The local beta build requires an Apple
   Development signing certificate on the Mac that performs the build. A
   replacement can still require one new macOS approval.

The ZIP includes a `dist/` staging folder so the build output has a predictable
place to appear. It starts with instructions only: the real
`dist/Bot Player.app` is created by PyInstaller on macOS, then copied to
`~/Applications/Bot Player.app`.

In **Mac setup & permissions**, click **Check again** after approval. The
checklist shows the running app's Apple signing authority and Team ID, checks
Screen Recording and Accessibility, and performs a one-frame capture test of
iPhone Mirroring by its authenticated macOS window ID so permission and
capture failures are distinguishable. Recording and template capture use this
window-specific path; automated input still stops if any window overlaps the
Mirroring region.

If System Settings shows **Bot Player** as allowed but the checklist still says
denied, select **Stale-permission cleanup** in the checklist. Quit Bot Player,
run the two displayed `tccutil reset` commands in Terminal, reopen
`~/Applications/Bot Player.app`, and approve the new prompts. The commands
reset only Bot Player's old macOS privacy entries.

## Optional standalone app build

The optional builder is useful if you want a normal `.app` after the first
test:

1. Double-click **Build Bot Player.command**.
2. Read the replacement warning, type `REBUILD`, and allow the command to run
   if macOS asks.
3. The command replaces the installed `~/Applications/Bot Player.app` and opens
   it automatically.
4. Approve Bot Player.app again only if macOS asks after this deliberate update.

## First-run test

1. Accept the Bot Player safety notice.
2. Open **Mac setup & permissions**. Approve Screen Recording and Accessibility
   when macOS opens their settings. These approvals must be made by the user
   and cannot be automated. Approve **Bot Player.app** at
   `~/Applications/Bot Player.app`.
3. Bot Player opens iPhone Mirroring and waits for its authenticated window.
4. The user must manually open **Block Jam 3D** on the mirrored iPhone. The
   game icon is included in Bot Player, so testers do not need to capture or
   upload it.
5. Press **Start Bot Player** only when ready to allow guarded play.
6. Confirm that **Stop Bot Player** halts the controller, and close/reopen the
   app to confirm the local templates remain available.

Bot Player stops rather than guessing when iPhone Mirroring disappears, moves,
is covered by another window, loses permission, or produces an uncertain board.

## Begin training for a game

Choose **Begin Training…** in Bot Player and enter the game name. Bot Player
keeps each game's recordings and reviewed examples separate.

- **Block Jam 3D** includes a bundled app icon.
- For another game, an app icon is only needed if you want Bot Player to open
  the game from the iPhone home screen. If you always manually open the game
  before starting Bot Player, you can train and review footage without adding
  an icon.
- The user must manually open the chosen game on the mirrored iPhone before
  recording. Bot Player does not open apps during recording.

## Record a training session

After choosing the game in **Begin Training…**, use **Start Recording Session**
when you want the user to demonstrate normal gameplay for later training:

1. Leave iPhone Mirroring visible and unobstructed.
2. Manually open the game on the mirrored iPhone.
3. Press **Start Recording Session** in Bot Player.
4. Move to the real mirrored iPhone and play the game normally. Bot Player is
   observation-only during this mode and does not open apps or send taps/drags.
5. Return to Bot Player and press **Stop & Save Recording**.

The session is saved locally as a folder of PNG frames plus a JSON manifest at
`~/Library/Application Support/BotPlayer/recordings/<game>/`. A session pauses
instead of capturing when the Mirroring window is missing, covered, moved, or
not permitted.


## Build training from local footage

With Bot Player stopped, choose **Import Training Footage**. Select either a
saved Bot Player recording session or a local gameplay clip you are allowed to
use (including a clip you prepared from YouTube footage). Bot Player samples
and groups frames on the Mac only; it never uploads the session or clip.

The review window shows only repeated target/board-item proposals. Deselect any
example you do not trust, then choose **Confirm and save selected** and confirm
the replacement. Until that final confirmation, the current templates are left
unchanged. Saving replaces templates only for the selected game; templates for
other games remain untouched and are loaded only on the next explicit
**Start Bot Player**.

Footage must contain at least 1.5 seconds and eight usable, unobscured gameplay
frames. Bot Player clearly rejects clips that are too short, blank/obscured,
damaged, unsupported, belong to a different game recording, or cannot produce
repeated target/board-item matches. For now, automatic grouping is guarded for
Block Jam 3D; use the manual capture flow for other games.
