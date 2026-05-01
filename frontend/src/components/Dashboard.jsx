import { useEffect } from 'react'
import { getDashboard } from '../api.js'

export default function Dashboard() {
  useEffect(() => {
    getDashboard()
  }, [])
  return <div data-testid="dashboard-view" />
}
