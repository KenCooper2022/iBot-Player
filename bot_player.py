#!/usr/bin/env python3
"""Bot Player's no-Xcode iPhone Mirroring controller for macOS.

The user opens Apple's iPhone Mirroring app. This process finds its visible
window, captures only that window region, applies conservative local template
matching, and sends a click through the mirrored window only after a match is
stable. It never clicks another app or guesses when a board is uncertain.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Iterable

try:
    import pyautogui
    from AppKit import NSRunningApplication
    from PIL import Image, ImageChops, ImageOps, ImageStat, ImageTk
    import Quartz
except ImportError as error:
    print(
        json.dumps(
            {
                "state": "stopped",
                "message": "Install the Bot Player Python requirements before starting.",
                "detail": str(error),
            }
        ),
        flush=True,
    )
    raise SystemExit(2)


MATCH_THRESHOLD = 0.86
STABLE_READINGS = 2
POLL_SECONDS = 0.55
MAX_ACTIONS = 50
IPHONE_MIRRORING_BUNDLE_IDENTIFIERS = {"com.apple.ScreenContinuity"}
DEFAULT_GAME_NAME = "Block Jam 3D"
CALIBRATION_FORMAT = "bot-player-calibration"
CALIBRATION_VERSION = 1
MAX_CALIBRATION_TEMPLATES = 100
MAX_CALIBRATION_IMAGE_BYTES = 4 * 1024 * 1024
MAX_CALIBRATION_BACKUP_BYTES = 32 * 1024 * 1024
MAX_CALIBRATION_IMAGE_PIXELS = 4_000_000
RECORDING_FORMAT = "bot-player-recording"
RECORDING_VERSION = 1
RECORDING_INTERVAL_SECONDS = 0.25
MAX_RECORDING_FRAMES = 12_000
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
MIN_TRAINING_FRAMES = 8
MIN_TRAINING_DURATION_SECONDS = 1.5
MAX_TRAINING_ANALYSIS_FRAMES = 120
MAX_TRAINING_CANDIDATES = 12
TRAINING_MATCH_THRESHOLD = 0.91
TRAINING_TARGET_REGION = (0.0, 0.0, 1.0, 0.30)
TRAINING_PILE_REGION = (0.02, 0.24, 0.96, 0.72)
STOP_REQUESTED = threading.Event()
START_REQUESTED = threading.Event()
RECORDING_STOP_REQUESTED = threading.Event()
CONNECTION_CHECK_STOP_REQUESTED = threading.Event()
CONNECTION_CHECK_ACTIVE = threading.Event()
CALIBRATION_LOCK = threading.RLock()
STATUS_SINK: Any = None
APP_BUNDLE_IDENTIFIER = "com.botplayer.iphone-mirroring"
CANONICAL_APP_NAME = "Bot Player.app"
DEFAULT_BLOCK_JAM_ICON_REGION = [0.0, 0.0, 0.18, 0.09]
DEFAULT_BLOCK_JAM_ICON_JPEG = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/4QBARXhpZgAATU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAAqACAAQAAAABAAAAn6ADAAQAAAABAAAAnAAAAAD/4gIoSUNDX1BST0ZJTEUAAQEAAAIYYXBwbAQAAABtbnRyUkdCIFhZWiAH5gABAAEAAAAAAABhY3NwQVBQTAAAAABBUFBMAAAAAAAAAAAAAAAAAAAAAAAA9tYAAQAAAADTLWFwcGwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAApkZXNjAAAA/AAAADBjcHJ0AAABLAAAAFB3dHB0AAABfAAAABRyWFlaAAABkAAAABRnWFlaAAABpAAAABRiWFlaAAABuAAAABRyVFJDAAABzAAAACBjaGFkAAAB7AAAACxiVFJDAAABzAAAACBnVFJDAAABzAAAACBtbHVjAAAAAAAAAAEAAAAMZW5VUwAAABQAAAAcAEQAaQBzAHAAbABhAHkAIABQADNtbHVjAAAAAAAAAAEAAAAMZW5VUwAAADQAAAAcAEMAbwBwAHkAcgBpAGgAdAAgAEEAcABwAGwAZQAgAEkAbgBjAC4ALAAgADIAMAAyADIWFlogAAAAAAAAg98AAD2////7tYWVogAAAAAAAASr8AALE3AAAKuVhZWiAAAAAAAAAoOAAAEQsAAMi5cGFyYQAAAAAAAwAAAAJmZgAA8qcAAA1ZAAAT0AAACltzZjMyAAAAAAABDEIAAAXe///zJgAAB5MAAP2Q///7ov///aMAAAPcAADAbv/bAEMABAMDAwMCBAMDAwQEBAUGCgYGBQUGDAgJBwoODA8ODgwNDQ8RFhMPEBURDQ0TGhMVFxgZGRkPEhsdGxgdFhgZGP/bAEMBBAQEBgUGCwYGCxgQDRAYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGP/AABEIAD8AQAMBIgACEQEDEQH/xAAbAAACAgMBAAAAAAAAAAAAAAAFBgQHAAIDAf/EADsQAAIBAwIDBAYHBwUAAAAAAAECAwQFEQAhBhIxBxNBYRQiQnGRsRUjMlFzgdEXJENiobLBMzRSU3L/xAAaAQACAwEBAAAAAAAAAAAAAAAGBwIDBQEA/8QAKhEAAQMCBgEDBQEBAAAAAAAAAQIEEQADBQYSITFBcVFhoRMUM5HBkrH/2gAMAwEAAhEDEQA/AGphk514g316TrF3OB8NANEWmt8ba5smdT0oKjGXCx+Uhwfh11hoHH8WM+4H9NRKvSpBNCjDrzuPLRdLfI5wGX+upMdgqpR6rxfmT+mqyqKmBQFI8HUyFdGk4TrzuJIPzJ/TXdOFrgnWSD4n9NeCprkUqE6N2ykEMCTn/XlHMp/618MeZ658B79AA3N6o8dtODAJWSrj1UbkA8l2/wAatA1KCRXDtuaE3jiOxcOIn0pVBJJN0hRS8j+eB4eZ0HftEsqyKptl0HN0LQhc/FtBae2W6upqriPiSpMnp9QGEKZ52iXPIqZ2XBGCfBffpiht7Xe2pSVttjhSQK1JOWMk4k2B53PUlRgDboNtN61lLBWSEW36ipZgE6tIk9CI78mlw6zS/XqvNwE2wfb+1lHx3RVFS0MFkuHMkZlYyciBVHiSTsNx78jWy9qttpndKiw3SPu88+OQlcdds658WVz8P08NLb4wlZX1DSrtkcuQOYjxxy4BPQsxGMDXGRo4ES3VpgljlCgUVRMWYMdj3bk5YeWcHoRqy7lfAU3NBsn/AGrb5rTa3sw38OTiaQPpqmNh1yeNhOwPG3VWBwzxVZuKLe1VZ6rveQgSROvLJGfuZf8APTRzmONUfaoH4W7Y6MW9USimqPRW7sEK6OASN9zgkHB6bavL1VBYjIUEke4Z0v8ANWXkYO8TbsqJQsSmeRvEHx/a18FxsP2inFwQU8x4map2m3qYh/Ovz04yf7up/Ef5nSjSr+9xfiL89N021TV+Tv8AM6wG350+R/2tu/8AjV4NJtfahX9lcPoM2J7afSDFGxUsjE84Pj1BO2xA8tTbLcGuPCscUbIvc4eM5wqsPa8zrnbeK6CyPS0txpFkWZeRAcAOFJ9Uk7A+ucH451vauz+81t+kksdwpFtDtzKtRIVkgBPRkxvjPUbHTCz1hynr7S0XquJ3KZ4ngge/fzSNS1cJapv3UkWyTpV0T2PNcuI4Ky+8d2+tAQpJTBiw+ynKSG38iNSfoSitF4ivFxtb1UEMgbcnm3+zJjPKR9wxsRjOdOvodHbe54dghNSsGXqKkgKxYnPKPuHQ492tr5cqaptFPa6OLvnlykahsNGfHfwHifDQc+zi4sYuiwUa9MBQHOvYEj1IIiDsd6e+F3nLjLdhtq+knQRIMAp33URwCN/bmk+40VPNxFY623zx1FE06S8yJylJGb1ub+Ylfyxjw1Yssn1Eu/8ADb+06Q3jp6G72qzU31iQzrI82/rvvkjy8fPTg8mYZN/Yb5HRdn1S1XWiliDp7557ilxlkJDB6LZlI1QfUQaram2q4vxF+emudSa2rQdTI4/qdK8AxVRf+1+em6pTFxqPxW/uOl0lZTcChzTFUkKBBqje0d5Ke0UWZGikhqG+z1GwB124O7TLlw+yQXcctPz8kUxbCuD/AMT7J8jtqwOLuB6LiqGLvKh6WaJiyuqhlY49oeOkz9i9TUVUM9XxFDM0beNOQMZzgDOBogzDi6MTefe25QqBxsQQADBHv8dVVl5jZZYeWDmFJlWxEggkkSPHzT7deKbDJPFeai6tSTGMGXDKveD2SwJOCBtkddKlZx1b5CUs1HPUtO2FkcthiDvjONs46DGiEfZYgu7VaXOJYni7mSIU/wBpfj1zqbbOy2KmvArqm9PMFwFjWEKFUdAN/doWTaLp4HDu4QpREq4jomEjfb91uJU0ZMzYapkJB0pMn3AlXU8TsKkcPRVNRxBSCV+9aLMkrAYAwPlk40/MpaN1HUgjUW22yjtkDR0qEFt2djlm950QjG+i7NGOWcTdI+1BFu2kJTPJjv1/e/ZoIwTBVtWlxDojXdJKo4E7QOv1t0K//9k="
)


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_window(cls, bounds: dict[str, Any]) -> "Rect":
        return cls(
            x=int(round(float(bounds["X"]))),
            y=int(round(float(bounds["Y"]))),
            width=int(round(float(bounds["Width"]))),
            height=int(round(float(bounds["Height"]))),
        )


@dataclass(frozen=True)
class MirroringWindow:
    window_id: int
    rect: Rect


@dataclass(frozen=True)
class Match:
    label: str
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class Template:
    label: str
    role: str
    relative_width: float
    relative_height: float
    image: Image.Image


@dataclass
class TrainingFrame:
    """A local frame eligible for conservative training analysis."""

    image: Image.Image
    index: int
    timestamp: float


class TrainingSourceError(ValueError):
    """A local recording or clip cannot produce safe training examples."""


def emit(state: str, message: str, **details: Any) -> None:
    payload = {"state": state, "message": message, **details}
    print(json.dumps(payload), flush=True)
    if STATUS_SINK:
        STATUS_SINK(payload)


def present_disclaimer() -> bool:
    """Require explicit acceptance before any screen capture or input."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    accepted = messagebox.askyesno(
        "Bot Player — safety notice",
        "Bot Player can read the visible iPhone Mirroring window and send clicks to the mirrored iPhone.\n\n"
        "Only use it with games and accounts you are allowed to control. Automated play can make unintended moves, "
        "spend in-app resources, or affect game progress. Bot Player stops when iPhone Mirroring disappears, a match "
        "is uncertain, or a board change is not confirmed.\n\n"
        "Do you understand and want to continue?",
        default=messagebox.NO,
        icon=messagebox.WARNING,
    )
    root.destroy()
    if not accepted:
        emit("stopped", "Safety notice was not accepted. Bot Player is closing without screen access.")
    return bool(accepted)


def canonical_app_path() -> Path:
    """Return the one user-writable app location used by the beta launcher."""
    return Path.home() / "Applications" / CANONICAL_APP_NAME


def running_app_path() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    for parent in (executable, *executable.parents):
        if parent.name.endswith(".app"):
            return parent
    return None


def permission_subject() -> str:
    app_path = running_app_path()
    if app_path is not None:
        return f"{CANONICAL_APP_NAME} at {app_path}"
    return (
        f"the packaged {CANONICAL_APP_NAME} at {canonical_app_path()} "
        "(this source launch is not the permission-granting identity)"
    )


def permission_identity_text() -> str:
    app_path = running_app_path() or canonical_app_path()
    runtime = "Packaged Bot Player.app" if getattr(sys, "frozen", False) else "Source launch"
    return (
        f"Permission subject: {permission_subject()}\n"
        f"Bundle identifier: {APP_BUNDLE_IDENTIFIER}\n"
        f"Runtime: {runtime}\n"
        f"Expected app location: {app_path}"
    )


def open_mac_permissions(permission: str = "screen") -> None:
    """Open one Apple permission pane; macOS still requires the user to approve."""
    urls = {
        "screen": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
        "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    }
    url = urls.get(permission, urls["screen"])
    try:
        subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def launch_iphone_mirroring() -> None:
    try:
        subprocess.Popen(["open", "-a", "iPhone Mirroring"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        emit("opening", "Opening Apple iPhone Mirroring. Keep the mirrored phone visible while Bot Player connects.")
    except OSError:
        emit("waiting", "Open Apple iPhone Mirroring to let Bot Player connect.")


def accessibility_permission() -> bool | None:
    checker = getattr(Quartz, "AXIsProcessTrusted", None)
    if not callable(checker):
        return None
    try:
        return bool(checker())
    except Exception:
        return None


def request_screen_capture_permission() -> bool | None:
    requester = getattr(Quartz, "CGRequestScreenCaptureAccess", None)
    if callable(requester):
        try:
            return bool(requester())
        except Exception:
            pass
    return screen_capture_permission()


def request_accessibility_permission() -> bool | None:
    requester = getattr(Quartz, "AXIsProcessTrustedWithOptions", None)
    if callable(requester):
        prompt_key = getattr(Quartz, "kAXTrustedCheckOptionPrompt", "AXTrustedCheckOptionPrompt")
        try:
            return bool(requester({prompt_key: True}))
        except Exception:
            pass
    return accessibility_permission()


def permission_status_text(value: bool | None) -> str:
    if value is True:
        return "Ready"
    if value is False:
        return "Needs approval"
    return "Status unavailable; use the setup buttons"


def packaged_app_identity_ready() -> bool:
    """Return whether this process is the canonical installed app."""
    if not getattr(sys, "frozen", False):
        return False
    app_path = running_app_path()
    if app_path is None:
        return False
    try:
        return app_path.resolve() == canonical_app_path().resolve()
    except OSError:
        return app_path == canonical_app_path()


def permission_identity_status_text() -> str:
    """Describe whether permission checks apply to the canonical app path."""
    if not getattr(sys, "frozen", False):
        return "App identity: Not validated — this is a source launch"
    app_path = running_app_path()
    if app_path is None:
        return "App identity: Not validated — packaged app path is unavailable"
    if packaged_app_identity_ready():
        return f"App identity: Verified — {app_path}"
    return (
        f"App identity: Not validated — running from {app_path}; "
        f"relaunch {canonical_app_path()}"
    )


def show_permission_setup(parent: Any = None) -> None:
    """Show a guided checklist for the exact packaged app requesting access."""
    import tkinter as tk
    from tkinter import ttk

    owns_root = parent is None
    root = parent
    if root is None:
        root = tk.Tk()
        root.withdraw()
    dialog = tk.Toplevel(root)
    dialog.title("Bot Player — Mac setup")
    dialog.geometry("700x440")
    dialog.minsize(600, 400)
    dialog.transient(root)

    ttk.Label(
        dialog,
        text="Approve the packaged Bot Player.app",
        font=("TkDefaultFont", 14, "bold"),
    ).pack(anchor=tk.W, padx=22, pady=(20, 4))
    ttk.Label(
        dialog,
        text=permission_identity_text(),
        justify=tk.LEFT,
        wraplength=590,
    ).pack(anchor=tk.W, padx=22)
    ttk.Label(
        dialog,
        text=(
            "These permissions are separate. Approve the app shown above, not a Python "
            "interpreter. If you deliberately install a newer beta, macOS may ask again "
            "because its ad-hoc app contents changed."
        ),
        justify=tk.LEFT,
        wraplength=590,
    ).pack(anchor=tk.W, padx=22, pady=(10, 14))

    status_frame = ttk.Frame(dialog)
    status_frame.pack(fill=tk.X, padx=22)
    screen_status = tk.StringVar()
    accessibility_status = tk.StringVar()
    mirroring_status = tk.StringVar()
    identity_status = tk.StringVar()
    validation_status = tk.StringVar()

    def refresh() -> bool:
        screen_permission = screen_capture_permission()
        accessibility = accessibility_permission()
        identity_ready = packaged_app_identity_ready()
        identity_status.set(permission_identity_status_text())
        screen_status.set(f"1. Screen Recording: {permission_status_text(screen_permission)}")
        accessibility_status.set(f"2. Accessibility: {permission_status_text(accessibility)}")
        mirroring_status.set(
            "3. iPhone Mirroring: Ready"
            if locate_iphone_mirroring_window()
            else "3. iPhone Mirroring: Open it and keep the phone window visible"
        )
        return identity_ready and screen_permission is True and accessibility is True

    def check_again() -> None:
        if refresh():
            validation_status.set(
                f"Validated: Screen Recording and Accessibility are granted to {canonical_app_path()}."
            )
        else:
            validation_status.set(
                "Not validated: approve both permissions for the verified app above, "
                "then click Check again."
            )

    ttk.Label(status_frame, textvariable=identity_status).pack(anchor=tk.W, pady=2)
    ttk.Label(status_frame, textvariable=screen_status).pack(anchor=tk.W, pady=2)
    ttk.Label(status_frame, textvariable=accessibility_status).pack(anchor=tk.W, pady=2)
    ttk.Label(status_frame, textvariable=mirroring_status).pack(anchor=tk.W, pady=2)
    ttk.Label(status_frame, textvariable=validation_status, wraplength=640).pack(anchor=tk.W, pady=(8, 2))

    actions = ttk.Frame(dialog)
    actions.pack(fill=tk.X, padx=22, pady=(18, 8))

    def open_screen() -> None:
        request_screen_capture_permission()
        open_mac_permissions("screen")

    def open_accessibility() -> None:
        request_accessibility_permission()
        open_mac_permissions("accessibility")

    ttk.Button(actions, text="Open Screen Recording", command=open_screen).pack(side=tk.LEFT)
    ttk.Button(actions, text="Open Accessibility", command=open_accessibility).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(actions, text="Check again", command=check_again).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(actions, text="Done", command=dialog.destroy).pack(side=tk.RIGHT)
    refresh()
    if owns_root:
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_window()
        root.destroy()


def screen_capture_permission() -> bool | None:
    preflight = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
    if not callable(preflight):
        return None
    try:
        return bool(preflight())
    except Exception:
        return None


def accessibility_block_reason() -> str | None:
    permission = accessibility_permission()
    if permission is False:
        return (
            f"macOS has not granted Accessibility to {permission_subject()}. "
            "Open Bot Player setup, approve Bot Player.app in System Settings → "
            "Privacy & Security → Accessibility, then check setup again."
        )
    return None


def offer_mac_permissions() -> None:
    show_permission_setup()


def mirroring_capture_block_reason(target: MirroringWindow | None) -> str | None:
    permission = screen_capture_permission()
    if permission is False:
        return (
            f"macOS has not granted Screen Recording to {permission_subject()}. "
            "Open Bot Player setup, approve Bot Player.app in System Settings → "
            "Privacy & Security → Screen Recording, then check setup again."
        )
    if not target:
        return (
            "No authenticated iPhone Mirroring window was found. Keep iPhone Mirroring "
            "open and unlocked, then bring its phone window fully into view."
        )
    current = window_is_unchanged(target)
    if not current:
        return "The authenticated iPhone Mirroring window moved or disappeared. Leave it still and try again."
    occluding_window = occluding_window_name(current)
    if occluding_window:
        return (
            f"{occluding_window} is above the iPhone Mirroring region. Move or minimize it before capturing."
        )
    return None


def application_support() -> Path:
    return Path.home() / "Library" / "Application Support"

def game_key(game: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", game.lower()).strip("-") or "game"
def game_directory(game: str) -> Path:
    directory = application_support() / "BotPlayer" / "games" / game_key(game)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def locate_iphone_mirroring_window() -> MirroringWindow | None:
    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    windows = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
    for window in windows:
        owner = str(window.get(Quartz.kCGWindowOwnerName, "")).lower()
        title = str(window.get(Quartz.kCGWindowName, "")).lower()
        if owner != "iphone mirroring" and "iphone mirroring" not in title:
            continue
        if int(window.get(Quartz.kCGWindowLayer, 0)) != 0 or float(window.get(Quartz.kCGWindowAlpha, 1)) < 0.95:
            continue
        bounds = window.get(Quartz.kCGWindowBounds)
        if not bounds:
            continue
        rect = Rect.from_window(bounds)
        if rect.width < 180 or rect.height < 250:
            continue
        window_id = int(window.get(Quartz.kCGWindowNumber, 0))
        owner_pid = int(window.get(Quartz.kCGWindowOwnerPID, 0))
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(owner_pid) if owner_pid else None
        bundle_identifier = str(app.bundleIdentifier()) if app and app.bundleIdentifier() else ""
        if window_id and bundle_identifier in IPHONE_MIRRORING_BUNDLE_IDENTIFIERS:
            return MirroringWindow(window_id=window_id, rect=rect)
    return None


def window_is_unchanged(target: MirroringWindow) -> MirroringWindow | None:
    current = locate_iphone_mirroring_window()
    if not current or current.window_id != target.window_id:
        return None
    if any(abs(left - right) > 2 for left, right in zip(
        (current.rect.x, current.rect.y, current.rect.width, current.rect.height),
        (target.rect.x, target.rect.y, target.rect.width, target.rect.height),
    )):
        return None
    return current


def rects_intersect(left: Rect, right: Rect) -> bool:
    return not (
        left.x + left.width <= right.x
        or right.x + right.width <= left.x
        or left.y + left.height <= right.y
        or right.y + right.height <= left.y
    )


def occluding_window_name(target: MirroringWindow) -> str | None:
    """Return a visible window macOS reports above the Mirroring window, if any."""
    options = Quartz.kCGWindowListOptionOnScreenAboveWindow | Quartz.kCGWindowListExcludeDesktopElements
    windows = Quartz.CGWindowListCopyWindowInfo(options, target.window_id) or []
    for window in windows:
        window_id = int(window.get(Quartz.kCGWindowNumber, 0))
        if window_id == target.window_id:
            continue
        bounds = window.get(Quartz.kCGWindowBounds)
        if not bounds or float(window.get(Quartz.kCGWindowAlpha, 1)) <= 0.01:
            continue
        if rects_intersect(target.rect, Rect.from_window(bounds)):
            owner = str(window.get(Quartz.kCGWindowOwnerName, "")).strip()
            title = str(window.get(Quartz.kCGWindowName, "")).strip()
            return " — ".join(part for part in (owner, title) if part) or "an unnamed macOS window"
    return None


def window_is_unobscured(target: MirroringWindow) -> bool:
    """Require the authenticated Mirroring window to have no visible foreground overlap."""
    return occluding_window_name(target) is None


def active_unobscured_window(target: MirroringWindow) -> MirroringWindow | None:
    current = window_is_unchanged(target)
    return current if current and window_is_unobscured(current) else None


def screenshot(target: MirroringWindow) -> Image.Image:
    rect = target.rect
    return pyautogui.screenshot(region=(rect.x, rect.y, rect.width, rect.height)).convert("RGB")


def swipe_mirrored_phone(
    target: MirroringWindow,
    start: tuple[float, float],
    end: tuple[float, float],
    duration: float = 0.55,
) -> bool:
    """Send one guarded swipe entirely inside the authenticated Mirroring window."""
    current = active_unobscured_window(target)
    if not current or CONNECTION_CHECK_STOP_REQUESTED.is_set():
        return False
    rect = current.rect
    start_x = rect.x + start[0] * rect.width
    start_y = rect.y + start[1] * rect.height
    end_x = rect.x + end[0] * rect.width
    end_y = rect.y + end[1] * rect.height
    pyautogui.moveTo(start_x, start_y, duration=0.1)
    current = active_unobscured_window(target)
    if not current or CONNECTION_CHECK_STOP_REQUESTED.is_set():
        return False
    rect = current.rect
    end_x = rect.x + end[0] * rect.width
    end_y = rect.y + end[1] * rect.height
    pyautogui.dragTo(end_x, end_y, duration=duration, button="left")
    return True


def tap_mirrored_phone(target: MirroringWindow, point: tuple[float, float]) -> bool:
    """Move and tap only after a second, immediately-before-input safety check."""
    current = active_unobscured_window(target)
    if not current or CONNECTION_CHECK_STOP_REQUESTED.is_set():
        return False
    rect = current.rect
    pyautogui.moveTo(rect.x + point[0] * rect.width, rect.y + point[1] * rect.height, duration=0.1)
    if not active_unobscured_window(target) or CONNECTION_CHECK_STOP_REQUESTED.is_set():
        return False
    pyautogui.click()
    return True


def connection_check_active() -> bool:
    return CONNECTION_CHECK_ACTIVE.is_set()


def _run_connection_check(_args: argparse.Namespace | None = None) -> int:
    """Demonstrate safe Mirroring input without starting game automation."""
    if CONNECTION_CHECK_STOP_REQUESTED.is_set():
        emit("stopped", "Connection check was stopped before it sent any input.")
        return 1
    if accessibility_permission() is not True:
        emit(
            "stopped",
            f"Connection check needs Accessibility for {permission_subject()}. "
            "Open Mac setup & permissions and approve Bot Player.app first.",
        )
        return 1
    if screen_capture_permission() is not True:
        emit(
            "stopped",
            f"Connection check needs Screen Recording for {permission_subject()}. "
            "Open Mac setup & permissions and approve Bot Player.app first.",
        )
        return 1

    target = locate_iphone_mirroring_window()
    target = active_unobscured_window(target) if target else None
    if not target:
        emit(
            "stopped",
            "Connection check needs a visible, unobscured iPhone Mirroring window. "
            "Open iPhone Mirroring and leave its phone window in view.",
        )
        return 1

    try:
        screenshot(target)
        emit("checking", "Connection confirmed. Swiping to the iPhone Home Screen.")
        if not swipe_mirrored_phone(target, (0.50, 0.92), (0.50, 0.48)):
            emit("stopped", "The Mirroring window changed before the Home Screen swipe. No more input was sent.")
            return 1
        time.sleep(0.7)
        target = active_unobscured_window(target)
        if not target or CONNECTION_CHECK_STOP_REQUESTED.is_set():
            emit("stopped", "The Mirroring window changed after the Home Screen swipe. No more input was sent.")
            return 1
        home_fingerprint = fingerprint(screenshot(target))
        time.sleep(0.25)
        target = active_unobscured_window(target)
        if not target or CONNECTION_CHECK_STOP_REQUESTED.is_set():
            emit("stopped", "The Mirroring window changed while confirming the Home Screen. No more input was sent.")
            return 1
        confirmed_home_fingerprint = fingerprint(screenshot(target))
        if not fingerprints_stable(home_fingerprint, confirmed_home_fingerprint):
            emit(
                "stopped",
                "Bot Player could not confirm a stable Home Screen before tapping an app. No app tap was sent.",
            )
            return 1

        emit(
            "checking",
            "Opening the app in the upper-left Home Screen app slot. "
            "The check will return to Home only after a visible change is confirmed.",
        )
        before_app = confirmed_home_fingerprint
        if not tap_mirrored_phone(target, (0.25, 0.25)):
            emit("stopped", "The Mirroring window changed before the app tap. No input was sent.")
            return 1

        opened = False
        opened_fingerprint: bytes | None = None
        current = target
        for _ in range(8):
            time.sleep(0.4)
            current = active_unobscured_window(current)
            if not current or CONNECTION_CHECK_STOP_REQUESTED.is_set():
                emit("stopped", "The Mirroring window changed while opening the app. No close gesture was sent.")
                return 1
            current_fingerprint = fingerprint(screenshot(current))
            if board_changed(before_app, current_fingerprint):
                opened = True
                opened_fingerprint = current_fingerprint
                target = current
                break
        if not opened:
            emit(
                "stopped",
                "The app slot did not visibly open. Bot Player stopped without sending a close gesture; "
                "confirm an app is in the upper-left Home Screen slot and try again.",
            )
            return 1

        emit("checking", "The app opened through iPhone Mirroring. Returning to the Home Screen.")
        if not swipe_mirrored_phone(target, (0.50, 0.92), (0.50, 0.48)):
            emit("stopped", "The Mirroring window changed before the close gesture. No more input was sent.")
            return 1
        time.sleep(0.7)
        target = active_unobscured_window(target)
        if not target or CONNECTION_CHECK_STOP_REQUESTED.is_set():
            emit("stopped", "The Mirroring window changed while returning Home. Check the phone manually.")
            return 1
        returned_home = fingerprint(screenshot(target))
        if (
            opened_fingerprint is None
            or not board_changed(opened_fingerprint, returned_home)
            or not fingerprints_stable(confirmed_home_fingerprint, returned_home)
        ):
            emit(
                "stopped",
                "Bot Player could not visually confirm that the app returned to Home. "
                "No further input was sent; check the phone manually.",
            )
            return 1
    except pyautogui.FailSafeException:
        emit("stopped", "PyAutoGUI fail-safe triggered. The connection check stopped immediately.")
        return 1
    except Exception as error:
        emit("stopped", f"Connection check stopped safely: {error}")
        return 1

    emit("ready", "Connection check passed: Bot Player swiped, opened an app, and returned to the Home Screen.")
    return 0


def run_connection_check(_args: argparse.Namespace | None = None) -> int:
    CONNECTION_CHECK_ACTIVE.set()
    try:
        return _run_connection_check(_args)
    finally:
        CONNECTION_CHECK_ACTIVE.clear()


def recording_directory(game: str) -> Path:
    directory = application_support() / "BotPlayer" / "recordings" / game_key(game)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def start_recording_session(game: str) -> tuple[Path, Path]:
    """Create a private session directory and its frame directory."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    session_directory = recording_directory(game) / f"{timestamp}-{uuid.uuid4().hex[:8]}"
    session_directory.mkdir(parents=True, exist_ok=False)
    frames_directory = session_directory / "frames"
    frames_directory.mkdir()
    return session_directory, frames_directory


def record_live_session(args: argparse.Namespace) -> int:
    """Observe the real Mirroring window and save a local frame dataset without input."""
    session_directory, frames_directory = start_recording_session(args.game)
    manifest_path = session_directory / "manifest.json"
    manifest: dict[str, Any] = {
        "format": RECORDING_FORMAT,
        "version": RECORDING_VERSION,
        "game": {"name": args.game, "key": game_key(args.game)},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "capture_interval_seconds": RECORDING_INTERVAL_SECONDS,
        "input_sent": False,
        "frames": [],
    }
    emit(
        "recording",
        f"Recording started for {args.game}. Move to the game on the mirrored iPhone and play normally. "
        "Bot Player is observing only and will not tap.",
        recording=str(session_directory),
    )
    last_waiting_message = ""
    frame_number = 0
    next_capture_at = time.monotonic()
    try:
        while not RECORDING_STOP_REQUESTED.is_set() and frame_number < MAX_RECORDING_FRAMES:
            target = locate_iphone_mirroring_window()
            if not target:
                message = "Recording is waiting for the authenticated iPhone Mirroring window."
                if message != last_waiting_message:
                    emit("recording-waiting", message, recording=str(session_directory))
                    last_waiting_message = message
                time.sleep(RECORDING_INTERVAL_SECONDS)
                continue

            block_reason = mirroring_capture_block_reason(target)
            if block_reason:
                message = f"Recording paused safely: {block_reason}"
                if message != last_waiting_message:
                    emit("recording-waiting", message, recording=str(session_directory))
                    last_waiting_message = message
                time.sleep(RECORDING_INTERVAL_SECONDS)
                continue

            current = active_unobscured_window(target)
            if not current:
                time.sleep(RECORDING_INTERVAL_SECONDS)
                continue
            try:
                frame = screenshot(current)
                frame_path = frames_directory / f"frame-{frame_number:06d}.png"
                frame.save(frame_path, "PNG")
            except Exception as error:
                emit("recording-waiting", f"Recording paused while reading the mirrored window: {error}")
                time.sleep(RECORDING_INTERVAL_SECONDS)
                continue

            manifest["frames"].append(
                {
                    "index": frame_number,
                    "path": str(frame_path.relative_to(session_directory)),
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "window": {
                        "x": current.rect.x,
                        "y": current.rect.y,
                        "width": current.rect.width,
                        "height": current.rect.height,
                    },
                }
            )
            frame_number += 1
            last_waiting_message = ""
            emit(
                "recording",
                f"Recording live. Saved {frame_number} frame{'s' if frame_number != 1 else ''}. "
                "Play the game normally, then choose Stop & Save Recording.",
                frames=frame_number,
                recording=str(session_directory),
            )
            next_capture_at = max(next_capture_at + RECORDING_INTERVAL_SECONDS, time.monotonic())
            time.sleep(max(0.0, next_capture_at - time.monotonic()))
    finally:
        manifest["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        manifest["frame_count"] = frame_number
        manifest["stopped_by_frame_limit"] = frame_number >= MAX_RECORDING_FRAMES
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        emit(
            "recording-saved",
            f"Saved recording session with {frame_number} frame{'s' if frame_number != 1 else ''} to {session_directory}.",
            frames=frame_number,
            recording=str(session_directory),
            manifest=str(manifest_path),
        )
    return 0


def discover_recording_sessions(game: str) -> list[Path]:
    """Return complete local recording sessions for the selected game."""
    root = recording_directory(game)
    sessions: list[Path] = []
    for candidate in sorted(root.iterdir(), reverse=True):
        if not candidate.is_dir() or not (candidate / "manifest.json").is_file():
            continue
        try:
            manifest = json.loads((candidate / "manifest.json").read_text())
            game_data = manifest.get("game", {})
            if (
                manifest.get("format") == RECORDING_FORMAT
                and manifest.get("version") == RECORDING_VERSION
                and isinstance(game_data, dict)
                and game_key(str(game_data.get("key", game))) == game_key(game)
            ):
                sessions.append(candidate)
        except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return sessions


def _load_recording_frames(source: Path, game: str) -> tuple[list[TrainingFrame], float]:
    """Read only frames referenced by a validated local recording manifest."""
    manifest_path = source / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise TrainingSourceError("The recording manifest is missing or unreadable.") from error
    if not isinstance(manifest, dict):
        raise TrainingSourceError("The recording manifest must be an object.")
    if manifest.get("format") != RECORDING_FORMAT or manifest.get("version") != RECORDING_VERSION:
        raise TrainingSourceError("This recording format or version is not supported.")
    game_data = manifest.get("game")
    if not isinstance(game_data, dict) or game_key(str(game_data.get("key", ""))) != game_key(game):
        raise TrainingSourceError(f"This recording belongs to a different game, not {game}.")
    frame_entries = manifest.get("frames")
    if not isinstance(frame_entries, list):
        raise TrainingSourceError("The recording does not contain a usable frame list.")

    source_root = source.resolve()
    frames: list[TrainingFrame] = []
    for fallback_index, entry in enumerate(frame_entries[:MAX_RECORDING_FRAMES]):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        frame_path = (source / entry["path"]).resolve()
        try:
            frame_path.relative_to(source_root)
            image = Image.open(frame_path).convert("RGB")
            image.load()
            timestamp = float(entry.get("timestamp_seconds", fallback_index * RECORDING_INTERVAL_SECONDS))
        except (OSError, TypeError, ValueError, AttributeError):
            continue
        if _frame_is_usable(image):
            frames.append(TrainingFrame(image=image, index=fallback_index, timestamp=max(0.0, timestamp)))
    try:
        interval = float(manifest.get("capture_interval_seconds", RECORDING_INTERVAL_SECONDS))
    except (TypeError, ValueError) as error:
        raise TrainingSourceError("The recording capture interval is invalid.") from error
    if not math.isfinite(interval) or interval <= 0:
        raise TrainingSourceError("The recording capture interval is invalid.")
    duration = max(
        (frames[-1].timestamp - frames[0].timestamp) if len(frames) > 1 else 0.0,
        max(0.0, (len(frames) - 1) * interval),
    )
    return frames, duration


def _video_frame_to_image(frame: Any) -> Image.Image:
    import cv2  # type: ignore

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    return Image.frombytes("RGB", (int(width), int(height)), rgb.tobytes())


def _load_video_frames(source: Path) -> tuple[list[TrainingFrame], float]:
    """Sample a local video without uploading or retaining the source file."""
    if source.suffix.casefold() not in VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(VIDEO_EXTENSIONS))
        raise TrainingSourceError(f"Unsupported clip format. Choose a local video ({supported}).")
    if not source.is_file():
        raise TrainingSourceError("The selected clip could not be found.")
    try:
        import cv2  # type: ignore
    except ImportError as error:
        raise TrainingSourceError(
            "Local video import needs OpenCV. Install the Bot Player requirements and try again."
        ) from error

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise TrainingSourceError("The clip could not be opened. It may be damaged or use an unsupported codec.")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    if duration and duration < MIN_TRAINING_DURATION_SECONDS:
        capture.release()
        raise TrainingSourceError(
            f"Footage is too short ({duration:.1f}s). Use at least {MIN_TRAINING_DURATION_SECONDS:.1f}s of unobscured gameplay."
        )

    sample_count = min(MAX_TRAINING_ANALYSIS_FRAMES, max(MIN_TRAINING_FRAMES, int(max(duration, 1) * 4)))
    frame_numbers = (
        [round(index * max(frame_count - 1, 1) / max(sample_count - 1, 1)) for index in range(sample_count)]
        if frame_count > 0
        else list(range(sample_count))
    )
    frames: list[TrainingFrame] = []
    try:
        for index, frame_number in enumerate(frame_numbers):
            if frame_count > 0:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, raw_frame = capture.read()
            if not ok:
                continue
            image = _video_frame_to_image(raw_frame)
            if _frame_is_usable(image):
                timestamp = frame_number / fps if fps > 0 else index / 4
                frames.append(TrainingFrame(image=image, index=index, timestamp=timestamp))
    finally:
        capture.release()
    if not duration and len(frames) > 1:
        duration = frames[-1].timestamp - frames[0].timestamp
    return frames, duration


def _frame_is_usable(image: Image.Image) -> bool:
    """Reject blank, tiny, or nearly uniform frames before matching."""
    try:
        width, height = image.size
        if width < 96 or height < 96:
            return False
        stats = ImageStat.Stat(ImageOps.grayscale(image))
        variance = float(stats.var[0])
        mean = float(stats.mean[0])
        return variance >= 18 and 6 <= mean <= 249
    except (AttributeError, IndexError, TypeError, ValueError):
        return False


def _training_patch_is_usable(image: Image.Image) -> bool:
    """Reject flat background patches while allowing intentionally small template crops."""
    try:
        width, height = image.size
        if width < 12 or height < 12:
            return False
        stats = ImageStat.Stat(ImageOps.grayscale(image))
        return float(stats.var[0]) >= 35
    except (AttributeError, IndexError, TypeError, ValueError):
        return False


def _training_similarity(left: Image.Image, right: Image.Image) -> float:
    sample_left = ImageOps.grayscale(left).resize((20, 20))
    sample_right = ImageOps.grayscale(right).resize((20, 20))
    return 1 - ImageStat.Stat(ImageChops.difference(sample_left, sample_right)).mean[0] / 255


def _training_patch_positions(region: tuple[float, float, float, float]) -> Iterable[tuple[float, float, float, float]]:
    """Use a modest fixed patch size so imported templates match the live classifier."""
    x, y, width, height = region
    patch_width = min(0.16, width * 0.8)
    patch_height = min(0.12, height * 0.8)
    step_x = max(patch_width * 0.55, 0.04)
    step_y = max(patch_height * 0.55, 0.04)
    current_y = y
    while current_y + patch_height <= y + height + 0.0001:
        current_x = x
        while current_x + patch_width <= x + width + 0.0001:
            yield current_x, current_y, patch_width, patch_height
            current_x += step_x
        current_y += step_y


def generate_training_candidates(frames: Iterable[TrainingFrame], game: str) -> list[dict[str, Any]]:
    """Propose repeated target/pile pairs; never invent labels from a single frame."""
    usable_frames = list(frames)
    if len(usable_frames) < MIN_TRAINING_FRAMES:
        raise TrainingSourceError(
            f"Footage is too short or obscured. Only {len(usable_frames)} usable frames were found; "
            f"at least {MIN_TRAINING_FRAMES} are needed."
        )

    proposals: list[dict[str, Any]] = []
    for frame in usable_frames[:: max(1, len(usable_frames) // 30)]:
        target_patches = [
            (rect, crop_normalized(frame.image, rect))
            for rect in _training_patch_positions(TRAINING_TARGET_REGION)
        ]
        pile_patches = [
            (rect, crop_normalized(frame.image, rect))
            for rect in _training_patch_positions(TRAINING_PILE_REGION)
        ]
        for target_rect, target_image in target_patches:
            if not _training_patch_is_usable(target_image):
                continue
            best_pair: tuple[float, tuple[float, float, float, float], Image.Image] | None = None
            for pile_rect, pile_image in pile_patches:
                if not _training_patch_is_usable(pile_image):
                    continue
                similarity = _training_similarity(target_image, pile_image)
                if similarity >= TRAINING_MATCH_THRESHOLD and (best_pair is None or similarity > best_pair[0]):
                    best_pair = similarity, pile_rect, pile_image
            if best_pair is None:
                continue
            similarity, pile_rect, pile_image = best_pair
            matched = None
            for proposal in proposals:
                if (
                    _training_similarity(proposal["_target_image"], target_image) >= TRAINING_MATCH_THRESHOLD
                    and _training_similarity(proposal["_pile_image"], pile_image) >= TRAINING_MATCH_THRESHOLD
                ):
                    matched = proposal
                    break
            if matched:
                matched["support"] += 1
                matched["confidence"] = max(matched["confidence"], round(similarity, 3))
                matched["frames"].append(frame.index)
                continue
            if len(proposals) < MAX_TRAINING_CANDIDATES:
                proposals.append(
                    {
                        "label": f"item {len(proposals) + 1:02d}",
                        "confidence": round(similarity, 3),
                        "support": 1,
                        "frames": [frame.index],
                        "target_rect": target_rect,
                        "pile_rect": pile_rect,
                        "_target_image": target_image,
                        "_pile_image": pile_image,
                    }
                )

    trustworthy = [proposal for proposal in proposals if proposal["support"] >= 2]
    if not trustworthy:
        raise TrainingSourceError(
            "No trustworthy target/board-item pairs were found. Use unobscured gameplay where the same pieces "
            "are visible in the top target strip and the lower board."
        )
    return trustworthy


def analyze_training_source(source: str | Path, game: str) -> dict[str, Any]:
    """Load a local session/clip and return a review-ready, non-persistent proposal."""
    source_path = Path(source).expanduser()
    if source_path.is_file() and source_path.name == "manifest.json":
        source_path = source_path.parent
    if source_path.is_dir():
        frames, duration = _load_recording_frames(source_path, game)
        source_kind = "recording"
    else:
        frames, duration = _load_video_frames(source_path)
        source_kind = "clip"
    if duration < MIN_TRAINING_DURATION_SECONDS:
        raise TrainingSourceError(
            f"Footage is too short ({duration:.1f}s). Use at least {MIN_TRAINING_DURATION_SECONDS:.1f}s of gameplay."
        )
    if len(frames) < MIN_TRAINING_FRAMES:
        raise TrainingSourceError(
            f"Footage is too short or obscured. Only {len(frames)} usable frames were found; "
            f"at least {MIN_TRAINING_FRAMES} are needed."
        )
    candidates = generate_training_candidates(frames, game)
    return {
        "source": str(source_path),
        "source_kind": source_kind,
        "game": game,
        "duration": round(duration, 2),
        "frame_count": len(frames),
        "candidates": candidates,
    }


def training_import_allowed(recording_active: bool) -> bool:
    """A passive ready-state controller never blocks local training review."""
    return not START_REQUESTED.is_set() and not recording_active


def save_training_set(game: str, candidates: Iterable[dict[str, Any]], source: str = "local footage") -> int:
    """Atomically replace one game's templates after the user confirms the review."""
    selected = list(candidates)
    if not selected:
        raise TrainingSourceError("No reviewed examples were selected.")
    complete: list[dict[str, Any]] = []
    labels: set[str] = set()
    for candidate in selected:
        label = str(candidate.get("label", "")).strip()
        target_image = candidate.get("_target_image")
        pile_image = candidate.get("_pile_image")
        if not label or not hasattr(target_image, "save") or not hasattr(pile_image, "save"):
            raise TrainingSourceError("A reviewed example is incomplete and was not saved.")
        if label.casefold() in labels:
            raise TrainingSourceError("Reviewed examples cannot use the same label twice.")
        labels.add(label.casefold())
        complete.extend(
            [
                {"label": label, "role": "target", "rect": candidate["target_rect"], "image": target_image},
                {"label": label, "role": "pile", "rect": candidate["pile_rect"], "image": pile_image},
            ]
        )
    if any(not isinstance(entry.get("rect"), tuple) or len(entry["rect"]) != 4 for entry in complete):
        raise TrainingSourceError("A reviewed example has an invalid capture region.")

    directory = application_support() / "RelayCockpit" / "box-jam-templates"
    directory.mkdir(parents=True, exist_ok=True)
    index_path = directory / "index.json"
    previous_entries = load_saved_template_entries()
    selected_game_key = game_key(game)
    preserved = [entry for entry in previous_entries if entry_game_key(entry) != selected_game_key]
    staged: list[Path] = []
    new_entries: list[dict[str, Any]] = []
    staged_index: Path | None = None
    try:
        for entry in complete:
            template_id = str(uuid.uuid4())
            staged_path = directory / f".training-{template_id}.png"
            entry["image"].convert("RGB").save(staged_path, "PNG")
            staged.append(staged_path)
            final_filename = f"{template_id}.png"
            final_path = directory / final_filename
            os.replace(staged_path, final_path)
            new_entries.append(
                {
                    "id": template_id,
                    "game": selected_game_key,
                    "label": entry["label"],
                    "role": entry["role"],
                    "rect": {
                        "x": entry["rect"][0],
                        "y": entry["rect"][1],
                        "width": entry["rect"][2],
                        "height": entry["rect"][3],
                    },
                    "filename": final_filename,
                    "source": source,
                }
            )
        staged_index = directory / f".training-index-{uuid.uuid4()}.json"
        staged_index.write_text(json.dumps(preserved + new_entries, indent=2) + "\n")
        os.replace(staged_index, index_path)
    except (OSError, TypeError, ValueError, AttributeError) as error:
        for path in staged:
            path.unlink(missing_ok=True)
        if staged_index is not None:
            staged_index.unlink(missing_ok=True)
        for entry in new_entries:
            (directory / str(entry["filename"])).unlink(missing_ok=True)
        raise TrainingSourceError(f"Training set could not be saved; current templates were left unchanged: {error}") from error

    referenced = {entry.get("filename") for entry in preserved + new_entries}
    for entry in previous_entries:
        old_path = template_entry_path(entry)
        if old_path and old_path.name not in referenced:
            old_path.unlink(missing_ok=True)
    START_REQUESTED.clear()
    emit(
        "ready",
        f"Saved {len(selected)} reviewed training example{'s' if len(selected) != 1 else ''} for {game}. "
        "Press Start Bot Player to load them.",
        training_examples=len(selected),
    )
    return len(selected)


def review_training_candidates(parent: Any, review: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Show a local review window and return only examples explicitly confirmed."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    window = tk.Toplevel(parent)
    window.title("Review imported training")
    window.geometry("760x620")
    window.minsize(620, 480)
    candidates = list(review.get("candidates", []))
    selected: list[tuple[Any, dict[str, Any]]] = []
    thumbnails: list[Any] = []

    ttk.Label(
        window,
        text=f"Review proposals for {review.get('game', 'the selected game')}",
        font=("Helvetica", 15, "bold"),
    ).pack(anchor=tk.W, padx=18, pady=(18, 3))
    ttk.Label(
        window,
        text=(
            f"Found {review.get('frame_count', 0)} usable frames over {float(review.get('duration', 0)):.1f}s. "
            "Only repeated target/board-item matches are shown. Nothing changes until you confirm below."
        ),
        wraplength=710,
    ).pack(anchor=tk.W, padx=18, pady=(0, 12))

    body = ttk.Frame(window)
    body.pack(fill=tk.BOTH, expand=True, padx=18)
    canvas = tk.Canvas(body, highlightthickness=0)
    scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
    rows = ttk.Frame(canvas)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.create_window((0, 0), window=rows, anchor=tk.NW)
    rows.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))

    for candidate in candidates:
        variable = tk.BooleanVar(value=True)
        selected.append((variable, candidate))
        row = ttk.Frame(rows)
        row.pack(fill=tk.X, pady=5)
        target_image = candidate["_target_image"].copy()
        pile_image = candidate["_pile_image"].copy()
        target_image.thumbnail((150, 90))
        pile_image.thumbnail((150, 90))
        target_photo = ImageTk.PhotoImage(target_image)
        pile_photo = ImageTk.PhotoImage(pile_image)
        thumbnails.extend((target_photo, pile_photo))
        ttk.Checkbutton(row, variable=variable).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(row, image=target_photo).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(row, image=pile_photo).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(
            row,
            text=(
                f"{candidate.get('label', 'example')}\n"
                f"Target / board item · {candidate.get('support', 0)} repeated frames · "
                f"{float(candidate.get('confidence', 0)):.0%} visual match"
            ),
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, anchor=tk.CENTER)

    result: list[dict[str, Any]] | None = None

    def confirm() -> None:
        nonlocal result
        chosen = [candidate for variable, candidate in selected if variable.get()]
        if not chosen:
            messagebox.showwarning("Nothing selected", "Select at least one reviewed example.", parent=window)
            return
        if not messagebox.askyesno(
            "Replace current training?",
            (
                f"Save {len(chosen)} reviewed example{'s' if len(chosen) != 1 else ''} for "
                f"{review.get('game', 'the selected game')}? This replaces that game's current target and "
                "board-item templates. Other games are not changed."
            ),
            parent=window,
            default=messagebox.NO,
        ):
            return
        try:
            save_training_set(str(review["game"]), chosen, str(review.get("source", "local footage")))
        except TrainingSourceError as error:
            messagebox.showerror("Training was not saved", str(error), parent=window)
            return
        result = chosen
        window.destroy()

    actions = ttk.Frame(window)
    actions.pack(fill=tk.X, padx=18, pady=16)
    ttk.Button(actions, text="Cancel", command=window.destroy).pack(side=tk.RIGHT)
    ttk.Button(actions, text="Confirm and save selected", command=confirm).pack(side=tk.RIGHT, padx=(0, 8))
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.transient(parent)
    window.grab_set()
    parent.wait_window(window)
    return result


def fingerprint(frame: Image.Image) -> bytes:
    return ImageOps.grayscale(frame).resize((16, 16)).tobytes()


def board_changed(before: bytes, after: bytes) -> bool:
    if len(before) != len(after):
        return True
    difference = sum(abs(left - right) for left, right in zip(before, after))
    return difference / (len(before) * 255) >= 0.045


def fingerprints_stable(before: bytes, after: bytes) -> bool:
    if len(before) != len(after):
        return False
    difference = sum(abs(left - right) for left, right in zip(before, after))
    return difference / (len(before) * 255) <= 0.015


def board_fingerprint(frame: Image.Image) -> bytes:
    return fingerprint(crop_normalized(frame, (0.02, 0.24, 0.96, 0.72)))


def normalized_region(value: str) -> tuple[float, float, float, float]:
    try:
        x, y, width, height = (float(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use x,y,width,height with values from 0 to 1.") from error
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < width <= 1 and 0 < height <= 1 and x + width <= 1 and y + height <= 1):
        raise argparse.ArgumentTypeError("The game-icon region must stay inside the mirrored window.")
    return x, y, width, height


def crop_normalized(frame: Image.Image, rect: tuple[float, float, float, float]) -> Image.Image:
    x, y, width, height = rect
    left = int(round(x * frame.width))
    top = int(round(y * frame.height))
    right = int(round((x + width) * frame.width))
    bottom = int(round((y + height) * frame.height))
    return frame.crop((left, top, right, bottom))


def select_region(frame: Image.Image, title: str) -> tuple[float, float, float, float] | None:
    """Let a user draw a local template without requiring a native app build."""
    import tkinter as tk

    max_width, max_height = 720, 760
    scale = min(max_width / frame.width, max_height / frame.height, 1)
    display = frame.resize((int(frame.width * scale), int(frame.height * scale)))
    root = tk.Tk()
    root.title(f"Bot Player — {title}")
    canvas = tk.Canvas(root, width=display.width, height=display.height, highlightthickness=0)
    canvas.pack()
    image = ImageTk.PhotoImage(display)
    canvas.create_image(0, 0, anchor=tk.NW, image=image)
    start: tuple[int, int] | None = None
    selection: tuple[int, int, int, int] | None = None
    rectangle: int | None = None

    def press(event: Any) -> None:
        nonlocal start, rectangle
        start = (event.x, event.y)
        rectangle = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#5b7cfa", width=3)

    def drag(event: Any) -> None:
        if start is not None and rectangle is not None:
            canvas.coords(rectangle, start[0], start[1], event.x, event.y)

    def release(event: Any) -> None:
        nonlocal selection
        if start is not None:
            selection = (start[0], start[1], event.x, event.y)
            root.destroy()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.mainloop()
    if not selection:
        return None
    x1, y1, x2, y2 = selection
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    if right - left < 12 or bottom - top < 12:
        return None
    return (
        left / display.width,
        top / display.height,
        (right - left) / display.width,
        (bottom - top) / display.height,
    )


def select_icon_region(frame: Image.Image, game: str) -> tuple[float, float, float, float] | None:
    return select_region(frame, f"draw around the {game} icon")


def save_game_icon_template(frame: Image.Image, game: str, region: tuple[float, float, float, float]) -> Path:
    directory = game_directory(game)
    image_path = directory / "icon.png"
    metadata_path = directory / "icon.json"
    crop_normalized(frame, region).save(image_path, "PNG")
    metadata_path.write_text(json.dumps({"region": region}, indent=2))
    return image_path


def seed_default_game_icon_template(game: str) -> bool:
    """Install the bundled Block Jam 3D icon once, without any tester upload."""
    if game_key(game) != game_key(DEFAULT_GAME_NAME):
        return False
    directory = game_directory(game)
    image_path = directory / "icon.png"
    metadata_path = directory / "icon.json"
    if image_path.exists() and metadata_path.exists():
        return True
    try:
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        bundled_icon = bundle_root / "block-jam-3d-icon.png"
        image = Image.open(bundled_icon)
        image.load()
        image.convert("RGB").save(image_path, "PNG")
        metadata_path.write_text(
            json.dumps({"region": DEFAULT_BLOCK_JAM_ICON_REGION, "source": "bundled-default"}, indent=2)
        )
        return True
    except (OSError, ValueError):
        return False


def load_game_icon_template(game: str) -> Template | None:
    directory = game_directory(game)
    image_path = directory / "icon.png"
    metadata_path = directory / "icon.json"
    if not image_path.exists() or not metadata_path.exists():
        seed_default_game_icon_template(game)
    if not image_path.exists() or not metadata_path.exists():
        return None
    try:
        region = json.loads(metadata_path.read_text())["region"]
        return Template(
            label=game,
            role="icon",
            relative_width=float(region[2]),
            relative_height=float(region[3]),
            image=Image.open(image_path).convert("RGB"),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def game_icon_source(game: str) -> str | None:
    """Report whether an icon is bundled or locally captured for the setup UI."""
    metadata_path = game_directory(game) / "icon.json"
    try:
        source = json.loads(metadata_path.read_text()).get("source")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return source if isinstance(source, str) else None


def remove_game_icon_template(game: str) -> bool:
    directory = game_directory(game)
    removed = False
    for filename in ("icon.png", "icon.json"):
        path = directory / filename
        try:
            path.unlink()
            removed = True
        except FileNotFoundError:
            pass
        except OSError:
            continue
    return removed


class CalibrationBackupError(ValueError):
    """A portable calibration backup is invalid or cannot be safely applied."""


def _validated_region(value: Any, field_name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise CalibrationBackupError(f"{field_name} must contain four normalized values.")
    try:
        region = [float(part) for part in value]
    except (TypeError, ValueError) as error:
        raise CalibrationBackupError(f"{field_name} must contain numeric values.") from error
    if (
        any(not math.isfinite(part) for part in region)
        or region[0] < 0
        or region[1] < 0
        or region[2] <= 0
        or region[3] <= 0
        or region[0] + region[2] > 1
        or region[1] + region[3] > 1
    ):
        raise CalibrationBackupError(f"{field_name} must stay inside the mirrored window.")
    return region


def _validated_rect(value: Any, field_name: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise CalibrationBackupError(f"{field_name} must be an object.")
    x, y, width, height = _validated_region(
        [value.get("x"), value.get("y"), value.get("width"), value.get("height")],
        field_name,
    )
    return {"x": x, "y": y, "width": width, "height": height}


def _validated_image_bytes(value: Any, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise CalibrationBackupError(f"{field_name} is missing.")
    try:
        image_bytes = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise CalibrationBackupError(f"{field_name} is not valid base64.") from error
    if not image_bytes or len(image_bytes) > MAX_CALIBRATION_IMAGE_BYTES:
        raise CalibrationBackupError(f"{field_name} is empty or too large.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size
            if width * height > MAX_CALIBRATION_IMAGE_PIXELS:
                raise CalibrationBackupError(f"{field_name} has too many pixels.")
            image.verify()
            image = Image.open(io.BytesIO(image_bytes))
            image.load()
    except CalibrationBackupError:
        raise
    except (OSError, ValueError, AttributeError, Warning) as error:
        raise CalibrationBackupError(f"{field_name} is not a readable image.") from error
    return image_bytes


def _read_calibration_index() -> list[dict[str, Any]]:
    directory = application_support() / "RelayCockpit" / "box-jam-templates"
    index_path = directory / "index.json"
    if not index_path.exists():
        return []
    try:
        entries = json.loads(index_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise CalibrationBackupError("The current template library cannot be read safely.") from error
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise CalibrationBackupError("The current template library has an invalid index.")
    return entries


def _validated_saved_calibration(game: str) -> dict[str, Any]:
    icon_directory = game_directory(game)
    icon_path = icon_directory / "icon.png"
    icon_metadata_path = icon_directory / "icon.json"
    if not icon_path.exists() or not icon_metadata_path.exists():
        raise CalibrationBackupError(f"The {game} game icon is missing.")
    try:
        icon_region = json.loads(icon_metadata_path.read_text())["region"]
        icon_bytes = icon_path.read_bytes()
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise CalibrationBackupError(f"The {game} game icon metadata is invalid.") from error
    icon_region = _validated_region(icon_region, "The game icon region")
    _validated_image_bytes(base64.b64encode(icon_bytes).decode("ascii"), "The game icon")

    entries = _read_calibration_index()
    selected_entries = [entry for entry in entries if entry_game_key(entry) == game_key(game)]
    if not selected_entries:
        raise CalibrationBackupError(f"No target/board-item templates are saved for {game}.")
    templates: list[dict[str, Any]] = []
    roles_by_label: dict[str, set[str]] = {}
    total_image_bytes = len(icon_bytes)
    for entry in selected_entries:
        label = entry.get("label")
        role = entry.get("role")
        if not isinstance(label, str) or not label.strip() or role not in {"target", "pile"}:
            raise CalibrationBackupError("The selected game's template library is incomplete.")
        image_path = template_entry_path(entry)
        if image_path is None or not image_path.exists():
            raise CalibrationBackupError(f"The saved {role} template for {label} is missing.")
        try:
            image_bytes = image_path.read_bytes()
        except OSError as error:
            raise CalibrationBackupError(f"The saved {role} template for {label} cannot be read.") from error
        _validated_image_bytes(base64.b64encode(image_bytes).decode("ascii"), f"The {role} template for {label}")
        total_image_bytes += len(image_bytes)
        if total_image_bytes > MAX_CALIBRATION_BACKUP_BYTES // 2:
            raise CalibrationBackupError(f"The {game} calibration is too large to back up safely.")
        rect = _validated_rect(entry.get("rect"), f"The {role} rectangle for {label}")
        clean_label = label.strip()
        label_key = clean_label.casefold()
        if role in roles_by_label.setdefault(label_key, set()):
            raise CalibrationBackupError(f"The {label} templates contain a duplicate {role}.")
        roles_by_label[label_key].add(role)
        templates.append({"label": clean_label, "role": role, "rect": rect, "image": image_bytes})
    if not templates or any(roles != {"target", "pile"} for roles in roles_by_label.values()):
        raise CalibrationBackupError("At least one complete target/board-item pair is required.")
    return {
        "format": CALIBRATION_FORMAT,
        "version": CALIBRATION_VERSION,
        "game": {"name": game, "key": game_key(game)},
        "icon": {
            "region": icon_region,
            "image": base64.b64encode(icon_bytes).decode("ascii"),
        },
        "templates": [
            {
                "label": template["label"],
                "role": template["role"],
                "rect": template["rect"],
                "image": base64.b64encode(template["image"]).decode("ascii"),
            }
            for template in templates
        ],
    }


def export_game_calibration(game: str, destination: str | Path) -> bool:
    try:
        payload = _validated_saved_calibration(game)
        destination_path = Path(destination).expanduser()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(json.dumps(payload, indent=2) + "\n")
    except (CalibrationBackupError, OSError, TypeError, ValueError) as error:
        emit("ready", f"Calibration backup was not exported: {error}")
        return False
    emit("ready", f"Exported the {game} calibration backup.", backup=str(destination_path))
    return True


def _validated_backup_payload(game: str, source: str | Path) -> dict[str, Any]:
    source_path = Path(source).expanduser()
    try:
        if source_path.stat().st_size > MAX_CALIBRATION_BACKUP_BYTES:
            raise CalibrationBackupError("The backup file is too large.")
        payload = json.loads(source_path.read_text())
    except CalibrationBackupError:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise CalibrationBackupError("The backup file is not readable JSON.") from error
    if not isinstance(payload, dict):
        raise CalibrationBackupError("The backup root must be an object.")
    if payload.get("format") != CALIBRATION_FORMAT or payload.get("version") != CALIBRATION_VERSION:
        raise CalibrationBackupError("This backup format or version is not supported.")
    game_data = payload.get("game")
    if not isinstance(game_data, dict) or not isinstance(game_data.get("name"), str):
        raise CalibrationBackupError("The backup does not identify a game.")
    backup_name = game_data["name"].strip()
    if (
        not backup_name
        or game_data.get("key") != game_key(backup_name)
        or game_key(backup_name) != game_key(game)
    ):
        raise CalibrationBackupError(f"This backup is for a different game, not {game}.")
    icon = payload.get("icon")
    if not isinstance(icon, dict):
        raise CalibrationBackupError("The game icon is missing from the backup.")
    icon_region = _validated_region(icon.get("region"), "The game icon region")
    icon_image = _validated_image_bytes(icon.get("image"), "The game icon")
    templates_data = payload.get("templates")
    if (
        not isinstance(templates_data, list)
        or not templates_data
        or len(templates_data) > MAX_CALIBRATION_TEMPLATES
    ):
        raise CalibrationBackupError("The backup must contain target/board-item templates.")
    templates: list[dict[str, Any]] = []
    roles_by_label: dict[str, set[str]] = {}
    total_image_bytes = len(icon_image)
    for template in templates_data:
        if not isinstance(template, dict):
            raise CalibrationBackupError("A backup template is not an object.")
        label = template.get("label")
        role = template.get("role")
        if not isinstance(label, str) or not label.strip() or role not in {"target", "pile"}:
            raise CalibrationBackupError("Every backup template needs a label and valid role.")
        clean_label = label.strip()
        label_key = clean_label.casefold()
        if role in roles_by_label.setdefault(label_key, set()):
            raise CalibrationBackupError(f"The backup contains a duplicate {role} for {clean_label}.")
        roles_by_label[label_key].add(role)
        template_image = _validated_image_bytes(template.get("image"), f"The {role} template for {clean_label}")
        total_image_bytes += len(template_image)
        if total_image_bytes > MAX_CALIBRATION_BACKUP_BYTES // 2:
            raise CalibrationBackupError("The backup images are too large.")
        templates.append(
            {
                "label": clean_label,
                "role": role,
                "rect": _validated_rect(template.get("rect"), f"The {role} rectangle for {clean_label}"),
                "image": template_image,
            }
        )
    if any(roles != {"target", "pile"} for roles in roles_by_label.values()):
        raise CalibrationBackupError("At least one complete target/board-item pair is required.")
    return {
        "icon_region": icon_region,
        "icon_image": icon_image,
        "templates": templates,
    }


def _stage_bytes(directory: Path, prefix: str, suffix: str, content: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return Path(temporary_name)


def _restore_from_backup(path: Path, backup_path: Path | None) -> bool:
    try:
        if backup_path is None:
            path.unlink(missing_ok=True)
        else:
            os.replace(backup_path, path)
    except OSError:
        return False
    return True


def _restore_game_calibration(game: str, source: str | Path) -> bool:
    if START_REQUESTED.is_set():
        emit(
            "ready",
            "Stop Bot Player before restoring calibration. Current setup was not changed, and restored templates "
            "always require a new Start.",
        )
        return False
    current_setup_unchanged = True
    keep_recovery_files = False
    temporary_paths: list[Path] = []
    try:
        payload = _validated_backup_payload(game, source)
        entries = _read_calibration_index()
        template_directory = application_support() / "RelayCockpit" / "box-jam-templates"
        template_directory.mkdir(parents=True, exist_ok=True)
        icon_directory = game_directory(game)
        index_path = template_directory / "index.json"
        icon_path = icon_directory / "icon.png"
        icon_metadata_path = icon_directory / "icon.json"
        new_entries = [entry for entry in entries if entry_game_key(entry) != game_key(game)]
        old_entries = [entry for entry in entries if entry_game_key(entry) == game_key(game)]
        staged_templates: list[tuple[Path, Path]] = []
        new_template_paths: list[Path] = []
        for template in payload["templates"]:
            filename = f"{uuid.uuid4()}.png"
            temporary_path = _stage_bytes(template_directory, ".restore-template-", ".png", template["image"])
            final_path = template_directory / filename
            temporary_paths.append(temporary_path)
            staged_templates.append((temporary_path, final_path))
            new_template_paths.append(final_path)
            new_entries.append(
                {
                    "id": str(uuid.uuid4()),
                    "game": game_key(game),
                    "label": template["label"],
                    "role": template["role"],
                    "rect": template["rect"],
                    "filename": filename,
                }
            )
        index_temp = _stage_bytes(
            template_directory,
            ".restore-index-",
            ".json",
            (json.dumps(new_entries, indent=2) + "\n").encode(),
        )
        icon_temp = _stage_bytes(icon_directory, ".restore-icon-", ".png", payload["icon_image"])
        icon_metadata_temp = _stage_bytes(
            icon_directory,
            ".restore-icon-",
            ".json",
            (json.dumps({"region": payload["icon_region"]}, indent=2) + "\n").encode(),
        )
        temporary_paths.extend((index_temp, icon_temp, icon_metadata_temp))
        index_backup = _stage_bytes(template_directory, ".restore-recovery-", ".json", index_path.read_bytes()) if index_path.exists() else None
        icon_backup = _stage_bytes(icon_directory, ".restore-recovery-", ".png", icon_path.read_bytes()) if icon_path.exists() else None
        icon_metadata_backup = (
            _stage_bytes(icon_directory, ".restore-recovery-", ".json", icon_metadata_path.read_bytes())
            if icon_metadata_path.exists()
            else None
        )
        temporary_paths.extend(path for path in (index_backup, icon_backup, icon_metadata_backup) if path)
        committed_index = committed_icon = committed_icon_metadata = False
        try:
            for temporary_path, final_path in staged_templates:
                os.replace(temporary_path, final_path)
            os.replace(index_temp, index_path)
            committed_index = True
            os.replace(icon_temp, icon_path)
            committed_icon = True
            os.replace(icon_metadata_temp, icon_metadata_path)
            committed_icon_metadata = True
        except OSError as error:
            rollback_succeeded = True
            if committed_icon_metadata:
                rollback_succeeded = _restore_from_backup(icon_metadata_path, icon_metadata_backup) and rollback_succeeded
            if committed_icon:
                rollback_succeeded = _restore_from_backup(icon_path, icon_backup) and rollback_succeeded
            if committed_index:
                rollback_succeeded = _restore_from_backup(index_path, index_backup) and rollback_succeeded
            current_setup_unchanged = rollback_succeeded
            keep_recovery_files = not rollback_succeeded
            if rollback_succeeded:
                raise CalibrationBackupError(f"Restore could not be completed ({error}); the current setup was restored.")
            raise CalibrationBackupError(
                "Restore could not be completed and automatic rollback failed. Close Bot Player and verify the "
                "selected game's calibration before pressing Start."
            ) from error

        referenced_filenames = {
            entry.get("filename")
            for entry in new_entries
            if isinstance(entry.get("filename"), str)
        }
        for entry in old_entries:
            old_path = template_entry_path(entry)
            if old_path and old_path.name not in referenced_filenames:
                try:
                    old_path.unlink(missing_ok=True)
                except OSError:
                    # Orphaned old captures are harmless; the committed index
                    # points only at the newly restored files.
                    pass
    except (CalibrationBackupError, OSError, TypeError, ValueError) as error:
        unchanged_message = "Current setup was not changed." if current_setup_unchanged else ""
        emit("ready", f"Calibration restore was rejected: {error} {unchanged_message}".strip())
        return False
    finally:
        if not keep_recovery_files:
            for temporary_path in temporary_paths:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
    # A restore is never an authorization to play. Clear any event that could
    # have been set while the local file transaction was in progress.
    START_REQUESTED.clear()
    emit("ready", f"Restored the {game} calibration. Press Start Bot Player to use it.", restored=True)
    return True


def restore_game_calibration(game: str, source: str | Path) -> bool:
    """Restore only while template loading cannot race with a controller start."""
    with CALIBRATION_LOCK:
        return _restore_game_calibration(game, source)


def entry_game_key(entry: dict[str, Any]) -> str:
    """Keep pre-library Block Jam captures usable without showing them for other games."""
    saved_game = entry.get("game")
    if isinstance(saved_game, str) and saved_game.strip():
        return game_key(saved_game)
    return game_key(DEFAULT_GAME_NAME)


def template_entry_path(entry: dict[str, Any]) -> Path | None:
    filename = entry.get("filename")
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        return None
    return application_support() / "RelayCockpit" / "box-jam-templates" / filename


def load_saved_template_entries(game: str | None = None) -> list[dict[str, Any]]:
    """Read the local index used by both the matcher and the template library."""
    directory = application_support() / "RelayCockpit" / "box-jam-templates"
    index_path = directory / "index.json"
    if not index_path.exists():
        return []
    try:
        entries = json.loads(index_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(entries, list):
        return []
    saved_entries = [entry for entry in entries if isinstance(entry, dict)]
    if game is None:
        return saved_entries
    selected_game = game_key(game)
    return [entry for entry in saved_entries if entry_game_key(entry) == selected_game]


def load_existing_game_templates(game: str) -> list[Template]:
    """Read the same locally saved target and pile templates as the prior matcher."""
    templates: list[Template] = []
    for entry in load_saved_template_entries(game):
        try:
            image_path = template_entry_path(entry)
            if image_path is None:
                continue
            rect = entry["rect"]
            if str(entry["role"]) not in {"target", "pile"}:
                continue
            templates.append(
                Template(
                    label=str(entry["label"]),
                    role=str(entry["role"]),
                    relative_width=float(rect["width"]),
                    relative_height=float(rect["height"]),
                    image=Image.open(image_path).convert("RGB"),
                )
            )
        except (KeyError, OSError, TypeError, ValueError, AttributeError):
            continue
    return templates


def save_game_template(frame: Image.Image, game: str, label: str, role: str) -> Path | None:
    clean_label = label.strip()
    if role not in {"target", "pile"} or not clean_label:
        return None
    region = select_region(frame, f"draw around the {role} template for {clean_label}")
    if not region:
        return None
    directory = application_support() / "RelayCockpit" / "box-jam-templates"
    directory.mkdir(parents=True, exist_ok=True)
    index_path = directory / "index.json"
    templates = load_saved_template_entries()
    template_id = str(uuid.uuid4())
    filename = f"{template_id}.png"
    crop_normalized(frame, region).save(directory / filename, "PNG")
    replaced_filenames = [
        template.get("filename")
        for template in templates
        if (
            str(template.get("label", "")).casefold() == clean_label.casefold()
            and str(template.get("role", "")) == role
            and entry_game_key(template) == game_key(game)
            and isinstance(template.get("filename"), str)
        )
    ]
    templates = [
        template
        for template in templates
        if not (
            str(template.get("label", "")).casefold() == clean_label.casefold()
            and str(template.get("role", "")) == role
            and entry_game_key(template) == game_key(game)
        )
    ]
    templates.append(
        {
            "id": template_id,
            "game": game_key(game),
            "label": clean_label,
            "role": role,
            "rect": {"x": region[0], "y": region[1], "width": region[2], "height": region[3]},
            "filename": filename,
        }
    )
    index_path.write_text(json.dumps(templates, indent=2))
    for old_filename in replaced_filenames:
        if old_filename != filename:
            old_path = directory / old_filename
            try:
                old_path.unlink()
            except (FileNotFoundError, OSError):
                pass
    return directory / filename

def remove_game_template(game: str, label: str, role: str) -> bool:
    clean_label = label.strip()
    if role not in {"target", "pile"} or not clean_label:
        return False
    directory = application_support() / "RelayCockpit" / "box-jam-templates"
    index_path = directory / "index.json"
    entries = load_saved_template_entries()
    removed_entries = [
        entry
        for entry in entries
        if (
            str(entry.get("label", "")).casefold() == clean_label.casefold()
            and str(entry.get("role", "")) == role
            and entry_game_key(entry) == game_key(game)
        )
    ]
    if not removed_entries:
        return False
    remaining = [entry for entry in entries if entry not in removed_entries]
    try:
        if remaining:
            index_path.write_text(json.dumps(remaining, indent=2))
        else:
            index_path.unlink(missing_ok=True)
    except OSError:
        return False
    for entry in removed_entries:
        image_path = template_entry_path(entry)
        if image_path:
            try:
                image_path.unlink()
            except (FileNotFoundError, OSError):
                pass
    return True
def best_match(
    frame: Image.Image,
    template: Template,
    region: tuple[float, float, float, float] = (0, 0, 1, 1),
) -> Match | None:
    frame_width, frame_height = frame.size
    expected_width = max(12, int(round(frame_width * template.relative_width)))
    expected_height = max(12, int(round(frame_height * template.relative_height)))
    if expected_width >= frame_width or expected_height >= frame_height:
        return None
    reference = ImageOps.grayscale(template.image.resize((20, 20)))
    left = int(region[0] * frame_width)
    top = int(region[1] * frame_height)
    right = min(frame_width - expected_width, int((region[0] + region[2]) * frame_width))
    bottom = min(frame_height - expected_height, int((region[1] + region[3]) * frame_height))
    if right <= left or bottom <= top:
        return None
    step = max(3, min(expected_width, expected_height) // 7)
    best: Match | None = None
    for y in range(top, bottom + 1, step):
        for x in range(left, right + 1, step):
            sample = ImageOps.grayscale(frame.crop((x, y, x + expected_width, y + expected_height)).resize((20, 20)))
            distance = ImageStat.Stat(ImageChops.difference(reference, sample)).mean[0] / 255
            confidence = 1 - distance
            if best is None or confidence > best.confidence:
                best = Match(
                    label=template.label,
                    x=(x + expected_width / 2) / frame_width,
                    y=(y + expected_height / 2) / frame_height,
                    confidence=confidence,
                )
    return best


class BlockJamClassifier:
    def __init__(self, templates: Iterable[Template]) -> None:
        self.targets = [template for template in templates if template.role == "target"]
        self.pile = [template for template in templates if template.role == "pile"]

    @property
    def ready(self) -> bool:
        labels = {template.label.casefold() for template in self.targets}
        return bool(labels & {template.label.casefold() for template in self.pile})

    def next_confirmed_action(self, frame: Image.Image) -> Match | None:
        """Match the same label in the target strip and play area before clicking."""
        target_matches = {
            template.label.casefold(): best_match(frame, template, (0, 0, 1, 0.30))
            for template in self.targets
        }
        pile_matches = {
            template.label.casefold(): best_match(frame, template, (0.02, 0.24, 0.96, 0.72))
            for template in self.pile
        }
        confirmed = [
            pile_match
            for label, pile_match in pile_matches.items()
            if pile_match
            and pile_match.confidence >= MATCH_THRESHOLD
            and target_matches.get(label)
            and target_matches[label].confidence >= MATCH_THRESHOLD
        ]
        return max(confirmed, default=None, key=lambda match: match.confidence)


class BotPlayer:
    def __init__(self, game: str, allow_play: bool, icon_template: Template | None, classifier: BlockJamClassifier) -> None:
        self.game = game
        self.allow_play = allow_play
        self.icon_template = icon_template
        self.classifier = classifier
        self.running = True
        self.phase = "waiting"
        self.phase_started = time.monotonic()
        self.icon_readings = 0
        self.previous_icon: Match | None = None
        self.pending_fingerprint: bytes | None = None
        self.pending_action: Match | None = None
        self.confirmation_fingerprint: bytes | None = None
        self.confirmation_frames = 0
        self.pending_at = 0.0
        self.actions = 0

    def stop(self, message: str) -> None:
        if self.running:
            self.running = False
            emit("stopped", message, actions=self.actions)

    def guarded_click(
        self,
        target: MirroringWindow,
        expected: Match,
        matcher: Callable[[Image.Image], Match | None],
    ) -> bool:
        if STOP_REQUESTED.is_set():
            self.stop("Stopped by you before another tap could be sent.")
            return False
        current = active_unobscured_window(target)
        if not current:
            self.stop("iPhone Mirroring changed, disappeared, or was covered before the tap. Stopped safely.")
            return False
        fresh = screenshot(current)
        fresh_match = matcher(fresh)
        if (
            not fresh_match
            or fresh_match.label.casefold() != expected.label.casefold()
            or fresh_match.confidence < MATCH_THRESHOLD
            or abs(fresh_match.x - expected.x) > 0.035
            or abs(fresh_match.y - expected.y) > 0.035
        ):
            self.stop("The phone screen changed before the tap could be confirmed. Stopped safely.")
            return False
        if STOP_REQUESTED.is_set() or not active_unobscured_window(current):
            self.stop("iPhone Mirroring changed, was covered, or Stop was requested before the tap. Stopped safely.")
            return False
        rect = current.rect
        pyautogui.click(rect.x + fresh_match.x * rect.width, rect.y + fresh_match.y * rect.height)
        return True

    def ingest(self, target: MirroringWindow, frame: Image.Image) -> None:
        if not self.running or STOP_REQUESTED.is_set():
            return
        action = self.classifier.next_confirmed_action(frame) if self.classifier.ready else None
        if self.phase == "waiting":
            if action:
                self.phase = "verifying"
                self.phase_started = time.monotonic()
                emit("verifying", f"Verified the {self.game} board from matching saved templates.")
                return
            self.phase = "finding"
            self.phase_started = time.monotonic()
            emit("finding", f"Looking for {self.game} on the visible mirrored iPhone.")

        if self.phase == "finding":
            if action:
                self.phase = "verifying"
                self.phase_started = time.monotonic()
                emit("verifying", f"Verified the {self.game} board from matching saved templates.")
                return
            if not self.icon_template:
                self.stop(f"No saved {self.game} icon template is available. Use --calibrate-game-icon while its icon is visible.")
                return
            icon = best_match(frame, self.icon_template)
            if not icon or icon.confidence < MATCH_THRESHOLD:
                if time.monotonic() - self.phase_started > 20:
                    self.stop(f"Could not find {self.game} on the visible iPhone screen. No other app was opened.")
                return
            if self.previous_icon and abs(self.previous_icon.x - icon.x) < 0.035 and abs(self.previous_icon.y - icon.y) < 0.035:
                self.icon_readings += 1
            else:
                self.previous_icon = icon
                self.icon_readings = 1
            if self.icon_readings < STABLE_READINGS:
                emit("finding", f"Found {self.game}. Confirming its icon before opening it.", confidence=round(icon.confidence, 3))
                return
            if not self.guarded_click(target, icon, lambda current: best_match(current, self.icon_template)):
                return
            self.phase = "opening"
            self.phase_started = time.monotonic()
            emit("opening", f"Opened {self.game}. Waiting for a verified board.", confidence=round(icon.confidence, 3))
            return

        if self.phase == "opening":
            if action:
                self.phase = "verifying"
                self.phase_started = time.monotonic()
                emit("verifying", f"Verified the {self.game} board from matching saved templates.")
            elif time.monotonic() - self.phase_started > 12:
                self.stop(f"{self.game} did not show a verified board after opening. No further tap was sent.")
            return

        if self.phase == "verifying":
            if not action:
                self.stop("The board no longer matches the saved templates. Stopped without a move.")
                return
            if not self.allow_play:
                self.stop("The board is verified. Start again with --play to allow guarded template-matched moves.")
                return
            self.phase = "playing"
            emit("playing", f"Playing {self.game} with guarded template matches.")

        if self.phase == "playing":
            if self.pending_fingerprint:
                current_fingerprint = board_fingerprint(frame)
                action_changed = not action or not self.pending_action or (
                    action.label.casefold() != self.pending_action.label.casefold()
                    or abs(action.x - self.pending_action.x) > 0.025
                    or abs(action.y - self.pending_action.y) > 0.025
                )
                if board_changed(self.pending_fingerprint, current_fingerprint) and action_changed:
                    if self.confirmation_fingerprint and fingerprints_stable(self.confirmation_fingerprint, current_fingerprint):
                        self.confirmation_frames += 1
                    else:
                        self.confirmation_fingerprint = current_fingerprint
                        self.confirmation_frames = 1
                    if self.confirmation_frames >= 2:
                        self.pending_fingerprint = None
                        self.pending_action = None
                        self.confirmation_fingerprint = None
                        self.confirmation_frames = 0
                        emit("playing", "Confirmed a stable board change after the previous move.", actions=self.actions)
                elif time.monotonic() - self.pending_at > 5:
                    self.stop("The last move did not produce a confirmed board change. Stopped safely.")
                return
            if not action:
                self.stop("Could not verify a matching target and board item. Stopped safely.")
                return
            if self.actions >= MAX_ACTIONS:
                self.stop("Reached the guarded 50-action limit. Stopped safely.")
                return
            self.pending_fingerprint = board_fingerprint(frame)
            self.pending_action = action
            self.confirmation_fingerprint = None
            self.confirmation_frames = 0
            self.pending_at = time.monotonic()
            if not self.guarded_click(target, action, self.classifier.next_confirmed_action):
                return
            self.actions += 1
            emit("playing", f"Tapped the confirmed {action.label} item. Checking for a board change.", actions=self.actions, confidence=round(action.confidence, 3))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Bot Player against the visible iPhone Mirroring window without Xcode.")
    parser.add_argument("--game", default="Block Jam 3D", help="Selected game name shown to the user.")
    parser.add_argument("--play", action="store_true", help="Allow guarded, template-matched game moves after verification.")
    parser.add_argument("--calibrate-game-icon", action="store_true", help="Capture the current game's icon from an on-screen selector, then exit.")
    parser.add_argument("--icon-region", type=normalized_region, help="Save the game icon using x,y,width,height normalized to the mirrored window, then exit.")
    parser.add_argument("--overwrite-game-icon", action="store_true", help="Allow --icon-region to replace an existing game icon template.")
    parser.add_argument("--cli", action="store_true", help="Use JSON-lines output instead of the compact app window.")
    args, unknown = parser.parse_known_args()
    finder_arguments = [argument for argument in unknown if not argument.startswith("-psn_")]
    if finder_arguments:
        parser.error(f"unrecognized arguments: {' '.join(finder_arguments)}")
    return args


def run_controller(args: argparse.Namespace) -> int:
    STOP_REQUESTED.clear()
    if args.play:
        START_REQUESTED.set()
    target = locate_iphone_mirroring_window()
    if target is None:
        emit("waiting", "Waiting for the active iPhone Mirroring window.")

    player: BotPlayer | None = None

    def stop_signal(_signal: int, _frame: Any) -> None:
        if player:
            player.stop("Stopped by you. No further tap will be sent.")
        else:
            STOP_REQUESTED.set()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, stop_signal)
        signal.signal(signal.SIGTERM, stop_signal)
    emit("waiting", "Waiting for the visible iPhone Mirroring window.")
    had_window = target is not None
    ready_message_sent = False
    icon_setup_requested = False
    last_waiting_message = ""
    while not STOP_REQUESTED.is_set() and (player is None or player.running):
        target = locate_iphone_mirroring_window()
        if not target:
            if had_window:
                if player:
                    player.stop("iPhone Mirroring is no longer visible. Stopped before another tap.")
                else:
                    emit("waiting", "iPhone Mirroring is no longer visible. Open it before starting Bot Player.")
                break
            message = mirroring_capture_block_reason(None) or "Waiting for the active iPhone Mirroring window."
            if message != last_waiting_message:
                emit("waiting", message)
                last_waiting_message = message
            time.sleep(POLL_SECONDS)
            continue
        had_window = True
        if not START_REQUESTED.is_set():
            block_reason = mirroring_capture_block_reason(target)
            if block_reason:
                if block_reason != last_waiting_message:
                    emit("waiting", block_reason)
                    last_waiting_message = block_reason
                time.sleep(POLL_SECONDS)
                continue
            if not load_game_icon_template(args.game) and not icon_setup_requested:
                icon_setup_requested = True
                emit(
                    "ready",
                    f"{args.game} has no saved app icon. This is optional when you manually open the game, "
                    "but add it from Advanced tools if you want Bot Player to open it from the iPhone home screen.",
                )
            if not ready_message_sent:
                emit(
                    "ready",
                    "iPhone Mirroring is ready. Start a recording or import gameplay footage to create reviewed training examples.",
                )
                ready_message_sent = True
            time.sleep(POLL_SECONDS)
            continue
        if player is None:
            with CALIBRATION_LOCK:
                if not START_REQUESTED.is_set():
                    continue
                icon_template = load_game_icon_template(args.game)
                classifier = BlockJamClassifier(load_existing_game_templates(args.game))
            player = BotPlayer(
                game=args.game,
                allow_play=True,
                icon_template=icon_template,
                classifier=classifier,
            )
            screen_capture_reason = None
            if screen_capture_permission() is False:
                screen_capture_reason = mirroring_capture_block_reason(target)
            if screen_capture_reason:
                player.stop(screen_capture_reason)
                break
            accessibility_reason = accessibility_block_reason()
            if accessibility_reason:
                player.stop(accessibility_reason)
                break
            missing: list[str] = []
            if not classifier.ready:
                missing.append("reviewed training examples")
            if missing:
                player.stop(
                    "Cannot start safely because "
                    + " and ".join(missing)
                    + " is missing. Choose Import Training Footage to build examples from a recording or local clip. "
                    "Advanced manual tools are only for repairing a training set."
                )
                break
            emit("starting", "Loaded saved game templates. Checking the selected game before any tap.")
        try:
            active_target = active_unobscured_window(target)
            if not active_target:
                player.stop(
                    mirroring_capture_block_reason(target)
                    or "iPhone Mirroring is covered or no longer owns its visible region. Stopped before another tap."
                )
                break
            target = active_target
            player.allow_play = True
            player.ingest(target, screenshot(target))
        except pyautogui.FailSafeException:
            player.stop("PyAutoGUI fail-safe triggered. Stopped before another tap.")
        except Exception as error:
            if screen_capture_permission() is False:
                open_mac_permissions()
                player.stop(f"macOS denied Screen Recording while reading the mirrored window: {error}")
            else:
                player.stop(f"Could not read the mirrored window safely: {error}")
        time.sleep(POLL_SECONDS)
    if STOP_REQUESTED.is_set() and player and player.running:
        player.stop("Stopped by you. No further tap will be sent.")
    return 0


def capture_icon(args: argparse.Namespace, replacement_confirmed: bool = False) -> int:
    if connection_check_active():
        emit("ready", "Wait for the connection check to finish before changing the game icon.")
        return 1
    if load_game_icon_template(args.game) and not replacement_confirmed:
        if args.icon_region:
            if not args.overwrite_game_icon:
                emit(
                    "stopped",
                    f"A saved {args.game} icon template already exists. Pass --overwrite-game-icon to replace it.",
                )
                return 1
        else:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            accepted = messagebox.askyesno(
                "Replace game icon?",
                f"Replace the saved {args.game} icon capture? This only changes local setup and is used on the next Start.",
                parent=root,
                default=messagebox.NO,
            )
            root.destroy()
            if not accepted:
                emit("ready", "Game icon replacement was cancelled. Nothing was saved.")
                return 0
    target = locate_iphone_mirroring_window()
    target = active_unobscured_window(target) if target else None
    if not target:
        emit(
            "stopped",
            mirroring_capture_block_reason(locate_iphone_mirroring_window())
            or "Keep iPhone Mirroring visible and unobscured before capturing the game icon template.",
        )
        return 1
    try:
        frame = screenshot(target)
    except Exception as error:
        open_mac_permissions()
        emit("stopped", f"Bot Player could not capture the mirrored window: {error}")
        return 1
    region = args.icon_region or select_icon_region(frame, args.game)
    if not region:
        emit("stopped", "No game icon region was selected. Nothing was saved.")
        return 1
    path = save_game_icon_template(frame, args.game, region)
    emit("ready", f"Saved the {args.game} icon template.", template=str(path))
    return 0


def capture_board_template(role: str, game: str, label: str | None = None, parent: Any = None) -> str | None:
    if connection_check_active():
        emit("ready", "Wait for the connection check to finish before capturing a board template.")
        return None
    import tkinter as tk
    from tkinter import simpledialog

    dialog_root = None
    if label is None:
        dialog_root = tk.Tk()
        dialog_root.withdraw()
        label = simpledialog.askstring(
            "Bot Player",
            f"Name this {role} template. Use the same name for its matching target and board item.",
            parent=parent or dialog_root,
        )
        dialog_root.destroy()
    if not label:
        emit("ready", "No template name was entered. Nothing was saved.")
        return None
    target = locate_iphone_mirroring_window()
    target = active_unobscured_window(target) if target else None
    if not target:
        emit(
            "waiting",
            mirroring_capture_block_reason(locate_iphone_mirroring_window())
            or "Keep iPhone Mirroring visible and unobscured before capturing a game template.",
        )
        return None
    try:
        path = save_game_template(screenshot(target), game, label, role)
    except Exception as error:
        open_mac_permissions()
        emit("stopped", f"Bot Player could not capture the {role} template: {error}")
        return None
    if path:
        emit("ready", f"Saved the {role} template for {label}.", template=str(path))
        return label
    else:
        emit("ready", "No template area was selected. Nothing was saved.")
        return None


def run_status_window(args: argparse.Namespace) -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    root = tk.Tk()
    root.title("Bot Player")
    root.geometry("700x620")
    root.minsize(620, 480)

    state_label = ttk.Label(root, text="WAITING", font=("Helvetica", 16, "bold"))
    message_label = ttk.Label(root, text="Waiting for the active iPhone Mirroring window.", wraplength=370)
    game_label = ttk.Label(root, text=f"Game: {args.game}")
    state_label.pack(anchor=tk.W, padx=22, pady=(22, 3))
    message_label.pack(anchor=tk.W, padx=22, pady=(0, 5))
    game_label.pack(anchor=tk.W, padx=22, pady=(0, 16))
    buttons = ttk.Frame(root)
    buttons.pack(fill=tk.X, padx=22)
    worker: threading.Thread | None = None
    recording_thread: threading.Thread | None = None
    connection_thread: threading.Thread | None = None
    restore_backup_button: Any = None
    record_button: Any = None
    training_button: Any = None
    connection_button: Any = None
    icon_button: Any = None
    status_queue: Queue[dict[str, Any]] = Queue()

    def update_selected_game_ui() -> None:
        game_label.configure(text=f"Game: {args.game}")
        setup.configure(text=f"Advanced: manual tools for {args.game}")
        library.configure(text=f"Saved training for {args.game}")
        icon_button.configure(
            text="Replace game icon (optional)"
            if game_key(args.game) == game_key(DEFAULT_GAME_NAME)
            else "Add game icon for auto-launch (optional)"
        )
        refresh_library()

    def begin_training_from_ui() -> None:
        if START_REQUESTED.is_set() or (recording_thread and recording_thread.is_alive()):
            messagebox.showinfo(
                "Stop first",
                "Stop Bot Player and save any recording before changing the game being trained.",
                parent=root,
            )
            return
        if connection_thread and connection_thread.is_alive():
            messagebox.showinfo(
                "Connection check is active",
                "Wait for the connection check to finish before changing the game being trained.",
                parent=root,
            )
            return
        selected_game = simpledialog.askstring(
            "Begin training",
            "Which game do you want to train?",
            initialvalue=args.game,
            parent=root,
        )
        if selected_game is None:
            return
        selected_game = selected_game.strip()
        if not selected_game:
            messagebox.showwarning("Game name needed", "Enter the name of the game you want to train.", parent=root)
            return
        args.game = selected_game
        update_selected_game_ui()
        icon_message = (
            "Block Jam 3D already has its bundled app icon."
            if game_key(args.game) == game_key(DEFAULT_GAME_NAME)
            else (
                "An app icon is optional if you manually open the game before starting Bot Player. "
                "Use Advanced tools to add an icon only if you want Bot Player to open the game from the iPhone home screen."
            )
        )
        messagebox.showinfo(
            f"Training {args.game}",
            (
                f"Next: manually open {args.game} on the mirrored iPhone, then choose Start Recording Session. "
                "Play normally, stop and save the session, then choose Import Training Footage to review the proposed examples.\n\n"
                f"{icon_message}\n\n"
                "Training is observation-only and will never tap or drag the phone."
            ),
            parent=root,
        )
        emit("ready", f"Training is set to {args.game}. Record gameplay or import a local clip to build reviewed examples.")

    def start_controller() -> None:
        nonlocal worker
        if recording_thread and recording_thread.is_alive():
            emit("ready", "Stop and save the recording before starting Bot Player.")
            return
        if connection_thread and connection_thread.is_alive():
            emit("ready", "Wait for the connection check to finish before starting Bot Player.")
            return
        START_REQUESTED.set()
        start_button.configure(state=tk.DISABLED)
        record_button.configure(state=tk.DISABLED)
        training_button.configure(state=tk.DISABLED)
        if restore_backup_button is not None:
            restore_backup_button.configure(state=tk.DISABLED)
        if worker is None or not worker.is_alive():
            STOP_REQUESTED.clear()
            worker = threading.Thread(target=run_controller, args=(args,), daemon=True)
            worker.start()

    def start_connection_check_from_ui() -> None:
        nonlocal connection_thread
        if START_REQUESTED.is_set():
            messagebox.showinfo(
                "Bot Player is running",
                "Stop Bot Player before running the connection check. The check uses simple test gestures and no game templates.",
                parent=root,
            )
            return
        if recording_thread and recording_thread.is_alive():
            messagebox.showinfo(
                "Recording is active",
                "Stop and save the recording before running the connection check.",
                parent=root,
            )
            return
        if connection_thread and connection_thread.is_alive():
            return
        if accessibility_permission() is not True or screen_capture_permission() is not True:
            show_permission_setup(root)
            emit(
                "waiting",
                "Grant Screen Recording and Accessibility to Bot Player.app, then run the connection check again.",
            )
            return
        accepted = messagebox.askyesno(
            "Test iPhone connection",
            (
                "Place any app in the upper-left app slot on the iPhone Home Screen and leave iPhone Mirroring visible.\n\n"
                "Bot Player will swipe to Home, tap that app slot, wait for a visible app change, and swipe Home "
                "again. This returns to the Home Screen rather than force-quitting the app. No game templates or "
                "automated play will be used.\n\nContinue?"
            ),
            parent=root,
            default=messagebox.NO,
        )
        if not accepted:
            emit("ready", "Connection check cancelled. No test input was sent.")
            return
        CONNECTION_CHECK_STOP_REQUESTED.clear()
        for button in (start_button, record_button, training_button, restore_backup_button, connection_button):
            if button is not None:
                button.configure(state=tk.DISABLED)
        set_connection_sensitive_controls_state(tk.DISABLED)
        connection_button.configure(text="Testing iPhone connection…")
        connection_thread = threading.Thread(target=run_connection_check, args=(args,), daemon=True)
        connection_thread.start()
        root.after(100, wait_for_connection_check)

    def start_recording_from_ui() -> None:
        nonlocal recording_thread
        if START_REQUESTED.is_set():
            messagebox.showinfo(
                "Bot Player is running",
                "Stop Bot Player before recording. Recording is observation-only and never runs alongside automated input.",
                parent=root,
            )
            return
        if connection_thread and connection_thread.is_alive():
            emit("ready", "Wait for the connection check to finish before recording.")
            return
        if recording_thread and recording_thread.is_alive():
            return
        block_reason = mirroring_capture_block_reason(locate_iphone_mirroring_window())
        if block_reason:
            emit("waiting", f"Recording cannot start yet: {block_reason}")
            return
        RECORDING_STOP_REQUESTED.clear()
        start_button.configure(state=tk.DISABLED)
        training_button.configure(state=tk.DISABLED)
        record_button.configure(text="Stop & Save Recording", command=stop_recording_from_ui)
        recording_thread = threading.Thread(target=record_live_session, args=(args,), daemon=True)
        recording_thread.start()

    def check_mac_setup_from_ui() -> None:
        block_reason = mirroring_capture_block_reason(locate_iphone_mirroring_window())
        accessibility_reason = accessibility_block_reason()
        show_permission_setup(root)
        if block_reason:
            emit("waiting", block_reason)
            return
        if accessibility_reason:
            emit("waiting", accessibility_reason)
            return
        emit(
            "ready",
            "Screen Recording and Accessibility are active, and iPhone Mirroring is ready. You can start a recording or import local footage.",
        )

    def stop_recording_from_ui() -> None:
        RECORDING_STOP_REQUESTED.set()
        record_button.configure(text="Saving recording…", state=tk.DISABLED)
        wait_for_recording_stop()

    def import_training_from_ui() -> None:
        if connection_thread and connection_thread.is_alive():
            messagebox.showinfo(
                "Connection check is active",
                "Wait for the connection check to finish before importing training footage.",
                parent=root,
            )
            return
        if not training_import_allowed(bool(recording_thread and recording_thread.is_alive())):
            messagebox.showinfo(
                "Stop before importing",
                "Stop Bot Player and save any recording before reviewing imported training. "
                "The active controller always keeps its original templates.",
                parent=root,
            )
            return
        source_choice = messagebox.askyesnocancel(
            "Choose training footage",
            (
                "Choose Yes to select a saved Bot Player recording session.\n\n"
                "Choose No to select a local video clip you are allowed to use, including a clip "
                "you prepared from YouTube footage. The clip remains on this Mac and is never uploaded."
            ),
            parent=root,
        )
        if source_choice is None:
            return
        if source_choice:
            source = filedialog.askdirectory(
                parent=root,
                title="Select a saved Bot Player recording session",
                initialdir=str(recording_directory(args.game)),
                mustexist=True,
            )
        else:
            source = filedialog.askopenfilename(
                parent=root,
                title="Select a local gameplay clip",
                filetypes=[
                    ("Supported gameplay clips", " ".join(f"*{extension}" for extension in sorted(VIDEO_EXTENSIONS))),
                    ("All files", "*"),
                ],
            )
        if not source:
            return
        training_button.configure(state=tk.DISABLED, text="Analyzing footage…")
        root.update_idletasks()
        try:
            review = analyze_training_source(source, args.game)
        except TrainingSourceError as error:
            message = str(error)
            emit("ready", f"Training import was not started: {message}")
            messagebox.showwarning("Footage cannot be used", message, parent=root)
            return
        finally:
            training_button.configure(state=tk.NORMAL, text="Import Training Footage")
        selected = review_training_candidates(root, review)
        if selected:
            refresh_library()

    begin_training_button = ttk.Button(buttons, text="Begin Training…", command=begin_training_from_ui)
    begin_training_button.pack(side=tk.LEFT)
    start_button = ttk.Button(buttons, text="Start Bot Player", command=start_controller)
    start_button.pack(side=tk.LEFT)
    connection_button = ttk.Button(buttons, text="Test iPhone connection", command=start_connection_check_from_ui)
    connection_button.pack(side=tk.LEFT, padx=(10, 0))
    record_button = ttk.Button(buttons, text="Start Recording Session", command=start_recording_from_ui)
    record_button.pack(side=tk.LEFT, padx=(10, 0))
    training_button = ttk.Button(buttons, text="Import Training Footage", command=import_training_from_ui)
    training_button.pack(side=tk.LEFT, padx=(10, 0))
    stop_button = ttk.Button(buttons, text="Stop Bot Player")
    stop_button.pack(side=tk.RIGHT)
    setup = ttk.LabelFrame(root, text=f"Advanced: manual tools for {args.game}")
    setup.pack(fill=tk.X, padx=22, pady=(14, 0))
    icon_button_text = "Replace game icon (optional)" if game_key(args.game) == game_key(DEFAULT_GAME_NAME) else "Add game icon for auto-launch (optional)"
    icon_button = ttk.Button(setup, text=icon_button_text, command=lambda: capture_icon_from_setup())
    icon_button.grid(row=0, column=0, padx=8, pady=8, sticky=tk.W)
    ttk.Button(setup, text="Capture target", command=lambda: capture_board_from_setup("target")).grid(row=0, column=1, padx=8, pady=8, sticky=tk.W)
    ttk.Button(setup, text="Capture board item", command=lambda: capture_board_from_setup("pile")).grid(row=0, column=2, padx=8, pady=8, sticky=tk.W)
    recording_help = ttk.Label(
        root,
        text=(
            "Recommended path: Begin Training, choose the game, manually open it on iPhone Mirroring, record normal "
            "gameplay, then Import Training Footage. Bot Player proposes examples for review and never replaces "
            "training until you confirm."
        ),
        wraplength=640,
    )
    recording_help.pack(anchor=tk.W, padx=22, pady=(10, 0))
    permission_button = ttk.Button(
        buttons,
        text="Mac setup & permissions",
        command=lambda: show_permission_setup(root),
    )
    permission_button.pack(side=tk.LEFT, padx=(12, 0))
    ttk.Button(buttons, text="Check setup", command=check_mac_setup_from_ui).pack(side=tk.LEFT, padx=(8, 0))
    footer = ttk.Label(
        root,
        text="Templates are saved only on this Mac. Library changes are loaded the next time you press Start Bot Player; the current run keeps its original templates.",
        wraplength=640,
    )
    footer.pack(anchor=tk.W, padx=22, pady=(14, 8))

    library = ttk.LabelFrame(root, text=f"Saved templates for {args.game}")
    library.pack(fill=tk.BOTH, expand=True, padx=22, pady=(0, 14))
    library.columnconfigure(0, weight=1)
    library.rowconfigure(1, weight=1)
    library_header = ttk.Frame(library)
    library_header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(8, 3))
    ttk.Label(library_header, text="Review saved captures before starting.").pack(side=tk.LEFT)
    library_backup_actions = ttk.Frame(library_header)
    library_backup_actions.pack(side=tk.RIGHT)
    library_body = ttk.Frame(library)
    library_body.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
    library_body.columnconfigure(0, weight=1)
    library_scroll = tk.Scrollbar(library, orient=tk.VERTICAL)
    library_scroll.grid(row=1, column=1, sticky=tk.NS, pady=(0, 10))
    library_canvas = tk.Canvas(library_body, highlightthickness=0, yscrollcommand=library_scroll.set)
    library_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    library_scroll.configure(command=library_canvas.yview)
    library_rows = ttk.Frame(library_canvas)
    library_window = library_canvas.create_window((0, 0), window=library_rows, anchor=tk.NW)

    def resize_library(_event: Any = None) -> None:
        library_canvas.configure(scrollregion=library_canvas.bbox("all"))
        library_canvas.itemconfigure(library_window, width=library_canvas.winfo_width())

    library_rows.bind("<Configure>", resize_library)
    library_canvas.bind("<Configure>", resize_library)

    def confirm_change(title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=root, default=messagebox.NO))

    def export_calibration() -> None:
        destination = filedialog.asksaveasfilename(
            parent=root,
            title=f"Back up {args.game} calibration",
            defaultextension=".botplayer.json",
            filetypes=[("Bot Player calibration", "*.botplayer.json"), ("JSON files", "*.json"), ("All files", "*")],
            initialfile=f"{game_key(args.game)}.botplayer.json",
        )
        if not destination:
            return
        destination_path = Path(destination).expanduser()
        if destination_path.exists() and not confirm_change(
            "Replace backup file?",
            f"A file already exists at {destination_path}. Replace it with the {args.game} calibration backup?",
        ):
            return
        export_game_calibration(args.game, destination_path)

    def restore_calibration() -> None:
        source = filedialog.askopenfilename(
            parent=root,
            title=f"Restore {args.game} calibration",
            filetypes=[("Bot Player calibration", "*.botplayer.json"), ("JSON files", "*.json"), ("All files", "*")],
        )
        if not source:
            return
        if not confirm_change(
            "Replace saved calibration?",
            f"Restore this backup into {args.game}? Its current icon and target/board-item templates will be replaced. "
            "A backup is checked completely first, and the restored setup will not be used until you press Start Bot Player.",
        ):
            return
        restore_game_calibration(args.game, source)
        refresh_library()

    ttk.Button(library_backup_actions, text="Export backup", command=export_calibration).pack(side=tk.LEFT, padx=(0, 6))
    restore_backup_button = ttk.Button(library_backup_actions, text="Restore backup", command=restore_calibration)
    restore_backup_button.pack(side=tk.LEFT)

    def has_saved_template(label: str, role: str) -> bool:
        return any(
            str(entry.get("label", "")).casefold() == label.casefold()
            and str(entry.get("role", "")) == role
            and template_entry_path(entry) is not None
            and template_entry_path(entry).exists()
            for entry in load_saved_template_entries(args.game)
        )

    def capture_icon_from_setup() -> None:
        if connection_thread and connection_thread.is_alive():
            emit("ready", "Wait for the connection check to finish before changing the game icon.")
            return
        if load_game_icon_template(args.game) and not confirm_change(
            "Replace game icon?",
            f"Replace the saved {args.game} icon capture? This only changes local setup and is used on the next Start.",
        ):
            return
        capture_icon(args, replacement_confirmed=True)
        refresh_library()

    def capture_board_from_setup(role: str) -> None:
        if connection_thread and connection_thread.is_alive():
            emit("ready", "Wait for the connection check to finish before capturing a board template.")
            return
        role_name = "board item" if role == "pile" else "target"
        label = simpledialog.askstring(
            "Bot Player",
            f"Name this {role_name} template. Use the same name for its matching target and board item.",
            parent=root,
        )
        if not label or not label.strip():
            emit("ready", "No template name was entered. Nothing was saved.")
            return
        label = label.strip()
        if has_saved_template(label, role) and not confirm_change(
            f"Replace {role_name}?",
            f"Replace the saved {role_name} capture named “{label}”? This only changes local setup and is used on the next Start.",
        ):
            return
        capture_board_template(role, args.game, label, root)
        refresh_library()

    def refresh_library() -> None:
        for child in library_rows.winfo_children():
            child.destroy()

        icon_row = ttk.Frame(library_rows)
        icon_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(icon_row, text="Game icon", width=22).pack(side=tk.LEFT, anchor=tk.W)
        icon_saved = load_game_icon_template(args.game) is not None
        icon_source = game_icon_source(args.game) if icon_saved else None
        icon_status = "Bundled default" if icon_source == "bundled-default" else "Saved" if icon_saved else "Not saved"
        ttk.Label(icon_row, text=icon_status).pack(side=tk.LEFT, anchor=tk.W)
        icon_actions = ttk.Frame(icon_row)
        icon_actions.pack(side=tk.RIGHT)

        def replace_icon() -> None:
            if not confirm_change(
                "Replace game icon?",
                f"Replace the saved {args.game} icon capture? This only changes local setup and is used on the next Start.",
            ):
                return
            capture_icon(args, replacement_confirmed=True)
            refresh_library()

        def remove_icon() -> None:
            if not confirm_change(
                "Remove game icon?",
                f"Remove the saved {args.game} icon capture? Bot Player will refuse to start until you capture it again.",
            ):
                return
            if remove_game_icon_template(args.game):
                emit("ready", f"Removed the {args.game} icon template. Save a replacement before starting.")
            refresh_library()

        ttk.Button(
            icon_actions,
            text="Replace" if icon_saved else "Capture",
            command=replace_icon if icon_saved else lambda: (capture_icon(args), refresh_library()),
        ).pack(side=tk.LEFT, padx=(0, 6))
        if icon_saved:
            ttk.Button(icon_actions, text="Remove", command=remove_icon).pack(side=tk.LEFT)

        ttk.Separator(library_rows, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))
        headings = ttk.Frame(library_rows)
        headings.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(headings, text="Target / board item pair", width=25).pack(side=tk.LEFT, anchor=tk.W)
        ttk.Label(headings, text="Target", width=14).pack(side=tk.LEFT, anchor=tk.W)
        ttk.Label(headings, text="Board item", width=14).pack(side=tk.LEFT, anchor=tk.W)
        ttk.Label(headings, text="Actions").pack(side=tk.LEFT, anchor=tk.W)

        grouped: dict[str, dict[str, str]] = {}
        for entry in load_saved_template_entries(args.game):
            label = str(entry.get("label", "")).strip()
            role = str(entry.get("role", ""))
            image_path = template_entry_path(entry)
            if not label or role not in {"target", "pile"} or image_path is None or not image_path.exists():
                continue
            key = label.casefold()
            grouped.setdefault(key, {"label": label})[role] = label

        if not grouped:
            ttk.Label(
                library_rows,
                text="No target or board-item captures saved yet. Capture both with the same name to create a playable pair.",
                wraplength=620,
            ).pack(anchor=tk.W, pady=(5, 0))
        else:
            for key in sorted(grouped, key=lambda value: grouped[value]["label"].casefold()):
                pair = grouped[key]
                label = pair["label"]
                row = ttk.Frame(library_rows)
                row.pack(fill=tk.X, pady=3)
                ttk.Label(row, text=label, width=25).pack(side=tk.LEFT, anchor=tk.W)
                target_saved = "target" in pair
                pile_saved = "pile" in pair
                ttk.Label(row, text="Saved" if target_saved else "Missing", width=14).pack(side=tk.LEFT, anchor=tk.W)
                ttk.Label(row, text="Saved" if pile_saved else "Missing", width=14).pack(side=tk.LEFT, anchor=tk.W)
                actions = ttk.Frame(row)
                actions.pack(side=tk.LEFT, anchor=tk.W)

                def replace(role: str = "target", template_label: str = label) -> None:
                    role_name = "board item" if role == "pile" else "target"
                    if not confirm_change(
                        f"Replace {role_name}?",
                        f"Replace the saved {role_name} capture named “{template_label}”? This only changes local setup and is used on the next Start.",
                    ):
                        return
                    capture_board_template(role, args.game, template_label, root)
                    refresh_library()

                def remove(role: str = "target", template_label: str = label) -> None:
                    role_name = "board item" if role == "pile" else "target"
                    if not confirm_change(
                        f"Remove {role_name}?",
                        f"Remove the saved {role_name} capture named “{template_label}”? A complete target/board-item pair is required before Bot Player can start.",
                    ):
                        return
                    if remove_game_template(args.game, template_label, role):
                        emit("ready", f"Removed the {role_name} template for {template_label}.")
                    refresh_library()

                ttk.Button(
                    actions,
                    text="Replace target" if target_saved else "Capture target",
                    command=(lambda action=replace: action("target"))
                    if target_saved
                    else (lambda template_label=label: (capture_board_template("target", args.game, template_label, root), refresh_library())),
                ).pack(side=tk.LEFT, padx=(0, 4))
                if target_saved:
                    ttk.Button(actions, text="Remove target", command=lambda action=remove: action("target")).pack(side=tk.LEFT, padx=(0, 8))
                ttk.Button(
                    actions,
                    text="Replace board item" if pile_saved else "Capture board item",
                    command=(lambda action=replace: action("pile"))
                    if pile_saved
                    else (lambda template_label=label: (capture_board_template("pile", args.game, template_label, root), refresh_library())),
                ).pack(side=tk.LEFT, padx=(0, 4))
                if pile_saved:
                    ttk.Button(actions, text="Remove board item", command=lambda action=remove: action("pile")).pack(side=tk.LEFT)

        library_canvas.after_idle(resize_library)

    refresh_library()

    def set_connection_sensitive_controls_state(state: str) -> None:
        def update_buttons(container: Any) -> None:
            for child in container.winfo_children():
                if child.winfo_class() in {"Button", "TButton"}:
                    child.configure(state=state)
                update_buttons(child)

        update_buttons(setup)
        update_buttons(library)

    def enable_start_after_stop() -> None:
        if (
            (worker and worker.is_alive())
            or (recording_thread and recording_thread.is_alive())
            or (connection_thread and connection_thread.is_alive())
        ):
            root.after(50, enable_start_after_stop)
            return
        START_REQUESTED.clear()
        if not recording_thread or not recording_thread.is_alive():
            start_button.configure(state=tk.NORMAL)
            record_button.configure(text="Start Recording Session", state=tk.NORMAL, command=start_recording_from_ui)
            training_button.configure(state=tk.NORMAL, text="Import Training Footage")
        connection_button.configure(text="Test iPhone connection", state=tk.NORMAL)
        if restore_backup_button is not None:
            restore_backup_button.configure(state=tk.NORMAL)
        stop_button.configure(text="Stop Bot Player", command=STOP_REQUESTED.set)

    def wait_for_connection_check() -> None:
        if connection_thread and connection_thread.is_alive():
            root.after(80, wait_for_connection_check)
            return
        set_connection_sensitive_controls_state(tk.NORMAL)
        connection_button.configure(text="Test iPhone connection", state=tk.NORMAL)
        if not START_REQUESTED.is_set() and not (recording_thread and recording_thread.is_alive()):
            start_button.configure(state=tk.NORMAL)
            record_button.configure(text="Start Recording Session", state=tk.NORMAL, command=start_recording_from_ui)
            training_button.configure(state=tk.NORMAL, text="Import Training Footage")
            if restore_backup_button is not None:
                restore_backup_button.configure(state=tk.NORMAL)

    def wait_for_recording_stop() -> None:
        if recording_thread and recording_thread.is_alive():
            root.after(80, wait_for_recording_stop)
            return
        record_button.configure(text="Start Recording Session", state=tk.NORMAL, command=start_recording_from_ui)
        training_button.configure(state=tk.NORMAL, text="Import Training Footage")
        if not worker or not worker.is_alive() or not START_REQUESTED.is_set():
            start_button.configure(state=tk.NORMAL)

    def close_when_stopped() -> None:
        if (
            (worker and worker.is_alive())
            or (recording_thread and recording_thread.is_alive())
            or (connection_thread and connection_thread.is_alive())
        ):
            root.after(80, close_when_stopped)
            return
        root.destroy()

    def request_stop() -> None:
        STOP_REQUESTED.set()
        RECORDING_STOP_REQUESTED.set()
        CONNECTION_CHECK_STOP_REQUESTED.set()
        start_button.configure(state=tk.DISABLED)
        connection_button.configure(state=tk.DISABLED)
        record_button.configure(state=tk.DISABLED)
        training_button.configure(state=tk.DISABLED)
        stop_button.configure(text="Stopping…", state=tk.DISABLED)
        close_when_stopped()

    stop_button.configure(command=request_stop)
    root.protocol("WM_DELETE_WINDOW", request_stop)

    def update_status(payload: dict[str, Any]) -> None:
        state = str(payload.get("state", "waiting")).upper()
        state_label.configure(text=state)
        message_label.configure(text=str(payload.get("message", "")))
        if state == "RECORDING-SAVED":
            root.after(50, wait_for_recording_stop)
        elif state == "STOPPED":
            root.after(50, enable_start_after_stop)

    def drain_status_queue() -> None:
        try:
            while True:
                update_status(status_queue.get_nowait())
        except Empty:
            pass
        if root.winfo_exists():
            root.after(80, drain_status_queue)

    global STATUS_SINK
    STATUS_SINK = status_queue.put

    RECORDING_STOP_REQUESTED.clear()
    CONNECTION_CHECK_STOP_REQUESTED.clear()
    worker = threading.Thread(target=run_controller, args=(args,), daemon=True)
    worker.start()
    root.after(80, drain_status_queue)
    root.after(220, lambda: show_permission_setup(root))
    root.mainloop()
    STATUS_SINK = None
    return 0


def main() -> int:
    args = parse_args()
    if not present_disclaimer():
        return 0
    launch_iphone_mirroring()
    if args.calibrate_game_icon or args.icon_region:
        offer_mac_permissions()
        return capture_icon(args)
    if args.cli:
        offer_mac_permissions()
        return run_controller(args)
    return run_status_window(args)


if __name__ == "__main__":
    raise SystemExit(main())
