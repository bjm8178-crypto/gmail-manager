/**
 * preload.js — Electron Preload Script
 * Runs before the renderer process loads. Exposes safe APIs
 * to the frontend via contextBridge (security best practice).
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose a limited API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Get the app version
  getVersion: () => ipcRenderer.invoke('get-version'),

  // Platform info (for OS-specific UI adjustments)
  platform: process.platform,

  // Notify main process that the app is ready
  appReady: () => ipcRenderer.send('app-ready'),
});

console.log('[PRELOAD] Preload script loaded. electronAPI exposed to renderer.');
