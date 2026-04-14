import { useEffect, useState, useRef } from 'react'
import { getESP32Status } from '../services/api'

// Poll ESP32 status at a relaxed interval (not critical real-time data)
const ESP32_POLL_MS = 30000

function StatusDisplay({ status, connected }) {
  const [esp32Status, setEsp32Status] = useState({ connected: false, status: 'unknown', mode: 'unknown' })
  const [logs, setLogs] = useState([])
  const fetchingRef = useRef(false)

  useEffect(() => {
    fetchESP32Status()
    const interval = setInterval(fetchESP32Status, ESP32_POLL_MS)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (status.state) {
      addLog(`STATE: ${status.state}`, 'info')
    }
  }, [status.state])

  const fetchESP32Status = async () => {
    if (fetchingRef.current) return
    fetchingRef.current = true
    try {
      const data = await getESP32Status()
      setEsp32Status(data)
    } catch (error) {
      setEsp32Status({ connected: false, status: 'error', mode: 'unknown' })
    } finally {
      fetchingRef.current = false
    }
  }

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev.slice(-9), { message, type, timestamp }])
  }

  const getStateEmoji = (state) => {
    const stateMap = {
      'IDLE': '⏸️',
      'PHASE_1_BOOT': '🔄',
      'PHASE_2_OVERWORLD': '🚶',
      'PHASE_2_WAIT': '⏳',
      'PHASE_3_MENU': '📋',
      'PHASE_4_CHECK': '🔍',
      'SHINY_FOUND': '✨',
    }
    return stateMap[state] || '❓'
  }

  return (
    <div className="panel status-display">
      <h2 className="panel-title">📊 Status Monitor</h2>
      
      <div className="stat-box holo-card">
        <div className="stat-label">Current State</div>
        <div className="stat-value" style={{ fontSize: '1.5rem' }}>
          {getStateEmoji(status.state)} {status.state || 'IDLE'}
        </div>
      </div>

      <div className="stat-box" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div>
          <div className="stat-label">Resets</div>
          <div className="stat-value" style={{ fontSize: '1.5rem' }}>
            {status.reset_count || 0}
          </div>
        </div>
        <div>
          <div className="stat-label">Running</div>
          <div className={`stat-value ${status.is_running ? 'shiny' : ''}`} style={{ fontSize: '1.5rem' }}>
            {status.is_running ? '✓' : '✗'}
          </div>
        </div>
      </div>

      <div className="stat-box">
        <div className="stat-label">ESP32 Connection</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
          <span className={`status-indicator ${esp32Status.connected ? 'connected' : 'disconnected'}`}></span>
          <span style={{ color: esp32Status.connected ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            {esp32Status.connected ? `OK (${esp32Status.mode})` : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      <div className="stat-box">
        <div className="stat-label">WebSocket</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
          <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></span>
          <span style={{ color: connected ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            {connected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <div className="stat-label" style={{ marginBottom: '0.5rem' }}>System Logs</div>
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.4)', 
          border: '1px solid rgba(0, 255, 255, 0.2)',
          borderRadius: '4px',
          padding: '0.5rem',
          maxHeight: '200px',
          overflowY: 'auto',
          fontSize: '0.75rem'
        }}>
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '1rem' }}>
              Waiting for events...
            </div>
          ) : (
            logs.map((log, idx) => (
              <div key={idx} className={`log-entry ${log.type}`}>
                <span style={{ color: 'var(--text-secondary)' }}>[{log.timestamp}]</span> {log.message}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

export default StatusDisplay
