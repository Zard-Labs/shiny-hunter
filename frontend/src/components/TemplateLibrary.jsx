import { useState, useEffect } from 'react'
import {
  getAutomationTemplates,
  deleteAutomationTemplate,
  activateAutomationTemplate,
  cloneAutomationTemplate,
  exportAutomationTemplate,
  importAutomationTemplate,
} from '../services/api'
import TemplateStepBuilder from './TemplateStepBuilder'

function TemplateLibrary({ onClose, onStartRecording }) {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null) // null = list view, 'new' or UUID = editor
  const [importJson, setImportJson] = useState('')
  const [showImport, setShowImport] = useState(false)

  useEffect(() => {
    fetchTemplates()
  }, [])

  const fetchTemplates = async () => {
    setLoading(true)
    try {
      const data = await getAutomationTemplates()
      setTemplates(data)
    } catch (err) {
      console.error('Failed to fetch templates:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleActivate = async (id) => {
    try {
      await activateAutomationTemplate(id)
      await fetchTemplates()
    } catch (err) {
      alert(`Activation failed: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleClone = async (id) => {
    try {
      const result = await cloneAutomationTemplate(id)
      await fetchTemplates()
      setEditingId(result.id)
    } catch (err) {
      alert(`Clone failed: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete template "${name}"? This cannot be undone.`)) return
    try {
      await deleteAutomationTemplate(id)
      await fetchTemplates()
    } catch (err) {
      alert(`Delete failed: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleExport = async (id) => {
    try {
      const data = await exportAutomationTemplate(id)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${data.name || 'template'}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert(`Export failed: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleImport = async () => {
    try {
      const data = JSON.parse(importJson)
      await importAutomationTemplate(data)
      setImportJson('')
      setShowImport(false)
      await fetchTemplates()
    } catch (err) {
      alert(`Import failed: ${err.message}`)
    }
  }

  const handleFileImport = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      setImportJson(ev.target.result)
    }
    reader.readAsText(file)
  }

  // If editing, show the step builder
  if (editingId) {
    return (
      <TemplateStepBuilder
        templateId={editingId === 'new' ? null : editingId}
        onClose={() => { setEditingId(null); fetchTemplates() }}
        onSaved={fetchTemplates}
      />
    )
  }

  const btnStyle = {
    padding: '0.3rem 0.6rem',
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.15)',
    color: 'var(--text-secondary)',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.75rem',
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      zIndex: 1000,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-start',
      padding: '2rem',
      overflow: 'auto',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '800px',
        background: 'var(--bg-primary, #0d0d1a)',
        borderRadius: '8px',
        border: '1px solid var(--accent-cyan, #00ffff)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.75rem 1rem',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          <h2 style={{ fontSize: '1.1rem', margin: 0, color: 'var(--accent-cyan)' }}>
            📚 Automation Templates
          </h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setEditingId('new')}
              style={{
                padding: '0.4rem 0.8rem',
                background: 'var(--accent-green, #00ff88)',
                border: 'none',
                color: '#000',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 'bold',
              }}
            >+ New Template</button>
            <button
              onClick={() => { onStartRecording?.(); }}
              style={{
                padding: '0.4rem 0.8rem',
                background: 'linear-gradient(135deg, #ff4444, #cc0000)',
                border: 'none',
                color: '#fff',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 'bold',
              }}
            >🎬 Record</button>
            <button
              onClick={() => setShowImport(!showImport)}
              style={{
                ...btnStyle,
                border: '1px solid var(--accent-cyan)',
                color: 'var(--accent-cyan)',
              }}
            >📥 Import</button>
            <button onClick={onClose} style={btnStyle}>✕ Close</button>
          </div>
        </div>

        {/* Import Panel */}
        {showImport && (
          <div style={{
            padding: '0.75rem 1rem',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(0, 0, 50, 0.3)',
          }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Paste exported JSON or select a file:
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <input
                type="file"
                accept=".json"
                onChange={handleFileImport}
                style={{ fontSize: '0.8rem', color: 'var(--text-primary)' }}
              />
            </div>
            <textarea
              value={importJson}
              onChange={(e) => setImportJson(e.target.value)}
              style={{
                width: '100%',
                height: '80px',
                background: 'var(--bg-tertiary, #252540)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'var(--text-primary)',
                borderRadius: '4px',
                padding: '0.5rem',
                fontFamily: "'Courier New', monospace",
                fontSize: '0.75rem',
                resize: 'vertical',
              }}
              placeholder='{"name": "...", "definition": {...}}'
            />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button
                onClick={handleImport}
                disabled={!importJson.trim()}
                style={{
                  ...btnStyle,
                  background: importJson.trim() ? 'var(--accent-green)' : 'transparent',
                  color: importJson.trim() ? '#000' : 'var(--text-secondary)',
                  border: '1px solid var(--accent-green)',
                }}
              >Import</button>
              <button onClick={() => { setShowImport(false); setImportJson('') }} style={btnStyle}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Template List */}
        <div style={{ padding: '0.75rem 1rem' }}>
          {loading && (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>
              Loading templates...
            </div>
          )}

          {!loading && templates.length === 0 && (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>
              No templates yet. Create one to get started!
            </div>
          )}

          {templates.map((tmpl) => (
            <div
              key={tmpl.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '0.75rem',
                marginBottom: '0.5rem',
                background: tmpl.is_active
                  ? 'rgba(0, 255, 136, 0.08)'
                  : 'rgba(0, 0, 0, 0.3)',
                border: tmpl.is_active
                  ? '1px solid rgba(0, 255, 136, 0.3)'
                  : '1px solid rgba(255, 255, 255, 0.05)',
                borderRadius: '6px',
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  marginBottom: '0.25rem',
                }}>
                  <span style={{ fontSize: '0.95rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                    {tmpl.name}
                  </span>
                  {tmpl.is_active && (
                    <span style={{
                      fontSize: '0.65rem',
                      padding: '0.1rem 0.4rem',
                      background: 'var(--accent-green, #00ff88)',
                      color: '#000',
                      borderRadius: '10px',
                      fontWeight: 'bold',
                    }}>ACTIVE</span>
                  )}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {tmpl.game} • {tmpl.pokemon_name} • {tmpl.step_count} steps • {tmpl.image_count} images • v{tmpl.version}
                </div>
                {tmpl.description && (
                  <div style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-secondary)',
                    marginTop: '0.2rem',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {tmpl.description}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.3rem', flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <button onClick={() => setEditingId(tmpl.id)}
                  style={{ ...btnStyle, border: '1px solid var(--accent-cyan)', color: 'var(--accent-cyan)' }}
                  title="Edit">✏️ Edit</button>
                {!tmpl.is_active && (
                  <button onClick={() => handleActivate(tmpl.id)}
                    style={{ ...btnStyle, border: '1px solid var(--accent-green)', color: 'var(--accent-green)' }}
                    title="Set as active">⚡ Activate</button>
                )}
                <button onClick={() => handleClone(tmpl.id)} style={btnStyle} title="Clone">📋</button>
                <button onClick={() => handleExport(tmpl.id)} style={btnStyle} title="Export">📤</button>
                {!tmpl.is_active && (
                  <button onClick={() => handleDelete(tmpl.id, tmpl.name)}
                    style={{ ...btnStyle, border: '1px solid rgba(255,68,68,0.3)', color: '#ff4444' }}
                    title="Delete">🗑</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default TemplateLibrary
