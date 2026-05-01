import React, { useState, useEffect } from 'react'
import { getGaps, generateForGap } from '../api.js'

export default function GapReport() {
  const [gaps, setGaps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generating, setGenerating] = useState({})
  const [results, setResults] = useState({})
  const [genErrors, setGenErrors] = useState({})

  useEffect(() => {
    let mounted = true
    getGaps(20)
      .then(gaps => { if (mounted) setGaps(gaps) })
      .catch(e => { if (mounted) setError(e.message) })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [])

  async function handleGenerate(gapId) {
    setGenerating(g => ({ ...g, [gapId]: true }))
    setGenErrors(e => { const n = { ...e }; delete n[gapId]; return n })
    try {
      const response = await generateForGap(gapId)
      setResults(r => ({ ...r, [gapId]: response.scenarios }))
    } catch (e) {
      setGenErrors(err => ({ ...err, [gapId]: e.message }))
    } finally {
      setGenerating(g => { const n = { ...g }; delete n[gapId]; return n })
    }
  }

  if (loading) return <div className="content" data-testid="gap-report-view"><p style={{ color: 'var(--text-mut)' }}>Loading…</p></div>
  if (error) return <div className="content" data-testid="gap-report-view"><p style={{ color: 'var(--fail)' }}>Error: {error}</p></div>

  return (
    <div className="content" data-testid="gap-report-view">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Score</th>
              <th>Reason</th>
              <th>Test Case</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {gaps.map(gap => (
              <React.Fragment key={gap.id}>
                <tr>
                  <td>
                    <div className="priority-bar-wrap">
                      <div className="priority-bar">
                        <div
                          className="priority-fill"
                          style={{
                            width: `${(gap.priority_score * 100).toFixed(0)}%`,
                            background: 'var(--brand)',
                          }}
                        />
                      </div>
                      <span className="score-val">{gap.priority_score.toFixed(2)}</span>
                    </div>
                  </td>
                  <td>{gap.gap_reason}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                    {gap.test_case_id.slice(0, 16)}…
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-primary"
                      disabled={!!generating[gap.id]}
                      onClick={() => handleGenerate(gap.id)}
                    >
                      {generating[gap.id] ? '⏳' : 'Generate'}
                    </button>
                  </td>
                </tr>
                {results[gap.id] && results[gap.id].map((scenario, i) => (
                  <tr key={`${gap.id}-s-${i}`}>
                    <td colSpan={4}>
                      <div style={{
                        padding: '12px',
                        background: 'var(--surface-sub)',
                        borderRadius: 'var(--r8)',
                        marginTop: '4px',
                      }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-sec)' }}>
                          {scenario.title}
                        </div>
                        <pre className="gherkin" style={{ margin: 0 }}>{scenario.gherkin}</pre>
                      </div>
                    </td>
                  </tr>
                ))}
                {genErrors[gap.id] && (
                  <tr key={`${gap.id}-err`}>
                    <td colSpan={4} style={{ color: 'var(--fail)', fontSize: '12px' }}>
                      Generation failed: {genErrors[gap.id]}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {gaps.length === 0 && (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-mut)', padding: '32px' }}>
                  No open gaps found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
