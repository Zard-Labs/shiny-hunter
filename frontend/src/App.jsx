import { useState, useEffect, useCallback } from 'react'
import LiveFeed from './components/LiveFeed'
import StatisticsPanel from './components/StatisticsPanel'
import ControlPanel from './components/ControlPanel'
import HistoryTable from './components/HistoryTable'
import StatusDisplay from './components/StatusDisplay'
import CalibrationModal from './components/CalibrationModal'
import CameraSelector from './components/CameraSelector'
import TemplateCapturePanel from './components/TemplateCapturePanel'
import HuntSelector from './components/HuntSelector'
import useWebSocket from './hooks/useWebSocket.jsx'
import { getAutomationStatus, getStatistics, getHistory } from './services/api'
import './styles/App.css'

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
  const [selectedHuntId, setSelectedHuntId] = useState(null) // null = active hunt
  const { connected, lastMessage } = useWebSocket()

  // Fetch data with optional hunt filter
  const fetchData = useCallback(async () => {
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
    }
  }, [selectedHuntId])

  // Fetch initial data and poll
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [fetchData])

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
        <h1>Shiny Hunter Dashboard</h1>
        <div className="connection-status">
          <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></span>
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      <div className="main-layout">
        <div className="left-panel">
          <CameraSelector onCameraChange={fetchData} />
          <TemplateCapturePanel />
          <ControlPanel
            isRunning={automationStatus.is_running}
            onRefresh={fetchData}
            onCalibrate={() => setShowCalibration(true)}
            onNewHunt={handleNewHunt}
          />
          <StatusDisplay
            status={automationStatus}
            connected={connected}
          />
        </div>

        <div className="center-panel">
          <LiveFeed />
        </div>

        <div className="right-panel">
          <HuntSelector
            selectedHuntId={selectedHuntId}
            onHuntChange={handleHuntChange}
          />
          <StatisticsPanel statistics={statistics} />
          <HistoryTable history={history} />
        </div>
      </div>

      {showCalibration && (
        <CalibrationModal onClose={() => setShowCalibration(false)} />
      )}
    </div>
  )
}

export default App
