import { useState, useEffect } from 'react'
import { getCameraDevices, selectCamera, saveCameraToConfig, getCropMode, setCropMode, saveCropModeToConfig } from '../services/api'

function CameraSelector({ onCameraChange }) {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [saving, setSaving] = useState(false)
  const [cropMode, setCropModeState] = useState('16:9')
  const [cropLoading, setCropLoading] = useState(false)
  const [cropSaving, setCropSaving] = useState(false)

  useEffect(() => {
    loadDevices()
    loadCropMode()
  }, [])

  const loadCropMode = async () => {
    try {
      const data = await getCropMode()
      setCropModeState(data.mode)
    } catch (error) {
      console.error('Failed to load crop mode:', error)
    }
  }

  const handleCropModeChange = async (mode) => {
    setCropLoading(true)
    try {
      const result = await setCropMode(mode)
      if (result.status === 'success') {
        setCropModeState(mode)
      } else {
        alert(`Failed to set crop mode: ${result.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to set crop mode:', error)
      alert('Failed to set crop mode')
    } finally {
      setCropLoading(false)
    }
  }

  const handleSaveCropMode = async () => {
    setCropSaving(true)
    try {
      const result = await saveCropModeToConfig(cropMode)
      if (result.status === 'success') {
        alert(`✅ Saved! Crop mode "${cropMode}" will be used on startup.`)
      } else {
        alert(`Failed to save: ${result.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to save crop mode:', error)
      alert('Failed to save crop mode to config')
    } finally {
      setCropSaving(false)
    }
  }

  const loadDevices = async () => {
    try {
      const data = await getCameraDevices()
      setDevices(data)
      const current = data.find(d => d.is_current)
      if (current) {
        setSelectedIndex(current.index)
      }
    } catch (error) {
      console.error('Failed to load camera devices:', error)
    }
  }

  const handleSelectCamera = async (index) => {
    setLoading(true)
    try {
      const response = await selectCamera(index)
      const result = response.data || response
      
      if (result.status === 'success') {
        setSelectedIndex(index)
        if (onCameraChange) {
          onCameraChange(index)
        }
        // Refresh device list after short delay
        setTimeout(() => loadDevices(), 500)
      } else {
        alert(`Failed to switch camera: ${result.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to select camera:', error)
      const errorMsg = error.response?.data?.message || error.message || 'Network error'
      alert(`Failed to switch camera: ${errorMsg}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveToConfig = async () => {
    setSaving(true)
    try {
      const response = await saveCameraToConfig(selectedIndex)
      const result = response.data || response
      
      if (result.status === 'success') {
        alert(`✅ Saved! Camera ${selectedIndex} will be used on startup.\n\nRestart backend to verify.`)
      } else {
        alert(`Failed to save: ${result.message || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to save to config:', error)
      alert('Failed to save to config file')
    } finally {
      setSaving(false)
    }
  }

  if (devices.length === 0) {
    return (
      <div className="stat-box" style={{ padding: '1rem' }}>
        <div className="stat-label">Camera Device</div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Loading devices...
        </div>
      </div>
    )
  }

  return (
    <div className="stat-box" style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <div className="stat-label" style={{ marginBottom: 0 }}>
          📹 Camera Device
        </div>
        <div className="neon-text" style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>
          #{selectedIndex}
        </div>
      </div>
      
      <select
        value={selectedIndex}
        onChange={(e) => handleSelectCamera(parseInt(e.target.value))}
        disabled={loading}
        style={{ 
          width: '100%', 
          padding: '0.75rem',
          fontSize: '0.9rem',
          background: 'rgba(0, 0, 0, 0.5)',
          border: '1px solid var(--accent-cyan)',
          color: 'var(--text-primary)',
          borderRadius: '4px',
          cursor: 'pointer'
        }}
      >
        {devices.map((device) => (
          <option 
            key={device.index} 
            value={device.index}
            style={{ background: 'var(--bg-secondary)' }}
          >
            {device.name} {device.is_current ? '(Current)' : ''}
          </option>
        ))}
      </select>

      {(loading || saving) && (
        <div style={{
          marginTop: '0.5rem',
          textAlign: 'center',
          color: 'var(--accent-cyan)',
          fontSize: '0.85rem'
        }}>
          {loading ? 'Switching camera...' : 'Saving to config...'}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.75rem' }}>
        <button
          onClick={loadDevices}
          disabled={loading || saving}
          style={{
            padding: '0.5rem',
            background: 'rgba(0, 255, 255, 0.1)',
            border: '1px solid var(--accent-cyan)',
            color: 'var(--accent-cyan)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'inherit'
          }}
        >
          🔄 Refresh
        </button>
        
        <button
          onClick={handleSaveToConfig}
          disabled={loading || saving}
          className="btn-primary"
          style={{
            padding: '0.5rem',
            background: 'rgba(0, 255, 0, 0.1)',
            border: '1px solid var(--accent-green)',
            color: 'var(--accent-green)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'inherit',
            fontWeight: 'bold'
          }}
        >
          💾 Save
        </button>
      </div>

      <div style={{
        marginTop: '0.75rem',
        fontSize: '0.7rem',
        color: 'var(--text-secondary)',
        lineHeight: '1.4'
      }}>
        💡 Select your capture card, then click Save to make it permanent
      </div>

      {/* Crop Mode Section */}
      <div style={{
        marginTop: '1rem',
        paddingTop: '1rem',
        borderTop: '1px solid var(--border-glow)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <div className="stat-label" style={{ marginBottom: 0 }}>
            🖥️ Aspect Ratio
          </div>
          <div className="neon-text" style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>
            {cropMode}
          </div>
        </div>

        <select
          value={cropMode}
          onChange={(e) => handleCropModeChange(e.target.value)}
          disabled={cropLoading}
          style={{
            width: '100%',
            padding: '0.75rem',
            fontSize: '0.9rem',
            background: 'rgba(0, 0, 0, 0.5)',
            border: '1px solid var(--accent-magenta)',
            color: 'var(--text-primary)',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          <option value="16:9" style={{ background: 'var(--bg-secondary)' }}>
            16:9 — Full Frame (Switch / Modern)
          </option>
          <option value="4:3" style={{ background: 'var(--bg-secondary)' }}>
            4:3 — Crop Sides (GBA / DS with black bars)
          </option>
        </select>

        {(cropLoading || cropSaving) && (
          <div style={{
            marginTop: '0.5rem',
            textAlign: 'center',
            color: 'var(--accent-magenta)',
            fontSize: '0.85rem'
          }}>
            {cropLoading ? 'Applying...' : 'Saving...'}
          </div>
        )}

        <button
          onClick={handleSaveCropMode}
          disabled={cropLoading || cropSaving}
          style={{
            width: '100%',
            marginTop: '0.5rem',
            padding: '0.5rem',
            background: 'rgba(0, 255, 0, 0.1)',
            border: '1px solid var(--accent-green)',
            color: 'var(--accent-green)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'inherit',
            fontWeight: 'bold'
          }}
        >
          💾 Save Aspect Ratio
        </button>

        <div style={{
          marginTop: '0.5rem',
          fontSize: '0.7rem',
          color: 'var(--accent-yellow)',
          lineHeight: '1.4'
        }}>
          ⚠️ Changing aspect ratio requires recapturing templates &amp; recalibrating detection zones
        </div>
      </div>
    </div>
  )
}

export default CameraSelector
