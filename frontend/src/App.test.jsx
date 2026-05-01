import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from './App.jsx'
import * as api from './api.js'

vi.mock('./api.js', () => ({
  getDashboard: vi.fn(),
  getTestCases: vi.fn(),
  getGaps: vi.fn(),
  generateForGap: vi.fn(),
}))

describe('App navigation', () => {
  beforeEach(() => {
    api.getDashboard.mockReturnValue(new Promise(() => {}))
    api.getTestCases.mockReturnValue(new Promise(() => {}))
    api.getGaps.mockReturnValue(new Promise(() => {}))
  })

  it('renders sidebar with 3 nav items', () => {
    render(<App />)
    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThan(0)
    expect(screen.getByText('Test Cases')).toBeInTheDocument()
    expect(screen.getByText('Gap Report')).toBeInTheDocument()
  })

  it('Dashboard view is active by default', () => {
    render(<App />)
    expect(screen.getByTestId('dashboard-view')).toBeInTheDocument()
    expect(screen.queryByTestId('test-cases-view')).not.toBeInTheDocument()
    expect(screen.queryByTestId('gap-report-view')).not.toBeInTheDocument()
  })

  it('navigates to Test Cases on sidebar click', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByText('Test Cases'))
    expect(screen.getByTestId('test-cases-view')).toBeInTheDocument()
    expect(screen.queryByTestId('dashboard-view')).not.toBeInTheDocument()
  })

  it('navigates to Gap Report on sidebar click', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByText('Gap Report'))
    expect(screen.getByTestId('gap-report-view')).toBeInTheDocument()
    expect(screen.queryByTestId('dashboard-view')).not.toBeInTheDocument()
  })
})
