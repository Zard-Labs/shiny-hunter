import { useState, useEffect } from 'react'
import { getTemplateStatus, captureTemplate, deleteTemplate, reloadTemplates, getTemplatePreviewUrl } from '../services/api'

function TemplateCapturePanel() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(false)
  const [capturingKey, setCapturingKey] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [cacheVersion, setCacheVersion] = useState(0)

  useEffect(() => {
    fetchStatus()
  }, [])

  const fetchStatus = async () => {
    try {
      const data = await getTemplateStatus()
      setTemplates(data)
    } catch (error) {
      console.error('Failed to fetch template status:', error)
    }
  }

  const handleCapture = async (templateKey) => {
    setCapturingKey(templateKey)
    setLoading(true)
    try {
      const result = await captureTemplate(templateKey)
      if (result.status === 'success') {
        setCacheVersion(v => v + 1)
        await fetchStatus()
      }
    } catch (error) {
      console.error('Failed to capture template:', error)
      const msg = error.response?.data?.detail || error.message || 'Unknown error'
      alert(`Capture failed: ${msg}`)
    } finally {
      setLoading(false)
      setCapturingKey(null)
    }
  }

  const handleDelete = async (templateKey) => {
    if (!confirm('Delete this template? You will need to recapture it.')) return
    try {
      await deleteTemplate(templateKey)
      await fetchStatus()
    } catch (error) {
      console.error('Failed to delete template:', error)
    }
  }

  const handleReload = async () => {
    try {
      const result = await reloadTemplates()
      alert(`Templates reloaded: ${result.loaded}/${result.total} loaded`)
      await fetchStatus()
    } catch (error) {
      console.error('Failed to reload templates:', error)
    }
  }

  const capturedCount = templates.filter(t => t.captured).length
  const totalCount = templates.length

  // Group templates by phase
  const phases = {}
  templates.forEach(t => {
    if (!phases[t.phase]) phases[t.phase] = []
    phases[t.phase].push(t)
  })

  return (
    <div className="panel" style={{ marginBottom: '1rem' }}>
      <div 
        onClick={() => setExpanded(!expanded)}
        style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          cursor: 'pointer',
          userSelect: 'none'
        }}
      >
        <h2 className="panel-title" style={{ marginBottom: 0, fontSize: '1rem' }}>
          🎯 Templates {expanded ? '▾' : '▸'}
        </h2>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '0.5rem',
          fontSize: '0.85rem'
        }}>
          <span style={{ 
            color: capturedCount === totalCount ? 'var(--accent-green, #00ff88)' : 'var(--accent-yellow, #ffaa00)',
            fontWeight: 'bold'
          }}>
            {capturedCount}/{totalCount}
          </span>
          {capturedCount === totalCount ? '✅' : '⚠️'}
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '1rem' }}>
          <p style={{ 
            color: 'var(--text-secondary)', 
            fontSize: '0.8rem', 
            marginBottom: '1rem',
            lineHeight: '1.4'
          }}>
            Navigate your game to each screen, then click <strong>Capture</strong> to save it as a template for automation.
          </p>

          {Object.entries(phases).map(([phase, items]) => (
            <div key={phase} style={{ marginBottom: '1rem' }}>
              <div style={{ 
                fontSize: '0.75rem', 
                color: 'var(--accent-cyan)', 
                marginBottom: '0.5rem',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 'bold'
              }}>
                {phase}
              </div>
              
              {items.map(template => (
                <div 
                  key={template.key}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.5rem',
                    marginBottom: '0.25rem',
                    background: 'rgba(0, 0, 0, 0.3)',
                    borderRadius: '4px',
                    border: template.captured 
                      ? '1px solid rgba(0, 255, 136, 0.2)' 
                      : '1px solid rgba(255, 170, 0, 0.2)'
                  }}
                >
                  {/* Preview thumbnail */}
                  <div style={{
                    width: '48px',
                    height: '36px',
                    borderRadius: '3px',
                    overflow: 'hidden',
                    flexShrink: 0,
                    background: '#111',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}>
                    {template.captured ? (
                      <img
                        src={getTemplatePreviewUrl(template.key) + '?v=' + cacheVersion}
                        alt={template.label}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={(e) => { e.target.style.display = 'none' }}
                      />
                    ) : (
                      <div style={{ 
                        width: '100%', 
                        height: '100%', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        color: '#444',
                        fontSize: '0.7rem'
                      }}>
                        —
                      </div>
                    )}
                  </div>

                  {/* Label and status */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ 
                      fontSize: '0.85rem', 
                      fontWeight: 'bold',
                      color: template.captured ? 'var(--text-primary)' : 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {template.captured ? '✅' : '❌'} {template.label}
                    </div>
                    <div style={{ 
                      fontSize: '0.7rem', 
                      color: 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {template.description}
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: '0.25rem', flexShrink: 0 }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleCapture(template.key) }}
                      disabled={loading}
                      style={{
                        padding: '0.3rem 0.6rem',
                        background: capturingKey === template.key 
                          ? 'rgba(0, 255, 136, 0.3)' 
                          : 'rgba(0, 255, 255, 0.1)',
                        border: '1px solid var(--accent-cyan)',
                        color: 'var(--accent-cyan)',
                        borderRadius: '3px',
                        cursor: loading ? 'wait' : 'pointer',
                        fontSize: '0.7rem',
                        fontFamily: 'inherit',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {capturingKey === template.key ? '⏳' : '📸'} {template.captured ? 'Re-capture' : 'Capture'}
                    </button>
                    
                    {template.captured && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(template.key) }}
                        disabled={loading}
                        style={{
                          padding: '0.3rem 0.4rem',
                          background: 'rgba(255, 50, 50, 0.1)',
                          border: '1px solid rgba(255, 50, 50, 0.3)',
                          color: '#ff5555',
                          borderRadius: '3px',
                          cursor: 'pointer',
                          fontSize: '0.7rem',
                          fontFamily: 'inherit'
                        }}
                      >
                        🗑️
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ))}

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
            <button
              onClick={fetchStatus}
              style={{
                flex: 1,
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
              onClick={handleReload}
              style={{
                flex: 1,
                padding: '0.5rem',
                background: 'rgba(255, 170, 0, 0.1)',
                border: '1px solid rgba(255, 170, 0, 0.5)',
                color: '#ffaa00',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.75rem',
                fontFamily: 'inherit'
              }}
            >
              🔃 Reload Detector
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default TemplateCapturePanel
