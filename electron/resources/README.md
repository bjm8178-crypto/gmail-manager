# Electron Resources

This directory contains the bundled Python backend executable.

## How to generate:
```bash
cd backend
pyinstaller --onefile --name gmail-manager-backend --distpath ../electron/resources main.py
```

The resulting `gmail-manager-backend.exe` (Windows) is spawned by Electron in production mode.
