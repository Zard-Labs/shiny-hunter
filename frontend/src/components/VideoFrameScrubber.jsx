import { useState, useEffect, useRef, useCallback } from 'react'
import { getRecordingFrameUrl } from '../services/api'

/**
 * Frame-by-frame video scrubber.
 *
 * Loads individual frames from the backend on demand — no video player
 * or codec needed.  Button press events are shown as markers on the
 * timeline slider.
 */
function VideoFrameScrubber({
  sessionId,
  totalFrames,
  fps = 10,
  events = [],
  onFrameSelect,
  selectedFrame = 0,
}) {
  const [currentFrame, setCurrentFrame] = useState(selectedFrame)
  const [frameUrl, setFrameUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const imgRef = useRef(null)
  const sliderRef = useRef(null)
  const debounceRef = useRef(null)

  // Preload frame when currentFrame changes (debounced)
  useEffect(() => {
    if (!sessionId || totalFrames === 0) return

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const url = getRecordingFrameUrl(sessionId, currentFrame)
      setFrameUrl(url)
      setLoading(true)
    }, 50) // 50ms debounce for smooth scrubbing

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [sessionId, currentFrame, totalFrames])

  // Notify parent of frame selection
  useEffect(() => {
    onFrameSelect?.(currentFrame)
  }, [currentFrame])

  const handleSliderChange = (e) => {
    setCurrentFrame(parseInt(e.target.value, 10))
  }

  const stepFrame = useCallback((delta) => {
    setCurrentFrame((prev) => {
      const next = prev + delta
      return Math.max(0, Math.min(totalFrames - 1, next))
    })
  }, [totalFrames])

  // Keyboard navigation
  useEffect(() => {
    const handleKey = (e) => {
      if (e.target.tagName === 'INPUT' && e.target.type !== 'range') return
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        stepFrame(e.shiftKey ? -10 : -1)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        stepFrame(e.shiftKey ? 10 : 1)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [stepFrame])

  const formatTimestamp = (frame) => {
    const seconds = frame / fps
    const m = Math.floor(seconds / 60)
    const s = (seconds % 60).toFixed(1)
    return `${m}:${s.padStart(4, '0')}`
  }

  // Compute marker positions for events on the slider
  const eventMarkers = events
    .filter((e) => e.event_type === 'button_press' || e.event_type === 'step_marker')
    .map((e) => ({
      frame: e.frame_number,
      position: totalFrames > 0 ? (e.frame_number / totalFrames) * 100 : 0,
      type: e.event_type,
      button: e.button,
      label: e.label,
    }))

  const jumpToEvent = (frameNum) => {
    setCurrentFrame(Math.max(0, Math.min(totalFrames - 1, frameNum)))
  }

  return (
    <div style={{ width: '100%' }}>
      {/* Frame display */}
      <div style={{
        position: 'relative',
        background: '#000',
        borderRadius: '6px',
        overflow: 'hidden',
        marginBottom: '0.5rem',
        aspectRatio: '4/3',
        maxHeight: '360px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {frameUrl ? (
          <img
            ref={imgRef}
            src={frameUrl}
            alt={`Frame ${currentFrame}`}
            onLoad={() => setLoading(false)}
            onError={() => setLoading(false)}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
              opacity: loading ? 0.5 : 1,
              transition: 'opacity 0.15s',
            }}
          />
        ) : (
          <span style={{ color: '#666', fontSize: '0.8rem' }}>No frames</span>
        )}

        {/* Frame info overlay */}
        <div style={{
          position: 'absolute',
          bottom: '8px',
          left: '8px',
          background: 'rgba(0, 0, 0, 0.7)',
          color: '#fff',
          padding: '3px 8px',
          borderRadius: '4px',
          fontSize: '0.7rem',
          fontFamily: "'Courier New', monospace",
        }}>
          Frame {currentFrame} / {totalFrames - 1} &nbsp;|&nbsp; {formatTimestamp(currentFrame)}
        </div>
      </div>

      {/* Slider with event markers */}
      <div style={{ position: 'relative', marginBottom: '0.5rem' }}>
        {/* Event markers behind the slider */}
        <div style={{
          position: 'absolute',
          top: '0',
          left: '0',
          right: '0',
          height: '20px',
          pointerEvents: 'none',
          zIndex: 1,
        }}>
          {eventMarkers.map((marker, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: `${marker.position}%`,
                top: '2px',
                width: marker.type === 'step_marker' ? '3px' : '4px',
                height: marker.type === 'step_marker' ? '16px' : '8px',
                background: marker.type === 'step_marker' ? '#44cc88' : '#ffaa00',
                borderRadius: marker.type === 'step_marker' ? '0' : '50%',
                transform: 'translateX(-50%)',
                pointerEvents: 'auto',
                cursor: 'pointer',
                zIndex: 2,
              }}
              title={
                marker.type === 'step_marker'
                  ? `Step: ${marker.label || 'boundary'}`
                  : `${marker.button} press`
              }
              onClick={(e) => {
                e.stopPropagation()
                jumpToEvent(marker.frame)
              }}
            />
          ))}
        </div>

        <input
          ref={sliderRef}
          type="range"
          min={0}
          max={Math.max(0, totalFrames - 1)}
          value={currentFrame}
          onChange={handleSliderChange}
          style={{
            width: '100%',
            height: '20px',
            cursor: 'pointer',
            accentColor: '#ff4444',
          }}
        />
      </div>

      {/* Controls */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        justifyContent: 'center',
      }}>
        <button onClick={() => setCurrentFrame(0)} style={navBtn} title="First frame">⏮</button>
        <button onClick={() => stepFrame(-10)} style={navBtn} title="-10 frames">⏪</button>
        <button onClick={() => stepFrame(-1)} style={navBtn} title="Previous frame">◀</button>
        <button onClick={() => stepFrame(1)} style={navBtn} title="Next frame">▶</button>
        <button onClick={() => stepFrame(10)} style={navBtn} title="+10 frames">⏩</button>
        <button onClick={() => setCurrentFrame(totalFrames - 1)} style={navBtn} title="Last frame">⏭</button>
      </div>

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: '1rem',
        justifyContent: 'center',
        marginTop: '0.4rem',
        fontSize: '0.65rem',
        color: 'var(--text-secondary, #888)',
      }}>
        <span>
          <span style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#ffaa00',
            marginRight: '3px',
            verticalAlign: 'middle',
          }} />
          Button press
        </span>
        <span>
          <span style={{
            display: 'inline-block',
            width: '3px',
            height: '12px',
            background: '#44cc88',
            marginRight: '3px',
            verticalAlign: 'middle',
          }} />
          Step marker
        </span>
        <span>← → Arrow keys to step</span>
      </div>
    </div>
  )
}

const navBtn = {
  padding: '0.3rem 0.6rem',
  background: 'var(--bg-tertiary, #252540)',
  border: '1px solid rgba(255,255,255,0.15)',
  color: 'var(--text-primary, #e0e0e0)',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.85rem',
}

export default VideoFrameScrubber
