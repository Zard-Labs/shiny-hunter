import { useEffect, useRef, useState } from 'react'
import useWebSocket from '../hooks/useWebSocket.jsx'

function LiveFeed() {
  const canvasRef = useRef(null)
  const { videoFrame } = useWebSocket()
  const [fps, setFps] = useState(0)
  const lastFrameTime = useRef(Date.now())
  const fpsCounter = useRef(0)
  const fpsInterval = useRef(null)

  useEffect(() => {
    // Calculate FPS
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

  useEffect(() => {
    if (!videoFrame || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    
    // Create image from base64
    const img = new Image()
    img.onload = () => {
      canvas.width = img.width
      canvas.height = img.height
      ctx.drawImage(img, 0, 0)

      // Draw detection zones if available
      if (videoFrame.annotations) {
        ctx.strokeStyle = '#00ff00'
        ctx.lineWidth = 2
        
        if (videoFrame.annotations.shiny_zone) {
          const zone = videoFrame.annotations.shiny_zone
          ctx.strokeRect(zone.ux, zone.uy, zone.lx - zone.ux, zone.ly - zone.uy)
          ctx.fillStyle = 'rgba(0, 255, 0, 0.1)'
          ctx.fillRect(zone.ux, zone.uy, zone.lx - zone.ux, zone.ly - zone.uy)
          
          // Label
          ctx.fillStyle = '#00ff00'
          ctx.font = '12px Courier New'
          ctx.fillText('SHINY ZONE', zone.ux, zone.uy - 5)
        }

        if (videoFrame.annotations.gender_zone) {
          ctx.strokeStyle = '#ff00ff'
          const zone = videoFrame.annotations.gender_zone
          ctx.strokeRect(zone.ux, zone.uy, zone.lx - zone.ux, zone.ly - zone.uy)
          ctx.fillStyle = 'rgba(255, 0, 255, 0.1)'
          ctx.fillRect(zone.ux, zone.uy, zone.lx - zone.ux, zone.ly - zone.uy)
          
          // Label
          ctx.fillStyle = '#ff00ff'
          ctx.font = '12px Courier New'
          ctx.fillText('GENDER ZONE', zone.ux, zone.uy - 5)
        }
      }

      fpsCounter.current++
    }
    img.src = `data:image/jpeg;base64,${videoFrame.frame}`
  }, [videoFrame])

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
