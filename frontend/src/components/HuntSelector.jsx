import { useState, useEffect } from 'react'
import { getHunts } from '../services/api'

function HuntSelector({ selectedHuntId, onHuntChange }) {
  const [hunts, setHunts] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchHunts = async () => {
    setLoading(true)
    try {
      const data = await getHunts()
      setHunts(data)
    } catch (error) {
      console.error('Failed to fetch hunts:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHunts()
    // Refresh hunts list every 10s in case a new hunt is created
    const interval = setInterval(fetchHunts, 10000)
    return () => clearInterval(interval)
  }, [])

  // Also refresh when the selected hunt changes (e.g. after reset)
  useEffect(() => {
    fetchHunts()
  }, [selectedHuntId])

  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const handleChange = (e) => {
    const value = e.target.value
    // '' means "active hunt" (no filter)
    onHuntChange(value || null)
  }

  if (hunts.length <= 1) {
    // Only one hunt, no need for a selector
    return null
  }

  return (
    <div className="hunt-selector" style={{ marginBottom: '1rem' }}>
      <label 
        htmlFor="hunt-select" 
        style={{ 
          display: 'block',
          fontSize: '0.75rem', 
          color: 'var(--accent-magenta)', 
          marginBottom: '0.4rem',
          textTransform: 'uppercase',
          letterSpacing: '0.1em'
        }}
      >
        Viewing Hunt
      </label>
      <select
        id="hunt-select"
        value={selectedHuntId || ''}
        onChange={handleChange}
        disabled={loading}
        style={{
          width: '100%',
          padding: '0.6rem 0.8rem',
          background: 'var(--bg-secondary, #1a1a2e)',
          border: '1px solid var(--accent-cyan, #00ffff)',
          color: 'var(--text-primary, #e0e0e0)',
          borderRadius: '4px',
          fontFamily: "'Courier New', monospace",
          fontSize: '0.85rem',
          cursor: 'pointer',
          outline: 'none'
        }}
      >
        <option value="">Current Hunt (Active)</option>
        {hunts.map((hunt) => (
          <option key={hunt.id} value={hunt.id}>
            {hunt.name || `Hunt ${hunt.id.slice(0, 8)}`}
            {' '}({hunt.total_encounters} enc)
            {hunt.status === 'active' ? ' ★' : ` - ${formatDate(hunt.ended_at)}`}
          </option>
        ))}
      </select>

      <style>{`
        .hunt-selector select:hover {
          border-color: var(--accent-magenta, #ff00ff);
          box-shadow: 0 0 8px rgba(0, 255, 255, 0.3);
        }
        .hunt-selector select:focus {
          border-color: var(--accent-magenta, #ff00ff);
          box-shadow: 0 0 12px rgba(255, 0, 255, 0.4);
        }
        .hunt-selector select option {
          background: #1a1a2e;
          color: #e0e0e0;
        }
      `}</style>
    </div>
  )
}

export default HuntSelector
