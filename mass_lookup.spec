# ============================================================
# HOW TO USE:
# 1. On Windows, run:  pyinstaller mass_lookup.spec
# ============================================================

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'sqlite3',
        'search.search_engine',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'tkinter'],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MassLookup',
    debug=False,
    strip=False,
    upx=True,
    console=False,      # No black terminal window — GUI only
                        # Change to True if app crashes on launch (to see errors)
    icon=None,          # Optional: put path to a .ico file here
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='MassLookup',
)