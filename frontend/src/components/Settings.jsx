import { useState, useEffect } from 'react'
import { getSettings, updateSettings } from '../api.js'

const PROVIDERS = ['openai', 'anthropic', 'ollama', 'azure']
const NAV_SECTIONS = ['LLM', 'Gap Analysis']

export default function Settings() {
  const [section, setSection] = useState('LLM')
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null)

  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [temperature, setTemperature] = useState(0.3)

  useEffect(() => {
    getSettings()
      .then(data => {
        setSettings(data)
        setProvider(data.llm.provider)
        setModel(data.llm.model)
        setTemperature(data.llm.temperature)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleSave() {
    setSaving(true)
    setSaveStatus(null)
    try {
      await updateSettings({ llm_provider: provider, llm_model: model, temperature })
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="content" data-testid="settings-view"><p style={{ color: 'var(--text-mut)' }}>Loading…</p></div>
  }
  if (error) {
    return <div className="content" data-testid="settings-view"><p style={{ color: 'var(--fail)' }}>Error: {error}</p></div>
  }

  return (
    <div className="content" data-testid="settings-view">
      <div className="settings-layout">
        <div className="settings-nav">
          {NAV_SECTIONS.map(s => (
            <div
              key={s}
              className={`settings-nav-item${section === s ? ' active' : ''}`}
              onClick={() => setSection(s)}
            >
              {s}
            </div>
          ))}
        </div>

        <div className="settings-form">
          {section === 'LLM' && (
            <>
              <div className="section-title">LLM Configuration</div>
              <div className="section-sub">Configure which AI provider powers test generation.</div>

              <div className="form-row">
                <label className="form-label">Provider</label>
                <select
                  className="form-select"
                  value={provider}
                  onChange={e => setProvider(e.target.value)}
                >
                  {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div className="form-row">
                <label className="form-label">Model</label>
                <input
                  className="form-input"
                  type="text"
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  placeholder="e.g. claude-sonnet-4-6"
                />
              </div>

              <div className="form-row">
                <label className="form-label">Temperature</label>
                <div className="slider-row">
                  <input
                    className="slider"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={temperature}
                    onChange={e => setTemperature(parseFloat(e.target.value))}
                    aria-label="Temperature"
                  />
                  <span className="slider-val">{temperature.toFixed(2)}</span>
                </div>
                <div className="form-help">Lower values produce more deterministic output.</div>
              </div>

              <hr className="divider" />

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button
                  className="btn btn-primary"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? 'Saving…' : 'Save Changes'}
                </button>
                {saveStatus === 'saved' && (
                  <span style={{ color: 'var(--pass)', fontSize: '13px', fontWeight: 600 }}>Saved!</span>
                )}
                {saveStatus === 'error' && (
                  <span style={{ color: 'var(--fail)', fontSize: '13px' }}>Save failed.</span>
                )}
              </div>
            </>
          )}

          {section === 'Gap Analysis' && settings && (
            <>
              <div className="section-title">Gap Analysis</div>
              <div className="section-sub">Scoring and detection settings (edit in testweavex.config.yaml to change).</div>

              <div className="form-row">
                <label className="form-label">Top Gaps Default</label>
                <input
                  className="form-input"
                  type="number"
                  readOnly
                  value={settings.gap_analysis.top_gaps_default}
                  onChange={() => {}}
                />
                <div className="form-help">Number of gaps returned by default.</div>
              </div>

              <div className="form-row">
                <label className="form-label">Match Threshold</label>
                <div className="slider-row">
                  <input
                    className="slider"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    readOnly
                    value={settings.gap_analysis.match_threshold}
                    onChange={() => {}}
                    aria-label="Match Threshold"
                  />
                  <span className="slider-val">{settings.gap_analysis.match_threshold.toFixed(2)}</span>
                </div>
                <div className="form-help">Minimum similarity score to consider a test case as covering a gap.</div>
              </div>

              <div className="form-row">
                <label className="form-label">TCM Provider</label>
                <div>
                  {settings.tcm.provider === 'none'
                    ? <span className="badge badge-brand">none (built-in)</span>
                    : <span className="connected-badge">&#x2713; {settings.tcm.provider}</span>
                  }
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
