import { useState } from 'react'
import { startAutomation, stopAutomation, sendButtonPress, resetStatistics } from '../services/api'

function ControlPanel({ isRunning, onRefresh, onCalibrate, onNewHunt }) {
  const [loading, setLoading] = useState(false)
  const [resetting, setResetting] = useState(false)

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

  return (
    <div className="panel control-panel">
      <h2 className="panel-title">⚡ Control Panel</h2>
      
      <div className="control-section">
        <h3 style={{ fontSize: '1rem', color: 'var(--accent-magenta)', marginBottom: '1rem' }}>
          AUTOMATION
        </h3>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
          {!isRunning ? (
            <button 
              className="btn btn-primary" 
              onClick={handleStart}
              disabled={loading}
              style={{ flex: 1 }}
            >
              {loading ? 'STARTING...' : '▶ START'}
            </button>
          ) : (
            <button 
              className="btn btn-danger" 
              onClick={handleStop}
              disabled={loading}
              style={{ flex: 1 }}
            >
              {loading ? 'STOPPING...' : '⏹ STOP'}
            </button>
          )}
        </div>
      </div>

      <div className="control-section">
        <h3 style={{ fontSize: '1rem', color: 'var(--accent-magenta)', marginBottom: '1rem' }}>
          MANUAL CONTROLS
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
          <div></div>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('UP')}
            disabled={isRunning}
          >
            ▲
          </button>
          <div></div>
          
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('LEFT')}
            disabled={isRunning}
          >
            ◄
          </button>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('DOWN')}
            disabled={isRunning}
          >
            ▼
          </button>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('RIGHT')}
            disabled={isRunning}
          >
            ►
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('A')}
            disabled={isRunning}
          >
            A
          </button>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('B')}
            disabled={isRunning}
          >
            B
          </button>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('START')}
            disabled={isRunning}
          >
            START
          </button>
          <button 
            className="btn-control" 
            onClick={() => handleButtonPress('SELECT')}
            disabled={isRunning}
          >
            SELECT
          </button>
        </div>

        <button 
          className="btn btn-danger" 
          onClick={() => handleButtonPress('RESET')}
          disabled={isRunning}
          style={{ width: '100%', marginBottom: '1rem' }}
        >
          SOFT RESET
        </button>
      </div>

      <div className="control-section">
        <button 
          className="btn btn-secondary" 
          onClick={onCalibrate}
          style={{ width: '100%', marginBottom: '0.5rem' }}
        >
          CALIBRATE
        </button>
        
        <button 
          className="btn btn-new-hunt"
          onClick={handleNewHunt}
          disabled={isRunning || resetting}
          style={{ width: '100%' }}
        >
          {resetting ? 'CREATING...' : 'NEW HUNT (RESET STATS)'}
        </button>
      </div>

      <style>{`
        .control-section {
          margin-bottom: 1.5rem;
        }

        .btn-control {
          padding: 1rem;
          background: rgba(0, 255, 255, 0.05);
          border: 1px solid var(--accent-cyan);
          color: var(--accent-cyan);
          font-family: 'Courier New', monospace;
          font-size: 1.2rem;
          font-weight: bold;
          cursor: pointer;
          border-radius: 4px;
          transition: all 0.2s ease;
        }

        .btn-control:hover:not(:disabled) {
          background: rgba(0, 255, 255, 0.2);
          box-shadow: 0 0 15px rgba(0, 255, 255, 0.5);
          transform: scale(1.05);
        }

        .btn-control:active:not(:disabled) {
          transform: scale(0.95);
        }

        .btn-control:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }

        .btn-new-hunt {
          padding: 0.7rem 1rem;
          background: rgba(255, 165, 0, 0.1);
          border: 1px solid #ff8c00;
          color: #ff8c00;
          font-family: 'Courier New', monospace;
          font-size: 0.85rem;
          font-weight: bold;
          cursor: pointer;
          border-radius: 4px;
          transition: all 0.2s ease;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .btn-new-hunt:hover:not(:disabled) {
          background: rgba(255, 165, 0, 0.25);
          box-shadow: 0 0 15px rgba(255, 165, 0, 0.4);
        }

        .btn-new-hunt:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  )
}

export default ControlPanel
