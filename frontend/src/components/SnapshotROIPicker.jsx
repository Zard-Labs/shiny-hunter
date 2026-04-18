import { useState, useRef, useCallback, useEffect } from 'react'
import { getCalibrationSnapshotUrl } from '../services/api'

/**
 * Reusable snapshot-based ROI (Region of Interest) picker.
 *
 * Loads a snapshot image from the capture card and lets the user click
 * two corners to define a rectangular region.  Display-space coordinates
 * are automatically scaled to actual frame coordinates.
 *
 * Props:
 *   onRegionSelected({ x, y, width, height })  – called on confirm
 *   onCancel()                                  – called on close/cancel
 *   initialRegion  – optional { x, y, width, height } to pre-draw
 *   frameWidth     – actual frame width  (default 640)
 *   frameHeight    – actual frame height (default 360)
 */
function SnapshotROIPicker({
  onRegionSelected,
  onCancel,
  initialRegion = null,
  frameWidth = 640,
  frameHeight = 360,
}) {
  const [snapshotUrl, setSnapshotUrl] = useState(null)
  const [clicks, setClicks] = useState([])           // [{x,y}, {x,y}]
  const [pendingRegion, setPendingRegion] = useState(initialRegion)
  const [imageLoaded, setImageLoaded] = useState(false)
  const imgRef = useRef(null)

  // Load snapshot on mount
  useEffect(() => {
    setSnapshotUrl(`${getCalibrationSnapshotUrl()}?t=${Date.now()}`)
    // Pre-populate clicks from initialRegion so the overlay draws
    if (initialRegion) {
      const { x, y, width, height } = initialRegion
      setClicks([
        { x, y },
        { x: x + width, y: y + height },
      ])
      setPendingRegion(initialRegion)
    }
  }, [])

  const handleImageClick = useCallback(
    (e) => {
      if (!imgRef.current) return

      const rect = imgRef.current.getBoundingClientRect()
      const displayX = e.clientX - rect.left
      const displayY = e.clientY - rect.top
      const displayW = rect.width
      const displayH = rect.height

      // Scale to actual frame coordinates
      const actualX = Math.round(displayX * (frameWidth / displayW))
      const actualY = Math.round(displayY * (frameHeight / displayH))

      // Clamp
      const cx = Math.max(0, Math.min(actualX, frameWidth - 1))
      const cy = Math.max(0, Math.min(actualY, frameHeight - 1))

      if (clicks.length === 0 || clicks.length === 2) {
        // First click (or restart)
        setClicks([{ x: cx, y: cy }])
        setPendingRegion(null)
      } else if (clicks.length === 1) {
        // Second click — compute region
        const p1 = clicks[0]
        const x1 = Math.min(p1.x, cx)
        const y1 = Math.min(p1.y, cy)
        const x2 = Math.max(p1.x, cx)
        const y2 = Math.max(p1.y, cy)

        setClicks([{ x: x1, y: y1 }, { x: x2, y: y2 }])
        setPendingRegion({ x: x1, y: y1, width: x2 - x1, height: y2 - y1 })
      }
    },
    [clicks, frameWidth, frameHeight],
  )

  const handleConfirm = () => {
    if (pendingRegion && onRegionSelected) {
      onRegionSelected(pendingRegion)
    }
  }

  const handleRefresh = () => {
    setSnapshotUrl(`${getCalibrationSnapshotUrl()}?t=${Date.now()}`)
    setClicks([])
    setPendingRegion(null)
    setImageLoaded(false)
  }

  // ── Overlay rendering ─────────────────────────────────────────────────

  const renderRectOverlay = () => {
    if (clicks.length < 2 || !imgRef.current || !imageLoaded) return null

    const rect = imgRef.current.getBoundingClientRect()
    const scaleX = rect.width / frameWidth
    const scaleY = rect.height / frameHeight

    const p1 = clicks[0]
    const p2 = clicks[1]

    const left = p1.x * scaleX
    const top = p1.y * scaleY
    const width = (p2.x - p1.x) * scaleX
    const height = (p2.y - p1.y) * scaleY

    return (
      <div
        style={{
          position: 'absolute',
          left: `${left}px`,
          top: `${top}px`,
          width: `${width}px`,
          height: `${height}px`,
          background: 'rgba(0, 255, 200, 0.2)',
          border: '2px solid #00ffc8',
          pointerEvents: 'none',
          zIndex: 3,
          boxSizing: 'border-box',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: '-18px',
            left: 0,
            fontSize: '0.65rem',
            color: '#00ffc8',
            whiteSpace: 'nowrap',
            fontWeight: 'bold',
            textShadow: '0 0 4px rgba(0,0,0,0.8)',
          }}
        >
          🔍 Search Region
        </span>
      </div>
    )
  }

  const renderClickMarker = (point, index) => {
    if (!imgRef.current || !imageLoaded) return null

    const rect = imgRef.current.getBoundingClientRect()
    const scaleX = rect.width / frameWidth
    const scaleY = rect.height / frameHeight

    const left = point.x * scaleX
    const top = point.y * scaleY

    return (
      <div
        key={index}
        style={{
          position: 'absolute',
          left: `${left - 5}px`,
          top: `${top - 5}px`,
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          background: index === 0 ? '#00ffc8' : '#ff6644',
          border: '2px solid white',
          pointerEvents: 'none',
          zIndex: 4,
        }}
      />
    )
  }

  // ── Styles ────────────────────────────────────────────────────────────

  const containerStyle = {
    border: '1px solid rgba(0, 255, 200, 0.3)',
    borderRadius: '6px',
    padding: '0.75rem',
    background: 'rgba(0, 10, 30, 0.9)',
    marginTop: '0.5rem',
  }

  const btnStyle = {
    padding: '0.3rem 0.7rem',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.75rem',
    fontFamily: "'Courier New', monospace",
  }

  const btnPrimary = {
    ...btnStyle,
    background: 'rgba(0, 255, 200, 0.15)',
    color: '#00ffc8',
    border: '1px solid rgba(0, 255, 200, 0.4)',
  }

  const btnDanger = {
    ...btnStyle,
    background: 'rgba(255, 68, 68, 0.1)',
    color: '#ff4444',
    border: '1px solid rgba(255, 68, 68, 0.3)',
  }

  const btnSecondary = {
    ...btnStyle,
    background: 'rgba(255, 255, 255, 0.05)',
    color: '#aaa',
  }

  return (
    <div style={containerStyle}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.5rem',
        }}
      >
        <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#00ffc8' }}>
          📷 Draw Search Region
        </span>
        <button onClick={handleRefresh} style={btnSecondary} title="Capture new snapshot">
          🔄 Refresh
        </button>
      </div>

      <p style={{ fontSize: '0.7rem', color: '#888', margin: '0 0 0.5rem 0' }}>
        Click two corners on the image to define the search region. The template will only be
        matched within this rectangle.
      </p>

      {/* Snapshot image with click handler */}
      <div style={{ position: 'relative', display: 'inline-block', cursor: 'crosshair' }}>
        {snapshotUrl && (
          <img
            ref={imgRef}
            src={snapshotUrl}
            alt="Snapshot"
            style={{
              maxWidth: '100%',
              width: '500px',
              borderRadius: '4px',
              border: '1px solid rgba(255,255,255,0.1)',
              display: 'block',
            }}
            onClick={handleImageClick}
            onLoad={() => setImageLoaded(true)}
            draggable={false}
          />
        )}
        {/* Overlays */}
        {imageLoaded && renderRectOverlay()}
        {imageLoaded && clicks.length >= 1 && clicks.length < 2 && renderClickMarker(clicks[0], 0)}
      </div>

      {/* Coordinates display */}
      {pendingRegion && (
        <div
          style={{
            marginTop: '0.5rem',
            padding: '0.4rem',
            background: 'rgba(0, 255, 200, 0.05)',
            border: '1px solid rgba(0, 255, 200, 0.15)',
            borderRadius: '3px',
            fontSize: '0.75rem',
            fontFamily: "'Courier New', monospace",
            color: '#ccc',
          }}
        >
          X: <strong>{pendingRegion.x}</strong> &nbsp; Y: <strong>{pendingRegion.y}</strong>{' '}
          &nbsp; W: <strong>{pendingRegion.width}</strong> &nbsp; H:{' '}
          <strong>{pendingRegion.height}</strong>
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
        <button
          onClick={handleConfirm}
          disabled={!pendingRegion}
          style={{
            ...btnPrimary,
            opacity: pendingRegion ? 1 : 0.4,
            cursor: pendingRegion ? 'pointer' : 'not-allowed',
          }}
        >
          ✓ Apply Region
        </button>
        <button onClick={onCancel} style={btnDanger}>
          ✕ Cancel
        </button>
      </div>
    </div>
  )
}

export default SnapshotROIPicker
