import { useState } from 'react'

const BUTTONS = ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT']
const ACTION_TYPES = [
  { value: 'press_button', label: 'Press Button' },
  { value: 'wait', label: 'Wait' },
  { value: 'soft_reset', label: 'Soft Reset' },
  { value: 'flush_camera', label: 'Flush Camera' },
]

function ActionSequenceBuilder({ actions = [], onChange, compact = false }) {
  const addAction = () => {
    onChange([...actions, { type: 'press_button', button: 'A' }])
  }

  const updateAction = (index, field, value) => {
    const updated = actions.map((a, i) =>
      i === index ? { ...a, [field]: value } : a
    )
    onChange(updated)
  }

  const removeAction = (index) => {
    onChange(actions.filter((_, i) => i !== index))
  }

  const moveAction = (index, direction) => {
    const newIndex = index + direction
    if (newIndex < 0 || newIndex >= actions.length) return
    const updated = [...actions]
    ;[updated[index], updated[newIndex]] = [updated[newIndex], updated[index]]
    onChange(updated)
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

  return (
    <div style={{ fontSize: '0.8rem' }}>
      {actions.map((action, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            marginBottom: '0.3rem',
            padding: compact ? '0.2rem' : '0.3rem',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '3px',
          }}
        >
          <select
            value={action.type}
            onChange={(e) => updateAction(i, 'type', e.target.value)}
            style={{ ...selectStyle, width: compact ? '90px' : '110px' }}
          >
            {ACTION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>

          {action.type === 'press_button' && (
            <>
              <select
                value={action.button || 'A'}
                onChange={(e) => updateAction(i, 'button', e.target.value)}
                style={{ ...selectStyle, width: '70px' }}
              >
                {BUTTONS.map((b) => (
                  <option key={b} value={b}>{b}</option>
                ))}
              </select>
              <input
                type="number"
                placeholder="wait"
                value={action.wait || ''}
                onChange={(e) => updateAction(i, 'wait', e.target.value ? parseFloat(e.target.value) : undefined)}
                style={{ ...inputStyle, width: '50px' }}
                step="0.1"
                min="0"
                title="Wait after (seconds)"
              />
            </>
          )}

          {action.type === 'wait' && (
            <input
              type="number"
              placeholder="seconds"
              value={action.duration || ''}
              onChange={(e) => updateAction(i, 'duration', parseFloat(e.target.value) || 0)}
              style={{ ...inputStyle, width: '70px' }}
              step="0.1"
              min="0"
            />
          )}

          {action.type === 'soft_reset' && (
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
              A+B+Start+Select
            </span>
          )}

          {action.type === 'flush_camera' && (
            <input
              type="number"
              placeholder="frames"
              value={action.frames || ''}
              onChange={(e) => updateAction(i, 'frames', parseInt(e.target.value) || 20)}
              style={{ ...inputStyle, width: '55px' }}
              min="1"
            />
          )}

          <div style={{ display: 'flex', gap: '0.15rem', marginLeft: 'auto', flexShrink: 0 }}>
            <button
              onClick={() => moveAction(i, -1)}
              disabled={i === 0}
              style={{ ...btnSmall, opacity: i === 0 ? 0.3 : 1 }}
              title="Move up"
            >↑</button>
            <button
              onClick={() => moveAction(i, 1)}
              disabled={i === actions.length - 1}
              style={{ ...btnSmall, opacity: i === actions.length - 1 ? 0.3 : 1 }}
              title="Move down"
            >↓</button>
            <button
              onClick={() => removeAction(i)}
              style={{ ...btnSmall, color: '#ff4444' }}
              title="Remove"
            >×</button>
          </div>
        </div>
      ))}

      <button
        onClick={addAction}
        style={{
          padding: '0.3rem 0.6rem',
          background: 'transparent',
          border: '1px dashed rgba(0, 255, 255, 0.3)',
          color: 'var(--accent-cyan, #00ffff)',
          borderRadius: '3px',
          cursor: 'pointer',
          fontSize: '0.75rem',
          width: '100%',
        }}
      >
        + Add Action
      </button>
    </div>
  )
}

const btnSmall = {
  padding: '0.15rem 0.35rem',
  background: 'transparent',
  border: '1px solid rgba(255,255,255,0.15)',
  color: 'var(--text-secondary)',
  borderRadius: '2px',
  cursor: 'pointer',
  fontSize: '0.7rem',
  lineHeight: 1,
}

export default ActionSequenceBuilder
