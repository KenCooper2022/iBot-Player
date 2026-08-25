# Bot Player for macOS

Bot Player is a Python-based Mac companion for Apple **iPhone Mirroring**. It
does not use Swift, Xcode, ScreenCaptureKit, Node, PostgreSQL, or a separately
running API server.

## User flow

1. Install **Bot Player.app**, then double-click its app icon. This opens the
   complete Bot Player window and controller together; no terminal, Python,
   browser, Node, or API server is needed.
2. Read the Bot Player safety notice. Choosing **No** closes Bot Player
   immediately without taking a screenshot or sending input.
3. After acceptance, Bot Player opens Apple **iPhone Mirroring** automatically.
   If macOS cannot find it, open it from Applications or Spotlight. The user
   must manually open the selected game on the mirrored iPhone; Bot Player does
   not open the game during recording.
4. Use **Mac setup & permissions** when prompted. Turn on Bot Player.app in
   both **Screen Recording** and **Accessibility** in macOS System Settings,
   then return to Bot Player. macOS requires the user to approve these
   permissions; the app cannot silently grant them.
5. **Block Jam 3D** includes a built-in game-icon template, so its first-use
   setup does not ask the tester to supply or capture the app icon. Other games
   still require their own local icon capture. Bot Player captures only the
   authenticated Mirroring window and never searches or clicks outside it. It
   authenticates the owner as Apple’s iPhone Mirroring process
   (`com.apple.ScreenContinuity`); if a future macOS version changes that
   identity, Bot Player stops rather than accepting a lookalike window. It also
   stops if any other visible window intersects the mirrored-phone region, so
   move dialogs and overlays away before starting or capturing a template.
6. In the game, capture one target and the matching board item with the same
   name. Bot Player prompts for this setup when a required pair is missing; it
   stops before any tap, so capture the pair and press **Start Bot Player**
   again to load it.
7. Review the **Saved templates** library. It shows the selected game's icon
   and each target/board-item pair. Use **Replace** to recapture an outdated
   image or **Remove** to delete one; Bot Player asks for confirmation before
   either change. Use **Export backup** to save that selected game's complete
   calibration as one `.botplayer.json` file. Keep the file somewhere you
   trust, such as encrypted storage or a removable drive.
8. Use **Restore backup** to choose a backup for the selected game. Bot Player
   asks before replacing local calibration, checks the entire file first, and
   rejects a backup with a different game, a missing icon, unreadable image,
   duplicate template, or incomplete target/board-item pair. A rejected backup
   leaves the current setup unchanged. Restore never starts the controller:
   all restored templates are loaded only after the next explicit **Start Bot
   Player**.
9. Choose **Start Bot Player**. This is the explicit permission to open the
   matched game and make guarded moves. It finds the saved game icon across
   stable frames, waits for saved target/pile templates to verify the board,
   and only sends a move when both templates meet the confidence threshold.
    Every move must produce a stable, expected board change. The double-clicked
    app remains open while it runs; choose **Stop Bot Player** or close iPhone
    Mirroring to stop input.
10. Choose **Begin Training…** and enter the game you want to train. Block Jam
    3D includes an icon. Other games need an icon only when Bot Player is
    expected to open them from the iPhone home screen; users can skip the icon
    when they manually open the game before starting the bot.
11. Choose **Start Recording Session** to collect a demonstration instead of
    running the bot. Manually open the selected game on the real mirrored iPhone,
    then play normally; this mode only captures authenticated Mirroring frames
    and never opens apps or sends input. Return to Bot Player and choose
    **Stop & Save Recording**. The session is
    stored locally as PNG frames and a JSON manifest under
    `~/Library/Application Support/BotPlayer/recordings/<game>/`.

Bot Player refuses to start if the selected game has no icon or if there is no
complete target/board-item pair. Block Jam 3D receives its icon automatically;
the target/board-item captures remain explicit so Bot Player never guesses what
an in-game piece means. Removing a required template therefore keeps guarded
play fail-closed; capture a replacement before starting again.

Recording sessions do not start automated play, upload data, or send taps. They
pause when the authenticated Mirroring window is unavailable, covered, moved,
or missing Screen Recording permission. Each saved session contains a manifest
with the game name, frame timestamps, Mirroring bounds, and the relative PNG
frame paths.


## Build training from local footage

With Bot Player stopped, choose **Import Training Footage**. Select either a
saved Bot Player recording session or a local gameplay clip you are allowed to
use, including a clip you prepared from YouTube footage. Bot Player samples and
groups frames locally on the Mac; it never uploads the session or clip.

The review window shows only repeated target/board-item proposals. Deselect any
example you do not trust, then choose **Confirm and save selected** and confirm
the replacement. Current templates remain unchanged until that final
confirmation. A saved import replaces templates for the selected game only and
is used only after the next explicit **Start Bot Player**.

Footage needs at least 1.5 seconds and eight usable, unobscured gameplay frames.
Bot Player rejects footage that is too short, blank/obscured, damaged,
unsupported, recorded for another game, or unable to produce trustworthy
repeated pairs. Automatic grouping is currently guarded for **Block Jam 3D**;
use manual capture for other games.

Game templates are saved locally in:

`~/Library/Application Support/RelayCockpit/box-jam-templates/`

Target and board-item captures are associated with the selected game, so captures
for one game are never listed or used for another. Existing unlabelled template
files remain compatible with **Block Jam 3D**, the original supported game.
Game-icon templates are saved under:

`~/Library/Application Support/BotPlayer/games/`

## Calibration backup format

Bot Player writes portable `.botplayer.json` files using the versioned
`bot-player-calibration` format. Each backup contains only one game's icon
image and region plus its target and board-item PNG templates and normalized
rectangles. The images are embedded in the JSON file so restoring it does not
depend on any neighboring local files.

Backups are intentionally scoped to the selected game. Restoring a backup for
another game is rejected, and a successful restore replaces only that game's
local icon and templates; other games remain untouched. A backup must have a
game icon and at least one complete target/board-item pair before it can be
exported or restored.

## Double-click startup

For the easiest test, double-click `DOUBLE-CLICK-TO-RUN (Mac).command`.
Following the same pattern as the Audio Stream Miner launcher, it finds Python,
creates a private `.bot-player-venv`, installs the required packages, builds a
real `Bot Player.app`, installs it in `~/Applications`, and opens that app. The
first build may take a few minutes; later launches open the same installed app
directly and intentionally ignore changed source-file timestamps. Because the
beta is not notarized, the first launch may require Control-click → **Open**.

The packaged app is important for macOS privacy permissions: enable
**Bot Player.app** in Screen Recording and Accessibility. The app's **Mac setup
& permissions** checklist identifies the exact installed app and opens the two
separate privacy panes one at a time.

To deliberately install a changed beta, use `Build Bot Player.command` and
type `REBUILD` at its confirmation prompt. Replacing an ad-hoc-signed app can
make macOS request Screen Recording and Accessibility approval again; normal
launches never replace the approved app automatically.

After both permissions are approved, use **Test iPhone connection** for a
limited end-to-end input check. Put any app in the upper-left Home Screen app
slot first. After you confirm, Bot Player swipes to Home, taps that slot, waits
for the screen to change, then swipes Home again. It returns to the Home Screen
instead of force-quitting the app and stops without the return swipe if opening
the app cannot be visually confirmed.

## Build the standalone Mac app without Xcode

On a Mac with Python 3:

```bash
cd artifacts/iphone-bot-control/desktop/python
chmod +x build-python-app.sh
./build-python-app.sh
```

The script installs the Python wheels and uses PyInstaller to bundle Python
into a hidden-console, double-clickable `dist/Bot Player.app`, then creates
`dist/Bot-Player-macOS.dmg` with the app and an Applications shortcut. No Xcode
project or Swift compiler is used. PyInstaller and the Python packages are
downloaded when the maintainer builds a release; end users receive the
finished app and do not need Python, pip, Node, or a terminal.

This standalone build is a changed ad-hoc app bundle. Move it to Applications
before granting permissions; replacing an earlier bundle can require a new
macOS approval.

The previous `desktop/macos/build-macos.sh` path remains as a compatibility
launcher and forwards to this Python build.

## Run the template safety regression tests

From this directory, run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

The suite uses temporary local storage and stubs macOS-only capture modules, so
it can run on a development machine or CI without iPhone Mirroring. It covers
icon removal, incomplete pairs stopping before input, per-game template
isolation, legacy Block Jam files, explicit replacement consent, and safe
calibration backup and restore validation.
