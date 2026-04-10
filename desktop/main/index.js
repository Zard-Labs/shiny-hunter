/**
 * ShinyStarter - Electron Main Process
 * 
 * Entry point for the desktop application. Manages:
 * - Splash screen display during backend startup
 * - Python backend lifecycle (via BackendManager)
 * - Main BrowserWindow loading the React frontend
 * - App lifecycle (quit, minimize to tray, etc.)
 */

const { app, BrowserWindow, ipcMain, dialog, shell, Notification } = require('electron')
const path = require('path')
const log = require('electron-log')
const { backendManager, BACKEND_PORT } = require('./backend-manager')

// Configure electron-log
log.transports.file.level = 'info'
log.transports.console.level = 'info'
log.transports.file.resolvePathFn = () => {
  return path.join(app.getPath('userData'), 'logs', 'electron.log')
}

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
}

let splashWindow = null
let mainWindow = null

/**
 * Create the splash/loading screen window.
 */
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 360,
    frame: false,
    transparent: false,
    resizable: false,
    skipTaskbar: false,
    alwaysOnTop: true,
    backgroundColor: '#0a0a1a',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '..', 'preload', 'index.js')
    }
  })

  splashWindow.loadFile(path.join(__dirname, 'splash.html'))

  splashWindow.once('ready-to-show', () => {
    splashWindow.show()
  })

  splashWindow.on('closed', () => {
    splashWindow = null
  })
}

/**
 * Create the main application window.
 */
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#0a0a1a',
    show: false,
    icon: path.join(__dirname, '..', 'resources', 'icon.ico'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '..', 'preload', 'index.js')
    }
  })

  // Load the React frontend served by FastAPI
  const backendUrl = backendManager.getBackendUrl()
  log.info(`[Main] Loading frontend from: ${backendUrl}`)
  mainWindow.loadURL(backendUrl)

  // Show window when content is ready
  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      splashWindow.close()
      splashWindow = null
    }
    mainWindow.show()
    mainWindow.focus()
    log.info('[Main] Main window shown')
  })

  // Handle window close - hide instead of quit (optional: could add tray)
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // Open external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http') && !url.includes('localhost')) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  // Open DevTools in development
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }
}

/**
 * Initialize the application.
 */
async function initialize() {
  log.info('='.repeat(60))
  log.info('  ShinyStarter Desktop - Starting')
  log.info(`  Version: ${app.getVersion()}`)
  log.info(`  Packaged: ${app.isPackaged}`)
  log.info(`  User Data: ${app.getPath('userData')}`)
  log.info('='.repeat(60))

  // Show splash screen
  createSplashWindow()

  // Set up backend status forwarding to splash screen
  backendManager.onStatusChange((status, detail) => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.send('backend-status', { status, detail })
    }
    // Also forward to main window if it exists
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-status', { status, detail })
    }
  })

  // Start the backend
  const started = await backendManager.start()

  if (!started) {
    log.error('[Main] Backend failed to start')

    const response = await dialog.showMessageBox(splashWindow || null, {
      type: 'error',
      title: 'ShinyStarter - Startup Error',
      message: 'Failed to start the backend server.',
      detail: 'The Python backend could not be started. This may be due to:\n\n' +
        '• Port 8000 is already in use\n' +
        '• Missing backend files\n' +
        '• Antivirus blocking the application\n\n' +
        'Check the logs at:\n' +
        path.join(app.getPath('userData'), 'logs', 'electron.log'),
      buttons: ['Retry', 'Open Logs', 'Quit'],
      defaultId: 0,
      cancelId: 2
    })

    if (response.response === 0) {
      // Retry
      if (splashWindow) splashWindow.close()
      return initialize()
    } else if (response.response === 1) {
      // Open logs
      shell.openPath(path.join(app.getPath('userData'), 'logs'))
      app.quit()
      return
    } else {
      app.quit()
      return
    }
  }

  // Backend is ready - create main window
  createMainWindow()
}

// ── IPC Handlers ──────────────────────────────────────────

// App info
ipcMain.handle('app:getVersion', () => app.getVersion())
ipcMain.handle('app:isPackaged', () => app.isPackaged)
ipcMain.handle('app:getPath', (_, name) => app.getPath(name))

// Window controls
ipcMain.on('window:minimize', () => {
  if (mainWindow) mainWindow.minimize()
})
ipcMain.on('window:maximize', () => {
  if (mainWindow) {
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize()
  }
})
ipcMain.on('window:close', () => {
  if (mainWindow) mainWindow.close()
})

// File dialog
ipcMain.handle('dialog:openFile', async (_, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options)
  return result
})

// Notifications (e.g., SHINY FOUND!)
ipcMain.on('notification:show', (_, { title, body }) => {
  new Notification({ title, body }).show()
})

// Open external URL
ipcMain.on('shell:openExternal', (_, url) => {
  shell.openExternal(url)
})

// Open log directory
ipcMain.on('shell:openLogs', () => {
  shell.openPath(path.join(app.getPath('userData'), 'logs'))
})

// Backend status query
ipcMain.handle('backend:getStatus', () => {
  return {
    running: backendManager.isRunning,
    port: backendManager.port,
    url: backendManager.getBackendUrl()
  }
})

// ── App Lifecycle ─────────────────────────────────────────

app.whenReady().then(() => {
  initialize()
})

// Handle second instance (bring existing window to front)
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

// Quit when all windows are closed
app.on('window-all-closed', () => {
  app.quit()
})

// Clean up backend on quit
app.on('before-quit', async (event) => {
  if (backendManager.isRunning) {
    event.preventDefault()
    log.info('[Main] Shutting down backend before quit...')
    await backendManager.stop()
    app.quit()
  }
})

// Final cleanup
app.on('will-quit', () => {
  log.info('[Main] Application quitting')
})

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  log.error('[Main] Uncaught exception:', error)
  dialog.showErrorBox(
    'ShinyStarter Error',
    `An unexpected error occurred:\n\n${error.message}\n\nThe application will now close.`
  )
  app.quit()
})
