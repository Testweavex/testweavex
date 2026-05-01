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
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Test Cases')).toBeInTheDocument()
    expect(screen.getByText('Gap Report')).toBeInTheDocument()
  })

  it('Dashboard is active by default', () => {
    render(<App />)
    expect(api.getDashboard).toHaveBeenCalled()
  })

  it('navigates to Test Cases on sidebar click', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getAllByText('Test Cases')[0])
    expect(api.getTestCases).toHaveBeenCalled()
  })

  it('navigates to Gap Report on sidebar click', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getAllByText('Gap Report')[0])
    expect(api.getGaps).toHaveBeenCalled()
  })
})
