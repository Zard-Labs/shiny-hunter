import { useEffect, useRef, useState, useCallback } from 'react'
import useWebSocket from '../hooks/useWebSocket.jsx'

function LiveFeed() {
  const canvasRef = useRef(null)
  const { videoFrame, annotations } = useWebSocket()
  const [fps, setFps] = useState(0)
  const fpsCounter = useRef(0)
  const fpsInterval = useRef(null)
  // Reuse a single Image object instead of creating new one per frame
  const imgRef = useRef(null)
  // Track previous blob URL to revoke and avoid memory leaks
  const prevUrlRef = useRef(null)
  // Cache canvas dimensions to avoid unnecessary layout reflow
  const canvasSizeRef = useRef({ width: 0, height: 0 })
  // Use requestAnimationFrame for smooth rendering
  const rafRef = useRef(null)
  const pendingFrameRef = useRef(null)

  // Initialize reusable Image object
  useEffect(() => {
    imgRef.current = new Image()
    return () => {
      imgRef.current = null
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current)
        prevUrlRef.current = null
      }
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [])

  // FPS counter
  useEffect(() => {
    fpsInterval.current = setInterval(() => {
      setFps(fpsCounter.current)
      fpsCounter.current = 0
    }, 1000)

    return () => {
      if (fpsInterval.current) {
        clearInterval(fpsInterval.current)
      }
    }
  }, [])

  // Render frame to canvas using requestAnimationFrame
  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img || !img.complete || img.naturalWidth === 0) return

    const ctx = canvas.getContext('2d')

    // Only resize canvas when dimensions actually change
    if (canvasSizeRef.current.width !== img.naturalWidth ||
        canvasSizeRef.current.height !== img.naturalHeight) {
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      canvasSizeRef.current = { width: img.naturalWidth, height: img.naturalHeight }
    }

    ctx.drawImage(img, 0, 0)

    // Draw detection zones from annotations (sent separately at lower frequency)
    if (annotations) {
      if (annotations.shiny_zone) {
        const zone = annotations.shiny_zone
        const ux = zone.upper_x ?? zone.ux
        const uy = zone.upper_y ?? zone.uy
        const lx = zone.lower_x ?? zone.lx
        const ly = zone.lower_y ?? zone.ly
        
        if (ux !== undefined && uy !== undefined && lx !== undefined && ly !== undefined) {
          ctx.strokeStyle = '#00ff00'
          ctx.lineWidth = 2
          ctx.strokeRect(ux, uy, lx - ux, ly - uy)
          ctx.fillStyle = 'rgba(0, 255, 0, 0.1)'
          ctx.fillRect(ux, uy, lx - ux, ly - uy)
          
          ctx.fillStyle = '#00ff00'
          ctx.font = '12px Courier New'
          ctx.fillText('SHINY ZONE', ux, uy - 5)
        }
      }

      if (annotations.gender_zone) {
        const zone = annotations.gender_zone
        const ux = zone.upper_x ?? zone.ux
        const uy = zone.upper_y ?? zone.uy
        const lx = zone.lower_x ?? zone.lx
        const ly = zone.lower_y ?? zone.ly
        
        if (ux !== undefined && uy !== undefined && lx !== undefined && ly !== undefined) {
          ctx.strokeStyle = '#ff00ff'
          ctx.lineWidth = 2
          ctx.strokeRect(ux, uy, lx - ux, ly - uy)
          ctx.fillStyle = 'rgba(255, 0, 255, 0.1)'
          ctx.fillRect(ux, uy, lx - ux, ly - uy)
          
          ctx.fillStyle = '#ff00ff'
          ctx.font = '12px Courier New'
          ctx.fillText('GENDER ZONE', ux, uy - 5)
        }
      }
    }

    fpsCounter.current++
  }, [annotations])

  // Handle new video frame (Blob from binary WebSocket)
  useEffect(() => {
    if (!videoFrame || !imgRef.current) return

    // Create object URL from Blob
    const url = URL.createObjectURL(videoFrame)

    // Set up onload to render when image is decoded
    imgRef.current.onload = () => {
      // Revoke previous URL to free memory
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current)
      }
      prevUrlRef.current = url

      // Use requestAnimationFrame for optimal render timing
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
      rafRef.current = requestAnimationFrame(renderFrame)
    }

    imgRef.current.src = url
  }, [videoFrame, renderFrame])

  return (
    <div className="panel live-feed">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 className="panel-title" style={{ marginBottom: 0 }}>📹 Live Feed</h2>
        <div className="stat-box" style={{ 
          display: 'inline-block', 
          padding: '0.5rem 1rem', 
          marginBottom: 0,
          background: 'rgba(0, 0, 0, 0.5)' 
        }}>
          <span className="neon-text">{fps} FPS</span>
        </div>
      </div>
      
      <div style={{ 
        position: 'relative', 
        background: '#000',
        borderRadius: '4px',
        overflow: 'hidden',
        border: '2px solid var(--accent-cyan)',
        boxShadow: '0 0 30px rgba(0, 255, 255, 0.3)'
      }}>
        <canvas 
          ref={canvasRef}
          style={{ 
            width: '100%', 
            height: 'auto',
            display: 'block'
          }}
        />
        {!videoFrame && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
            color: 'var(--text-secondary)'
          }}>
            <div className="loading" style={{ margin: '0 auto 1rem' }}></div>
            <div>Waiting for video feed...</div>
          </div>
        )}
        <div className="grid-overlay"></div>
      </div>
    </div>
  )
}

export default LiveFeed
