function DetectionConfigPanel({ definition, onChange }) {
  const detection = definition.detection || {}
  const gender = definition.gender_detection || { enabled: true, zone: {} }
  const nature = definition.nature_detection || { enabled: true, zone: {} }
  const softReset = definition.soft_reset || { hold_duration: 0.5, wait_after: 3.0, max_retries: 3 }

  const updateDetection = (field, value) => {
    onChange({
      ...definition,
      detection: { ...detection, [field]: value },
    })
  }

  const updateZone = (section, field, value) => {
    const current = definition[section] || {}
    const zone = current.zone || {}
    onChange({
      ...definition,
      [section]: { ...current, zone: { ...zone, [field]: parseInt(value) || 0 } },
    })
  }

  const updateDetectionZone = (field, value) => {
    const zone = detection.zone || {}
    onChange({
      ...definition,
      detection: { ...detection, zone: { ...zone, [field]: parseInt(value) || 0 } },
    })
  }

  const updateSoftReset = (field, value) => {
    onChange({
      ...definition,
      soft_reset: { ...softReset, [field]: value },
    })
  }

  const toggleSection = (section) => {
    const current = definition[section] || {}
    onChange({
      ...definition,
      [section]: { ...current, enabled: !current.enabled },
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

  const ZoneInputs = ({ zone, onUpdate }) => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '0.3rem' }}>
      {['upper_x', 'upper_y', 'lower_x', 'lower_y'].map((k) => (
        <div key={k}>
          <label style={{ ...labelStyle, fontSize: '0.65rem' }}>{k.replace('_', ' ')}</label>
          <input
            type="number"
            value={zone[k] || 0}
            onChange={(e) => onUpdate(k, e.target.value)}
            style={inputStyle}
            min="0"
          />
        </div>
      ))}
    </div>
  )

  return (
    <div>
      {/* Shiny Detection */}
      <div style={sectionStyle}>
        <div style={headingStyle}>⭐ Shiny Detection</div>
        <div style={{ marginBottom: '0.4rem' }}>
          <label style={labelStyle}>Method</label>
          <select
            value={detection.method || 'yellow_star_pixels'}
            onChange={(e) => updateDetection('method', e.target.value)}
            style={{ ...inputStyle, width: '150px', cursor: 'pointer' }}
          >
            <option value="yellow_star_pixels">Yellow Star Pixels</option>
          </select>
        </div>

        <div style={{ marginBottom: '0.4rem' }}>
          <label style={labelStyle}>Pixel Threshold</label>
          <input
            type="number"
            value={detection.threshold || 20}
            onChange={(e) => updateDetection('threshold', parseInt(e.target.value) || 0)}
            style={inputStyle}
            min="0"
          />
        </div>

        <label style={labelStyle}>Detection Zone</label>
        <ZoneInputs zone={detection.zone || {}} onUpdate={updateDetectionZone} />
      </div>

      {/* Gender Detection */}
      <div style={sectionStyle}>
        <div style={headingStyle}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={gender.enabled !== false}
              onChange={() => toggleSection('gender_detection')}
            />
            ♂♀ Gender Detection
          </label>
        </div>
        {gender.enabled !== false && gender.zone && Object.keys(gender.zone).length > 0 && (
          <ZoneInputs
            zone={gender.zone}
            onUpdate={(f, v) => updateZone('gender_detection', f, v)}
          />
        )}
        {gender.enabled !== false && (!gender.zone || Object.keys(gender.zone).length === 0) && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Using default calibration zone
          </span>
        )}
      </div>

      {/* Nature Detection */}
      <div style={sectionStyle}>
        <div style={headingStyle}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={nature.enabled !== false}
              onChange={() => toggleSection('nature_detection')}
            />
            📖 Nature Detection (OCR)
          </label>
        </div>
        {nature.enabled !== false && nature.zone && Object.keys(nature.zone).length > 0 && (
          <ZoneInputs
            zone={nature.zone}
            onUpdate={(f, v) => updateZone('nature_detection', f, v)}
          />
        )}
        {nature.enabled !== false && (!nature.zone || Object.keys(nature.zone).length === 0) && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Using default calibration zone
          </span>
        )}
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

export default DetectionConfigPanel
