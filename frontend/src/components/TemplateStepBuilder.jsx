import { useState, useEffect } from 'react'
import RuleEditor from './RuleEditor'
import ActionSequenceBuilder from './ActionSequenceBuilder'
import DetectionConfigPanel from './DetectionConfigPanel'
import TemplateImageManager from './TemplateImageManager'
import {
  getAutomationTemplate,
  createAutomationTemplate,
  updateAutomationTemplate,
} from '../services/api'

const STEP_TYPES = [
  { value: 'navigate', label: 'Navigate (Template Match + Buttons)' },
  { value: 'timed_wait', label: 'Timed Wait' },
  { value: 'shiny_check', label: 'Shiny Check' },
]

const DEFAULT_STEP = {
  name: 'NEW_STEP',
  display_name: 'New Step',
  type: 'navigate',
  cooldown: 0.6,
  rules: [],
  default_action: [],
}

function TemplateStepBuilder({ templateId, onClose, onSaved }) {
  const [template, setTemplate] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [game, setGame] = useState('Pokemon Red')
  const [pokemonName, setPokemonName] = useState('Charmander')
  const [definition, setDefinition] = useState({ version: 1, steps: [], detection: {}, soft_reset: {} })
  const [selectedStepIndex, setSelectedStepIndex] = useState(0)
  const [activeTab, setActiveTab] = useState('steps') // 'steps', 'detection', 'images'
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  const isNew = !templateId

  useEffect(() => {
    if (templateId) loadTemplate()
  }, [templateId])

  const loadTemplate = async () => {
    try {
      const data = await getAutomationTemplate(templateId)
      setTemplate(data)
      setName(data.name)
      setDescription(data.description || '')
      setGame(data.game)
      setPokemonName(data.pokemon_name)
      setDefinition(data.definition || { version: 1, steps: [] })
    } catch (err) {
      console.error('Failed to load template:', err)
    }
  }

  const steps = definition.steps || []
  const currentStep = steps[selectedStepIndex] || null
  const stepNames = steps.map((s) => s.name)

  // Collect all template image keys from rules
  const allTemplateKeys = []
  for (const step of steps) {
    for (const rule of step.rules || []) {
      if (rule.condition?.template) allTemplateKeys.push(rule.condition.template)
    }
  }
  const uniqueTemplateKeys = [...new Set(allTemplateKeys)]

  const updateDefinition = (newDef) => {
    setDefinition(newDef)
    setDirty(true)
  }

  const updateStep = (index, updated) => {
    const newSteps = steps.map((s, i) => (i === index ? updated : s))
    updateDefinition({ ...definition, steps: newSteps })
  }

  const addStep = () => {
    const num = steps.length + 1
    const newStep = {
      ...DEFAULT_STEP,
      name: `STEP_${num}`,
      display_name: `Step ${num}`,
    }
    updateDefinition({ ...definition, steps: [...steps, newStep] })
    setSelectedStepIndex(steps.length)
  }

  const removeStep = (index) => {
    if (!confirm(`Delete step "${steps[index].name}"?`)) return
    const newSteps = steps.filter((_, i) => i !== index)
    updateDefinition({ ...definition, steps: newSteps })
    if (selectedStepIndex >= newSteps.length) {
      setSelectedStepIndex(Math.max(0, newSteps.length - 1))
    }
  }

  const moveStep = (index, direction) => {
    const newIndex = index + direction
    if (newIndex < 0 || newIndex >= steps.length) return
    const newSteps = [...steps]
    ;[newSteps[index], newSteps[newIndex]] = [newSteps[newIndex], newSteps[index]]
    updateDefinition({ ...definition, steps: newSteps })
    setSelectedStepIndex(newIndex)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        name,
        description,
        game,
        pokemon_name: pokemonName,
        definition,
      }

      if (isNew) {
        const result = await createAutomationTemplate(payload)
        setTemplate(result)
      } else {
        await updateAutomationTemplate(templateId, payload)
      }
      setDirty(false)
      onSaved?.()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      alert(`Save failed: ${msg}`)
    } finally {
      setSaving(false)
    }
  }

  // ── Styles ──
  const panelBg = { background: 'var(--bg-secondary, #1a1a2e)', borderRadius: '6px', padding: '0.75rem' }
  const inputStyle = {
    padding: '0.4rem 0.6rem',
    background: 'var(--bg-tertiary, #252540)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary, #e0e0e0)',
    borderRadius: '3px',
    fontSize: '0.85rem',
    fontFamily: "'Courier New', monospace",
    width: '100%',
  }
  const labelStyle = {
    fontSize: '0.7rem',
    color: 'var(--accent-cyan, #00ffff)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '0.25rem',
    display: 'block',
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      zIndex: 1000,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'stretch',
      padding: '1.5rem',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '1200px',
        background: 'var(--bg-primary, #0d0d1a)',
        borderRadius: '8px',
        border: '1px solid var(--accent-cyan, #00ffff)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* ── Header ── */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.75rem 1rem',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          <h2 style={{ fontSize: '1.1rem', margin: 0, color: 'var(--accent-cyan)' }}>
            🛠️ {isNew ? 'New Automation Template' : `Edit: ${name}`}
          </h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: '0.4rem 1rem',
                background: dirty ? 'var(--accent-green, #00ff88)' : 'rgba(0,255,136,0.2)',
                border: '1px solid var(--accent-green, #00ff88)',
                color: dirty ? '#000' : 'var(--accent-green)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 'bold',
              }}
            >
              {saving ? 'Saving...' : dirty ? '💾 Save*' : '💾 Save'}
            </button>
            <button
              onClick={onClose}
              style={{
                padding: '0.4rem 1rem',
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.2)',
                color: 'var(--text-secondary)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              ✕ Close
            </button>
          </div>
        </div>

        {/* ── Metadata Row ── */}
        <div style={{
          display: 'flex',
          gap: '0.5rem',
          padding: '0.5rem 1rem',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
          flexWrap: 'wrap',
        }}>
          <div style={{ flex: 2, minWidth: '150px' }}>
            <label style={labelStyle}>Name</label>
            <input value={name} onChange={(e) => { setName(e.target.value); setDirty(true) }}
              style={inputStyle} placeholder="My Automation" />
          </div>
          <div style={{ flex: 1, minWidth: '100px' }}>
            <label style={labelStyle}>Game</label>
            <input value={game} onChange={(e) => { setGame(e.target.value); setDirty(true) }}
              style={inputStyle} />
          </div>
          <div style={{ flex: 1, minWidth: '100px' }}>
            <label style={labelStyle}>Pokémon</label>
            <input value={pokemonName} onChange={(e) => { setPokemonName(e.target.value); setDirty(true) }}
              style={inputStyle} />
          </div>
        </div>

        {/* ── Tab Bar ── */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          padding: '0 1rem',
        }}>
          {[
            { key: 'steps', label: `📋 Steps (${steps.length})` },
            { key: 'detection', label: '⭐ Detection' },
            { key: 'images', label: `🖼️ Images (${uniqueTemplateKeys.length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: '0.5rem 1rem',
                background: activeTab === tab.key ? 'rgba(0, 255, 255, 0.1)' : 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.key ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                color: activeTab === tab.key ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Content ── */}
        <div style={{ flex: 1, overflow: 'auto', padding: '0.75rem 1rem' }}>
          {/* Steps Tab */}
          {activeTab === 'steps' && (
            <div style={{ display: 'flex', gap: '0.75rem', height: '100%' }}>
              {/* Step List */}
              <div style={{ width: '200px', flexShrink: 0, ...panelBg, overflow: 'auto' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--accent-magenta)', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  STEPS
                </div>
                {steps.map((step, i) => (
                  <div
                    key={i}
                    onClick={() => setSelectedStepIndex(i)}
                    style={{
                      padding: '0.4rem 0.5rem',
                      marginBottom: '0.25rem',
                      background: selectedStepIndex === i ? 'rgba(0, 255, 255, 0.15)' : 'rgba(0,0,0,0.2)',
                      border: selectedStepIndex === i ? '1px solid var(--accent-cyan)' : '1px solid transparent',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {step.display_name || step.name}
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>
                        {step.type} • {step.name}
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                      <button onClick={(e) => { e.stopPropagation(); moveStep(i, -1) }}
                        style={miniBtn} disabled={i === 0}>↑</button>
                      <button onClick={(e) => { e.stopPropagation(); moveStep(i, 1) }}
                        style={miniBtn} disabled={i === steps.length - 1}>↓</button>
                    </div>
                  </div>
                ))}
                <button onClick={addStep} style={{
                  width: '100%',
                  padding: '0.4rem',
                  background: 'transparent',
                  border: '1px dashed rgba(0, 255, 255, 0.3)',
                  color: 'var(--accent-cyan)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  marginTop: '0.25rem',
                }}>+ Add Step</button>
              </div>

              {/* Step Editor */}
              <div style={{ flex: 1, ...panelBg, overflow: 'auto' }}>
                {currentStep ? (
                  <StepEditor
                    step={currentStep}
                    onChange={(updated) => updateStep(selectedStepIndex, updated)}
                    onRemove={() => removeStep(selectedStepIndex)}
                    stepNames={stepNames}
                    templateKeys={uniqueTemplateKeys}
                    inputStyle={inputStyle}
                    labelStyle={labelStyle}
                  />
                ) : (
                  <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>
                    No steps yet. Click "+ Add Step" to begin.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Detection Tab */}
          {activeTab === 'detection' && (
            <div style={panelBg}>
              <DetectionConfigPanel
                definition={definition}
                onChange={(newDef) => updateDefinition(newDef)}
              />
            </div>
          )}

          {/* Images Tab */}
          {activeTab === 'images' && (
            <div style={panelBg}>
              <TemplateImageManager
                templateId={templateId || template?.id}
                definition={definition}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


function StepEditor({ step, onChange, onRemove, stepNames, templateKeys, inputStyle, labelStyle }) {
  const updateField = (field, value) => {
    onChange({ ...step, [field]: value })
  }

  const addRule = () => {
    const rules = step.rules || []
    onChange({
      ...step,
      rules: [...rules, {
        condition: { type: 'template_match', template: '', threshold: 0.80 },
        actions: [],
      }],
    })
  }

  const updateRule = (index, updated) => {
    const rules = (step.rules || []).map((r, i) => (i === index ? updated : r))
    onChange({ ...step, rules })
  }

  const removeRule = (index) => {
    onChange({ ...step, rules: (step.rules || []).filter((_, i) => i !== index) })
  }

  const sectionStyle = {
    marginBottom: '0.75rem',
    padding: '0.5rem',
    background: 'rgba(0, 0, 0, 0.15)',
    borderRadius: '4px',
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', color: 'var(--accent-magenta)' }}>
          ✏️ {step.display_name || step.name}
        </h3>
        <button
          onClick={onRemove}
          style={{
            padding: '0.3rem 0.6rem',
            background: 'transparent',
            border: '1px solid rgba(255,68,68,0.3)',
            color: '#ff4444',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '0.75rem',
          }}
        >🗑 Delete Step</button>
      </div>

      {/* Basic fields */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
        <div style={{ flex: 1, minWidth: '120px' }}>
          <label style={labelStyle}>Step Name (ID)</label>
          <input value={step.name} onChange={(e) => updateField('name', e.target.value.toUpperCase().replace(/\s/g, '_'))}
            style={inputStyle} />
        </div>
        <div style={{ flex: 2, minWidth: '150px' }}>
          <label style={labelStyle}>Display Name</label>
          <input value={step.display_name || ''} onChange={(e) => updateField('display_name', e.target.value)}
            style={inputStyle} />
        </div>
        <div style={{ flex: 1, minWidth: '160px' }}>
          <label style={labelStyle}>Type</label>
          <select
            value={step.type}
            onChange={(e) => updateField('type', e.target.value)}
            style={{ ...inputStyle, cursor: 'pointer' }}
          >
            {STEP_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Type-specific editors */}
      {step.type === 'navigate' && (
        <>
          <div style={{ marginBottom: '0.5rem' }}>
            <label style={labelStyle}>Cooldown (seconds)</label>
            <input type="number" value={step.cooldown || 0.6}
              onChange={(e) => updateField('cooldown', parseFloat(e.target.value) || 0)}
              style={{ ...inputStyle, width: '80px' }} step="0.1" min="0" />
          </div>

          <div style={sectionStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <label style={{ ...labelStyle, margin: 0 }}>Rules ({(step.rules || []).length})</label>
              <button onClick={addRule} style={{
                padding: '0.2rem 0.5rem',
                background: 'rgba(0,255,255,0.1)',
                border: '1px solid var(--accent-cyan)',
                color: 'var(--accent-cyan)',
                borderRadius: '3px',
                cursor: 'pointer',
                fontSize: '0.75rem',
              }}>+ Add Rule</button>
            </div>
            {(step.rules || []).map((rule, i) => (
              <RuleEditor
                key={i}
                rule={rule}
                onChange={(updated) => updateRule(i, updated)}
                onRemove={() => removeRule(i)}
                stepNames={stepNames}
                templateKeys={templateKeys}
              />
            ))}
            {(step.rules || []).length === 0 && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic', padding: '0.5rem' }}>
                No rules. Add rules to react to game screen changes.
              </div>
            )}
          </div>

          <div style={sectionStyle}>
            <label style={labelStyle}>Default Action (when no rule matches)</label>
            <ActionSequenceBuilder
              actions={step.default_action || []}
              onChange={(actions) => updateField('default_action', actions)}
            />
          </div>
        </>
      )}

      {step.type === 'timed_wait' && (
        <>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <div>
              <label style={labelStyle}>Duration (s)</label>
              <input type="number" value={step.duration || 5}
                onChange={(e) => updateField('duration', parseFloat(e.target.value) || 0)}
                style={{ ...inputStyle, width: '80px' }} step="0.5" min="0" />
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Transition To</label>
              <select value={step.transition || ''}
                onChange={(e) => updateField('transition', e.target.value)}
                style={{ ...inputStyle, cursor: 'pointer' }}>
                <option value="">— none —</option>
                {stepNames.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>During Wait Action</label>
            <ActionSequenceBuilder
              actions={step.during_wait_action || []}
              onChange={(a) => updateField('during_wait_action', a)}
            />
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>On Complete Actions</label>
            <ActionSequenceBuilder
              actions={step.on_complete_actions || []}
              onChange={(a) => updateField('on_complete_actions', a)}
            />
          </div>
        </>
      )}

      {step.type === 'shiny_check' && (
        <>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            <div>
              <label style={labelStyle}>Pre-Check Delay (s)</label>
              <input type="number" value={step.pre_check_delay || 1.5}
                onChange={(e) => updateField('pre_check_delay', parseFloat(e.target.value) || 0)}
                style={{ ...inputStyle, width: '80px' }} step="0.5" min="0" />
            </div>
            <div>
              <label style={labelStyle}>Flush Frames</label>
              <input type="number" value={step.buffer_flush_frames || 20}
                onChange={(e) => updateField('buffer_flush_frames', parseInt(e.target.value) || 20)}
                style={{ ...inputStyle, width: '70px' }} min="0" />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', color: 'var(--text-primary)', cursor: 'pointer' }}>
              <input type="checkbox" checked={step.collect_gender !== false}
                onChange={(e) => updateField('collect_gender', e.target.checked)} />
              Collect Gender
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', color: 'var(--text-primary)', cursor: 'pointer' }}>
              <input type="checkbox" checked={step.collect_nature !== false}
                onChange={(e) => updateField('collect_nature', e.target.checked)} />
              Collect Nature
            </label>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>On Normal → Go To</label>
              <select value={step.on_normal_transition || ''}
                onChange={(e) => updateField('on_normal_transition', e.target.value)}
                style={{ ...inputStyle, cursor: 'pointer' }}>
                <option value="">— none —</option>
                {stepNames.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>On Normal Actions (before transition)</label>
            <ActionSequenceBuilder
              actions={step.on_normal_actions || []}
              onChange={(a) => updateField('on_normal_actions', a)}
            />
          </div>
        </>
      )}
    </div>
  )
}

const miniBtn = {
  padding: '0.1rem 0.25rem',
  background: 'transparent',
  border: '1px solid rgba(255,255,255,0.1)',
  color: 'var(--text-secondary)',
  borderRadius: '2px',
  cursor: 'pointer',
  fontSize: '0.6rem',
  lineHeight: 1,
}

export default TemplateStepBuilder
