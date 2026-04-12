# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ShinyStarter Backend.

Bundles the entire FastAPI backend + dependencies into a single directory
distribution with backend.exe as the entry point.

Usage:
    cd backend
    pyinstaller pyinstaller.spec
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Project root
backend_dir = os.path.dirname(os.path.abspath(SPEC))

# Collect data files for packages that need them
datas = []

# Include config.yaml.example as default config
if os.path.exists(os.path.join(backend_dir, 'config.yaml.example')):
    datas.append(('config.yaml.example', '.'))

# Include templates directory if it exists
templates_dir = os.path.join(backend_dir, 'templates')
if os.path.exists(templates_dir):
    datas.append(('templates', 'templates'))

# Collect rapidocr data files (models, etc.)
try:
    datas += collect_data_files('rapidocr_onnxruntime')
except Exception:
    print("WARNING: rapidocr_onnxruntime data files not found, skipping")

# Collect onnxruntime data files
try:
    datas += collect_data_files('onnxruntime')
except Exception:
    print("WARNING: onnxruntime data files not found, skipping")

# Hidden imports that PyInstaller can't detect automatically
hiddenimports = [
    # uvicorn internals
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    # FastAPI / Starlette
    'fastapi',
    'starlette',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    # SQLAlchemy
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.ext.baked',
    # Pydantic
    'pydantic',
    'pydantic_settings',
    # App modules
    'app',
    'app.main',
    'app.config',
    'app.database',
    'app.models',
    'app.schemas',
    'app.routes',
    'app.routes.automation',
    'app.routes.control',
    'app.routes.statistics',
    'app.routes.websocket',
    'app.routes.camera',
    'app.routes.templates',
    'app.routes.calibration',
    'app.services',
    'app.services.esp32_manager',
    'app.services.game_engine',
    'app.services.opencv_detector',
    'app.services.video_capture',
    'app.utils',
    'app.utils.command_builder',
    'app.utils.logger',
    # Other
    'cv2',
    'numpy',
    'PIL',
    'aiofiles',
    'websockets',
    'yaml',
    'serial',
    'multipart',
    'h11',
    'httptools',
    'dotenv',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
]

# Collect all submodules for tricky packages
try:
    hiddenimports += collect_submodules('uvicorn')
except Exception:
    pass
try:
    hiddenimports += collect_submodules('starlette')
except Exception:
    pass

a = Analysis(
    ['backend_entry.py'],
    pathex=[backend_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        '_tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'setuptools',
        'pip',
        'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for logging; can change to False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='backend',
)
