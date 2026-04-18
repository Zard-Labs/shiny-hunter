import { useState, useEffect, useCallback } from 'react'
import {
  getNotificationSettings,
  saveNotificationSettings,
  sendTestNotification,
} from '../services/api'

// Pushover sound options
const PUSHOVER_SOUNDS = [
  { value: 'pushover', label: 'Pushover (default)' },
  { value: 'bike', label: 'Bike' },
  { value: 'bugle', label: 'Bugle' },
  { value: 'cashregister', label: 'Cash Register' },
  { value: 'classical', label: 'Classical' },
  { value: 'cosmic', label: 'Cosmic' },
  { value: 'falling', label: 'Falling' },
  { value: 'gamelan', label: 'Gamelan' },
  { value: 'incoming', label: 'Incoming' },
  { value: 'intermission', label: 'Intermission' },
  { value: 'magic', label: 'Magic' },
  { value: 'mechanical', label: 'Mechanical' },
  { value: 'pianobar', label: 'Piano Bar' },
  { value: 'siren', label: 'Siren' },
  { value: 'spacealarm', label: 'Space Alarm' },
  { value: 'tugboat', label: 'Tugboat' },
  { value: 'alien', label: 'Alien Alarm (long)' },
  { value: 'climb', label: 'Climb (long)' },
  { value: 'persistent', label: 'Persistent (long)' },
  { value: 'echo', label: 'Echo (long)' },
  { value: 'updown', label: 'Up Down (long)' },
  { value: 'vibrate', label: 'Vibrate Only' },
  { value: 'none', label: 'None (silent)' },
]

const PRIORITY_OPTIONS = [
  { value: -2, label: 'Lowest' },
  { value: -1, label: 'Low' },
  { value: 0, label: 'Normal' },
  { value: 1, label: 'High' },
  { value: 2, label: 'Emergency' },
]

// Settings tabs
const TABS = [
  { id: 'notifications', label: '🔔 Notifications' },
]

function SettingsModal({ onClose }) {
  const [activeTab, setActiveTab] = useState('notifications')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState(null) // { type: 'success'|'error', text: '...' }

  // Pushover form state
  const [pushoverEnabled, setPushoverEnabled] = useState(false)
  const [pushoverAppToken, setPushoverAppToken] = useState('')
  const [pushoverUserKey, setPushoverUserKey] = useState('')
  const [pushoverPriority, setPushoverPriority] = useState(1)
  const [pushoverSound, setPushoverSound] = useState('persistent')

  // Track whether the user has modified token fields (to avoid sending masked values)
  const [tokenDirty, setTokenDirty] = useState(false)
  const [userKeyDirty, setUserKeyDirty] = useState(false)

  // ── Load settings on mount ──────────────────────────────────────

  const loadSettings = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getNotificationSettings()
      setPushoverEnabled(data.pushover_enabled || false)
      setPushoverAppToken(data.pushover_app_token || '')
      setPushoverUserKey(data.pushover_user_key || '')
      setPushoverPriority(data.pushover_priority ?? 1)
      setPushoverSound(data.pushover_sound || 'persistent')
      setTokenDirty(false)
      setUserKeyDirty(false)
    } catch (err) {
      console.error('Failed to load notification settings:', err)
      setMessage({ type: 'error', text: 'Failed to load settings.' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  // ── Save ────────────────────────────────────────────────────────

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const payload = {
        pushover_enabled: pushoverEnabled,
        pushover_priority: pushoverPriority,
        pushover_sound: pushoverSound,
      }
      // Only send token/key if the user actually modified them
      if (tokenDirty) payload.pushover_app_token = pushoverAppToken
      if (userKeyDirty) payload.pushover_user_key = pushoverUserKey

      const updated = await saveNotificationSettings(payload)
      setPushoverAppToken(updated.pushover_app_token || '')
      setPushoverUserKey(updated.pushover_user_key || '')
      setTokenDirty(false)
      setUserKeyDirty(false)
      setMessage({ type: 'success', text: '✓ Settings saved successfully.' })
    } catch (err) {
      console.error('Failed to save settings:', err)
      setMessage({ type: 'error', text: 'Failed to save settings.' })
    } finally {
      setSaving(false)
    }
  }

  // ── Test notification ───────────────────────────────────────────

  const handleTest = async () => {
    setTesting(true)
    setMessage(null)
    try {
      // Build override settings with the current form values
      const overrides = {
        pushover_enabled: true, // force enabled for test
        pushover_priority: pushoverPriority,
        pushover_sound: pushoverSound,
      }
      if (tokenDirty) overrides.pushover_app_token = pushoverAppToken
      if (userKeyDirty) overrides.pushover_user_key = pushoverUserKey

      const result = await sendTestNotification(overrides)
      if (result.success) {
        setMessage({ type: 'success', text: '✓ Test notification sent! Check your device.' })
      } else {
        setMessage({ type: 'error', text: `✗ Test failed: ${result.detail}` })
      }
    } catch (err) {
      console.error('Test notification failed:', err)
      const detail = err?.response?.data?.detail || err.message || 'Unknown error'
      setMessage({ type: 'error', text: `✗ Test failed: ${detail}` })
    } finally {
      setTesting(false)
    }
  }

  // ── Close on backdrop click ─────────────────────────────────────

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  // ── Close on Escape key ─────────────────────────────────────────

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  // ── Render helpers ──────────────────────────────────────────────

  const renderNotificationsTab = () => (
    <div className="settings-section">
      <h3 className="settings-section-title">Pushover Notifications</h3>
      <p className="settings-section-desc">
        Get push notifications on your phone when a shiny is found.
        Create a free account at{' '}
        <a href="https://pushover.net" target="_blank" rel="noopener noreferrer">
          pushover.net
        </a>{' '}
        and create an application to get your API token.
      </p>

      {/* Enable toggle */}
      <div className="settings-form-group">
        <label className="settings-label">Enable Pushover</label>
        <label className="toggle-switch">
          <input
            type="checkbox"
            checked={pushoverEnabled}
            onChange={(e) => setPushoverEnabled(e.target.checked)}
          />
          <span className="toggle-slider"></span>
        </label>
      </div>

      {/* App Token */}
      <div className="settings-form-group">
        <label className="settings-label">Application Token</label>
        <input
          type="text"
          className="settings-input"
          placeholder="azGDORePK8gMaC0QOYAMyEEuzJnyUi"
          value={pushoverAppToken}
          onChange={(e) => {
            setPushoverAppToken(e.target.value)
            setTokenDirty(true)
          }}
          disabled={!pushoverEnabled}
        />
        <span className="settings-hint">
          From your Pushover application page
        </span>
      </div>

      {/* User Key */}
      <div className="settings-form-group">
        <label className="settings-label">User Key</label>
        <input
          type="text"
          className="settings-input"
          placeholder="uQiRzpo4DXghDmr9QzzfQu27cmVRsG"
          value={pushoverUserKey}
          onChange={(e) => {
            setPushoverUserKey(e.target.value)
            setUserKeyDirty(true)
          }}
          disabled={!pushoverEnabled}
        />
        <span className="settings-hint">
          From your Pushover dashboard
        </span>
      </div>

      {/* Priority */}
      <div className="settings-form-group">
        <label className="settings-label">Priority</label>
        <select
          className="settings-input"
          value={pushoverPriority}
          onChange={(e) => setPushoverPriority(Number(e.target.value))}
          disabled={!pushoverEnabled}
        >
          {PRIORITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Sound */}
      <div className="settings-form-group">
        <label className="settings-label">Sound</label>
        <select
          className="settings-input"
          value={pushoverSound}
          onChange={(e) => setPushoverSound(e.target.value)}
          disabled={!pushoverEnabled}
        >
          {PUSHOVER_SOUNDS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Actions */}
      <div className="settings-actions">
        <button
          className="settings-btn-test"
          onClick={handleTest}
          disabled={testing || !pushoverAppToken || !pushoverUserKey}
        >
          {testing ? '⏳ Sending...' : '🔔 Send Test'}
        </button>
        <button
          className="settings-btn-save"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? '⏳ Saving...' : '💾 Save'}
        </button>
      </div>

      {/* Status message */}
      {message && (
        <div className={`settings-message settings-message-${message.type}`}>
          {message.text}
        </div>
      )}
    </div>
  )

  // ── Main render ─────────────────────────────────────────────────

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content settings-modal">
        {/* Header */}
        <div className="settings-header">
          <h2 className="settings-title">⚙ Settings</h2>
          <button className="settings-close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="settings-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="settings-body">
          {loading ? (
            <div className="settings-loading">Loading settings...</div>
          ) : (
            <>
              {activeTab === 'notifications' && renderNotificationsTab()}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default SettingsModal
