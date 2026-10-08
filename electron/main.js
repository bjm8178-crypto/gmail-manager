/**
 * main.js — Electron Main Process (Phase 10 — Production Ready)
 * Responsible for:
 * 1. Detecting dev vs production environment
 * 2. Spawning the correct backend (python script or bundled exe)
 * 3. Health-checking the backend before opening the window
 * 4. Opening the Electron window pointed at the correct URL
 * 5. Cleaning up the backend process when the app closes
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

// ---------- GLOBALS ----------
let mainWindow = null;     // Reference to the main Electron window
let pythonProcess = null;  // Reference to the spawned backend process

// ---------- ENVIRONMENT DETECTION ----------

/**
 * Check if we're running in development mode.
 * Development: NODE_ENV is 'development' OR we detect the source backend folder.
 * Production: The app is packaged via electron-builder (app.isPackaged = true).
 */
function isDev() {
  return !app.isPackaged || process.env.NODE_ENV === 'development';
}

// ---------- PYTHON BACKEND MANAGEMENT ----------

/**
 * Start the backend server.
 * - In development: runs `python main.py` from the backend/ folder
 * - In production: runs the bundled `gmail-manager-backend.exe` from resources/
 */
function startBackend() {
  if (isDev()) {
    // DEVELOPMENT: spawn Python directly
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const mainPyPath = path.join(__dirname, '..', 'backend', 'main.py');

    console.log(`[ELECTRON] DEV MODE — Starting Python backend: ${pythonCmd} ${mainPyPath}`);

    pythonProcess = spawn(pythonCmd, [mainPyPath], {
      cwd: path.join(__dirname, '..', 'backend'),
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });
  } else {
    // PRODUCTION: spawn the PyInstaller-built executable
    const exeName = process.platform === 'win32'
      ? 'gmail-manager-backend.exe'
      : 'gmail-manager-backend';

    // electron-builder puts extraResources into process.resourcesPath
    const exePath = path.join(process.resourcesPath, 'resources', exeName);

    console.log(`[ELECTRON] PRODUCTION MODE — Starting backend exe: ${exePath}`);

    pythonProcess = spawn(exePath, [], {
      cwd: path.dirname(exePath),
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });
  }

  // Log backend stdout
  pythonProcess.stdout.on('data', (data) => {
    console.log(`[BACKEND] ${data.toString().trim()}`);
  });

  // Log backend stderr
  pythonProcess.stderr.on('data', (data) => {
    console.error(`[BACKEND ERROR] ${data.toString().trim()}`);
  });

  // Handle backend exit
  pythonProcess.on('close', (code) => {
    console.log(`[BACKEND] Process exited with code ${code}`);
    pythonProcess = null;
  });

  // Handle spawn errors
  pythonProcess.on('error', (err) => {
    console.error(`[BACKEND] Failed to start: ${err.message}`);
  });
}

/**
 * Stop the backend process gracefully.
 */
function stopBackend() {
  if (pythonProcess) {
    console.log('[ELECTRON] Stopping backend...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t']);
    } else {
      pythonProcess.kill('SIGTERM');
    }
    pythonProcess = null;
  }
}

// ---------- HEALTH CHECK ----------

/**
 * Poll the backend health endpoint until it responds.
 * Returns a Promise that resolves when the backend is ready.
 * Times out after maxAttempts * interval ms.
 */
function waitForBackend(maxAttempts = 30, interval = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const check = () => {
      attempts++;
      const req = http.get('http://localhost:8000/', (res) => {
        if (res.statusCode === 200) {
          console.log(`[ELECTRON] Backend ready after ${attempts} attempts (${attempts * interval}ms)`);
          resolve();
        } else {
          retry();
        }
      });

      req.on('error', () => retry());
      req.setTimeout(1000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (attempts >= maxAttempts) {
        console.error(`[ELECTRON] Backend failed to start after ${maxAttempts} attempts.`);
        reject(new Error('Backend timeout'));
      } else {
        setTimeout(check, interval);
      }
    };

    check();
  });
}

// ---------- WINDOW MANAGEMENT ----------

/**
 * Create the main application window.
 * In dev: loads Vite dev server (localhost:5173)
 * In prod: loads the built frontend from frontend/dist/index.html
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    resizable: true,
    frame: true,
    autoHideMenuBar: true,
    backgroundColor: '#0F172A',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Gmail Manager',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
  });

  if (isDev()) {
    // Development: load from Vite dev server
    mainWindow.loadURL('http://localhost:5173');
    console.log('[ELECTRON] Loading from Vite dev server (http://localhost:5173)');
  } else {
    // Production: load from built frontend files
    const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
    console.log(`[ELECTRON] Loading from built frontend: ${indexPath}`);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ---------- IPC HANDLERS ----------

ipcMain.handle('get-version', () => {
  return app.getVersion();
});

// ---------- APP LIFECYCLE ----------

app.whenReady().then(async () => {
  console.log(`[ELECTRON] App ready. Mode: ${isDev() ? 'DEVELOPMENT' : 'PRODUCTION'}`);

  // Start the backend
  startBackend();

  // Wait for backend to be ready (health check polling)
  try {
    await waitForBackend(30, 500); // 30 attempts × 500ms = 15s max wait
  } catch (err) {
    console.error('[ELECTRON] Could not reach backend. Opening window anyway...');
  }

  // Open the main window
  createWindow();

  // macOS: re-create window on dock click
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows closed (except macOS)
app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Ensure cleanup on app exit
app.on('before-quit', () => {
  stopBackend();
});

// Handle uncaught exceptions
process.on('uncaughtException', (err) => {
  console.error('[ELECTRON] Uncaught exception:', err);
  stopBackend();
});
