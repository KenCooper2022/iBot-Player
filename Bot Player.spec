# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/kencooper/Desktop/iBot-Player/bot_player.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/kencooper/Desktop/iBot-Player/block-jam-3d-icon.png', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Bot Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Bot Player',
)
app = BUNDLE(
    coll,
    name='Bot Player.app',
    icon=None,
    bundle_identifier='com.botplayer.iphone-mirroring',
)
