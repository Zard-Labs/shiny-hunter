import { useEffect, useState, useRef } from 'react'
import { getESP32Status } from '../services/api'

const ESP32_POLL_MS = 30000

const STEP_TYPE_ICONS = {
  'navigate':           '🧭',
  'timed_wait':         '⏳',
  'shiny_check':        '🔍',
  'battle_shiny_check': '⚔️',
}

function StateBanner({ status, connected }) {
  const [esp32Status, setEsp32Status] = useState({ connected: false, mode: 'unknown' })
  const fetchingRef = useRef(false)

  useEffect(() => {
    fetchESP32Status()
    const interval = setInterval(fetchESP32Status, ESP32_POLL_MS)
    return () => clearInterval(interval)
  }, [])

  const fetchESP32Status = async () => {
    if (fetchingRef.current) return
    fetchingRef.current = true
    try {
      const data = await getESP32Status()
      setEsp32Status(data)
    } catch {
      setEsp32Status({ connected: false, mode: 'unknown' })
    } finally {
      fetchingRef.current = false
    }
  }

  const stateKey = status.state || 'IDLE'
  const isShiny = stateKey === 'SHINY_FOUND'
  const isRunning = status.is_running
  const hasStepInfo = status.current_step_index >= 0 && status.total_steps > 0

  // Derive display label: use step_display_name if available, else raw state
  const stateLabel = status.step_display_name || stateKey
  const stepType = status.step_type
  const stepIcon = STEP_TYPE_ICONS[stepType] || (isRunning ? '🔄' : '⏸️')

  return (
    <div className={`state-banner ${isShiny ? 'state-banner--shiny' : ''}`}>
      {/* Current State - prominent */}
      <div className="state-banner__state">
        <span className="state-banner__emoji">{isShiny ? '✨' : stepIcon}</span>
        <span className="state-banner__label" style={{
          color: isShiny
            ? 'var(--accent-yellow)'
            : isRunning
              ? 'var(--accent-cyan)'
              : 'var(--text-secondary)'
        }}>
          {isShiny ? 'SHINY FOUND!' : stateKey}
        </span>
        {isRunning && (
          <span className="state-banner__pulse" />
        )}
      </div>

      {/* Step info — shown when automation is running with a loaded template */}
      {isRunning && hasStepInfo && (
        <div className="state-banner__step-info">
          <span className="state-banner__step-number">
            Step {status.current_step_index + 1}/{status.total_steps}
          </span>
          <span className="state-banner__step-name">
            {stateLabel}
          </span>
        </div>
      )}

      {/* Stats */}
      <div className="state-banner__stats">
        <div className="state-banner__stat">
          <span className="state-banner__stat-label">Resets</span>
          <span className="state-banner__stat-value">{status.reset_count || 0}</span>
        </div>
      </div>

      {/* Connection indicators */}
      <div className="state-banner__connections">
        <div className="state-banner__conn" title={`WebSocket: ${connected ? 'Connected' : 'Disconnected'}`}>
          <span className={`state-banner__dot ${connected ? 'state-banner__dot--ok' : 'state-banner__dot--err'}`} />
          <span className="state-banner__conn-label">WS</span>
        </div>
        <div className="state-banner__conn" title={`ESP32: ${esp32Status.connected ? 'Connected' : 'Disconnected'}`}>
          <span className={`state-banner__dot ${esp32Status.connected ? 'state-banner__dot--ok' : 'state-banner__dot--err'}`} />
          <span className="state-banner__conn-label">ESP32</span>
        </div>
        <div className="state-banner__conn" title={`Shiny Monitor: ${status.continuous_monitor_active ? 'Active' : 'Off'}`}>
          <span className={`state-banner__dot ${status.continuous_monitor_active ? 'state-banner__dot--ok' : 'state-banner__dot--off'}`} />
          <span className="state-banner__conn-label">MON</span>
        </div>
      </div>
    </div>
  )
}

export default StateBanner
