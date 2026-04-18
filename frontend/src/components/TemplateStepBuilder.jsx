import { useState, useEffect } from 'react'
import RuleEditor from './RuleEditor'
import ActionSequenceBuilder from './ActionSequenceBuilder'
import SoftResetPanel from './SoftResetPanel'
import TemplateImageManager from './TemplateImageManager'
import {
  getAutomationTemplate,
  createAutomationTemplate,
  updateAutomationTemplate,
  getAutomationTemplateImages,
  getGameLanguage,
} from '../services/api'
import { displayNature } from '../utils/natureUtils'

const STEP_TYPES = [
  { value: 'navigate', label: 'Navigate (Template Match + Buttons)' },
  { value: 'timed_wait', label: 'Timed Wait' },
  { value: 'shiny_check', label: 'Shiny Check (Summary Screen)' },
  { value: 'battle_shiny_check', label: '⚔️ Battle Sparkle Check' },
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
  const [activeTab, setActiveTab] = useState('steps') // 'steps', 'reset', 'images'
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [apiImageKeys, setApiImageKeys] = useState([])

  const isNew = !templateId

  const effectiveTemplateId = templateId || template?.id

  useEffect(() => {
    if (templateId) loadTemplate()
  }, [templateId])

  // Fetch template images from backend whenever the template is loaded or tab changes
  useEffect(() => {
    if (effectiveTemplateId) fetchTemplateImageKeys()
  }, [effectiveTemplateId, activeTab])

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

  const fetchTemplateImageKeys = async () => {
    try {
      const images = await getAutomationTemplateImages(effectiveTemplateId)
      setApiImageKeys(images.map((img) => img.key))
    } catch (err) {
      console.error('Failed to fetch template image keys:', err)
    }
  }

  const steps = definition.steps || []
  const currentStep = steps[selectedStepIndex] || null
  const stepNames = steps.map((s) => s.name)

  // Collect template image keys from rules AND from API-stored images
  const ruleTemplateKeys = []
  for (const step of steps) {
    for (const rule of step.rules || []) {
      if (rule.condition?.template) ruleTemplateKeys.push(rule.condition.template)
    }
  }
  const uniqueTemplateKeys = [...new Set([...ruleTemplateKeys, ...apiImageKeys])].sort()

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
            { key: 'reset', label: '🔄 Soft Reset' },
            { key: 'watchdog', label: '⏱ Watchdog' },
            { key: 'target', label: '🎯 Target Criteria' },
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

          {/* Soft Reset Tab */}
          {activeTab === 'reset' && (
            <div style={panelBg}>
              <SoftResetPanel
                definition={definition}
                onChange={(newDef) => updateDefinition(newDef)}
              />
            </div>
          )}

          {/* Watchdog Tab */}
          {activeTab === 'watchdog' && (
            <div style={panelBg}>
              <WatchdogPanel
                definition={definition}
                onChange={(newDef) => updateDefinition(newDef)}
              />
            </div>
          )}

          {/* Target Criteria Tab */}
          {activeTab === 'target' && (
            <div style={panelBg}>
              <TargetCriteriaPanel
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

      {step.type === 'battle_shiny_check' && (
        <>
          <div style={{
            padding: '0.4rem 0.5rem',
            marginBottom: '0.5rem',
            background: 'rgba(255, 170, 0, 0.08)',
            border: '1px solid rgba(255, 170, 0, 0.2)',
            borderRadius: '4px',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
            lineHeight: '1.5'
          }}>
            ⚔️ <strong>Battle Sparkle Check</strong> — Captures a window of frames during
            battle entry and analyses them for the shiny sparkle animation.
            Uses the ring buffer for multi-frame detection. Detection zone &amp;
            thresholds can also be set in the template&apos;s top-level detection config.
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            <div>
              <label style={labelStyle}>Pre-Check Delay (s)</label>
              <input type="number" value={step.pre_check_delay ?? 0.5}
                onChange={(e) => updateField('pre_check_delay', parseFloat(e.target.value) || 0)}
                style={{ ...inputStyle, width: '80px' }} step="0.1" min="0" />
            </div>
            <div>
              <label style={labelStyle}>Capture Window (s)</label>
              <input type="number" value={step.capture_window_seconds ?? 1.5}
                onChange={(e) => updateField('capture_window_seconds', parseFloat(e.target.value) || 0)}
                style={{ ...inputStyle, width: '80px' }} step="0.1" min="0.5" />
            </div>
            <div>
              <label style={labelStyle}>Analysis Frames</label>
              <input type="number" value={step.analysis_frames ?? 45}
                onChange={(e) => updateField('analysis_frames', parseInt(e.target.value) || 45)}
                style={{ ...inputStyle, width: '70px' }} min="10" max="90" />
            </div>
            <div>
              <label style={labelStyle}>Ring Buffer</label>
              <input type="number" value={step.ring_buffer_frames ?? 90}
                onChange={(e) => updateField('ring_buffer_frames', parseInt(e.target.value) || 90)}
                style={{ ...inputStyle, width: '70px' }} min="30" max="300" />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            <div>
              <label style={labelStyle}>Spark Threshold</label>
              <input type="number" value={step.spark_threshold ?? 10}
                onChange={(e) => updateField('spark_threshold', parseInt(e.target.value) || 10)}
                style={{ ...inputStyle, width: '70px' }} min="1" />
            </div>
            <div>
              <label style={labelStyle}>Peak Threshold</label>
              <input type="number" value={step.peak_threshold ?? 50}
                onChange={(e) => updateField('peak_threshold', parseInt(e.target.value) || 50)}
                style={{ ...inputStyle, width: '70px' }} min="1" />
            </div>
            <div>
              <label style={labelStyle}>Min Spike Frames</label>
              <input type="number" value={step.min_spike_frames ?? 3}
                onChange={(e) => updateField('min_spike_frames', parseInt(e.target.value) || 3)}
                style={{ ...inputStyle, width: '70px' }} min="1" />
            </div>
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


// ── Watchdog Panel ─────────────────────────────────────────────

const RECOVERY_STRATEGIES = [
  { value: 'soft_reset', label: 'Soft Reset (go to first step)' },
  { value: 'retry_step', label: 'Retry Step (reset timer, stay here)' },
  { value: 'goto_step', label: 'Go To Step (jump to named step)' },
  { value: 'stop', label: 'Stop Automation' },
]

function WatchdogPanel({ definition, onChange }) {
  const gr = definition.global_recovery || {}
  const defaultTimeout = gr.default_timeout ?? 60
  const defaultStrategy = gr.default_strategy || 'soft_reset'
  const maxConsecutive = gr.max_consecutive_recoveries ?? 10
  const stopOnMax = gr.stop_on_max_recoveries !== false

  const steps = definition.steps || []

  const updateGlobal = (patch) => {
    onChange({
      ...definition,
      global_recovery: { ...gr, ...patch },
    })
  }

  const updateStepField = (stepIndex, field, value) => {
    const newSteps = steps.map((s, i) => {
      if (i !== stepIndex) return s
      if (field === 'timeout') {
        return { ...s, timeout: value }
      }
      // recovery sub-object fields
      const recovery = s.recovery || {}
      return { ...s, recovery: { ...recovery, [field]: value } }
    })
    onChange({ ...definition, steps: newSteps })
  }

  const inputStyle = {
    padding: '0.4rem 0.6rem',
    background: 'var(--bg-tertiary, #252540)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary, #e0e0e0)',
    borderRadius: '3px',
    fontSize: '0.85rem',
    fontFamily: "'Courier New', monospace",
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
    <div>
      <h3 style={{ color: 'var(--accent-cyan)', fontSize: '0.95rem', marginTop: 0 }}>
        ⏱ Watchdog & Recovery
      </h3>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 0 }}>
        Detect when the automation gets stuck in a step and automatically recover.
        The watchdog monitors how long each step has been running; if a step exceeds its
        timeout, the configured recovery strategy fires automatically.
      </p>

      {/* ── Global Recovery Defaults ── */}
      <div style={{
        padding: '0.75rem',
        background: 'rgba(0, 0, 0, 0.2)',
        borderRadius: '4px',
        border: '1px solid rgba(255,255,255,0.05)',
        marginBottom: '1rem',
      }}>
        <div style={{ ...labelStyle, fontSize: '0.8rem', color: 'var(--accent-magenta)', marginBottom: '0.5rem' }}>
          GLOBAL DEFAULTS
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
          <div>
            <label style={labelStyle}>Default Timeout (seconds)</label>
            <input
              type="number"
              min="0"
              step="5"
              value={defaultTimeout}
              onChange={(e) => updateGlobal({ default_timeout: parseInt(e.target.value, 10) || 0 })}
              style={{ ...inputStyle, width: '100px' }}
            />
            <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
              0 = disabled (no watchdog)
            </div>
          </div>

          <div>
            <label style={labelStyle}>Default Strategy</label>
            <select
              value={defaultStrategy}
              onChange={(e) => updateGlobal({ default_strategy: e.target.value })}
              style={{ ...inputStyle, width: '250px' }}
            >
              {RECOVERY_STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={labelStyle}>Max Consecutive Recoveries</label>
            <input
              type="number"
              min="0"
              value={maxConsecutive}
              onChange={(e) => updateGlobal({ max_consecutive_recoveries: parseInt(e.target.value, 10) || 0 })}
              style={{ ...inputStyle, width: '80px' }}
            />
          </div>

          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            cursor: 'pointer',
            paddingBottom: '0.4rem',
          }}>
            <input
              type="checkbox"
              checked={stopOnMax}
              onChange={(e) => updateGlobal({ stop_on_max_recoveries: e.target.checked })}
              style={{ accentColor: 'var(--accent-cyan)' }}
            />
            <span style={{ color: 'var(--text-primary)', fontSize: '0.8rem' }}>
              Stop automation when max reached
            </span>
          </label>
        </div>
      </div>

      {/* ── Per-Step Timeout & Recovery ── */}
      <div style={{
        padding: '0.75rem',
        background: 'rgba(0, 0, 0, 0.2)',
        borderRadius: '4px',
        border: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ ...labelStyle, fontSize: '0.8rem', color: 'var(--accent-magenta)', marginBottom: '0.5rem' }}>
          PER-STEP TIMEOUTS
        </div>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', margin: '0 0 0.5rem 0' }}>
          Override the global default timeout and strategy for individual steps.
          Leave timeout blank to use the global default ({defaultTimeout}s).
        </p>

        {steps.length === 0 ? (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic', padding: '1rem', textAlign: 'center' }}>
            No steps defined. Add steps in the Steps tab first.
          </div>
        ) : (
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.8rem',
          }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-secondary)', fontWeight: 'normal', fontSize: '0.7rem', textTransform: 'uppercase' }}>Step</th>
                <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-secondary)', fontWeight: 'normal', fontSize: '0.7rem', textTransform: 'uppercase' }}>Type</th>
                <th style={{ textAlign: 'center', padding: '0.4rem 0.5rem', color: 'var(--text-secondary)', fontWeight: 'normal', fontSize: '0.7rem', textTransform: 'uppercase', width: '90px' }}>Timeout (s)</th>
                <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-secondary)', fontWeight: 'normal', fontSize: '0.7rem', textTransform: 'uppercase' }}>Recovery Strategy</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step, i) => {
                const stepTimeout = step.timeout
                const stepStrategy = step.recovery?.strategy || ''
                const hasOverride = stepTimeout !== undefined || stepStrategy
                return (
                  <tr
                    key={i}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      background: hasOverride ? 'rgba(0, 255, 255, 0.03)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '0.35rem 0.5rem' }}>
                      <div style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        {step.display_name || step.name}
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>
                        {step.name}
                      </div>
                    </td>
                    <td style={{ padding: '0.35rem 0.5rem', color: 'var(--text-secondary)' }}>
                      {step.type}
                    </td>
                    <td style={{ padding: '0.35rem 0.5rem', textAlign: 'center' }}>
                      <input
                        type="number"
                        min="0"
                        step="5"
                        value={stepTimeout ?? ''}
                        placeholder={String(defaultTimeout)}
                        onChange={(e) => {
                          const val = e.target.value === '' ? undefined : parseInt(e.target.value, 10)
                          updateStepField(i, 'timeout', val)
                        }}
                        style={{
                          ...inputStyle,
                          width: '70px',
                          textAlign: 'center',
                          opacity: stepTimeout !== undefined ? 1 : 0.5,
                        }}
                      />
                    </td>
                    <td style={{ padding: '0.35rem 0.5rem' }}>
                      <select
                        value={stepStrategy}
                        onChange={(e) => updateStepField(i, 'strategy', e.target.value || undefined)}
                        style={{
                          ...inputStyle,
                          width: '100%',
                          opacity: stepStrategy ? 1 : 0.5,
                        }}
                      >
                        <option value="">— use global —</option>
                        {RECOVERY_STRATEGIES.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Summary ── */}
      <div style={{
        marginTop: '0.75rem',
        padding: '0.5rem 0.75rem',
        background: 'rgba(0, 255, 255, 0.05)',
        border: '1px solid rgba(0, 255, 255, 0.15)',
        borderRadius: '4px',
        fontSize: '0.75rem',
        color: 'var(--text-secondary)',
      }}>
        <span style={{ color: 'var(--accent-cyan)', fontWeight: 'bold' }}>📋 Summary: </span>
        {defaultTimeout > 0 ? (
          <>
            Watchdog active — steps time out after{' '}
            <span style={{ color: 'var(--accent-green)' }}>{defaultTimeout}s</span> by default,{' '}
            recovery: <span style={{ color: 'var(--accent-green)' }}>{defaultStrategy}</span>,{' '}
            max consecutive: <span style={{ color: 'var(--accent-yellow)' }}>{maxConsecutive}</span>
            {stopOnMax ? ' (stops on max)' : ' (continues after max)'}
          </>
        ) : (
          <span style={{ color: 'var(--accent-yellow)' }}>
            Watchdog disabled — set a default timeout greater than 0 to enable
          </span>
        )}
      </div>
    </div>
  )
}


// ── Target Criteria Panel ──────────────────────────────────────

const ALL_NATURES = [
  'Hardy', 'Lonely', 'Brave', 'Adamant', 'Naughty',
  'Bold', 'Docile', 'Relaxed', 'Impish', 'Lax',
  'Timid', 'Hasty', 'Serious', 'Jolly', 'Naive',
  'Modest', 'Mild', 'Quiet', 'Bashful', 'Rash',
  'Calm', 'Gentle', 'Sassy', 'Careful', 'Quirky',
]

function TargetCriteriaPanel({ definition, onChange }) {
  const [gameLanguage, setGameLanguage] = useState('en')
  
  useEffect(() => {
    getGameLanguage()
      .then(data => setGameLanguage(data.language || 'en'))
      .catch(() => {})
  }, [])

  const tc = definition.target_criteria || {}
  const enabled = tc.enabled !== undefined ? tc.enabled : false
  const desiredNatures = tc.desired_natures || []
  const desiredGender = tc.desired_gender || 'any'
  const onMismatch = tc.on_mismatch || 'keep_hunting'
  const maxShinySkips = tc.max_shiny_skips ?? 0

  const update = (patch) => {
    onChange({
      ...definition,
      target_criteria: { ...tc, ...patch },
    })
  }

  const toggleNature = (nature) => {
    const next = desiredNatures.includes(nature)
      ? desiredNatures.filter((n) => n !== nature)
      : [...desiredNatures, nature]
    update({ desired_natures: next })
  }

  const inputStyle = {
    padding: '0.4rem 0.6rem',
    background: 'var(--bg-tertiary, #252540)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: 'var(--text-primary, #e0e0e0)',
    borderRadius: '3px',
    fontSize: '0.85rem',
    fontFamily: "'Courier New', monospace",
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
    <div>
      <h3 style={{ color: 'var(--accent-cyan)', fontSize: '0.95rem', marginTop: 0 }}>
        🎯 Target Criteria
      </h3>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 0 }}>
        Define which shinies to keep. When a shiny is found but doesn't match these criteria,
        the automation can skip it and continue hunting.
      </p>

      {/* Enable/Disable toggle */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => update({ enabled: e.target.checked })}
            style={{ accentColor: 'var(--accent-cyan)' }}
          />
          <span style={{ color: enabled ? 'var(--accent-green)' : 'var(--text-secondary)', fontWeight: 'bold', fontSize: '0.85rem' }}>
            {enabled ? 'Target filtering ENABLED' : 'Target filtering disabled'}
          </span>
        </label>
      </div>

      {enabled && (
        <>
          {/* Desired Natures */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>
              Desired Natures {desiredNatures.length > 0 && `(${desiredNatures.length} selected)`}
            </label>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, 1fr)',
              gap: '0.25rem',
              maxHeight: '200px',
              overflowY: 'auto',
              padding: '0.5rem',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '4px',
              border: '1px solid rgba(255,255,255,0.05)',
            }}>
              {ALL_NATURES.map((nature) => {
                const isSelected = desiredNatures.includes(nature)
                return (
                  <label
                    key={nature}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                      cursor: 'pointer',
                      padding: '0.15rem 0.3rem',
                      borderRadius: '3px',
                      fontSize: '0.75rem',
                      background: isSelected ? 'rgba(0, 255, 255, 0.1)' : 'transparent',
                      color: isSelected ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                      border: isSelected ? '1px solid rgba(0,255,255,0.3)' : '1px solid transparent',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleNature(nature)}
                      style={{ accentColor: 'var(--accent-cyan)', width: '12px', height: '12px' }}
                    />
                    {displayNature(nature, gameLanguage)}
                  </label>
                )
              })}
            </div>
            {desiredNatures.length === 0 && (
              <div style={{ fontSize: '0.7rem', color: 'var(--accent-yellow)', marginTop: '0.25rem' }}>
                ⚠ No natures selected — any nature will be accepted
              </div>
            )}
          </div>

          {/* Gender */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Desired Gender</label>
            <select
              value={desiredGender}
              onChange={(e) => update({ desired_gender: e.target.value })}
              style={{ ...inputStyle, width: '200px' }}
            >
              <option value="any">Any</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>

          {/* On Mismatch Behavior */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>On Mismatch Behavior</label>
            <select
              value={onMismatch}
              onChange={(e) => update({ on_mismatch: e.target.value })}
              style={{ ...inputStyle, width: '250px' }}
            >
              <option value="keep_hunting">Keep Hunting (soft reset &amp; continue)</option>
              <option value="always_stop">Always Stop (pause for manual decision)</option>
            </select>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              {onMismatch === 'keep_hunting'
                ? 'Automation will soft-reset and continue hunting when a shiny doesn\'t match criteria.'
                : 'Automation will stop when a shiny is found, even if it doesn\'t match criteria.'}
            </div>
          </div>

          {/* Max Shiny Skips */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Max Shiny Skips (0 = unlimited)</label>
            <input
              type="number"
              min="0"
              value={maxShinySkips}
              onChange={(e) => update({ max_shiny_skips: parseInt(e.target.value, 10) || 0 })}
              style={{ ...inputStyle, width: '120px' }}
            />
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              {maxShinySkips === 0
                ? 'Will keep skipping non-matching shinies indefinitely.'
                : `Will stop after skipping ${maxShinySkips} shiny Pokémon.`}
            </div>
          </div>

          {/* Summary */}
          {desiredNatures.length > 0 && (
            <div style={{
              padding: '0.75rem',
              background: 'rgba(0, 255, 255, 0.05)',
              border: '1px solid rgba(0, 255, 255, 0.15)',
              borderRadius: '4px',
              fontSize: '0.8rem',
            }}>
              <div style={{ color: 'var(--accent-cyan)', fontWeight: 'bold', marginBottom: '0.3rem' }}>
                📋 Target Summary
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>
                Looking for: <span style={{ color: 'var(--accent-green)' }}>{desiredNatures.map(n => displayNature(n, gameLanguage)).join(', ')}</span>
                {desiredGender !== 'any' && (
                  <> • Gender: <span style={{ color: 'var(--accent-green)' }}>{desiredGender}</span></>
                )}
                {maxShinySkips > 0 && (
                  <> • Max skips: <span style={{ color: 'var(--accent-yellow)' }}>{maxShinySkips}</span></>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default TemplateStepBuilder
