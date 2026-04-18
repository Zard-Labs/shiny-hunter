import { useState, useEffect, useCallback, useRef } from 'react'
import LiveFeed from './components/LiveFeed'
import StatisticsPanel from './components/StatisticsPanel'
import ControlPanel from './components/ControlPanel'
import HistoryTable from './components/HistoryTable'
import StateBanner from './components/StateBanner'
import CalibrationModal from './components/CalibrationModal'
import SettingsModal from './components/SettingsModal'
import CameraSelector from './components/CameraSelector'
import ESP32Config from './components/ESP32Config'
import TemplateCapturePanel from './components/TemplateCapturePanel'
import HuntSelector from './components/HuntSelector'
import TemplateLibrary from './components/TemplateLibrary'
import MacroRecordingPanel from './components/MacroRecordingPanel'
import RecordingReviewTimeline from './components/RecordingReviewTimeline'
import RecoveryLog from './components/RecoveryLog'
import useWebSocket from './hooks/useWebSocket.jsx'
import { getAutomationStatus, getStatistics, getHistory, getGameLanguage } from './services/api'
import './styles/App.css'

// Polling interval when WebSocket is disconnected (fallback only)
const FALLBACK_POLL_MS = 15000

function App() {
  const [automationStatus, setAutomationStatus] = useState({
    is_running: false,
    state: 'IDLE',
    reset_count: 0
  })
  const [statistics, setStatistics] = useState({
    encounters: 0,
    natures: {},
    genders: {},
    last_encounter: null,
    hunt_id: null,
    hunt_name: null
  })
  const [history, setHistory] = useState([])
  const [showCalibration, setShowCalibration] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showTemplateLibrary, setShowTemplateLibrary] = useState(false)
  const [showRecordingPanel, setShowRecordingPanel] = useState(false)
  const [reviewSessionId, setReviewSessionId] = useState(null)
  const [selectedHuntId, setSelectedHuntId] = useState(null) // null = active hunt
  const [gameLanguage, setGameLanguageState] = useState('en')
  const { connected, lastMessage } = useWebSocket()

  // In-flight guard to prevent overlapping requests
  const fetchingRef = useRef(false)

  // Fetch data with optional hunt filter — guarded against overlapping calls
  const fetchData = useCallback(async () => {
    if (fetchingRef.current) return // skip if already in-flight
    fetchingRef.current = true
    try {
      const [status, stats, historyData] = await Promise.all([
        getAutomationStatus(),
        getStatistics(selectedHuntId),
        getHistory(100, 0, selectedHuntId)
      ])
      setAutomationStatus(status)
      setStatistics(stats)
      setHistory(historyData.encounters || [])
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      fetchingRef.current = false
    }
  }, [selectedHuntId])

  // Fetch once on mount and when hunt changes
  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Fetch game language on mount
  useEffect(() => {
    getGameLanguage()
      .then(data => setGameLanguageState(data.language || 'en'))
      .catch(() => {})
  }, [])

  // Fallback polling — ONLY when WebSocket is disconnected
  useEffect(() => {
    if (connected) return // WebSocket provides real-time updates, no polling needed

    const interval = setInterval(fetchData, FALLBACK_POLL_MS)
    return () => clearInterval(interval)
  }, [connected, fetchData])

  // Sync data when WebSocket reconnects
  const prevConnectedRef = useRef(false)
  useEffect(() => {
    if (connected && !prevConnectedRef.current) {
      // Just reconnected — do one fetch to sync state
      fetchData()
    }
    prevConnectedRef.current = connected
  }, [connected, fetchData])

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return

    switch (lastMessage.type) {
      case 'state_update':
        setAutomationStatus(prev => ({
          ...prev,
          ...lastMessage.data
        }))
        break
      case 'encounter_detected':
      case 'shiny_found':
        fetchData()
        break
      case 'recovery_triggered':
        // Re-fetch data to update stats
        fetchData()
        break
      case 'automation_error':
        fetchData()
        break
      case 'shiny_skipped':
        fetchData()
        break
      default:
        break
    }
  }, [lastMessage, fetchData])

  // When hunt changes, re-fetch data
  const handleHuntChange = (huntId) => {
    setSelectedHuntId(huntId)
  }

  // When a new hunt is created (reset), clear the selected hunt to show the new active one
  const handleNewHunt = () => {
    setSelectedHuntId(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-title-group">
          <h1>Shiny Hunter Dashboard</h1>
          <span className="app-version">v{__APP_VERSION__}</span>
        </div>
        <div className="header-actions">
          <button
            className="settings-btn"
            onClick={() => setShowSettings(true)}
            title="Settings"
          >
            ⚙ Settings
          </button>
          <div className="connection-status">
            <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></span>
            {connected ? 'Connected' : 'Disconnected'}
          </div>
        </div>
      </header>

      <div className="main-layout">
        <div className="left-panel">
          <CameraSelector onCameraChange={fetchData} gameLanguage={gameLanguage} onLanguageChange={setGameLanguageState} />
          <ESP32Config />
          <TemplateCapturePanel />
        </div>

        <div className="center-panel">
          {/* Macro Recording Panel — floats above the live feed when recording */}
          {showRecordingPanel && (
            <MacroRecordingPanel
              onRecordingStopped={(sid) => {
                setShowRecordingPanel(false)
                setReviewSessionId(sid)
              }}
              onClose={() => setShowRecordingPanel(false)}
            />
          )}
          <LiveFeed />
          <StateBanner
            status={automationStatus}
            connected={connected}
          />
          <ControlPanel
            isRunning={automationStatus.is_running}
            monitorActive={automationStatus.continuous_monitor_active || false}
            onRefresh={fetchData}
            onCalibrate={() => setShowCalibration(true)}
            onNewHunt={handleNewHunt}
            onOpenTemplates={() => setShowTemplateLibrary(true)}
          />
        </div>

        <div className="right-panel">
          <HuntSelector
            selectedHuntId={selectedHuntId}
            onHuntChange={handleHuntChange}
          />
          <StatisticsPanel statistics={statistics} automationStatus={automationStatus} gameLanguage={gameLanguage} />
          <HistoryTable history={history} gameLanguage={gameLanguage} />
          <RecoveryLog huntId={selectedHuntId} />
        </div>
      </div>

      {showCalibration && (
        <CalibrationModal onClose={() => setShowCalibration(false)} />
      )}

      {showSettings && (
        <SettingsModal onClose={() => setShowSettings(false)} />
      )}

      {showTemplateLibrary && (
        <TemplateLibrary
          onClose={() => setShowTemplateLibrary(false)}
          onStartRecording={() => {
            setShowTemplateLibrary(false)
            setShowRecordingPanel(true)
          }}
        />
      )}

      {/* Recording Review Timeline (full-screen modal) */}
      {reviewSessionId && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.85)',
          zIndex: 1000,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: '2rem',
          overflow: 'auto',
        }}>
          <div style={{ width: '100%', maxWidth: '900px' }}>
            <RecordingReviewTimeline
              sessionId={reviewSessionId}
              onTemplateCreated={(templateId) => {
                setReviewSessionId(null)
                setShowTemplateLibrary(true)
              }}
              onClose={() => setReviewSessionId(null)}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default App
