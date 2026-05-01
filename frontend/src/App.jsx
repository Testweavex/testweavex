import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Dashboard from './components/Dashboard.jsx'
import TestCases from './components/TestCases.jsx'
import GapReport from './components/GapReport.jsx'

const TITLES = {
  dashboard: 'Dashboard',
  'test-cases': 'Test Cases',
  gaps: 'Gap Report',
}

export default function App() {
  const [view, setView] = useState('dashboard')

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar view={view} setView={setView} />
      <div className="main">
        <div className="topbar">
          <span className="page-title">{TITLES[view]}</span>
        </div>
        {view === 'dashboard' && <Dashboard />}
        {view === 'test-cases' && <TestCases />}
        {view === 'gaps' && <GapReport />}
      </div>
    </div>
  )
}
