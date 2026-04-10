/**
 * Preload Script
 * 
 * Exposes a limited, secure API to the renderer process via contextBridge.
 * This allows the React frontend to access native features without
 * enabling nodeIntegration.
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // ── App Info ──
  getVersion: () => ipcRenderer.invoke('app:getVersion'),
  isPackaged: () => ipcRenderer.invoke('app:isPackaged'),
  getPath: (name) => ipcRenderer.invoke('app:getPath', name),

  // ── Window Controls ──
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),

  // ── Native Dialogs ──
  openFileDialog: (options) => ipcRenderer.invoke('dialog:openFile', options),

  // ── Notifications ──
  showNotification: (title, body) => {
    ipcRenderer.send('notification:show', { title, body })
  },

  // ── Shell ──
  openExternal: (url) => ipcRenderer.send('shell:openExternal', url),
  openLogs: () => ipcRenderer.send('shell:openLogs'),

  // ── Backend Status ──
  getBackendStatus: () => ipcRenderer.invoke('backend:getStatus'),
  onBackendStatus: (callback) => {
    const handler = (_, data) => callback(data)
    ipcRenderer.on('backend-status', handler)
    // Return cleanup function
    return () => ipcRenderer.removeListener('backend-status', handler)
  },

  // ── Platform Info ──
  platform: process.platform,
  isElectron: true
})
