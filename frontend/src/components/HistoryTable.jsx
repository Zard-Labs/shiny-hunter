import { useState } from 'react'
import { API_BASE_URL } from '../services/api'

function HistoryTable({ history }) {
  const [selectedEncounter, setSelectedEncounter] = useState(null)

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString()
  }

  /** Build a full screenshot URL, handling both relative paths and legacy absolute paths. */
  const getScreenshotUrl = (path) => {
    if (!path) return null
    // Extract just the filename to be safe (handles Windows backslash paths)
    const filename = path.split(/[/\\]/).pop()
    return `${API_BASE_URL}/encounters/${filename}`
  }

  return (
    <div className="panel history-table">
      <h2 className="panel-title">📜 Encounter History</h2>
      
      {history.length === 0 ? (
        <div style={{ 
          textAlign: 'center', 
          padding: '2rem', 
          color: 'var(--text-secondary)' 
        }}>
          No encounters yet. Start hunting!
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Time</th>
                <th>Gender</th>
                <th>Nature</th>
                <th>✨</th>
              </tr>
            </thead>
            <tbody>
              {history.map((encounter) => (
                <tr 
                  key={encounter.id} 
                  className={encounter.is_shiny ? 'shiny-row' : ''}
                  onClick={() => setSelectedEncounter(encounter)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <span className="neon-text">#{encounter.encounter_number}</span>
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>
                    {formatTimestamp(encounter.timestamp)}
                  </td>
                  <td>
                    <span style={{ 
                      color: encounter.gender === 'Male' ? '#00aaff' : 
                             encounter.gender === 'Female' ? '#ff0088' : 
                             'var(--text-secondary)' 
                    }}>
                      {encounter.gender || '?'}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.85rem' }}>
                    {encounter.nature || 'Unknown'}
                  </td>
                  <td>
                    {encounter.is_shiny && (
                      <span className="neon-text yellow" style={{ fontSize: '1.2rem' }}>
                        ✨
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedEncounter && (
        <div className="modal-overlay" onClick={() => setSelectedEncounter(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="neon-text" style={{ marginBottom: '1rem' }}>
              Encounter #{selectedEncounter.encounter_number}
            </h2>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div className="stat-box">
                <div className="stat-label">Pokemon</div>
                <div className="stat-value" style={{ fontSize: '1.5rem' }}>
                  {selectedEncounter.pokemon_name}
                </div>
              </div>
              
              <div className="stat-box">
                <div className="stat-label">Shiny</div>
                <div className={`stat-value ${selectedEncounter.is_shiny ? 'shiny' : ''}`} style={{ fontSize: '1.5rem' }}>
                  {selectedEncounter.is_shiny ? '✨ YES' : 'NO'}
                </div>
              </div>
              
              <div className="stat-box">
                <div className="stat-label">Gender</div>
                <div className="stat-value" style={{ fontSize: '1.5rem' }}>
                  {selectedEncounter.gender || 'Unknown'}
                </div>
              </div>
              
              <div className="stat-box">
                <div className="stat-label">Nature</div>
                <div className="stat-value" style={{ fontSize: '1.5rem' }}>
                  {selectedEncounter.nature || 'Unknown'}
                </div>
              </div>
            </div>

            {selectedEncounter.screenshot_path && (
              <div style={{ marginBottom: '1rem' }}>
                <div className="stat-label" style={{ marginBottom: '0.5rem' }}>Screenshot</div>
                <img
                  src={getScreenshotUrl(selectedEncounter.screenshot_path)}
                  alt="Encounter"
                  style={{ 
                    width: '100%', 
                    border: '2px solid var(--accent-cyan)',
                    borderRadius: '4px',
                    boxShadow: '0 0 20px rgba(0, 255, 255, 0.3)'
                  }}
                />
              </div>
            )}

            <button 
              className="btn" 
              onClick={() => setSelectedEncounter(null)}
              style={{ width: '100%' }}
            >
              CLOSE
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default HistoryTable
