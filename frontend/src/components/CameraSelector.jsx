import { useState, useEffect } from 'react'
import { getCameraDevices, selectCamera, saveCameraToConfig } from '../services/api'

function CameraSelector({ onCameraChange }) {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadDevices()
  }, [])

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
    </div>
  )
}

export default CameraSelector
