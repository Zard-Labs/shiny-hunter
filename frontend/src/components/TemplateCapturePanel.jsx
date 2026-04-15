import { useState, useEffect } from 'react'
import {
  getAutomationTemplates,
  getAutomationTemplateImages,
  captureAutomationTemplateImage,
  deleteAutomationTemplateImage,
  getAutomationTemplateImagePreviewUrl,
} from '../services/api'

function TemplateCapturePanel() {
  const [images, setImages] = useState([])
  const [activeTemplate, setActiveTemplate] = useState(null)
  const [loading, setLoading] = useState(false)
  const [capturingKey, setCapturingKey] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [cacheVersion, setCacheVersion] = useState(Date.now())

  useEffect(() => {
    fetchActiveTemplate()
  }, [])

  const fetchActiveTemplate = async () => {
    try {
      const templates = await getAutomationTemplates()
      const active = templates.find(t => t.is_active)
      setActiveTemplate(active || null)
      if (active) {
        await fetchImages(active.id)
      }
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    }
  }

  const fetchImages = async (templateId) => {
    try {
      const data = await getAutomationTemplateImages(templateId)
      setImages(data)
    } catch (error) {
      console.error('Failed to fetch template images:', error)
    }
  }

  const handleCapture = async (imageKey, imageLabel) => {
    if (!activeTemplate) return
    setCapturingKey(imageKey)
    setLoading(true)
    try {
      await captureAutomationTemplateImage(activeTemplate.id, {
        key: imageKey,
        label: imageLabel,
        threshold: 0.80,
      })
      setCacheVersion(v => v + 1)
      await fetchImages(activeTemplate.id)
    } catch (error) {
      console.error('Failed to capture template:', error)
      const msg = error.response?.data?.detail || error.message || 'Unknown error'
      alert(`Capture failed: ${msg}`)
    } finally {
      setLoading(false)
      setCapturingKey(null)
    }
  }

  const handleDelete = async (imageKey) => {
    if (!activeTemplate) return
    if (!confirm('Delete this template image? You will need to recapture it.')) return
    try {
      await deleteAutomationTemplateImage(activeTemplate.id, imageKey)
      await fetchImages(activeTemplate.id)
    } catch (error) {
      console.error('Failed to delete template:', error)
    }
  }

  const capturedCount = images.filter(t => t.captured).length
  const totalCount = images.length

  // Group images by their template key prefix for visual organization
  // (no phase grouping since that's now in the definition, just show a flat list)

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
            color: capturedCount === totalCount && totalCount > 0 
              ? 'var(--accent-green, #00ff88)' 
              : 'var(--accent-yellow, #ffaa00)',
            fontWeight: 'bold'
          }}>
            {capturedCount}/{totalCount}
          </span>
          {capturedCount === totalCount && totalCount > 0 ? '✅' : '⚠️'}
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '1rem' }}>
          {/* Show which template these images belong to */}
          {activeTemplate && (
            <div style={{
              fontSize: '0.75rem',
              color: 'var(--accent-cyan)',
              marginBottom: '0.75rem',
              padding: '0.4rem 0.5rem',
              background: 'rgba(0, 255, 255, 0.05)',
              borderRadius: '4px',
              border: '1px solid rgba(0, 255, 255, 0.15)',
            }}>
              📋 <strong>{activeTemplate.name}</strong>
              <span style={{ color: 'var(--text-secondary)', marginLeft: '0.5rem' }}>
                ({activeTemplate.pokemon_name})
              </span>
            </div>
          )}

          {!activeTemplate && (
            <div style={{
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
              marginBottom: '0.75rem',
              fontStyle: 'italic',
            }}>
              No active template. Open 📚 Manage to create or activate one.
            </div>
          )}

          <p style={{ 
            color: 'var(--text-secondary)', 
            fontSize: '0.8rem', 
            marginBottom: '1rem',
            lineHeight: '1.4'
          }}>
            Navigate your game to each screen, then click <strong>📸 Capture</strong> to save it.
          </p>

          {images.length === 0 && activeTemplate && (
            <div style={{
              fontSize: '0.8rem',
              color: 'var(--text-secondary)',
              fontStyle: 'italic',
              padding: '0.5rem',
            }}>
              No template images defined yet. Add rules with template_match conditions in the step builder.
            </div>
          )}

          {images.map(img => (
            <div 
              key={img.key}
              style={{
                padding: '0.5rem',
                marginBottom: '0.35rem',
                background: 'rgba(0, 0, 0, 0.3)',
                borderRadius: '4px',
                border: img.captured 
                  ? '1px solid rgba(0, 255, 136, 0.2)' 
                  : '1px solid rgba(255, 170, 0, 0.2)'
              }}
            >
              {/* Top row: thumbnail + label + buttons */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '0.3rem',
              }}>
                {/* Preview thumbnail */}
                <div style={{
                  width: '40px',
                  height: '30px',
                  borderRadius: '3px',
                  overflow: 'hidden',
                  flexShrink: 0,
                  background: '#111',
                  border: '1px solid rgba(255,255,255,0.1)'
                }}>
                  {img.captured && img.preview_url ? (
                    <img
                      src={img.preview_url + '?v=' + cacheVersion}
                      alt={img.label || img.key}
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

                {/* Label */}
                <div style={{ 
                  flex: 1,
                  fontSize: '0.85rem', 
                  fontWeight: 'bold',
                  color: img.captured ? 'var(--text-primary)' : 'var(--text-secondary)',
                }}>
                  {img.captured ? '✅' : '❌'} {img.label || img.key.replace(/_/g, ' ')}
                </div>

                {/* Action buttons */}
                <div style={{ display: 'flex', gap: '0.25rem', flexShrink: 0 }}>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleCapture(img.key, img.label) }}
                    disabled={loading || !activeTemplate}
                    style={{
                      padding: '0.3rem 0.6rem',
                      background: capturingKey === img.key 
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
                    {capturingKey === img.key ? '⏳' : '📸'} {img.captured ? 'Re-capture' : 'Capture'}
                  </button>
                  
                  {img.captured && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(img.key) }}
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

              {/* Description - always visible */}
              {img.description && (
                <div style={{ 
                  fontSize: '0.75rem', 
                  color: 'var(--accent-yellow, #ffaa00)',
                  lineHeight: '1.3',
                  paddingLeft: '0.25rem',
                }}>
                  📌 {img.description}
                </div>
              )}

              {/* Key identifier */}
              <div style={{ 
                fontSize: '0.65rem', 
                color: 'var(--text-secondary)',
                paddingLeft: '0.25rem',
                marginTop: '0.1rem',
                opacity: 0.7,
              }}>
                key: {img.key}
              </div>
            </div>
          ))}

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
            <button
              onClick={fetchActiveTemplate}
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
          </div>
        </div>
      )}
    </div>
  )
}

export default TemplateCapturePanel
