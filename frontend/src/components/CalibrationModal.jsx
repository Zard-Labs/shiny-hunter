import { useState, useEffect } from 'react'
import { getCurrentCalibration, saveZone, uploadTemplate } from '../services/api'

function CalibrationModal({ onClose }) {
  const [calibration, setCalibration] = useState({ zones: {}, templates: [] })
  const [selectedZone, setSelectedZone] = useState('shiny')
  const [coordinates, setCoordinates] = useState({ ux: 0, uy: 0, lx: 0, ly: 0 })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchCalibration()
  }, [])

  const fetchCalibration = async () => {
    try {
      const data = await getCurrentCalibration()
      setCalibration(data)
      if (data.zones && data.zones[selectedZone]) {
        setCoordinates(data.zones[selectedZone])
      }
    } catch (error) {
      console.error('Failed to fetch calibration:', error)
    }
  }

  const handleSaveZone = async () => {
    setLoading(true)
    try {
      await saveZone(selectedZone, coordinates)
      alert('Zone saved successfully!')
      fetchCalibration()
    } catch (error) {
      console.error('Failed to save zone:', error)
      alert('Failed to save zone')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    formData.append('template_name', file.name.replace(/\.[^/.]+$/, ''))

    setLoading(true)
    try {
      await uploadTemplate(formData)
      alert('Template uploaded successfully!')
      fetchCalibration()
    } catch (error) {
      console.error('Failed to upload template:', error)
      alert('Failed to upload template')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ minWidth: '600px' }}>
        <h2 className="neon-text" style={{ marginBottom: '2rem' }}>
          🎯 Calibration Settings
        </h2>

        <div style={{ marginBottom: '2rem' }}>
          <h3 className="panel-title" style={{ fontSize: '1rem' }}>Detection Zones</h3>
          
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
              Zone Type:
            </label>
            <select 
              value={selectedZone}
              onChange={(e) => {
                setSelectedZone(e.target.value)
                if (calibration.zones && calibration.zones[e.target.value]) {
                  setCoordinates(calibration.zones[e.target.value])
                }
              }}
              style={{ width: '100%', padding: '0.75rem' }}
            >
              <option value="shiny">Shiny Zone</option>
              <option value="gender">Gender Zone</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-magenta)' }}>
                Upper X:
              </label>
              <input 
                type="number"
                value={coordinates.ux}
                onChange={(e) => setCoordinates({ ...coordinates, ux: parseInt(e.target.value) })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-magenta)' }}>
                Upper Y:
              </label>
              <input 
                type="number"
                value={coordinates.uy}
                onChange={(e) => setCoordinates({ ...coordinates, uy: parseInt(e.target.value) })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-magenta)' }}>
                Lower X:
              </label>
              <input 
                type="number"
                value={coordinates.lx}
                onChange={(e) => setCoordinates({ ...coordinates, lx: parseInt(e.target.value) })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-magenta)' }}>
                Lower Y:
              </label>
              <input 
                type="number"
                value={coordinates.ly}
                onChange={(e) => setCoordinates({ ...coordinates, ly: parseInt(e.target.value) })}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          <button 
            className="btn btn-primary" 
            onClick={handleSaveZone}
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? 'SAVING...' : 'SAVE ZONE'}
          </button>
        </div>

        <div style={{ marginBottom: '2rem' }}>
          <h3 className="panel-title" style={{ fontSize: '1rem' }}>Upload Template</h3>
          
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
              Template Image:
            </label>
            <input 
              type="file"
              accept="image/*"
              onChange={handleFileUpload}
              disabled={loading}
              style={{ width: '100%' }}
            />
          </div>

          {calibration.templates && calibration.templates.length > 0 && (
            <div>
              <div className="stat-label" style={{ marginBottom: '0.5rem' }}>
                Current Templates: {calibration.templates.length}
              </div>
              <div style={{ 
                maxHeight: '150px', 
                overflowY: 'auto',
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '0.5rem',
                borderRadius: '4px',
                border: '1px solid rgba(0, 255, 255, 0.2)'
              }}>
                {calibration.templates.map((template, idx) => (
                  <div key={idx} style={{ 
                    padding: '0.25rem', 
                    fontSize: '0.8rem',
                    color: 'var(--text-secondary)'
                  }}>
                    • {template}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <button 
          className="btn" 
          onClick={onClose}
          style={{ width: '100%' }}
        >
          CLOSE
        </button>
      </div>
    </div>
  )
}

export default CalibrationModal
