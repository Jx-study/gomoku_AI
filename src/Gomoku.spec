# -*- mode: python ; coding: utf-8 -*-
import platform

# 副檔名須與 utils/build.py 的 EXT_BY_SYSTEM 一致
LIB = {"Windows": "ai.dll", "Linux": "ai.so", "Darwin": "ai.dylib"}[platform.system()]
NAME = {"Windows": "Gomoku-windows", "Linux": "Gomoku-linux", "Darwin": "Gomoku-macos"}[platform.system()]

a = Analysis(
    ['Gomoku.py'],
    pathex=[],
    binaries=[(LIB, '.')],
    datas=[('200w.gif', '.')],
    hiddenimports=['graphics'],
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
    a.binaries,
    a.datas,
    [],
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,   # macOS 的 ad-hoc 簽章在 release.yml 裡做
    entitlements_file=None,
)
