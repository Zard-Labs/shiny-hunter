/**
 * SoftResetPanel — per-template soft-reset timing configuration.
 *
 * Detection zones and thresholds are now configured globally via the
 * Calibration Modal (config.yaml), so this panel only handles reset timing
 * which can vary per game / automation template.
 */
function SoftResetPanel({ definition, onChange }) {
  const softReset = definition.soft_reset || { hold_duration: 0.5, wait_after: 3.0, max_retries: 3 }

  const updateSoftReset = (field, value) => {
    onChange({
      ...definition,
      soft_reset: { ...softReset, [field]: value },
    })
  }

  const inputStyle = {
    padding: '0.3rem 0.5rem',
    background: 'var(--bg-tertiary, #252540)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary, #e0e0e0)',
    borderRadius: '3px',
    fontSize: '0.8rem',
    fontFamily: "'Courier New', monospace",
    width: '65px',
  }

  const labelStyle = {
    fontSize: '0.7rem',
    color: 'var(--accent-cyan, #00ffff)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '0.2rem',
    display: 'block',
  }

  const sectionStyle = {
    marginBottom: '0.75rem',
    padding: '0.5rem',
    background: 'rgba(0, 0, 0, 0.2)',
    borderRadius: '4px',
  }

  const headingStyle = {
    fontSize: '0.8rem',
    fontWeight: 'bold',
    color: 'var(--text-primary)',
    marginBottom: '0.4rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  }

  return (
    <div>
      {/* Info banner */}
      <div style={{
        padding: '0.5rem 0.75rem',
        marginBottom: '0.75rem',
        background: 'rgba(0, 255, 255, 0.05)',
        border: '1px solid rgba(0, 255, 255, 0.15)',
        borderRadius: '4px',
        fontSize: '0.75rem',
        color: 'var(--text-secondary)',
        lineHeight: '1.5',
      }}>
        ℹ️ Detection zones and thresholds (shiny, gender, nature) are configured
        globally via the <strong style={{ color: 'var(--accent-cyan)' }}>Calibration Modal</strong> on
        the main dashboard. They apply to all templates.
      </div>

      {/* Soft Reset */}
      <div style={sectionStyle}>
        <div style={headingStyle}>🔄 Soft Reset Timing</div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <div>
            <label style={labelStyle}>Hold (s)</label>
            <input
              type="number"
              value={softReset.hold_duration}
              onChange={(e) => updateSoftReset('hold_duration', parseFloat(e.target.value) || 0)}
              style={inputStyle}
              step="0.1"
              min="0"
            />
          </div>
          <div>
            <label style={labelStyle}>Wait After (s)</label>
            <input
              type="number"
              value={softReset.wait_after}
              onChange={(e) => updateSoftReset('wait_after', parseFloat(e.target.value) || 0)}
              style={inputStyle}
              step="0.5"
              min="0"
            />
          </div>
          <div>
            <label style={labelStyle}>Retries</label>
            <input
              type="number"
              value={softReset.max_retries}
              onChange={(e) => updateSoftReset('max_retries', parseInt(e.target.value) || 1)}
              style={inputStyle}
              min="1"
              max="10"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default SoftResetPanel
