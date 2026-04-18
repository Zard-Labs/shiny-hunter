import { useState } from 'react'
import ActionSequenceBuilder from './ActionSequenceBuilder'
import SnapshotROIPicker from './SnapshotROIPicker'

function RuleEditor({ rule, onChange, onRemove, stepNames = [], templateKeys = [] }) {
  const condition = rule.condition || {}
  const [showROIPicker, setShowROIPicker] = useState(false)

  const hasROI = !!condition.roi
  const roi = condition.roi || { x: 0, y: 0, width: 0, height: 0 }

  const updateCondition = (field, value) => {
    onChange({
      ...rule,
      condition: { ...condition, [field]: value },
    })
  }

  const updateROIField = (field, value) => {
    const updated = { ...roi, [field]: parseInt(value, 10) || 0 }
    updateCondition('roi', updated)
  }

  const toggleROI = () => {
    if (hasROI) {
      // Remove ROI from condition
      const { roi: _, ...rest } = condition
      onChange({ ...rule, condition: rest })
    } else {
      // Add empty ROI
      updateCondition('roi', { x: 0, y: 0, width: 0, height: 0 })
    }
  }

  const handleROISelected = (region) => {
    updateCondition('roi', region)
    setShowROIPicker(false)
  }

  const clearROI = () => {
    const { roi: _, ...rest } = condition
    onChange({ ...rule, condition: rest })
  }

  const updateActions = (actions) => {
    onChange({ ...rule, actions })
  }

  const updateTransition = (transition) => {
    if (transition === '') {
      const { transition: _, ...rest } = rule
      onChange(rest)
    } else {
      onChange({ ...rule, transition })
    }
  }

  const inputStyle = {
    padding: '0.3rem 0.5rem',
    background: 'var(--bg-tertiary, #252540)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary, #e0e0e0)',
    borderRadius: '3px',
    fontSize: '0.8rem',
    fontFamily: "'Courier New', monospace",
  }

  const selectStyle = { ...inputStyle, cursor: 'pointer' }

  const labelStyle = {
    fontSize: '0.7rem',
    color: 'var(--accent-cyan, #00ffff)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '0.25rem',
    display: 'block',
  }

  const smallBtnStyle = {
    padding: '0.2rem 0.5rem',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.7rem',
    fontFamily: "'Courier New', monospace",
    background: 'rgba(255,255,255,0.05)',
    color: '#aaa',
  }

  return (
    <div
      style={{
        border: '1px solid rgba(0, 255, 255, 0.15)',
        borderRadius: '4px',
        padding: '0.6rem',
        marginBottom: '0.5rem',
        background: 'rgba(0, 0, 50, 0.2)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
          IF Condition
        </span>
        <button
          onClick={onRemove}
          style={{
            padding: '0.15rem 0.4rem',
            background: 'transparent',
            border: '1px solid rgba(255,68,68,0.3)',
            color: '#ff4444',
            borderRadius: '2px',
            cursor: 'pointer',
            fontSize: '0.7rem',
          }}
        >
          Remove Rule
        </button>
      </div>

      {/* Condition */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
        <div>
          <label style={labelStyle}>Type</label>
          <select
            value={condition.type || 'template_match'}
            onChange={(e) => updateCondition('type', e.target.value)}
            style={selectStyle}
          >
            <option value="template_match">Template Match</option>
          </select>
        </div>

        {condition.type === 'template_match' && (
          <>
            <div style={{ flex: 1, minWidth: '120px' }}>
              <label style={labelStyle}>Template Image</label>
              {templateKeys.length > 0 ? (
                <select
                  value={condition.template || ''}
                  onChange={(e) => updateCondition('template', e.target.value)}
                  style={{ ...selectStyle, width: '100%' }}
                >
                  <option value="">— select —</option>
                  {templateKeys.map((k) => (
                    <option key={k} value={k}>{k.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="e.g. title_screen"
                  value={condition.template || ''}
                  onChange={(e) => updateCondition('template', e.target.value)}
                  style={{ ...inputStyle, width: '100%' }}
                />
              )}
            </div>
            <div>
              <label style={labelStyle}>Threshold</label>
              <input
                type="number"
                value={condition.threshold || 0.80}
                onChange={(e) => updateCondition('threshold', parseFloat(e.target.value))}
                style={{ ...inputStyle, width: '60px' }}
                step="0.05"
                min="0"
                max="1"
              />
            </div>
          </>
        )}
      </div>

      {/* ROI (Search Region) — only for template_match */}
      {condition.type === 'template_match' && (
        <div style={{ marginBottom: '0.5rem' }}>
          <label
            style={{
              ...labelStyle,
              cursor: 'pointer',
              userSelect: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
            onClick={toggleROI}
          >
            <input
              type="checkbox"
              checked={hasROI}
              onChange={toggleROI}
              style={{ margin: 0, cursor: 'pointer' }}
              onClick={(e) => e.stopPropagation()}
            />
            Limit search to region (ROI)
          </label>

          {hasROI && (
            <div
              style={{
                marginTop: '0.35rem',
                padding: '0.4rem',
                border: '1px solid rgba(0, 255, 200, 0.15)',
                borderRadius: '3px',
                background: 'rgba(0, 255, 200, 0.03)',
              }}
            >
              {/* Coordinate inputs */}
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
                {['x', 'y', 'width', 'height'].map((field) => (
                  <div key={field}>
                    <label
                      style={{
                        fontSize: '0.65rem',
                        color: '#00ffc8',
                        textTransform: 'uppercase',
                        display: 'block',
                        marginBottom: '0.15rem',
                      }}
                    >
                      {field === 'width' ? 'W' : field === 'height' ? 'H' : field.toUpperCase()}
                    </label>
                    <input
                      type="number"
                      value={roi[field] || 0}
                      onChange={(e) => updateROIField(field, e.target.value)}
                      style={{ ...inputStyle, width: '60px' }}
                      min="0"
                    />
                  </div>
                ))}
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button
                  onClick={() => setShowROIPicker(true)}
                  style={{
                    ...smallBtnStyle,
                    background: 'rgba(0, 255, 200, 0.1)',
                    color: '#00ffc8',
                    border: '1px solid rgba(0, 255, 200, 0.3)',
                  }}
                >
                  📷 Draw on Snapshot
                </button>
                <button onClick={clearROI} style={smallBtnStyle}>
                  ✕ Clear Region
                </button>
              </div>

              {/* Inline snapshot ROI picker */}
              {showROIPicker && (
                <SnapshotROIPicker
                  initialRegion={roi.width > 0 ? roi : null}
                  onRegionSelected={handleROISelected}
                  onCancel={() => setShowROIPicker(false)}
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div style={{ marginBottom: '0.5rem' }}>
        <label style={labelStyle}>THEN Actions</label>
        <ActionSequenceBuilder
          actions={rule.actions || []}
          onChange={updateActions}
          compact
        />
      </div>

      {/* Transition */}
      <div>
        <label style={labelStyle}>GO TO Step (optional)</label>
        <select
          value={rule.transition || ''}
          onChange={(e) => updateTransition(e.target.value)}
          style={{ ...selectStyle, width: '100%' }}
        >
          <option value="">— stay in current step —</option>
          {stepNames.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
      </div>
    </div>
  )
}

export default RuleEditor
