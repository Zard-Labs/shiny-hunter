import { useState, useEffect } from 'react'
import { getESP32Config, updateESP32Config } from '../services/api'

function ESP32Config() {
  const [ip, setIp] = useState('')
  const [port, setPort] = useState(80)
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    loadConfig()
  }, [])

  // Poll connection status every 10 seconds
  useEffect(() => {
    const interval = setInterval(loadConfig, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadConfig = async () => {
    try {
      const data = await getESP32Config()
      setIp(data.ip || 'shinystarter.local')
      setPort(data.port || 80)
      setConnected(data.connected || false)
    } catch (error) {
      console.error('Failed to load ESP32 config:', error)
    }
  }

  const showMessage = (text, type = 'info') => {
    setMessage({ text, type })
    setTimeout(() => setMessage(null), 4000)
  }

  const handleConnect = async () => {
    if (!ip.trim()) {
      showMessage('Please enter an IP address or hostname', 'error')
      return
    }

    setLoading(true)
    setMessage(null)
    try {
      const result = await updateESP32Config({
        ip: ip.trim(),
        port: port,
        save: false
      })

      setConnected(result.connected)
      if (result.connected) {
        showMessage(`Connected to ${ip}`, 'success')
      } else {
        showMessage(`Could not reach ESP32 at ${ip}`, 'error')
      }
    } catch (error) {
      console.error('Failed to update ESP32 config:', error)
      const errorMsg = error.response?.data?.detail || error.message || 'Connection failed'
      showMessage(errorMsg, 'error')
      setConnected(false)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!ip.trim()) {
      showMessage('Please enter an IP address or hostname', 'error')
      return
    }

    setSaving(true)
    setMessage(null)
    try {
      const result = await updateESP32Config({
        ip: ip.trim(),
        port: port,
        save: true
      })

      setConnected(result.connected)
      if (result.connected) {
        showMessage('Saved & connected! Will use this on startup.', 'success')
      } else {
        showMessage('Saved to config, but could not connect now.', 'warning')
      }
    } catch (error) {
      console.error('Failed to save ESP32 config:', error)
      showMessage('Failed to save configuration', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleConnect()
    }
  }

  return (
    <div className="stat-box" style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <div className="stat-label" style={{ marginBottom: 0 }}>
          🎮 Controller Connection
        </div>
        <span
          className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}
          title={connected ? 'Connected' : 'Disconnected'}
        ></span>
      </div>

      {/* IP / Hostname Input */}
      <div style={{ marginBottom: '0.5rem' }}>
        <label style={{
          display: 'block',
          fontSize: '0.7rem',
          color: 'var(--text-secondary)',
          marginBottom: '0.25rem',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}>
          IP Address / Hostname
        </label>
        <input
          type="text"
          value={ip}
          onChange={(e) => setIp(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="shinystarter.local"
          disabled={loading || saving}
          style={{
            width: '100%',
            padding: '0.6rem 0.75rem',
            fontSize: '0.9rem',
            background: 'rgba(0, 0, 0, 0.5)',
            border: `1px solid ${connected ? 'var(--accent-green)' : 'var(--accent-cyan)'}`,
            color: 'var(--text-primary)',
            borderRadius: '4px',
            fontFamily: "'Courier New', monospace",
            outline: 'none',
            transition: 'border-color 0.2s ease'
          }}
        />
      </div>

      {/* Port Input */}
      <div style={{ marginBottom: '0.75rem' }}>
        <label style={{
          display: 'block',
          fontSize: '0.7rem',
          color: 'var(--text-secondary)',
          marginBottom: '0.25rem',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}>
          Port
        </label>
        <input
          type="number"
          value={port}
          onChange={(e) => setPort(parseInt(e.target.value) || 80)}
          disabled={loading || saving}
          min={1}
          max={65535}
          style={{
            width: '80px',
            padding: '0.4rem 0.5rem',
            fontSize: '0.85rem',
            background: 'rgba(0, 0, 0, 0.5)',
            border: '1px solid var(--accent-cyan)',
            color: 'var(--text-primary)',
            borderRadius: '4px',
            fontFamily: "'Courier New', monospace",
            outline: 'none'
          }}
        />
      </div>

      {/* Status message */}
      {message && (
        <div style={{
          padding: '0.4rem 0.6rem',
          marginBottom: '0.5rem',
          borderRadius: '4px',
          fontSize: '0.75rem',
          fontFamily: "'Courier New', monospace",
          background: message.type === 'success' ? 'rgba(0, 255, 0, 0.1)'
            : message.type === 'error' ? 'rgba(255, 0, 0, 0.1)'
            : message.type === 'warning' ? 'rgba(255, 165, 0, 0.1)'
            : 'rgba(0, 255, 255, 0.1)',
          border: `1px solid ${
            message.type === 'success' ? 'var(--accent-green)'
            : message.type === 'error' ? 'var(--accent-red)'
            : message.type === 'warning' ? '#ff8c00'
            : 'var(--accent-cyan)'
          }`,
          color: message.type === 'success' ? 'var(--accent-green)'
            : message.type === 'error' ? 'var(--accent-red)'
            : message.type === 'warning' ? '#ff8c00'
            : 'var(--accent-cyan)'
        }}>
          {message.text}
        </div>
      )}

      {/* Loading indicator */}
      {(loading || saving) && (
        <div style={{
          textAlign: 'center',
          color: 'var(--accent-cyan)',
          fontSize: '0.85rem',
          marginBottom: '0.5rem'
        }}>
          {loading ? '🔌 Connecting...' : '💾 Saving...'}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
        <button
          onClick={handleConnect}
          disabled={loading || saving}
          style={{
            padding: '0.5rem',
            background: 'rgba(0, 255, 255, 0.1)',
            border: '1px solid var(--accent-cyan)',
            color: 'var(--accent-cyan)',
            borderRadius: '4px',
            cursor: loading || saving ? 'not-allowed' : 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'inherit',
            opacity: loading || saving ? 0.5 : 1,
            transition: 'all 0.2s ease'
          }}
        >
          🔌 Connect
        </button>

        <button
          onClick={handleSave}
          disabled={loading || saving}
          style={{
            padding: '0.5rem',
            background: 'rgba(0, 255, 0, 0.1)',
            border: '1px solid var(--accent-green)',
            color: 'var(--accent-green)',
            borderRadius: '4px',
            cursor: loading || saving ? 'not-allowed' : 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'inherit',
            fontWeight: 'bold',
            opacity: loading || saving ? 0.5 : 1,
            transition: 'all 0.2s ease'
          }}
        >
          💾 Save
        </button>
      </div>

      {/* Helper text */}
      <div style={{
        marginTop: '0.75rem',
        fontSize: '0.7rem',
        color: 'var(--text-secondary)',
        lineHeight: '1.4'
      }}>
        💡 Default: <span style={{ color: 'var(--accent-cyan)' }}>shinystarter.local</span>
        <br />
        Or enter the IP from serial monitor / router
      </div>
    </div>
  )
}

export default ESP32Config
