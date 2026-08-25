# Bot Player build output

This folder is intentionally included in the macOS beta ZIP as the local
staging location for the real app bundle.

On macOS, run **Build Bot Player.command** and type `REBUILD`. PyInstaller
creates `dist/Bot Player.app` here, then the launcher installs that same bundle
at `~/Applications/Bot Player.app`. A prebuilt app is not included because
this package is assembled outside macOS and the bundle must be built on the
Mac where it will run. The Mac performing the build needs a Developer ID
Application or Apple Development signing certificate; unsigned app bundles are
not produced.