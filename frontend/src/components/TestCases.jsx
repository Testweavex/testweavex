import { useState, useEffect, useCallback } from 'react'
import {
  getTestCases, getTestCase,
  createTestCase, updateTestCase, deleteTestCase,
  executeTestCase,
} from '../api.js'

const TEST_TYPES = [
  'smoke', 'e2e', 'integration', 'sanity',
  'happy_path', 'data_driven', 'edge_cases', 'accessibility',
  'system', 'cross_browser',
]

const TYPE_BADGE = {
  smoke: 'badge-smoke',
  e2e: 'badge-e2e',
  integration: 'badge-integration',
  sanity: 'badge-sanity',
}

const STATUS_BADGE = {
  passed: 'badge-pass',
  failed: 'badge-fail',
  skipped: 'badge-skip',
  flaky: 'badge-flaky',
  pending: 'badge-brand',
}

function typeBadge(t) { return TYPE_BADGE[t] || 'badge-brand' }
function statusBadge(s) { return STATUS_BADGE[s] || 'badge-brand' }

function emptyForm() {
  return { title: '', test_type: 'smoke', priority: 2, is_automated: false, tags: '', gherkin: '' }
}

function tcToForm(tc) {
  return {
    title: tc.title,
    test_type: tc.test_type,
    priority: tc.priority,
    is_automated: tc.is_automated,
    tags: (tc.tags || []).join(', '),
    gherkin: tc.gherkin || '',
  }
}

function formatDuration(ms) {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

function parseSteps(gherkin) {
  if (!gherkin) return []
  const steps = []
  for (const rawLine of gherkin.split('\n')) {
    const line = rawLine.trim()
    const m = line.match(/^(Given|When|Then|And|But)\s+(.+)/)
    if (m) steps.push({ keyword: m[1], text: m[2] })
  }
  return steps
}

function parseScenarioTitle(gherkin) {
  if (!gherkin) return null
  for (const rawLine of gherkin.split('\n')) {
    const m = rawLine.trim().match(/^Scenario(?:\s+Outline)?:\s*(.+)/)
    if (m) return m[1]
  }
  return null
}

export default function TestCases() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [automatedFilter, setAutomatedFilter] = useState('all')

  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState({ loading: false, data: null, error: null })

  // mode: 'view' | 'edit' | 'create' | 'execute'
  const [mode, setMode] = useState('view')
  const [form, setForm] = useState(emptyForm())
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [executing, setExecuting] = useState(false)
  const [executeError, setExecuteError] = useState(null)

  useEffect(() => {
    getTestCases()
      .then(setCases)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const loadDetail = useCallback(async (id) => {
    setDetail({ loading: true, data: null, error: null })
    try {
      const data = await getTestCase(id)
      setDetail({ loading: false, data, error: null })
    } catch (e) {
      setDetail({ loading: false, data: null, error: e.message })
    }
  }, [])

  function handleRowClick(tc) {
    if (selectedId === tc.id && mode === 'view') { closePanel(); return }
    setSelectedId(tc.id)
    setMode('view')
    setDeleteConfirm(false)
    setSaveError(null)
    setExecuteError(null)
    loadDetail(tc.id)
  }

  function closePanel() {
    setSelectedId(null)
    setMode('view')
    setDeleteConfirm(false)
    setSaveError(null)
    setExecuteError(null)
  }

  function startEdit() {
    if (!detail.data) return
    setForm(tcToForm(detail.data))
    setSaveError(null)
    setMode('edit')
  }

  function startCreate() {
    setSelectedId(null)
    setForm(emptyForm())
    setSaveError(null)
    setDeleteConfirm(false)
    setMode('create')
  }

  function startExecute() {
    setExecuteError(null)
    setMode('execute')
  }

  async function handleSave() {
    setSaving(true)
    setSaveError(null)
    const payload = {
      title: form.title,
      test_type: form.test_type,
      priority: Number(form.priority),
      is_automated: form.is_automated,
      tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      gherkin: form.gherkin,
    }
    try {
      if (mode === 'create') {
        const created = await createTestCase(payload)
        setCases(prev => [created, ...prev])
        setSelectedId(created.id)
        setDetail({ loading: false, data: created, error: null })
        setMode('view')
      } else {
        const updated = await updateTestCase(selectedId, payload)
        setCases(prev => prev.map(tc => tc.id === selectedId ? updated : tc))
        setDetail({ loading: false, data: updated, error: null })
        setMode('view')
      }
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) { setDeleteConfirm(true); return }
    setDeleting(true)
    try {
      await deleteTestCase(selectedId)
      setCases(prev => prev.filter(tc => tc.id !== selectedId))
      closePanel()
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  async function handleExecuteComplete({ steps, notes, duration_ms }) {
    setExecuting(true)
    setExecuteError(null)
    try {
      const res = await executeTestCase(selectedId, { steps, notes, duration_ms })
      setCases(prev => prev.map(tc =>
        tc.id === selectedId ? { ...tc, status: res.test_case.status } : tc
      ))
      await loadDetail(selectedId)
      setMode('view')
    } catch (e) {
      setExecuteError(e.message)
    } finally {
      setExecuting(false)
    }
  }

  if (loading) return <div className="content" data-testid="test-cases-view"><p style={{ color: 'var(--text-mut)' }}>Loading…</p></div>
  if (error) return <div className="content" data-testid="test-cases-view"><p style={{ color: 'var(--fail)' }}>Error: {error}</p></div>

  const filtered = cases.filter(tc => {
    if (typeFilter !== 'all' && tc.test_type !== typeFilter) return false
    if (automatedFilter === 'automated' && !tc.is_automated) return false
    if (automatedFilter === 'manual' && tc.is_automated) return false
    if (search) {
      const q = search.toLowerCase()
      if (!tc.title.toLowerCase().includes(q) && !(tc.tags || []).some(t => t.toLowerCase().includes(q))) return false
    }
    return true
  })

  const panelOpen = selectedId !== null || mode === 'create'

  const panelTitle =
    mode === 'create' ? 'New Test Case' :
    mode === 'edit' ? 'Edit Test Case' :
    mode === 'execute' ? `Execute: ${detail.data?.title || '…'}` :
    (detail.data?.title || '…')

  return (
    <div
      className="content"
      data-testid="test-cases-view"
      style={{ padding: 0, display: 'flex', overflow: 'hidden' }}
    >
      {/* ── Table pane ── */}
      <div style={{ flex: 1, overflow: 'auto', padding: '24px', minWidth: 0 }}>
        <div className="table-wrap">
          <div className="filter-bar">
            <input
              className="search-input"
              type="text"
              placeholder="Search title or tag…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              aria-label="Search test cases"
            />
            <select
              className="search-input"
              style={{ flex: '0 0 auto', width: '150px' }}
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
            >
              <option value="all">All Types</option>
              {TEST_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <select
              className="search-input"
              style={{ flex: '0 0 auto', width: '140px' }}
              value={automatedFilter}
              onChange={e => setAutomatedFilter(e.target.value)}
            >
              <option value="all">All</option>
              <option value="automated">Automated</option>
              <option value="manual">Manual</option>
            </select>
            <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-mut)', whiteSpace: 'nowrap' }}>
              {filtered.length} case{filtered.length !== 1 ? 's' : ''}
            </span>
            <button className="btn btn-primary btn-sm" onClick={startCreate}>+ New</button>
          </div>

          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Auto</th>
                <th>Pri</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(tc => (
                <tr
                  key={tc.id}
                  onClick={() => handleRowClick(tc)}
                  className={selectedId === tc.id ? 'selected' : ''}
                >
                  <td>{tc.title}</td>
                  <td><span className={`badge ${typeBadge(tc.test_type)}`}>{tc.test_type}</span></td>
                  <td>
                    <span className={`badge ${tc.is_automated ? 'badge-pass' : 'badge-manual'}`}>
                      {tc.is_automated ? 'yes' : 'no'}
                    </span>
                  </td>
                  <td>{tc.priority ?? '—'}</td>
                  <td><span className={`badge ${statusBadge(tc.status)}`}>{tc.status}</span></td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-mut)', padding: '32px' }}>
                    No test cases match filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Detail / Edit / Create / Execute panel ── */}
      {panelOpen && (
        <div className="detail-panel" data-testid="detail-panel">
          <div className="panel-header">
            <span className="panel-title">{panelTitle}</span>
            <button className="panel-close" onClick={closePanel} aria-label="Close panel">×</button>
          </div>

          <div className="panel-body">
            {(mode === 'edit' || mode === 'create') ? (
              <EditForm
                form={form}
                setForm={setForm}
                onSave={handleSave}
                onCancel={() => mode === 'create' ? closePanel() : setMode('view')}
                saving={saving}
                saveError={saveError}
              />
            ) : mode === 'execute' ? (
              detail.data ? (
                <ExecuteView
                  tc={detail.data}
                  onComplete={handleExecuteComplete}
                  onCancel={() => setMode('view')}
                  executing={executing}
                  executeError={executeError}
                />
              ) : null
            ) : detail.loading ? (
              <p style={{ color: 'var(--text-mut)' }}>Loading…</p>
            ) : detail.error ? (
              <p style={{ color: 'var(--fail)' }}>Error: {detail.error}</p>
            ) : detail.data ? (
              <DetailView
                tc={detail.data}
                onEdit={startEdit}
                onExecute={startExecute}
                onDelete={handleDelete}
                deleteConfirm={deleteConfirm}
                deleting={deleting}
                saveError={saveError}
              />
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Structured step display ────────────────────────────────────────────────

function StepsDisplay({ gherkin }) {
  const title = parseScenarioTitle(gherkin)
  const steps = parseSteps(gherkin)

  if (!gherkin) return null

  if (!steps.length && !title) {
    return <pre className="gherkin" style={{ color: '#CDD6F4' }}>{gherkin}</pre>
  }

  return (
    <div className="steps-list">
      {title && <div className="step-scenario-title">Scenario: {title}</div>}
      {steps.map((s, i) => (
        <div key={i} className="step-item">
          <span className="step-keyword">{s.keyword}</span>
          <span className="step-text">{s.text}</span>
        </div>
      ))}
    </div>
  )
}

// ── Execute view ───────────────────────────────────────────────────────────

function ExecuteView({ tc, onComplete, onCancel, executing, executeError }) {
  const steps = parseSteps(tc.gherkin)
  const [stepResults, setStepResults] = useState(() => steps.map(() => 'passed'))
  const [directResult, setDirectResult] = useState('passed')
  const [notes, setNotes] = useState('')
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  function setStep(i, status) {
    setStepResults(prev => prev.map((s, idx) => idx === i ? status : s))
  }

  const hasSteps = steps.length > 0

  const overallStatus = hasSteps
    ? (stepResults.some(s => s === 'failed') ? 'failed'
       : stepResults.every(s => s === 'skipped') ? 'skipped'
       : 'passed')
    : directResult

  const mins = Math.floor(elapsed / 60).toString().padStart(2, '0')
  const secs = (elapsed % 60).toString().padStart(2, '0')

  function handleComplete() {
    const payload = hasSteps
      ? { steps: steps.map((s, i) => ({ ...s, status: stepResults[i] })), notes, duration_ms: elapsed * 1000 }
      : { steps: [{ keyword: 'Manual', text: tc.title, status: directResult }], notes, duration_ms: elapsed * 1000 }
    onComplete(payload)
  }

  return (
    <>
      <div className="execute-header">
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-sec)' }}>Manual Execution</span>
        <span className="execute-timer" data-testid="execute-timer">{mins}:{secs}</span>
      </div>

      {hasSteps ? (
        steps.map((step, i) => (
          <div key={i} className={`execute-step step-${stepResults[i]}`} data-testid={`execute-step-${i}`}>
            <div className="execute-step-line">
              <span className="execute-step-kw">{step.keyword}</span>
              <span className="execute-step-text">{step.text}</span>
            </div>
            <div className="execute-step-btns">
              {[['passed', '✓ Pass', 'active-pass'], ['failed', '✗ Fail', 'active-fail'], ['skipped', '− Skip', 'active-skip']].map(
                ([status, label, cls]) => (
                  <button
                    key={status}
                    className={`step-btn${stepResults[i] === status ? ` ${cls}` : ''}`}
                    onClick={() => setStep(i, status)}
                  >
                    {label}
                  </button>
                )
              )}
            </div>
          </div>
        ))
      ) : (
        <div style={{ marginBottom: '16px' }}>
          <p style={{ color: 'var(--text-sec)', fontSize: '13px', marginBottom: '12px' }}>
            No Gherkin steps found. Record overall result:
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            {[['passed', '✓ Pass', 'active-pass'], ['failed', '✗ Fail', 'active-fail'], ['skipped', '− Skip', 'active-skip']].map(
              ([status, label, cls]) => (
                <button
                  key={status}
                  className={`step-btn${directResult === status ? ` ${cls}` : ''}`}
                  onClick={() => setDirectResult(status)}
                >
                  {label}
                </button>
              )
            )}
          </div>
        </div>
      )}

      <div className="form-row" style={{ marginTop: '16px' }}>
        <label className="form-label">Notes / Observations</label>
        <textarea
          className="form-input"
          rows={3}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Failure details, environment notes, reproduction steps…"
          style={{ resize: 'vertical', fontSize: '12px' }}
          aria-label="Execution notes"
        />
      </div>

      <div className={`execute-overall status-${overallStatus}`}>
        <span style={{ color: 'var(--text-sec)' }}>Overall result:</span>
        <span className={`badge badge-${overallStatus === 'passed' ? 'pass' : overallStatus === 'failed' ? 'fail' : 'skip'}`}>
          {overallStatus}
        </span>
      </div>

      {executeError && (
        <p style={{ color: 'var(--fail)', fontSize: '12px', marginBottom: '12px' }}>{executeError}</p>
      )}

      <div style={{ display: 'flex', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border)' }}>
        <button
          className="btn btn-primary btn-sm"
          onClick={handleComplete}
          disabled={executing}
          data-testid="complete-execution-btn"
        >
          {executing ? 'Saving…' : 'Complete Execution'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={executing}>
          Cancel
        </button>
      </div>
    </>
  )
}

// ── Edit / Create form ─────────────────────────────────────────────────────

function EditForm({ form, setForm, onSave, onCancel, saving, saveError }) {
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  return (
    <>
      <div className="form-row">
        <label className="form-label">Title *</label>
        <input
          className="form-input"
          type="text"
          value={form.title}
          onChange={e => set('title', e.target.value)}
          placeholder="Scenario title"
          aria-label="Title"
        />
      </div>
      <div className="form-row">
        <label className="form-label">Type</label>
        <select className="form-select" value={form.test_type} onChange={e => set('test_type', e.target.value)}>
          {TEST_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div className="form-row">
        <label className="form-label">Priority</label>
        <select className="form-select" value={form.priority} onChange={e => set('priority', Number(e.target.value))}>
          <option value={1}>1 — High</option>
          <option value={2}>2 — Medium</option>
          <option value={3}>3 — Low</option>
        </select>
      </div>
      <div className="form-row" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <input
          type="checkbox"
          id="is_automated"
          checked={form.is_automated}
          onChange={e => set('is_automated', e.target.checked)}
        />
        <label htmlFor="is_automated" className="form-label" style={{ margin: 0 }}>Automated</label>
      </div>
      <div className="form-row">
        <label className="form-label">Tags</label>
        <input
          className="form-input"
          type="text"
          value={form.tags}
          onChange={e => set('tags', e.target.value)}
          placeholder="smoke, login, regression"
          aria-label="Tags"
        />
        <div className="form-help">Comma-separated</div>
      </div>
      <div className="form-row">
        <label className="form-label">Gherkin</label>
        <textarea
          className="form-input"
          rows={8}
          value={form.gherkin}
          onChange={e => set('gherkin', e.target.value)}
          placeholder={'Scenario: …\n  Given …\n  When …\n  Then …'}
          aria-label="Gherkin"
          style={{ fontFamily: 'monospace', fontSize: '12px', resize: 'vertical' }}
        />
      </div>
      {saveError && <p style={{ color: 'var(--fail)', fontSize: '12px', marginBottom: '12px' }}>{saveError}</p>}
      <div style={{ display: 'flex', gap: '8px' }}>
        <button className="btn btn-primary btn-sm" onClick={onSave} disabled={saving || !form.title.trim()}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={saving}>Cancel</button>
      </div>
    </>
  )
}

// ── Detail view ────────────────────────────────────────────────────────────

function DetailView({ tc, onEdit, onExecute, onDelete, deleteConfirm, deleting, saveError }) {
  return (
    <>
      <div className="panel-section">
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
          <span className={`badge ${typeBadge(tc.test_type)}`}>{tc.test_type}</span>
          <span className={`badge ${tc.is_automated ? 'badge-pass' : 'badge-manual'}`}>
            {tc.is_automated ? 'automated' : 'manual'}
          </span>
          <span className="badge badge-brand">P{tc.priority}</span>
          <span className={`badge ${statusBadge(tc.status)}`}>{tc.status}</span>
        </div>
        {tc.tags && tc.tags.length > 0 && (
          <div style={{ marginBottom: '12px' }}>
            {tc.tags.map(tag => <span key={tag} className="tag">{tag}</span>)}
          </div>
        )}
      </div>

      {tc.gherkin && (
        <div className="panel-section">
          <div className="panel-label">Steps</div>
          <StepsDisplay gherkin={tc.gherkin} />
        </div>
      )}

      {tc.recent_results && tc.recent_results.length > 0 && (
        <div className="panel-section">
          <div className="panel-label">Recent Results</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--text-mut)', fontWeight: 600, fontSize: '10px', textTransform: 'uppercase' }}>Status</th>
                <th style={{ textAlign: 'right', padding: '4px 8px', color: 'var(--text-mut)', fontWeight: 600, fontSize: '10px', textTransform: 'uppercase' }}>Duration</th>
              </tr>
            </thead>
            <tbody>
              {tc.recent_results.map(r => (
                <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '6px 8px' }}>
                    <span className={`badge ${statusBadge(r.status)}`}>{r.status}</span>
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--text-sec)' }}>
                    {formatDuration(r.duration_ms)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel-section" style={{ marginTop: '8px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text-mut)', marginBottom: '4px', fontFamily: 'monospace' }}>
          ID: {tc.id.slice(0, 16)}…
        </div>
        {tc.source_file && (
          <div style={{ fontSize: '10px', color: 'var(--text-mut)', marginBottom: '12px' }}>
            {tc.source_file}
          </div>
        )}
      </div>

      {saveError && <p style={{ color: 'var(--fail)', fontSize: '12px', marginBottom: '12px' }}>{saveError}</p>}

      <div style={{ display: 'flex', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
        <button className="btn btn-green btn-sm" onClick={onExecute} data-testid="run-manually-btn">
          ▶ Run Manually
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onEdit}>Edit</button>
        <button
          className={`btn btn-sm ${deleteConfirm ? 'btn-red' : 'btn-ghost'}`}
          onClick={onDelete}
          disabled={deleting}
          style={deleteConfirm ? { borderColor: 'var(--fail)', color: 'var(--fail)' } : {}}
        >
          {deleting ? 'Deleting…' : deleteConfirm ? 'Confirm delete' : 'Delete'}
        </button>
      </div>
    </>
  )
}
