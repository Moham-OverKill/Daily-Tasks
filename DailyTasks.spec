# -*- mode: python ; coding: utf-8 -*-
# DailyTasks.spec - Optimized build configuration

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Explicitly list what we NEED
NEEDED_QT_DLLS = [
    'Qt6Core.dll',
    'Qt6Gui.dll', 
    'Qt6Widgets.dll',
]

# Qt modules/DLLs to EXCLUDE (saves ~36MB+)
EXCLUDED_BINARIES = [
    'opengl32sw.dll',      # 20MB - Software OpenGL fallback
    'Qt6Quick.dll',        # 6MB - QML engine
    'Qt6Pdf.dll',          # 5MB - PDF support
    'Qt6Qml.dll',          # 5MB - QML support  
    'Qt6QmlModels.dll',
    'Qt6QmlMeta.dll',
    'Qt6VirtualKeyboard.dll',
    'Qt6Svg.dll',          # SVG support (not needed)
    'd3dcompiler_47.dll',
    'qdirect2d.dll',
    'libcrypto-3-x64.dll',
    
    # NEW EXCLUSIONS FOR EXTREME LIGHTWEIGHTING
    # 'Qt6Network.dll', # Restored: Needed for QLocalServer (Single Instance Lock)
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
    # 'QtNetwork.pyd',  # Restored: Needed for QLocalServer/IPC
    'QtSql.pyd',
    'QtMultimedia.pyd',
]

# Exclude entire unnecessary Qt plugin folders
EXCLUDED_QT_PLUGINS = [
    'qml',
    'translations',
    'virtualkeyboard',
    'sqldrivers',
    'multimedia',
    'webview',
    'tls',
    'scenegraph'
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
        'src.prayer_calculator',
        'email',
        'email.mime',
        'email.mime.multipart',
        'email.mime.text',
        'email.parser',
        'shutil',
        'uuid',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'customtkinter', 
        'numpy',
        'matplotlib',
        'pandas',
        'scipy',
        'unittest',
        'pydoc',
        'pdb',
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
        'telnetlib',
        'multiprocessing',
        'curses',
        'dbm',
        'ctypes.test',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out excluded binaries
a.binaries = [b for b in a.binaries if not any(excl in b[0] for excl in EXCLUDED_BINARIES)]

# Filter out excluded Qt plugins
a.datas = [d for d in a.datas if not any(f'PySide6/{plugin}' in d[0] for plugin in EXCLUDED_QT_PLUGINS)]

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
    upx=True,  # Enable UPX compression if available
    upx_dir='.',
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
    upx=True,
    upx_exclude=[],
    name='Daily Tasks',
)
