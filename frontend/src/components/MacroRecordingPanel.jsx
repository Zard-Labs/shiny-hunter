import { useState, useEffect, useRef } from 'react'
import {
  startMacroRecording,
  stopMacroRecording,
  getMacroRecordingStatus,
  markRecordingStep,
  captureRecordingScreenshot,
  sendButtonPress,
} from '../services/api'

const BUTTONS = ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT']

function MacroRecordingPanel({ onRecordingStopped, onClose }) {
  const [recording, setRecording] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [eventCount, setEventCount] = useState(0)
  const [screenshotCount, setScreenshotCount] = useState(0)
  const [frameCount, setFrameCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stepLabel, setStepLabel] = useState('')
  const timerRef = useRef(null)
  const pollRef = useRef(null)

  // Poll recording status while recording
  useEffect(() => {
    if (recording) {
      pollRef.current = setInterval(async () => {
        try {
          const status = await getMacroRecordingStatus()
          setElapsed(status.elapsed || 0)
          setEventCount(status.event_count || 0)
          setScreenshotCount(status.screenshot_count || 0)
          setFrameCount(status.frame_count || 0)
        } catch (err) {
          // Ignore polling errors
        }
      }, 1000)
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [recording])

  const handleStart = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await startMacroRecording()
      setSessionId(result.session_id)
      setRecording(true)
      setElapsed(0)
      setEventCount(0)
      setScreenshotCount(0)
      setFrameCount(0)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to start recording')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await stopMacroRecording()
      setRecording(false)
      if (pollRef.current) clearInterval(pollRef.current)
      onRecordingStopped?.(result.session_id)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to stop recording')
    } finally {
      setLoading(false)
    }
  }

  const handleMarkStep = async () => {
    try {
      await markRecordingStep(stepLabel || null)
      setStepLabel('')
    } catch (err) {
      console.error('Failed to mark step:', err)
    }
  }

  const handleScreenshot = async () => {
    try {
      await captureRecordingScreenshot()
    } catch (err) {
      console.error('Failed to capture screenshot:', err)
    }
  }

  const handleButtonPress = async (button) => {
    try {
      await sendButtonPress(button)
    } catch (err) {
      console.error(`Failed to press ${button}:`, err)
    }
  }

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div style={{
      background: 'var(--bg-secondary, #1a1a2e)',
      border: '2px solid var(--accent-red, #ff4444)',
      borderRadius: '8px',
      padding: '1rem',
      marginBottom: '1rem',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0.75rem',
      }}>
        <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          🎬 Macro Recording
          {recording && (
            <span style={{
              display: 'inline-block',
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: '#ff4444',
              animation: 'pulse 1s infinite',
            }} />
          )}
        </h3>
        {!recording && (
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '1.2rem',
            }}
            title="Close"
          >×</button>
        )}
      </div>

      {error && (
        <div style={{
          background: 'rgba(255, 68, 68, 0.15)',
          border: '1px solid rgba(255, 68, 68, 0.3)',
          borderRadius: '4px',
          padding: '0.5rem',
          marginBottom: '0.75rem',
          fontSize: '0.8rem',
          color: '#ff6666',
        }}>
          {error}
        </div>
      )}

      {/* Recording status */}
      {recording && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '0.5rem',
          marginBottom: '0.75rem',
          fontSize: '0.8rem',
        }}>
          <div style={statBox}>
            <div style={statLabel}>⏱ Time</div>
            <div style={statValue}>{formatTime(elapsed)}</div>
          </div>
          <div style={statBox}>
            <div style={statLabel}>🎮 Presses</div>
            <div style={statValue}>{eventCount}</div>
          </div>
          <div style={statBox}>
            <div style={statLabel}>📸 Shots</div>
            <div style={statValue}>{screenshotCount}</div>
          </div>
          <div style={statBox}>
            <div style={statLabel}>🎞 Frames</div>
            <div style={statValue}>{frameCount}</div>
          </div>
        </div>
      )}

      {/* Main controls */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
        {!recording ? (
          <button
            onClick={handleStart}
            disabled={loading}
            style={{
              ...btnStyle,
              background: 'linear-gradient(135deg, #ff4444, #cc0000)',
              flex: 1,
            }}
          >
            {loading ? '⏳ Starting...' : '⏺ Start Recording'}
          </button>
        ) : (
          <>
            <button
              onClick={handleStop}
              disabled={loading}
              style={{
                ...btnStyle,
                background: 'linear-gradient(135deg, #666, #444)',
                flex: 1,
              }}
            >
              {loading ? '⏳ Stopping...' : '⏹ Stop Recording'}
            </button>
            <button
              onClick={handleScreenshot}
              style={{
                ...btnStyle,
                background: 'linear-gradient(135deg, #4488ff, #2266cc)',
              }}
              title="Capture extra screenshot"
            >
              📸
            </button>
          </>
        )}
      </div>

      {/* Step marker */}
      {recording && (
        <div style={{
          display: 'flex',
          gap: '0.5rem',
          marginBottom: '0.75rem',
        }}>
          <input
            type="text"
            placeholder="Step label (optional)"
            value={stepLabel}
            onChange={(e) => setStepLabel(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleMarkStep()}
            style={{
              flex: 1,
              padding: '0.4rem 0.6rem',
              background: 'var(--bg-tertiary, #252540)',
              border: '1px solid rgba(255,255,255,0.1)',
              color: 'var(--text-primary, #e0e0e0)',
              borderRadius: '4px',
              fontSize: '0.8rem',
            }}
          />
          <button
            onClick={handleMarkStep}
            style={{
              ...btnStyle,
              background: 'linear-gradient(135deg, #44cc88, #22aa66)',
              whiteSpace: 'nowrap',
            }}
          >
            ✂️ Mark Step
          </button>
        </div>
      )}

      {/* D-Pad + buttons during recording */}
      {recording && (
        <div>
          <div style={{
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
            marginBottom: '0.5rem',
          }}>
            Press buttons below — each press is recorded with a screenshot:
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '0.3rem',
          }}>
            {BUTTONS.map((btn) => (
              <button
                key={btn}
                onClick={() => handleButtonPress(btn)}
                style={{
                  padding: '0.5rem',
                  background: 'var(--bg-tertiary, #252540)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: 'var(--text-primary, #e0e0e0)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  fontWeight: 'bold',
                  fontFamily: "'Courier New', monospace",
                }}
              >
                {btn}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Instructions when not recording */}
      {!recording && !error && (
        <div style={{
          fontSize: '0.75rem',
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
        }}>
          <p style={{ margin: '0 0 0.3rem 0' }}>
            📋 <strong>How it works:</strong>
          </p>
          <ol style={{ margin: 0, paddingLeft: '1.2rem' }}>
            <li>Click <strong>Start Recording</strong> to begin</li>
            <li>Press game buttons — each press is logged with a screenshot</li>
            <li>Optionally mark step boundaries with <strong>Mark Step</strong></li>
            <li>Click <strong>Stop</strong> to finish</li>
            <li>Review the timeline, pick template images, and generate your template</li>
          </ol>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}

const statBox = {
  background: 'rgba(0,0,0,0.3)',
  borderRadius: '4px',
  padding: '0.4rem',
  textAlign: 'center',
}

const statLabel = {
  color: 'var(--text-secondary, #888)',
  fontSize: '0.65rem',
  marginBottom: '0.2rem',
}

const statValue = {
  color: 'var(--text-primary, #e0e0e0)',
  fontSize: '1rem',
  fontWeight: 'bold',
  fontFamily: "'Courier New', monospace",
}

const btnStyle = {
  padding: '0.5rem 1rem',
  border: 'none',
  borderRadius: '6px',
  color: '#fff',
  fontWeight: 'bold',
  cursor: 'pointer',
  fontSize: '0.85rem',
}

export default MacroRecordingPanel
