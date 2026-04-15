import { useState, useEffect } from 'react'
import {
  getAutomationTemplateImages,
  createAutomationTemplateImage,
  captureAutomationTemplateImage,
  updateAutomationTemplateImage,
  deleteAutomationTemplateImage,
  getAutomationTemplateImagePreviewUrl,
} from '../services/api'

function TemplateImageManager({ templateId, definition }) {
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(false)
  const [capturingKey, setCapturingKey] = useState(null)
  const [cacheVersion, setCacheVersion] = useState(Date.now())
  const [showAddForm, setShowAddForm] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [editingKey, setEditingKey] = useState(null)
  const [editLabel, setEditLabel] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // Derive required image keys from the definition's rules
  const requiredKeys = new Set()
  if (definition?.steps) {
    for (const step of definition.steps) {
      for (const rule of step.rules || []) {
        const tmpl = rule.condition?.template
        if (tmpl) requiredKeys.add(tmpl)
      }
    }
  }

  useEffect(() => {
    if (templateId) fetchImages()
  }, [templateId])

  const fetchImages = async () => {
    try {
      const data = await getAutomationTemplateImages(templateId)
      setImages(data)
    } catch (err) {
      console.error('Failed to fetch template images:', err)
    }
  }

  const handleCapture = async (key, label) => {
    setCapturingKey(key)
    setLoading(true)
    try {
      await captureAutomationTemplateImage(templateId, {
        key,
        label: label || key.replace(/_/g, ' '),
        threshold: 0.80,
      })
      setCacheVersion((v) => v + 1)
      await fetchImages()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      alert(`Capture failed: ${msg}`)
    } finally {
      setLoading(false)
      setCapturingKey(null)
    }
  }

  const handleDelete = async (key) => {
    if (!confirm('Delete this template image?')) return
    try {
      await deleteAutomationTemplateImage(templateId, key)
      await fetchImages()
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  const handleAddImage = async () => {
    if (!newKey.trim()) return
    try {
      await createAutomationTemplateImage(templateId, {
        key: newKey.trim().toLowerCase().replace(/\s+/g, '_'),
        label: newLabel.trim() || newKey.trim(),
        description: newDescription.trim() || null,
        threshold: 0.80,
      })
      setNewKey('')
      setNewLabel('')
      setNewDescription('')
      setShowAddForm(false)
      await fetchImages()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      alert(`Failed to add image: ${msg}`)
    }
  }

  const startEditing = (img) => {
    setEditingKey(img.key)
    setEditLabel(img.label || '')
    setEditDescription(img.description || '')
  }

  const cancelEditing = () => {
    setEditingKey(null)
  }

  const saveEdit = async (key) => {
    try {
      await updateAutomationTemplateImage(templateId, key, {
        label: editLabel.trim(),
        description: editDescription.trim() || null,
      })
      setEditingKey(null)
      await fetchImages()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      alert(`Failed to update: ${msg}`)
    }
  }

  // Merge required keys with existing images
  const imageMap = {}
  for (const img of images) imageMap[img.key] = img
  // Also show keys from rules that don't have DB rows yet
  for (const key of requiredKeys) {
    if (!imageMap[key]) {
      imageMap[key] = { key, label: key.replace(/_/g, ' '), captured: false, _missing: true }
    }
  }
  const allKeys = Object.keys(imageMap).sort()

  if (!templateId) {
    return (
      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        Save the template first to manage images.
      </div>
    )
  }

  // Styles
  const inputStyle = {
    padding: '0.3rem 0.5rem',
    background: 'var(--bg-tertiary, #252540)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary, #e0e0e0)',
    borderRadius: '3px',
    fontSize: '0.8rem',
    fontFamily: "'Courier New', monospace",
    width: '100%',
  }

  const labelStyle = {
    fontSize: '0.7rem',
    color: 'var(--accent-cyan, #00ffff)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '0.2rem',
    display: 'block',
  }

  return (
    <div>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0.5rem',
      }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          Navigate your game to each screen, then click <strong>📷</strong> to capture.
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          style={{
            padding: '0.3rem 0.6rem',
            background: showAddForm ? 'rgba(0, 255, 255, 0.15)' : 'transparent',
            border: '1px solid var(--accent-cyan, #00ffff)',
            color: 'var(--accent-cyan)',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '0.75rem',
            flexShrink: 0,
          }}
        >
          {showAddForm ? '✕ Cancel' : '+ Add Image'}
        </button>
      </div>

      {/* Add New Image Form */}
      {showAddForm && (
        <div style={{
          padding: '0.6rem',
          marginBottom: '0.5rem',
          background: 'rgba(0, 255, 255, 0.05)',
          border: '1px solid rgba(0, 255, 255, 0.2)',
          borderRadius: '4px',
        }}>
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Key (ID)</label>
              <input
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                style={inputStyle}
                placeholder="e.g. battle_screen"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Label</label>
              <input
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                style={inputStyle}
                placeholder="e.g. Battle Screen"
              />
            </div>
          </div>
          <div style={{ marginBottom: '0.4rem' }}>
            <label style={labelStyle}>Description</label>
            <input
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              style={inputStyle}
              placeholder="What does this screen look like?"
            />
          </div>
          <button
            onClick={handleAddImage}
            disabled={!newKey.trim()}
            style={{
              padding: '0.3rem 0.8rem',
              background: newKey.trim() ? 'var(--accent-green, #00ff88)' : 'transparent',
              border: '1px solid var(--accent-green, #00ff88)',
              color: newKey.trim() ? '#000' : 'var(--text-secondary)',
              borderRadius: '3px',
              cursor: newKey.trim() ? 'pointer' : 'default',
              fontSize: '0.8rem',
              fontWeight: 'bold',
            }}
          >
            ✓ Add Image
          </button>
        </div>
      )}

      {allKeys.length === 0 && !showAddForm && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
          No template images defined. Click "+ Add Image" or add rules with template_match conditions.
        </div>
      )}

      {allKeys.map((key) => {
        const img = imageMap[key]
        const isCapturing = capturingKey === key
        const isEditing = editingKey === key
        const isFromRule = requiredKeys.has(key)

        return (
          <div
            key={key}
            style={{
              padding: '0.5rem',
              marginBottom: '0.35rem',
              background: 'rgba(0, 0, 0, 0.3)',
              borderRadius: '4px',
              border: img.captured
                ? '1px solid rgba(0, 255, 136, 0.2)'
                : '1px solid rgba(255, 170, 0, 0.2)',
            }}
          >
            {/* Top row: thumbnail + label + buttons */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '0.25rem',
            }}>
              {/* Thumbnail */}
              <div style={{
                width: '48px',
                height: '36px',
                borderRadius: '3px',
                overflow: 'hidden',
                flexShrink: 0,
                background: '#111',
                border: '1px solid rgba(255,255,255,0.1)',
              }}>
                {img.captured && img.preview_url ? (
                  <img
                    src={img.preview_url + '?v=' + cacheVersion}
                    alt={key}
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
                    fontSize: '0.7rem',
                  }}>—</div>
                )}
              </div>

              {/* Label (or edit field) */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {isEditing ? (
                  <input
                    value={editLabel}
                    onChange={(e) => setEditLabel(e.target.value)}
                    style={{ ...inputStyle, fontSize: '0.8rem', padding: '0.2rem 0.4rem' }}
                    placeholder="Label"
                    autoFocus
                  />
                ) : (
                  <div style={{
                    fontSize: '0.85rem',
                    fontWeight: 'bold',
                    color: img.captured ? 'var(--text-primary)' : 'var(--text-secondary)',
                  }}>
                    {img.captured ? '✅' : '❌'} {img.label || key.replace(/_/g, ' ')}
                  </div>
                )}
              </div>

              {/* Buttons */}
              <div style={{ display: 'flex', gap: '0.2rem', flexShrink: 0 }}>
                <button
                  onClick={() => handleCapture(key, img.label)}
                  disabled={loading}
                  style={{
                    padding: '0.2rem 0.5rem',
                    background: isCapturing ? 'var(--accent-cyan)' : 'rgba(0, 255, 255, 0.1)',
                    border: '1px solid var(--accent-cyan, #00ffff)',
                    color: isCapturing ? '#000' : 'var(--accent-cyan)',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontSize: '0.7rem',
                  }}
                  title="Capture from live feed"
                >
                  {isCapturing ? '⏳' : '📷'}
                </button>
                {!isEditing ? (
                  <button
                    onClick={() => startEditing(img)}
                    style={{
                      padding: '0.2rem 0.5rem',
                      background: 'transparent',
                      border: '1px solid rgba(255,255,255,0.15)',
                      color: 'var(--text-secondary)',
                      borderRadius: '3px',
                      cursor: 'pointer',
                      fontSize: '0.7rem',
                    }}
                    title="Edit label & description"
                  >✏️</button>
                ) : (
                  <>
                    <button
                      onClick={() => saveEdit(key)}
                      style={{
                        padding: '0.2rem 0.5rem',
                        background: 'rgba(0, 255, 136, 0.2)',
                        border: '1px solid var(--accent-green)',
                        color: 'var(--accent-green)',
                        borderRadius: '3px',
                        cursor: 'pointer',
                        fontSize: '0.7rem',
                      }}
                      title="Save changes"
                    >✓</button>
                    <button
                      onClick={cancelEditing}
                      style={{
                        padding: '0.2rem 0.5rem',
                        background: 'transparent',
                        border: '1px solid rgba(255,255,255,0.15)',
                        color: 'var(--text-secondary)',
                        borderRadius: '3px',
                        cursor: 'pointer',
                        fontSize: '0.7rem',
                      }}
                      title="Cancel editing"
                    >✕</button>
                  </>
                )}
                {img.captured && (
                  <button
                    onClick={() => handleDelete(key)}
                    style={{
                      padding: '0.2rem 0.5rem',
                      background: 'transparent',
                      border: '1px solid rgba(255,68,68,0.3)',
                      color: '#ff4444',
                      borderRadius: '3px',
                      cursor: 'pointer',
                      fontSize: '0.7rem',
                    }}
                    title="Delete image"
                  >🗑</button>
                )}
              </div>
            </div>

            {/* Description (edit or display) */}
            {isEditing ? (
              <div style={{ marginTop: '0.25rem' }}>
                <input
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  style={{ ...inputStyle, fontSize: '0.75rem', padding: '0.2rem 0.4rem' }}
                  placeholder="Description — what does this screen look like?"
                />
              </div>
            ) : (
              img.description && (
                <div style={{
                  fontSize: '0.75rem',
                  color: 'var(--accent-yellow, #ffaa00)',
                  lineHeight: '1.3',
                  paddingLeft: '0.25rem',
                }}>
                  📌 {img.description}
                </div>
              )
            )}

            {/* Key + source info */}
            <div style={{
              display: 'flex',
              gap: '0.5rem',
              fontSize: '0.65rem',
              color: 'var(--text-secondary)',
              paddingLeft: '0.25rem',
              marginTop: '0.1rem',
              opacity: 0.7,
            }}>
              <span>key: {key}</span>
              {isFromRule && <span style={{ color: 'var(--accent-cyan)' }}>• used in rules</span>}
              {img._missing && <span style={{ color: '#ff8800' }}>• not in DB yet</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default TemplateImageManager
