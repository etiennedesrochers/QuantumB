# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Etienne Desrochers\\OneDrive - XNNOV\\Documents\\GitHub\\Nouveau dossier (2)\\QuantumB\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('symbols', 'symbols')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'ezdxf', 'pandas'],
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
    name='QuantumB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
