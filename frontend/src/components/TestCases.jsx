import { useState, useEffect } from 'react'
import { getTestCases } from '../api.js'

const TEST_TYPES = [
  'smoke', 'e2e', 'integration', 'sanity',
  'happy_path', 'data_driven', 'edge_case', 'accessibility',
]

const TYPE_BADGE = {
  smoke: 'badge-smoke',
  e2e: 'badge-e2e',
  integration: 'badge-integration',
  sanity: 'badge-sanity',
}

function typeBadge(t) {
  return TYPE_BADGE[t] || 'badge-brand'
}

export default function TestCases() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [typeFilter, setTypeFilter] = useState('all')
  const [automatedFilter, setAutomatedFilter] = useState('all')

  useEffect(() => {
    getTestCases()
      .then(setCases)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="content" data-testid="test-cases-view"><p style={{ color: 'var(--text-mut)' }}>Loading…</p></div>
  if (error) return <div className="content" data-testid="test-cases-view"><p style={{ color: 'var(--fail)' }}>Error: {error}</p></div>

  const filtered = cases.filter(tc => {
    if (typeFilter !== 'all' && tc.test_type !== typeFilter) return false
    if (automatedFilter === 'automated' && !tc.is_automated) return false
    if (automatedFilter === 'manual' && tc.is_automated) return false
    return true
  })

  return (
    <div className="content" data-testid="test-cases-view">
      <div className="table-wrap">
        <div className="filter-bar">
          <select
            className="search-input"
            style={{ flex: '0 0 auto', width: '160px' }}
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
          >
            <option value="all">All Types</option>
            {TEST_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select
            className="search-input"
            style={{ flex: '0 0 auto', width: '160px' }}
            value={automatedFilter}
            onChange={e => setAutomatedFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="automated">Automated</option>
            <option value="manual">Manual</option>
          </select>
          <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-mut)' }}>
            {filtered.length} test case{filtered.length !== 1 ? 's' : ''}
          </span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Type</th>
              <th>Automated</th>
              <th>Priority</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(tc => (
              <tr key={tc.id}>
                <td>{tc.title}</td>
                <td><span className={`badge ${typeBadge(tc.test_type)}`}>{tc.test_type}</span></td>
                <td>
                  <span className={`badge ${tc.is_automated ? 'badge-pass' : 'badge-manual'}`}>
                    {tc.is_automated ? 'yes' : 'no'}
                  </span>
                </td>
                <td>{tc.priority ?? '—'}</td>
                <td><span className="badge badge-brand">{tc.status}</span></td>
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
  )
}
