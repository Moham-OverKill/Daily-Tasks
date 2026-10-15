# -*- mode: python ; coding: utf-8 -*-
# DailyTasks.spec - Optimized build configuration

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Qt modules/DLLs to EXCLUDE
EXCLUDED_BINARIES = [
    'opengl32sw.dll',       # 20MB - Software OpenGL fallback
    'Qt6OpenGL.dll',        # 1.9MB - Not imported by QtWidgets/QtGui/QtCore
    'Qt6Network.dll',       # 1.7MB - Replaced by Win32 Named Pipe + WinINet
    'Qt6Quick.dll',         # QML engine
    'Qt6Pdf.dll',           # PDF support
    'Qt6Qml.dll',           # QML support
    'Qt6QmlModels.dll',
    'Qt6QmlMeta.dll',
    'Qt6QmlWorkerScript.dll',
    'Qt6VirtualKeyboard.dll',
    'Qt6Svg.dll',
    'd3dcompiler_47.dll',
    'qdirect2d.dll',

    '_lzma.pyd',
    '_bz2.pyd',
    'unicodedata.pyd',      # 1.1MB - Not needed at runtime
    'Qt6WebEngineCore.dll',
    'Qt6WebEngineWidgets.dll',
    'Qt6Sql.dll',
    'Qt6Multimedia.dll',
    'Qt6Sensors.dll',
    'Qt6Bluetooth.dll',
    'Qt6DBus.dll',
    'Qt6StateMachine.dll',
    'QtQuick.pyd',
    'QtQml.pyd',
    'QtOpenGL.pyd',
    'QtPdf.pyd',
    'QtSvg.pyd',
    'QtNetwork.pyd',        # 1.1MB - Replaced by Win32 Named Pipe IPC
    'QtSql.pyd',
    'QtMultimedia.pyd',
    # Unused image format & platform plugins (keep qwindows.dll, qico.dll, qjpeg.dll)
    'qwebp.dll',
    'qtiff.dll',
    'qicns.dll',
    'qpdf.dll',
    'qwbmp.dll',
    'qsvg.dll',
    'qgif.dll',
    'qtga.dll',
    'qminimal.dll',
    'qoffscreen.dll',
    'qsvgicon.dll',
    'qtuiotouchplugin.dll',
    'qtvirtualkeyboardplugin.dll',
]

# Exclude entire unnecessary Qt plugin folders
EXCLUDED_QT_PLUGINS = [
    'qml',
    'translations',
    'virtualkeyboard',
    'platforminputcontexts',
    'sqldrivers',
    'multimedia',
    'webview',
    'tls',
    'networkinformation',
    'generic',
    'iconengines',
    'scenegraph',
    'geometryloaders',
    'renderers',
    'renderplugins',
    'sceneparsers',
]

# Strip all Qt translation .qm files and unused asset files
EXCLUDED_DATA_PATTERNS = [
    '.qm',          # Qt translation files (~8.5 MB across 97 locale files)
    'badge.ico',    # Unused legacy icon
    'check.svg',    # Unused SVG asset
]

a = Analysis(
    ['start.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'plyer.platforms.win.notification',
        'src',
        'src.qt_app',
        'src.qt_components',
        'src.qt_effects',
        'src.task_manager',
        'src.sound_manager',
        'src.api_handler',
        'src.updater',
        'shutil',
        'uuid',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',
        'setuptools',
        'tkinter',
        'customtkinter',
        'numpy',
        'matplotlib',
        'pandas',
        'scipy',
        'requests',
        'urllib3',
        'charset_normalizer',
        'idna',
        'certifi',
        'unittest',
        'pydoc',
        'doctest',
        'compileall',
        'mailbox',
        'py_compile',
        'turtledemo',
        'lzma',
        '_lzma',
        'bz2',
        '_bz2',
        # PySide6 modules not used
        'PySide6.QtNetwork',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQml',
        'PySide6.QtQmlCore',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtTest',
        'PySide6.QtXml',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DExtras',
        'PySide6.QtDataVisualization',
        'PySide6.QtCharts',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtUiTools',
        'asyncio',
        'concurrent',
        'sqlite3',
        'xmlrpc',
        'http.server',
        'ftplib',
        'poplib',
        'imaplib',
        'smtplib',
        'multiprocessing',
        'curses',
        'dbm',
        'ctypes.test',
        'test',
        '_decimal',
        '_zstd',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

# ─── Filter excluded binaries & Qt plugin folders ───────────────────────────
def _keep_binary(dest_name):
    norm = dest_name.replace('\\', '/')
    base = norm.rsplit('/', 1)[-1]
    if any(excl.lower() in norm.lower() for excl in EXCLUDED_BINARIES):
        return False
    if any(f'PySide6/plugins/{plugin}/' in norm or f'PySide6/{plugin}/' in norm for plugin in EXCLUDED_QT_PLUGINS):
        return False
    # Deduplicate MSVC runtime DLLs: keep VCRUNTIME140* in root and MSVCP140* in PySide6/
    if 'shiboken6/' in norm and (
        base.upper().startswith('MSVCP140') or base.upper().startswith('VCRUNTIME140')
    ):
        return False
    if 'PySide6/' in norm and base.upper().startswith('VCRUNTIME140'):
        return False
    return True

a.binaries = [b for b in a.binaries if _keep_binary(b[0])]

# ─── Filter excluded Qt plugin folders & unused data files ──────────────────
a.datas = [d for d in a.datas if not any(
    f'PySide6/plugins/{plugin}' in d[0].replace('\\', '/') or
    f'PySide6/{plugin}' in d[0].replace('\\', '/')
    for plugin in EXCLUDED_QT_PLUGINS
)]
a.datas = [d for d in a.datas if not any(d[0].replace('\\', '/').endswith(pat) for pat in EXCLUDED_DATA_PATTERNS)]
a.datas = [d for d in a.datas if 'certifi' not in d[0].replace('\\', '/')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Daily Tasks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Daily Tasks',
)
