# -*- mode: python ; coding: utf-8 -*-
"""
Gmail Manager Backend — PyInstaller Spec File
Bundles the FastAPI backend into a single executable.

Usage:
  cd backend
  pyinstaller gmail-manager-backend.spec

Or use the simpler command:
  pyinstaller --onefile --name gmail-manager-backend main.py
"""

import os

block_cipher = None

# Collect all .py files in backend/
backend_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[backend_dir],
    binaries=[],
    datas=[
        # Include .env file for API keys
        ('.env', '.'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'httpx',
        'sse_starlette',
        'google.auth',
        'google.auth.transport.requests',
        'google_auth_oauthlib',
        'googleapiclient',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='gmail-manager-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console=True so we can see backend logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
