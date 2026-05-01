import { useState, useEffect } from 'react'
import { getDashboard } from '../api.js'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="content" data-testid="dashboard-view"><p style={{ color: 'var(--text-mut)' }}>Loading…</p></div>
  if (error) return <div className="content" data-testid="dashboard-view"><p style={{ color: 'var(--fail)' }}>Error: {error}</p></div>

  const lastRun = data.last_run_id ? data.last_run_id.slice(0, 8) + '…' : 'None'

  return (
    <div className="content" data-testid="dashboard-view">
      <div className="kpi-row">
        <div className="kpi-card">
          <div className="kpi-label">Total Tests</div>
          <div className="kpi-value">{data.total_test_cases}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Automated %</div>
          <div className="kpi-value">{(data.coverage_percentage ?? 0).toFixed(1)}%</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Open Gaps</div>
          <div className="kpi-value">{data.open_gaps}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Last Run</div>
          <div className="kpi-value" style={{ fontSize: '16px' }}>{lastRun}</div>
        </div>
      </div>
    </div>
  )
}
