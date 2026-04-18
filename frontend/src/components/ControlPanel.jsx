import { useState, useEffect } from 'react'
import {
  startAutomation,
  stopAutomation,
  sendButtonPress,
  resetStatistics,
  getAutomationTemplates,
  activateAutomationTemplate,
  toggleContinuousMonitor,
} from '../services/api'

function ControlPanel({ isRunning, monitorActive, onRefresh, onCalibrate, onNewHunt, onOpenTemplates }) {
  const [loading, setLoading] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [monitorToggling, setMonitorToggling] = useState(false)
  const [templates, setTemplates] = useState([])
  const [activeTemplate, setActiveTemplate] = useState(null)

  useEffect(() => {
    fetchTemplates()
  }, [])

  const fetchTemplates = async () => {
    try {
      const data = await getAutomationTemplates()
      setTemplates(data)
      const active = data.find((t) => t.is_active)
      setActiveTemplate(active || null)
    } catch (err) {
      console.error('Failed to fetch templates:', err)
    }
  }

  const handleTemplateChange = async (e) => {
    const id = e.target.value
    if (!id) return
    try {
      await activateAutomationTemplate(id)
      await fetchTemplates()
    } catch (err) {
      alert(`Failed to activate: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleStart = async () => {
    setLoading(true)
    try {
      await startAutomation()
      onRefresh()
    } catch (error) {
      console.error('Failed to start automation:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      await stopAutomation()
      onRefresh()
    } catch (error) {
      console.error('Failed to stop automation:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleButtonPress = async (button) => {
    try {
      await sendButtonPress(button)
    } catch (error) {
      console.error(`Failed to press ${button}:`, error)
    }
  }

  const handleNewHunt = async () => {
    const confirmed = window.confirm(
      'Start a new hunt?\n\n' +
      'This will archive the current hunt\'s stats and create a fresh one.\n' +
      'All previous data is preserved and viewable via the hunt selector.'
    )
    if (!confirmed) return

    setResetting(true)
    try {
      const result = await resetStatistics()
      console.log('New hunt started:', result)
      if (onNewHunt) onNewHunt()
      onRefresh()
    } catch (error) {
      console.error('Failed to start new hunt:', error)
      if (error.response?.status === 409) {
        alert('Cannot reset while automation is running. Stop automation first.')
      }
    } finally {
      setResetting(false)
    }
  }

  const handleMonitorToggle = async () => {
    setMonitorToggling(true)
    try {
      await toggleContinuousMonitor(!monitorActive)
      onRefresh()
    } catch (error) {
      console.error('Failed to toggle monitor:', error)
      if (error.response?.status === 409) {
        alert('Automation must be running to toggle the shiny monitor.')
      }
    } finally {
      setMonitorToggling(false)
    }
  }

  return (
    <div className="panel control-panel-center">
      <h2 className="panel-title">⚡ Control Panel</h2>

      {/* Row 1: Template Selector + Start/Stop */}
      <div className="cp-automation-row">
        <div className="cp-template-group">
          <div className="cp-template-header">
            <label className="cp-template-label">Active Template</label>
            <button onClick={onOpenTemplates} className="cp-manage-btn">📚 Manage</button>
          </div>
          <select
            value={activeTemplate?.id || ''}
            onChange={handleTemplateChange}
            disabled={isRunning}
            className="cp-template-select"
          >
            {templates.length === 0 && <option value="">Loading...</option>}
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.pokemon_name})
              </option>
            ))}
          </select>
          {activeTemplate && (
            <div className="cp-template-meta">
              {activeTemplate.game} • {activeTemplate.step_count} steps • v{activeTemplate.version}
            </div>
          )}
        </div>

        <div className="cp-start-stop">
          {!isRunning ? (
            <button
              className="btn btn-primary cp-big-btn"
              onClick={handleStart}
              disabled={loading}
            >
              {loading ? 'STARTING...' : '▶ START'}
            </button>
          ) : (
            <button
              className="btn btn-danger cp-big-btn"
              onClick={handleStop}
              disabled={loading}
            >
              {loading ? 'STOPPING...' : '⏹ STOP'}
            </button>
          )}
        </div>
      </div>

      {/* Shiny Monitor Toggle — always visible for standalone testing */}
      {(
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.5rem 0.75rem',
          marginBottom: '0.75rem',
          background: monitorActive
            ? 'rgba(0, 255, 136, 0.08)'
            : 'rgba(255, 255, 255, 0.03)',
          border: monitorActive
            ? '1px solid rgba(0, 255, 136, 0.25)'
            : '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '6px',
          transition: 'all 0.2s ease',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1rem' }}>🔍</span>
            <div>
              <div style={{
                fontSize: '0.8rem',
                fontWeight: 'bold',
                color: monitorActive ? 'var(--accent-green, #00ff88)' : 'var(--text-secondary)',
              }}>
                Shiny Monitor
              </div>
              <div style={{
                fontSize: '0.65rem',
                color: 'var(--text-secondary)',
              }}>
                {monitorActive ? 'Continuously scanning for shiny sparkles' : 'Background sparkle detection off'}
              </div>
            </div>
          </div>
          <button
            onClick={handleMonitorToggle}
            disabled={monitorToggling}
            style={{
              padding: '0.35rem 0.75rem',
              fontSize: '0.75rem',
              fontWeight: 'bold',
              fontFamily: 'inherit',
              borderRadius: '4px',
              cursor: monitorToggling ? 'wait' : 'pointer',
              border: monitorActive
                ? '1px solid rgba(255, 100, 100, 0.4)'
                : '1px solid rgba(0, 255, 136, 0.4)',
              background: monitorActive
                ? 'rgba(255, 100, 100, 0.1)'
                : 'rgba(0, 255, 136, 0.1)',
              color: monitorActive
                ? '#ff6464'
                : 'var(--accent-green, #00ff88)',
              transition: 'all 0.2s ease',
            }}
          >
            {monitorToggling ? '...' : monitorActive ? 'DISABLE' : 'ENABLE'}
          </button>
        </div>
      )}

      {/* Row 2: Manual Controls - horizontal layout */}
      <div className="cp-manual-row">
        {/* D-Pad */}
        <div className="cp-dpad">
          <div className="cp-dpad-grid">
            <div />
            <button className="btn-control cp-ctrl-sm" onClick={() => handleButtonPress('UP')} disabled={isRunning}>▲</button>
            <div />
            <button className="btn-control cp-ctrl-sm" onClick={() => handleButtonPress('LEFT')} disabled={isRunning}>◄</button>
            <button className="btn-control cp-ctrl-sm" onClick={() => handleButtonPress('DOWN')} disabled={isRunning}>▼</button>
            <button className="btn-control cp-ctrl-sm" onClick={() => handleButtonPress('RIGHT')} disabled={isRunning}>►</button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="cp-action-btns">
          <button className="btn-control cp-ctrl-sm" onClick={() => handleButtonPress('A')} disabled={isRunning}>A</button>
          <button className="btn-control cp-ctrl-sm" onClick={() => handleButtonPress('B')} disabled={isRunning}>B</button>
          <button className="btn-control cp-ctrl-sm cp-ctrl-wide" onClick={() => handleButtonPress('START')} disabled={isRunning}>START</button>
          <button className="btn-control cp-ctrl-sm cp-ctrl-wide" onClick={() => handleButtonPress('SELECT')} disabled={isRunning}>SELECT</button>
        </div>

        {/* Utility Buttons */}
        <div className="cp-utility-btns">
          <button className="btn btn-danger cp-util-btn" onClick={() => handleButtonPress('RESET')} disabled={isRunning}>
            SOFT RESET
          </button>
          <button className="btn btn-secondary cp-util-btn" onClick={onCalibrate}>
            CALIBRATE
          </button>
          <button className="btn btn-new-hunt cp-util-btn" onClick={handleNewHunt} disabled={isRunning || resetting}>
            {resetting ? 'CREATING...' : 'NEW HUNT'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ControlPanel
