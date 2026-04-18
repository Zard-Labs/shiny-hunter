import { useState, useEffect } from 'react'
import { getRecoveryEvents } from '../services/api'

function RecoveryLog({ huntId }) {
  const [events, setEvents] = useState([])
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (expanded) {
      loadEvents()
    }
  }, [expanded, huntId])

  const loadEvents = async () => {
    try {
      const data = await getRecoveryEvents(huntId, 20)
      setEvents(data.events || [])
    } catch (err) {
      console.error('Failed to load recovery events:', err)
    }
  }

  if (events.length === 0 && !expanded) return null // Hide entirely if no events

  return (
    <div className="panel" style={{ marginTop: '1rem' }}>
      <h2 
        className="panel-title" 
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={() => setExpanded(!expanded)}
      >
        🔄 Recovery Log {expanded ? '▼' : '▶'}
      </h2>
      
      {expanded && (
        <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
          {events.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-secondary)' }}>
              No recovery events recorded
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Step</th>
                  <th>Stuck For</th>
                  <th>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td style={{ fontSize: '0.8rem' }}>
                      {new Date(e.timestamp).toLocaleString()}
                    </td>
                    <td>
                      <span className="neon-text">{e.step_name}</span>
                    </td>
                    <td>{e.time_in_step?.toFixed(1)}s</td>
                    <td>
                      <span style={{
                        color: e.strategy === 'soft_reset' ? 'var(--accent-cyan)' :
                               e.strategy === 'stop' ? '#ff4444' :
                               'var(--accent-yellow)'
                      }}>
                        {e.strategy}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default RecoveryLog
