const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'test-cases', label: 'Test Cases', icon: '📋' },
  { id: 'gaps', label: 'Gap Report', icon: '🔍' },
]

export default function Sidebar({ view, setView }) {
  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-mark">Test<span>WeaveX</span></div>
        <div className="logo-sub">Test Intelligence</div>
      </div>
      <nav className="nav">
        <div className="nav-section">Navigation</div>
        {NAV_ITEMS.map(item => (
          <div
            key={item.id}
            className={`nav-item${view === item.id ? ' active' : ''}`}
            onClick={() => setView(item.id)}
          >
            <span className="icon">{item.icon}</span>
            {item.label}
          </div>
        ))}
      </nav>
    </div>
  )
}
