import React, { useState, useEffect } from 'react'
import { getRuns, getRun } from '../api.js'

const RESULT_BADGE = {
  passed: 'badge-pass',
  failed: 'badge-fail',
  skipped: 'badge-skip',
  flaky: 'badge-flaky',
  pending: 'badge-brand',
}

function resultBadge(status) {
  return RESULT_BADGE[status] || 'badge-brand'
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

function formatDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function RunDetail({ state }) {
  if (!state || state.loading) {
    return <p style={{ padding: '16px', color: 'var(--text-mut)' }}>Loading…</p>
  }
  if (state.error) {
    return <p style={{ padding: '16px', color: 'var(--fail)' }}>Error: {state.error}</p>
  }
  const { data } = state
  if (!data.results || data.results.length === 0) {
    return <p style={{ padding: '16px', color: 'var(--text-mut)' }}>No results for this run.</p>
  }

  const passed = data.results.filter(r => r.status === 'passed').length
  const failed = data.results.filter(r => r.status === 'failed').length
  const skipped = data.results.filter(r => r.status === 'skipped').length

  return (
    <div style={{ padding: '16px' }}>
      <div className="run-meta" style={{ marginBottom: '12px' }}>
        <div className="run-meta-item">
          <span className="run-meta-label">Passed</span>
          <span className="run-meta-value" style={{ color: 'var(--pass)' }}>{passed}</span>
        </div>
        <div className="run-meta-item">
          <span className="run-meta-label">Failed</span>
          <span className="run-meta-value" style={{ color: 'var(--fail)' }}>{failed}</span>
        </div>
        <div className="run-meta-item">
          <span className="run-meta-label">Skipped</span>
          <span className="run-meta-value" style={{ color: 'var(--skip)' }}>{skipped}</span>
        </div>
        {data.browser && (
          <div className="run-meta-item">
            <span className="run-meta-label">Browser</span>
            <span className="run-meta-value">{data.browser}</span>
          </div>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Test Case ID</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {data.results.map(r => (
            <tr key={r.id}>
              <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{r.test_case_id.slice(0, 16)}…</td>
              <td><span className={`badge ${resultBadge(r.status)}`}>{r.status}</span></td>
              <td>{formatDuration(r.duration_ms)}</td>
              <td style={{ color: 'var(--fail)', fontSize: '12px' }}>{r.error_message || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function TestRuns() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [detail, setDetail] = useState({})

  useEffect(() => {
    getRuns(50)
      .then(setRuns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleToggle(runId) {
    if (expanded === runId) {
      setExpanded(null)
      return
    }
    setExpanded(runId)
    if (detail[runId]) return
    setDetail(d => ({ ...d, [runId]: { loading: true, data: null, error: null } }))
    try {
      const data = await getRun(runId)
      setDetail(d => ({ ...d, [runId]: { loading: false, data, error: null } }))
    } catch (e) {
      setDetail(d => ({ ...d, [runId]: { loading: false, data: null, error: e.message } }))
    }
  }

  if (loading) {
    return <div className="content" data-testid="test-runs-view"><p style={{ color: 'var(--text-mut)' }}>Loading…</p></div>
  }
  if (error) {
    return <div className="content" data-testid="test-runs-view"><p style={{ color: 'var(--fail)' }}>Error: {error}</p></div>
  }

  return (
    <div className="content" data-testid="test-runs-view">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Suite</th>
              <th>Environment</th>
              <th>Started</th>
              <th>Tests</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map(run => (
              <React.Fragment key={run.id}>
                <tr onClick={() => handleToggle(run.id)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{run.id.slice(0, 8)}…</td>
                  <td>{run.suite}</td>
                  <td>{run.environment}</td>
                  <td>{formatDate(run.started_at)}</td>
                  <td>{run.result_ids ? run.result_ids.length : 0}</td>
                  <td style={{ textAlign: 'right', color: 'var(--text-mut)', fontSize: '12px' }}>
                    {expanded === run.id ? '▲' : '▼'}
                  </td>
                </tr>
                {expanded === run.id && (
                  <tr>
                    <td colSpan={6} style={{ padding: 0, background: 'var(--surface-sub)' }}>
                      <RunDetail state={detail[run.id]} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-mut)', padding: '32px' }}>
                  No test runs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
