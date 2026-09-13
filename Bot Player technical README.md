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
    then play normally; this mode never opens apps or sends input itself. If
    Input Monitoring permission is granted, it also passively observes your own
    taps and swipes (never anyone else's, and never anything Bot Player sends)
    so a bot can later be trained from them; without that permission it falls
    back to capturing frames only, exactly as before. Return to Bot Player and
    choose **Stop & Save Recording**. The session is stored locally as PNG
    frames and a JSON manifest (including any recorded actions) under
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

## Train a bot from recorded gameplay

Choose **Train Bot** to build a bot from your own recordings instead of manual
target/board-item templates. Bot Player lists your saved recording sessions for
the selected game (each showing how many frames and recorded actions it
contains); pick the ones to learn from and confirm. Nothing is trained until
you confirm.

Bot Player pairs every recorded tap, swipe, or hold with the gameplay frame
captured just before it -- never the frame after, so a move is never labeled
with its own outcome -- then trains a small local nearest-neighbor model: given
a new frame, it finds the most visually similar recorded frame and proposes
that frame's action, or proposes nothing if no recorded frame is a close
enough match. This mirrors the app's existing "never guess" behavior, and
every proposed action is still independently re-verified against a fresh
frame immediately before any tap is sent, exactly like template matching is.

Unlike the target/board-item classifier, a trained bot is not limited to
tap-a-matching-tile games: recorded actions can be taps, swipes, drags, or
holds, so this generalizes to other game mechanics as long as you have
recorded gameplay to train from. If a game has a trained model, **Start Bot
Player** uses it automatically; otherwise it falls back to template matching
as before. Trained models are saved locally per game under
`~/Library/Application Support/BotPlayer/models/<game>/` and are never
uploaded -- training, like recording, stays entirely on your Mac.

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
first build may take a few minutes. Later launches reuse the installed app when
its build revision matches; when the package has a newer revision, the launcher
rebuilds and replaces the same canonical app path so macOS checks the current
signed bundle. Because the beta is not notarized, the first launch may require
Control-click → **Open**.

The packaged app is important for macOS privacy permissions: enable
**Bot Player.app** in Screen Recording and Accessibility. The app's **Mac setup
& permissions** checklist identifies the exact installed app and opens the two
separate privacy panes one at a time. Its **Check again** action also displays
the Apple signing authority and Team ID for the running app, then performs a
one-frame iPhone Mirroring capture test. This makes it clear whether a failure
comes from signing identity, TCC authorization, Mirroring visibility, or the
actual capture call.

To deliberately force a replacement, use `Build Bot Player.command` and type
`REBUILD` at its confirmation prompt. A normal double-click also replaces the
canonical app automatically when its packaged revision is newer. Any
replacement can make macOS request Screen Recording and Accessibility approval
again.

If the macOS privacy page shows **Bot Player** as allowed but the checklist
still reports a denial, use the **Stale-permission cleanup** button in the
checklist. It shows two `tccutil reset` commands scoped to Bot Player's bundle
identifier; quit the app, run both commands, then reopen the canonical app and
approve its fresh prompts. This removes only Bot Player's prior permission
decisions.

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
into a hidden-console, double-clickable `dist/Bot Player.app`, then signs the
native code and app bundle with the hardened runtime before creating
`dist/Bot-Player-macOS.dmg`. No Xcode project or Swift compiler is used.
PyInstaller and the Python packages are downloaded when the maintainer builds
a release; end users receive the finished app and do not need Python, pip,
Node, or a terminal.

The normal double-click launcher performs a **development** build and requires
an **Apple Development** certificate in the Mac's keychain. The standalone
DMG builder performs a **distribution** build and requires a **Developer ID
Application** certificate. Neither path creates an unsigned or ad-hoc-signed
app. Set `BOT_PLAYER_SIGNING_IDENTITY` to choose a specific installed
certificate of the required type. Notarize the signed DMG with Apple before
distributing it outside your team.

The previous `desktop/macos/build-macos.sh` path remains as a compatibility
launcher and forwards to this Python build.

## Run the regression tests

From this directory, using the same virtualenv the app runs in (so PyInstaller's
dependencies -- PyObjC, Pillow -- are importable):

```bash
.bot-player-venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

The suite is pure-Python and uses only temporary local storage, so it runs
without iPhone Mirroring, Screen Recording, or Accessibility permissions. It
covers template matching (`best_match`, board-change fingerprints), the
Block Jam target/pile classifier, automatic training-candidate extraction
from footage, the `Action`/`Policy` abstraction that lets a trained model
stand in for template matching, and the recording-to-dataset-to-trained-policy
pipeline (frame/action alignment, and a save/load round trip for a trained
nearest-neighbor model).
