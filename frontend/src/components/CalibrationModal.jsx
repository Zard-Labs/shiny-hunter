import { useState, useEffect, useRef, useCallback } from 'react'
import { getCurrentCalibration, saveZone, getCalibrationSnapshotUrl } from '../services/api'

// Zone display configuration
const ZONE_COLORS = {
  shiny:  { fill: 'rgba(255, 255, 0, 0.25)', stroke: '#ffff00', label: '⭐ Shiny Zone' },
  gender: { fill: 'rgba(0, 200, 255, 0.25)', stroke: '#00c8ff', label: '⚧ Gender Zone' },
  nature: { fill: 'rgba(255, 100, 255, 0.25)', stroke: '#ff64ff', label: '📖 Nature Text Zone' },
}

function CalibrationModal({ onClose }) {
  // State
  const [calibration, setCalibration] = useState(null)
  const [selectedZone, setSelectedZone] = useState('shiny')
  const [snapshotUrl, setSnapshotUrl] = useState(null)
  const [frameSize, setFrameSize] = useState({ width: 640, height: 480 })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [clicks, setClicks] = useState([])          // [{x, y}, {x, y}]
  const [pendingCoords, setPendingCoords] = useState(null) // {upper_x, upper_y, lower_x, lower_y}
  const [savedMessage, setSavedMessage] = useState(null)

  // Refs
  const imgRef = useRef(null)
  const containerRef = useRef(null)

  // ── Data Loading ────────────────────────────────────────────────────────

  const fetchCalibration = useCallback(async () => {
    try {
      const data = await getCurrentCalibration()
      setCalibration(data)
      if (data.frame_size) {
        setFrameSize(data.frame_size)
      }
    } catch (error) {
      console.error('Failed to fetch calibration:', error)
    }
  }, [])

  const captureSnapshot = useCallback(() => {
    // Append timestamp to bust cache
    setSnapshotUrl(`${getCalibrationSnapshotUrl()}?t=${Date.now()}`)
    setClicks([])
    setPendingCoords(null)
  }, [])

  useEffect(() => {
    fetchCalibration()
    captureSnapshot()
  }, [fetchCalibration, captureSnapshot])

  // ── Click Handling ──────────────────────────────────────────────────────

  const handleImageClick = (e) => {
    if (!imgRef.current) return

    const rect = imgRef.current.getBoundingClientRect()
    const displayX = e.clientX - rect.left
    const displayY = e.clientY - rect.top
    const displayW = rect.width
    const displayH = rect.height

    // Scale to actual frame coordinates
    const actualX = Math.round(displayX * (frameSize.width / displayW))
    const actualY = Math.round(displayY * (frameSize.height / displayH))

    // Clamp to frame bounds
    const x = Math.max(0, Math.min(actualX, frameSize.width - 1))
    const y = Math.max(0, Math.min(actualY, frameSize.height - 1))

    if (clicks.length === 0) {
      // First click = upper-left corner
      setClicks([{ x, y }])
      setPendingCoords(null)
      setSavedMessage(null)
    } else if (clicks.length === 1) {
      // Second click = lower-right corner
      const p1 = clicks[0]
      const upper_x = Math.min(p1.x, x)
      const upper_y = Math.min(p1.y, y)
      const lower_x = Math.max(p1.x, x)
      const lower_y = Math.max(p1.y, y)

      setClicks([{ x: upper_x, y: upper_y }, { x: lower_x, y: lower_y }])
      setPendingCoords({ upper_x, upper_y, lower_x, lower_y })
    } else {
      // Reset and start over
      setClicks([{ x, y }])
      setPendingCoords(null)
      setSavedMessage(null)
    }
  }

  // ── Save Handler ────────────────────────────────────────────────────────

  const handleSaveZone = async () => {
    if (!pendingCoords) return

    setSaving(true)
    setSavedMessage(null)
    try {
      const result = await saveZone(selectedZone, pendingCoords)
      if (result.status === 'success' || result.status === 'partial') {
        setSavedMessage({ type: 'success', text: `✅ ${result.message}` })
        // Refresh calibration data to show updated zones
        await fetchCalibration()
        // Clear pending selection
        setClicks([])
        setPendingCoords(null)
      } else {
        setSavedMessage({ type: 'error', text: `❌ ${result.message || 'Save failed'}` })
      }
    } catch (error) {
      console.error('Failed to save zone:', error)
      const msg = error.response?.data?.detail || error.message || 'Unknown error'
      setSavedMessage({ type: 'error', text: `❌ Failed to save zone: ${msg}` })
    } finally {
      setSaving(false)
    }
  }

  // ── Zone Overlay Rendering ──────────────────────────────────────────────

  const renderZoneOverlay = (zoneType, coords, isActive) => {
    if (!coords || !imgRef.current) return null

    const rect = imgRef.current.getBoundingClientRect()
    const scaleX = rect.width / frameSize.width
    const scaleY = rect.height / frameSize.height

    const left = coords.upper_x * scaleX
    const top = coords.upper_y * scaleY
    const width = (coords.lower_x - coords.upper_x) * scaleX
    const height = (coords.lower_y - coords.upper_y) * scaleY

    const colors = ZONE_COLORS[zoneType]

    return (
      <div
        key={zoneType}
        style={{
          position: 'absolute',
          left: `${left}px`,
          top: `${top}px`,
          width: `${width}px`,
          height: `${height}px`,
          background: colors.fill,
          border: `2px ${isActive ? 'solid' : 'dashed'} ${colors.stroke}`,
          pointerEvents: 'none',
          zIndex: isActive ? 3 : 2,
          boxSizing: 'border-box',
        }}
      >
        <span style={{
          position: 'absolute',
          top: '-18px',
          left: 0,
          fontSize: '0.65rem',
          color: colors.stroke,
          whiteSpace: 'nowrap',
          fontWeight: isActive ? 'bold' : 'normal',
          textShadow: '0 0 4px rgba(0,0,0,0.8)',
        }}>
          {colors.label}
        </span>
      </div>
    )
  }

  const renderClickMarker = (point, index) => {
    if (!imgRef.current) return null

    const rect = imgRef.current.getBoundingClientRect()
    const scaleX = rect.width / frameSize.width
    const scaleY = rect.height / frameSize.height

    return (
      <div
        key={`click-${index}`}
        style={{
          position: 'absolute',
          left: `${point.x * scaleX - 6}px`,
          top: `${point.y * scaleY - 6}px`,
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          background: ZONE_COLORS[selectedZone].stroke,
          border: '2px solid white',
          pointerEvents: 'none',
          zIndex: 10,
        }}
      />
    )
  }

  // ── Render ──────────────────────────────────────────────────────────────

  const currentZoneCoords = calibration?.zones?.[selectedZone]

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ minWidth: '720px', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto' }}
      >
        <h2 className="neon-text" style={{ marginBottom: '1rem' }}>
          🎯 Visual Calibration
        </h2>

        {/* Zone Type Selector */}
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-cyan)', fontSize: '0.9rem' }}>
            Select Zone to Calibrate:
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {Object.entries(ZONE_COLORS).map(([type, config]) => (
              <button
                key={type}
                onClick={() => {
                  setSelectedZone(type)
                  setClicks([])
                  setPendingCoords(null)
                  setSavedMessage(null)
                }}
                style={{
                  flex: 1,
                  padding: '0.6rem 0.5rem',
                  background: selectedZone === type ? config.fill : 'rgba(0,0,0,0.3)',
                  border: `2px solid ${selectedZone === type ? config.stroke : 'rgba(255,255,255,0.15)'}`,
                  color: selectedZone === type ? config.stroke : 'var(--text-secondary)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontFamily: 'inherit',
                  fontWeight: selectedZone === type ? 'bold' : 'normal',
                  transition: 'all 0.2s',
                }}
              >
                {config.label}
              </button>
            ))}
          </div>
        </div>

        {/* Instructions */}
        <div style={{
          padding: '0.5rem 0.75rem',
          marginBottom: '0.75rem',
          background: 'rgba(0, 255, 255, 0.05)',
          border: '1px solid rgba(0, 255, 255, 0.15)',
          borderRadius: '4px',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
          lineHeight: '1.5',
        }}>
          {clicks.length === 0 && '👆 Click the image to place the UPPER-LEFT corner of the zone'}
          {clicks.length === 1 && '👆 Click again to place the LOWER-RIGHT corner'}
          {clicks.length === 2 && pendingCoords && '✅ Zone defined! Click "Save Zone" to apply, or click the image to restart'}
        </div>

        {/* Snapshot Image with Overlays */}
        <div
          ref={containerRef}
          style={{
            position: 'relative',
            display: 'inline-block',
            width: '100%',
            marginBottom: '0.75rem',
            background: '#000',
            borderRadius: '6px',
            overflow: 'hidden',
            cursor: 'crosshair',
          }}
        >
          {snapshotUrl ? (
            <img
              ref={imgRef}
              src={snapshotUrl}
              alt="Calibration snapshot"
              onClick={handleImageClick}
              onLoad={() => {
                // Force re-render so overlays position correctly
                setClicks(prev => [...prev])
              }}
              style={{
                width: '100%',
                display: 'block',
                userSelect: 'none',
                WebkitUserDrag: 'none',
              }}
              draggable={false}
            />
          ) : (
            <div style={{
              width: '100%',
              height: '300px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-secondary)',
            }}>
              Loading snapshot...
            </div>
          )}

          {/* Saved zone overlays */}
          {imgRef.current && calibration?.zones && Object.entries(calibration.zones).map(([type, coords]) => {
            // Don't render the active zone's saved overlay if we have a pending selection
            if (type === selectedZone && pendingCoords) return null
            return renderZoneOverlay(type, coords, type === selectedZone)
          })}

          {/* Pending selection overlay */}
          {imgRef.current && pendingCoords && renderZoneOverlay(selectedZone, pendingCoords, true)}

          {/* Click markers */}
          {imgRef.current && clicks.length === 1 && renderClickMarker(clicks[0], 0)}
        </div>

        {/* Snapshot Controls */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <button
            onClick={captureSnapshot}
            style={{
              flex: 1,
              padding: '0.5rem',
              background: 'rgba(0, 255, 255, 0.1)',
              border: '1px solid rgba(0, 255, 255, 0.4)',
              color: '#00e5ff',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.75rem',
              fontFamily: 'inherit',
            }}
          >
            📸 Recapture Snapshot
          </button>
        </div>

        {/* Current Coordinates Display */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '0.75rem',
          marginBottom: '0.75rem',
        }}>
          {/* Saved coordinates */}
          <div style={{
            padding: '0.6rem',
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '4px',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
              Current Saved ({ZONE_COLORS[selectedZone].label}):
            </div>
            {currentZoneCoords ? (
              <div style={{ fontSize: '0.8rem', color: ZONE_COLORS[selectedZone].stroke, fontFamily: 'monospace' }}>
                ({currentZoneCoords.upper_x}, {currentZoneCoords.upper_y}) → ({currentZoneCoords.lower_x}, {currentZoneCoords.lower_y})
              </div>
            ) : (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Not set</div>
            )}
          </div>

          {/* Pending coordinates */}
          <div style={{
            padding: '0.6rem',
            background: pendingCoords ? 'rgba(255,255,0,0.05)' : 'rgba(0,0,0,0.3)',
            border: `1px solid ${pendingCoords ? 'rgba(255,255,0,0.3)' : 'rgba(255,255,255,0.1)'}`,
            borderRadius: '4px',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
              New Selection:
            </div>
            {pendingCoords ? (
              <div style={{ fontSize: '0.8rem', color: '#ffff00', fontFamily: 'monospace' }}>
                ({pendingCoords.upper_x}, {pendingCoords.upper_y}) → ({pendingCoords.lower_x}, {pendingCoords.lower_y})
              </div>
            ) : (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {clicks.length === 1 ? `First point: (${clicks[0].x}, ${clicks[0].y})` : 'Click image to define'}
              </div>
            )}
          </div>
        </div>

        {/* Save / Message */}
        {savedMessage && (
          <div style={{
            padding: '0.5rem 0.75rem',
            marginBottom: '0.5rem',
            background: savedMessage.type === 'success' ? 'rgba(0,255,0,0.1)' : 'rgba(255,0,0,0.1)',
            border: `1px solid ${savedMessage.type === 'success' ? 'rgba(0,255,0,0.3)' : 'rgba(255,0,0,0.3)'}`,
            borderRadius: '4px',
            fontSize: '0.8rem',
            color: savedMessage.type === 'success' ? '#00ff88' : '#ff4444',
          }}>
            {savedMessage.text}
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-primary"
            onClick={handleSaveZone}
            disabled={!pendingCoords || saving}
            style={{
              flex: 2,
              opacity: pendingCoords ? 1 : 0.4,
            }}
          >
            {saving ? 'SAVING...' : `SAVE ${selectedZone.toUpperCase()} ZONE`}
          </button>

          <button
            className="btn"
            onClick={onClose}
            style={{ flex: 1 }}
          >
            CLOSE
          </button>
        </div>

        {/* Frame Info */}
        <div style={{
          marginTop: '0.5rem',
          fontSize: '0.65rem',
          color: 'var(--text-secondary)',
          textAlign: 'center',
        }}>
          Frame: {frameSize.width}×{frameSize.height} | Crop Mode: {calibration?.crop_mode || '?'}
        </div>
      </div>
    </div>
  )
}

export default CalibrationModal
