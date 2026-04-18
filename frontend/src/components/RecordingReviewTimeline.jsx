import { useState, useEffect, useMemo } from 'react'
import VideoFrameScrubber from './VideoFrameScrubber'
import {
  getRecordingSession,
  getRecordingScreenshotUrl,
  extractRecordingFrame,
  convertRecordingToTemplate,
} from '../services/api'

/**
 * Post-recording review timeline.
 *
 * Shows all recorded events grouped into steps.  The user can:
 * - Scrub the video frame-by-frame to find perfect screenshots
 * - Group button presses into steps (auto-grouped by pauses)
 * - Select template images from auto-captures or video frames
 * - Generate a complete automation template
 */

const PAUSE_THRESHOLD = 2.0 // seconds — auto-insert step boundary after this gap

function RecordingReviewTimeline({ sessionId, onTemplateCreated, onClose }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [stepGroups, setStepGroups] = useState([])
  const [selectedFrame, setSelectedFrame] = useState(0)
  const [generating, setGenerating] = useState(false)

  // Template metadata
  const [templateName, setTemplateName] = useState('')
  const [templateGame, setTemplateGame] = useState('Pokemon RedGreen')
  const [templatePokemon, setTemplatePokemon] = useState('Starters')

  // Load session data
  useEffect(() => {
    loadSession()
  }, [sessionId])

  const loadSession = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getRecordingSession(sessionId)
      setSession(data)
      setTemplateName(`Recording ${new Date(data.started_at).toLocaleDateString()}`)

      // Auto-group events into steps
      const groups = autoGroupEvents(data.events)
      setStepGroups(groups)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load session')
    } finally {
      setLoading(false)
    }
  }

  // Auto-group events by pauses >2s
  const autoGroupEvents = (events) => {
    if (!events || events.length === 0) return []

    const groups = []
    let currentGroup = {
      name: 'STEP_1',
      display_name: 'Step 1',
      event_indices: [],
      template_image: null,
    }

    let prevTimestamp = null
    const stepMarkerIndices = new Set()

    // Find step markers first
    events.forEach((e, i) => {
      if (e.event_type === 'step_marker') stepMarkerIndices.add(i)
    })

    events.forEach((event, index) => {
      if (event.event_type === 'step_marker') {
        // Force a new group at step markers
        if (currentGroup.event_indices.length > 0) {
          groups.push(currentGroup)
          const num = groups.length + 1
          currentGroup = {
            name: event.label || `STEP_${num}`,
            display_name: event.label || `Step ${num}`,
            event_indices: [],
            template_image: null,
          }
        } else {
          // Rename current empty group
          currentGroup.name = event.label || currentGroup.name
          currentGroup.display_name = event.label || currentGroup.display_name
        }
        prevTimestamp = event.timestamp
        return
      }

      if (event.event_type !== 'button_press') return

      // Check for pause-based split
      if (
        prevTimestamp !== null &&
        event.timestamp - prevTimestamp > PAUSE_THRESHOLD &&
        currentGroup.event_indices.length > 0
      ) {
        groups.push(currentGroup)
        const num = groups.length + 1
        currentGroup = {
          name: `STEP_${num}`,
          display_name: `Step ${num}`,
          event_indices: [],
          template_image: null,
        }
      }

      currentGroup.event_indices.push(index)
      prevTimestamp = event.timestamp
    })

    // Push last group
    if (currentGroup.event_indices.length > 0) {
      groups.push(currentGroup)
    }

    // Auto-select the first screenshot of each group as its template image
    groups.forEach((group) => {
      if (group.event_indices.length > 0) {
        const firstEventIdx = group.event_indices[0]
        const firstEvent = events[firstEventIdx]
        if (firstEvent && firstEvent.screenshot_index != null) {
          group.template_image = {
            source: 'screenshot',
            index: firstEvent.screenshot_index,
          }
        }
      }
    })

    return groups
  }

  // Insert a step boundary between two step groups
  const insertBoundaryAfter = (groupIndex) => {
    const newGroups = [...stepGroups]
    const group = newGroups[groupIndex]
    if (group.event_indices.length < 2) return

    // Split in half
    const mid = Math.ceil(group.event_indices.length / 2)
    const firstHalf = group.event_indices.slice(0, mid)
    const secondHalf = group.event_indices.slice(mid)

    const num = newGroups.length + 1
    newGroups.splice(groupIndex, 1,
      { ...group, event_indices: firstHalf },
      {
        name: `STEP_${num}`,
        display_name: `Step ${num}`,
        event_indices: secondHalf,
        template_image: null,
      }
    )
    setStepGroups(newGroups)
  }

  // Merge a step group with the next one
  const mergeWithNext = (groupIndex) => {
    if (groupIndex >= stepGroups.length - 1) return
    const newGroups = [...stepGroups]
    const current = newGroups[groupIndex]
    const next = newGroups[groupIndex + 1]
    newGroups.splice(groupIndex, 2, {
      ...current,
      event_indices: [...current.event_indices, ...next.event_indices],
    })
    setStepGroups(newGroups)
  }

  // Remove a step group
  const removeGroup = (groupIndex) => {
    if (!confirm('Delete this step and all its events?')) return
    const newGroups = stepGroups.filter((_, i) => i !== groupIndex)
    setStepGroups(newGroups)
  }

  // Rename a step
  const renameGroup = (groupIndex, newName) => {
    const newGroups = [...stepGroups]
    newGroups[groupIndex] = {
      ...newGroups[groupIndex],
      name: newName.toUpperCase().replace(/\s+/g, '_'),
      display_name: newName,
    }
    setStepGroups(newGroups)
  }

  // Use current scrubber frame as template image for a step
  const useFrameAsTemplateImage = async (groupIndex) => {
    const group = stepGroups[groupIndex]
    const name = group.name.toLowerCase()
    try {
      await extractRecordingFrame(sessionId, selectedFrame, name)
      const newGroups = [...stepGroups]
      newGroups[groupIndex] = {
        ...newGroups[groupIndex],
        template_image: { source: 'extracted', name },
      }
      setStepGroups(newGroups)
    } catch (err) {
      alert(`Failed to extract frame: ${err.response?.data?.detail || err.message}`)
    }
  }

  // Use an auto-captured screenshot as template image
  const useScreenshotAsTemplateImage = (groupIndex, screenshotIndex) => {
    const newGroups = [...stepGroups]
    newGroups[groupIndex] = {
      ...newGroups[groupIndex],
      template_image: { source: 'screenshot', index: screenshotIndex },
    }
    setStepGroups(newGroups)
  }

  // Generate template
  const handleGenerate = async () => {
    if (!templateName.trim()) {
      alert('Please enter a template name')
      return
    }
    if (stepGroups.length === 0) {
      alert('No steps to convert')
      return
    }

    setGenerating(true)
    try {
      const payload = {
        name: templateName,
        description: `Auto-generated from macro recording session`,
        game: templateGame,
        pokemon_name: templatePokemon,
        step_groups: stepGroups,
      }
      const result = await convertRecordingToTemplate(sessionId, payload)
      onTemplateCreated?.(result.template_id)
    } catch (err) {
      alert(`Template generation failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center', padding: '2rem', color: '#888' }}>
          Loading recording session...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center', padding: '2rem', color: '#ff6666' }}>
          {error}
        </div>
        <button onClick={onClose} style={{ ...btnPrimary, margin: '0 auto', display: 'block' }}>
          Close
        </button>
      </div>
    )
  }

  if (!session) return null

  const buttonEvents = session.events.filter((e) => e.event_type === 'button_press')

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1rem',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
        paddingBottom: '0.75rem',
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            📼 Recording Review
          </h2>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
            Duration: {formatDuration(session.duration)} &nbsp;|&nbsp;
            {buttonEvents.length} button presses &nbsp;|&nbsp;
            {stepGroups.length} steps &nbsp;|&nbsp;
            {session.total_frames} video frames
          </div>
        </div>
        <button onClick={onClose} style={closeBtn}>✕</button>
      </div>

      {/* Video scrubber */}
      <div style={{ marginBottom: '1rem' }}>
        <VideoFrameScrubber
          sessionId={sessionId}
          totalFrames={session.total_frames}
          fps={session.fps}
          events={session.events}
          selectedFrame={selectedFrame}
          onFrameSelect={setSelectedFrame}
        />
      </div>

      {/* Step Groups */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.5rem',
        }}>
          <h3 style={{ margin: 0, fontSize: '0.9rem' }}>Step Groups</h3>
          <button
            onClick={() => setStepGroups(autoGroupEvents(session.events))}
            style={btnSmall}
          >
            🔄 Re-group by Pauses
          </button>
        </div>

        {stepGroups.map((group, gi) => (
          <div key={gi} style={stepGroupStyle}>
            {/* Step header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '0.5rem',
            }}>
              <span style={{
                background: 'var(--accent-cyan, #44aaff)',
                color: '#000',
                padding: '0.15rem 0.4rem',
                borderRadius: '3px',
                fontSize: '0.7rem',
                fontWeight: 'bold',
              }}>
                {gi + 1}
              </span>
              <input
                type="text"
                value={group.display_name}
                onChange={(e) => renameGroup(gi, e.target.value)}
                style={{
                  background: 'transparent',
                  border: '1px solid transparent',
                  color: 'var(--text-primary, #e0e0e0)',
                  fontSize: '0.85rem',
                  fontWeight: 'bold',
                  padding: '0.2rem 0.4rem',
                  borderRadius: '3px',
                  flex: 1,
                }}
                onFocus={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.2)'}
                onBlur={(e) => e.target.style.borderColor = 'transparent'}
              />
              <div style={{ display: 'flex', gap: '0.2rem' }}>
                <button onClick={() => insertBoundaryAfter(gi)} style={btnTiny} title="Split step">✂️</button>
                {gi < stepGroups.length - 1 && (
                  <button onClick={() => mergeWithNext(gi)} style={btnTiny} title="Merge with next">🔗</button>
                )}
                <button onClick={() => removeGroup(gi)} style={{ ...btnTiny, color: '#ff4444' }} title="Delete step">🗑️</button>
              </div>
            </div>

            {/* Button press thumbnails */}
            <div style={{
              display: 'flex',
              gap: '0.3rem',
              overflowX: 'auto',
              paddingBottom: '0.3rem',
              marginBottom: '0.5rem',
            }}>
              {group.event_indices.map((eventIdx) => {
                const event = session.events[eventIdx]
                if (!event || event.event_type !== 'button_press') return null
                const isSelected =
                  group.template_image?.source === 'screenshot' &&
                  group.template_image?.index === event.screenshot_index

                return (
                  <div
                    key={eventIdx}
                    onClick={() => useScreenshotAsTemplateImage(gi, event.screenshot_index)}
                    style={{
                      flexShrink: 0,
                      width: '80px',
                      cursor: 'pointer',
                      border: isSelected
                        ? '2px solid var(--accent-green, #00ff88)'
                        : '2px solid transparent',
                      borderRadius: '4px',
                      overflow: 'hidden',
                      background: 'rgba(0,0,0,0.3)',
                    }}
                    title={`${event.button} at ${event.timestamp.toFixed(1)}s — click to use as template image`}
                  >
                    {event.screenshot_index != null && (
                      <img
                        src={getRecordingScreenshotUrl(sessionId, event.screenshot_index)}
                        alt={`${event.button} press`}
                        style={{ width: '100%', height: '60px', objectFit: 'cover' }}
                        loading="lazy"
                      />
                    )}
                    <div style={{
                      padding: '0.15rem',
                      textAlign: 'center',
                      fontSize: '0.6rem',
                      fontFamily: "'Courier New', monospace",
                    }}>
                      <div style={{ fontWeight: 'bold' }}>{event.button}</div>
                      <div style={{ color: '#888' }}>{event.timestamp.toFixed(1)}s</div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Template image selection */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.75rem',
            }}>
              <span style={{ color: 'var(--text-secondary)' }}>
                Template image:
              </span>
              {group.template_image ? (
                <span style={{ color: 'var(--accent-green, #00ff88)' }}>
                  ✅ {group.template_image.source === 'screenshot'
                    ? `Screenshot #${group.template_image.index}`
                    : `Extracted: ${group.template_image.name}`
                  }
                </span>
              ) : (
                <span style={{ color: '#ffaa00' }}>⚠️ None selected</span>
              )}
              <button
                onClick={() => useFrameAsTemplateImage(gi)}
                style={btnSmall}
                title="Use the current video scrubber frame as this step's template image"
              >
                📸 Use Current Frame
              </button>
            </div>
          </div>
        ))}

        {stepGroups.length === 0 && (
          <div style={{ textAlign: 'center', padding: '1rem', color: '#888', fontSize: '0.8rem' }}>
            No steps — try recording with some button presses first.
          </div>
        )}
      </div>

      {/* Template metadata + generate */}
      <div style={{
        borderTop: '1px solid rgba(255,255,255,0.1)',
        paddingTop: '1rem',
      }}>
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem' }}>Generate Template</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={labelStyle}>Template Name</label>
            <input
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              style={inputStyle}
              placeholder="My Template"
            />
          </div>
          <div>
            <label style={labelStyle}>Game</label>
            <input
              type="text"
              value={templateGame}
              onChange={(e) => setTemplateGame(e.target.value)}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Pokemon</label>
            <input
              type="text"
              value={templatePokemon}
              onChange={(e) => setTemplatePokemon(e.target.value)}
              style={inputStyle}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={handleGenerate}
            disabled={generating || stepGroups.length === 0}
            style={{
              ...btnPrimary,
              flex: 1,
              opacity: generating || stepGroups.length === 0 ? 0.5 : 1,
            }}
          >
            {generating ? '⏳ Generating...' : '✨ Generate Template'}
          </button>
          <button onClick={onClose} style={btnSecondary}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function formatDuration(seconds) {
  if (!seconds) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── Styles ──────────────────────────────────────────────────────

const containerStyle = {
  background: 'var(--bg-secondary, #1a1a2e)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px',
  padding: '1rem',
}

const stepGroupStyle = {
  background: 'rgba(0,0,0,0.2)',
  borderRadius: '6px',
  padding: '0.75rem',
  marginBottom: '0.5rem',
  border: '1px solid rgba(255,255,255,0.05)',
}

const closeBtn = {
  background: 'none',
  border: 'none',
  color: 'var(--text-secondary)',
  cursor: 'pointer',
  fontSize: '1.2rem',
  padding: '0.3rem',
}

const btnPrimary = {
  padding: '0.6rem 1.2rem',
  background: 'linear-gradient(135deg, #44cc88, #22aa66)',
  border: 'none',
  borderRadius: '6px',
  color: '#fff',
  fontWeight: 'bold',
  cursor: 'pointer',
  fontSize: '0.9rem',
}

const btnSecondary = {
  padding: '0.6rem 1.2rem',
  background: 'var(--bg-tertiary, #252540)',
  border: '1px solid rgba(255,255,255,0.15)',
  borderRadius: '6px',
  color: 'var(--text-primary, #e0e0e0)',
  cursor: 'pointer',
  fontSize: '0.9rem',
}

const btnSmall = {
  padding: '0.25rem 0.5rem',
  background: 'var(--bg-tertiary, #252540)',
  border: '1px solid rgba(255,255,255,0.1)',
  color: 'var(--text-primary, #e0e0e0)',
  borderRadius: '3px',
  cursor: 'pointer',
  fontSize: '0.7rem',
}

const btnTiny = {
  padding: '0.15rem 0.3rem',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: '0.75rem',
}

const labelStyle = {
  display: 'block',
  fontSize: '0.7rem',
  color: 'var(--text-secondary, #888)',
  marginBottom: '0.2rem',
}

const inputStyle = {
  width: '100%',
  padding: '0.4rem 0.6rem',
  background: 'var(--bg-tertiary, #252540)',
  border: '1px solid rgba(255,255,255,0.1)',
  color: 'var(--text-primary, #e0e0e0)',
  borderRadius: '4px',
  fontSize: '0.8rem',
  boxSizing: 'border-box',
}

export default RecordingReviewTimeline
