import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Dashboard from './Dashboard.jsx'
import * as api from '../api.js'

vi.mock('../api.js', () => ({
  getDashboard: vi.fn(),
}))

const mockData = {
  coverage_percentage: 75.5,
  total_test_cases: 20,
  automated: 15,
  open_gaps: 5,
  last_run_id: 'abcdef1234567890',
}

describe('Dashboard', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('shows loading state initially', () => {
    api.getDashboard.mockReturnValue(new Promise(() => {}))
    render(<Dashboard />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders 4 KPI cards after successful load', async () => {
    api.getDashboard.mockResolvedValue(mockData)
    render(<Dashboard />)
    expect(await screen.findByText('20')).toBeInTheDocument()
    expect(await screen.findByText('75.5%')).toBeInTheDocument()
    expect(await screen.findByText('5')).toBeInTheDocument()
    expect(await screen.findByText('abcdef12…')).toBeInTheDocument()
  })

  it('shows KPI labels', async () => {
    api.getDashboard.mockResolvedValue(mockData)
    render(<Dashboard />)
    expect(await screen.findByText('Total Tests')).toBeInTheDocument()
    expect(await screen.findByText('Automated %')).toBeInTheDocument()
    expect(await screen.findByText('Open Gaps')).toBeInTheDocument()
    expect(await screen.findByText('Last Run')).toBeInTheDocument()
  })

  it('shows "None" when last_run_id is null', async () => {
    api.getDashboard.mockResolvedValue({ ...mockData, last_run_id: null })
    render(<Dashboard />)
    expect(await screen.findByText('None')).toBeInTheDocument()
  })

  it('shows "0.0%" when coverage_percentage is null', async () => {
    api.getDashboard.mockResolvedValue({ ...mockData, coverage_percentage: null })
    render(<Dashboard />)
    expect(await screen.findByText('0.0%')).toBeInTheDocument()
  })

  it('shows error message on API failure', async () => {
    api.getDashboard.mockRejectedValue(new Error('HTTP 500'))
    render(<Dashboard />)
    expect(await screen.findByText(/Error: HTTP 500/)).toBeInTheDocument()
  })
})
