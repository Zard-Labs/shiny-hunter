/**
 * Backend Process Manager
 * 
 * Manages the lifecycle of the PyInstaller-bundled Python backend:
 * - Spawns backend.exe as a child process
 * - Polls /health endpoint until ready
 * - Monitors for crashes and supports auto-restart
 * - Handles graceful shutdown
 */

const { spawn } = require('child_process')
const { app } = require('electron')
const path = require('path')
const http = require('http')
const fs = require('fs')
const log = require('electron-log')

const BACKEND_PORT = 8000
const HEALTH_CHECK_URL = `http://localhost:${BACKEND_PORT}/health`
const HEALTH_POLL_INTERVAL_MS = 500
const HEALTH_TIMEOUT_MS = 30000
const SHUTDOWN_TIMEOUT_MS = 5000

class BackendManager {
  constructor() {
    this._process = null
    this._isRunning = false
    this._isShuttingDown = false
    this._onStatusChange = null
    this._restartCount = 0
    this._maxRestarts = 3
  }

  /**
   * Set a callback for status change events.
   * @param {function} callback - (status: string, detail?: string) => void
   */
  onStatusChange(callback) {
    this._onStatusChange = callback
  }

  _emitStatus(status, detail = '') {
    log.info(`[Backend] Status: ${status} ${detail}`)
    if (this._onStatusChange) {
      this._onStatusChange(status, detail)
    }
  }

  /**
   * Resolve the path to the backend executable.
   * In development: runs Python directly from the backend/ directory.
   * In production: uses the PyInstaller-bundled backend.exe from extraResources.
   */
  _getBackendPath() {
    const isDev = !app.isPackaged

    if (isDev) {
      // Development mode: run Python directly
      return {
        command: 'python',
        args: ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', String(BACKEND_PORT)],
        cwd: path.join(__dirname, '..', '..', 'backend'),
        isDev: true
      }
    }

    // Production mode: run bundled backend.exe
    const resourcesPath = process.resourcesPath
    const backendDir = path.join(resourcesPath, 'backend')
    const backendExe = path.join(backendDir, 'backend.exe')

    if (!fs.existsSync(backendExe)) {
      throw new Error(`Backend executable not found at: ${backendExe}`)
    }

    return {
      command: backendExe,
      args: [],
      cwd: backendDir,
      isDev: false
    }
  }

  /**
   * Resolve the user data directory for config, database, encounters, etc.
   * In production, this is %APPDATA%/ShinyStarter
   * In dev, this is the backend directory itself.
   */
  getUserDataPath() {
    if (!app.isPackaged) {
      return path.join(__dirname, '..', '..', 'backend')
    }
    const userDataDir = path.join(app.getPath('userData'))
    // Ensure directory exists
    if (!fs.existsSync(userDataDir)) {
      fs.mkdirSync(userDataDir, { recursive: true })
    }
    return userDataDir
  }

  /**
   * Check if port is already in use.
   * @returns {Promise<boolean>}
   */
  _checkPortInUse() {
    return new Promise((resolve) => {
      const req = http.get(HEALTH_CHECK_URL, () => {
        resolve(true) // Something responded
      })
      req.on('error', () => {
        resolve(false) // Nothing listening
      })
      req.setTimeout(1000, () => {
        req.destroy()
        resolve(false)
      })
    })
  }

  /**
   * Poll the /health endpoint until the backend is ready.
   * @returns {Promise<boolean>} true if healthy, false if timed out
   */
  _waitForHealthy() {
    return new Promise((resolve) => {
      const startTime = Date.now()

      const poll = () => {
        if (Date.now() - startTime > HEALTH_TIMEOUT_MS) {
          log.error('[Backend] Health check timed out')
          resolve(false)
          return
        }

        const req = http.get(HEALTH_CHECK_URL, (res) => {
          let data = ''
          res.on('data', (chunk) => { data += chunk })
          res.on('end', () => {
            try {
              const json = JSON.parse(data)
              if (json.status === 'healthy') {
                resolve(true)
                return
              }
            } catch (e) {
              // Not ready yet
            }
            setTimeout(poll, HEALTH_POLL_INTERVAL_MS)
          })
        })

        req.on('error', () => {
          // Backend not ready yet
          setTimeout(poll, HEALTH_POLL_INTERVAL_MS)
        })

        req.setTimeout(2000, () => {
          req.destroy()
          setTimeout(poll, HEALTH_POLL_INTERVAL_MS)
        })
      }

      poll()
    })
  }

  /**
   * Start the backend process.
   * @returns {Promise<boolean>} true if backend started successfully
   */
  async start() {
    if (this._isRunning) {
      log.warn('[Backend] Already running')
      return true
    }

    // Check if port is already in use
    this._emitStatus('checking', 'Checking if port is available...')
    const portInUse = await this._checkPortInUse()
    if (portInUse) {
      log.warn(`[Backend] Port ${BACKEND_PORT} already in use - attempting to use existing backend`)
      const healthy = await this._waitForHealthy()
      if (healthy) {
        this._isRunning = true
        this._emitStatus('ready', 'Connected to existing backend')
        return true
      }
      this._emitStatus('error', `Port ${BACKEND_PORT} is in use by another application`)
      return false
    }

    this._emitStatus('starting', 'Starting backend server...')

    try {
      const { command, args, cwd, isDev } = this._getBackendPath()
      const userDataPath = this.getUserDataPath()

      log.info(`[Backend] Starting: ${command} ${args.join(' ')}`)
      log.info(`[Backend] Working directory: ${cwd}`)
      log.info(`[Backend] User data path: ${userDataPath}`)

      // Set environment variables for the backend
      const env = {
        ...process.env,
        SHINYSTARTER_PACKAGED: app.isPackaged ? '1' : '0',
        SHINYSTARTER_USER_DATA: userDataPath,
        SHINYSTARTER_PORT: String(BACKEND_PORT),
        SHINYSTARTER_RESOURCES_PATH: process.resourcesPath || '',
        // Prevent Python from buffering stdout/stderr
        PYTHONUNBUFFERED: '1'
      }

      this._process = spawn(command, args, {
        cwd,
        env,
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true
      })

      // Pipe stdout to log
      this._process.stdout.on('data', (data) => {
        const text = data.toString().trim()
        if (text) {
          log.info(`[Backend stdout] ${text}`)
        }
      })

      // Pipe stderr to log
      this._process.stderr.on('data', (data) => {
        const text = data.toString().trim()
        if (text) {
          log.warn(`[Backend stderr] ${text}`)
        }
      })

      // Handle process exit
      this._process.on('exit', (code, signal) => {
        log.info(`[Backend] Process exited with code ${code}, signal ${signal}`)
        this._isRunning = false
        this._process = null

        if (!this._isShuttingDown) {
          // Unexpected crash
          this._emitStatus('crashed', `Backend crashed (exit code: ${code})`)

          // Auto-restart if under limit
          if (this._restartCount < this._maxRestarts) {
            this._restartCount++
            log.info(`[Backend] Auto-restarting (attempt ${this._restartCount}/${this._maxRestarts})`)
            this._emitStatus('restarting', `Restarting backend (attempt ${this._restartCount})...`)
            setTimeout(() => this.start(), 2000)
          } else {
            this._emitStatus('error', 'Backend crashed too many times. Check logs.')
          }
        }
      })

      // Handle spawn errors
      this._process.on('error', (err) => {
        log.error(`[Backend] Spawn error: ${err.message}`)
        this._isRunning = false
        this._process = null
        this._emitStatus('error', `Failed to start backend: ${err.message}`)
      })

      // Wait for backend to become healthy
      this._emitStatus('waiting', 'Waiting for backend to be ready...')
      const healthy = await this._waitForHealthy()

      if (healthy) {
        this._isRunning = true
        this._restartCount = 0
        this._emitStatus('ready', 'Backend is ready')
        return true
      } else {
        this._emitStatus('error', 'Backend failed to start (health check timed out)')
        await this.stop()
        return false
      }

    } catch (err) {
      log.error(`[Backend] Start error: ${err.message}`)
      this._emitStatus('error', err.message)
      return false
    }
  }

  /**
   * Stop the backend process gracefully.
   * @returns {Promise<void>}
   */
  async stop() {
    if (!this._process) {
      this._isRunning = false
      return
    }

    this._isShuttingDown = true
    this._emitStatus('stopping', 'Shutting down backend...')
    log.info('[Backend] Stopping...')

    return new Promise((resolve) => {
      const forceKillTimer = setTimeout(() => {
        if (this._process) {
          log.warn('[Backend] Force killing after timeout')
          this._process.kill('SIGKILL')
        }
        cleanup()
      }, SHUTDOWN_TIMEOUT_MS)

      const cleanup = () => {
        clearTimeout(forceKillTimer)
        this._process = null
        this._isRunning = false
        this._isShuttingDown = false
        log.info('[Backend] Stopped')
        resolve()
      }

      this._process.on('exit', () => {
        cleanup()
      })

      // Try graceful shutdown first
      // On Windows, SIGTERM doesn't work well, so we use taskkill
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(this._process.pid), '/T', '/F'], {
          windowsHide: true
        })
      } else {
        this._process.kill('SIGTERM')
      }
    })
  }

  /**
   * Get the backend URL.
   * @returns {string}
   */
  getBackendUrl() {
    return `http://localhost:${BACKEND_PORT}`
  }

  /**
   * Check if backend is currently running.
   * @returns {boolean}
   */
  get isRunning() {
    return this._isRunning
  }

  /**
   * Get the backend port.
   * @returns {number}
   */
  get port() {
    return BACKEND_PORT
  }
}

// Singleton instance
const backendManager = new BackendManager()

module.exports = { backendManager, BACKEND_PORT }
