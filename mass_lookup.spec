# mass_lookup.spec
# PyInstaller spec for LUCID
# Build with: pyinstaller mass_lookup.spec

block_cipher = None

a = Analysis(
    ['ui/main_window.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config.ini', '.'),
        ('lucid.ico', '.'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.certs',
        'requests.cookies',
        'requests.exceptions',
        'requests.hooks',
        'requests.models',
        'requests.sessions',
        'requests.structures',
        'requests.utils',
        'urllib3',
        'urllib3.util',
        'urllib3.util.retry',
        'urllib3.contrib',
        'certifi',
        'charset_normalizer',
        'idna',
        'configparser',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['search', 'scripts', 'database'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LUCID',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='lucid.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LUCID',
)
