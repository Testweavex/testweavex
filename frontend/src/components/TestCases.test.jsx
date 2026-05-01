import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TestCases from './TestCases.jsx'
import * as api from '../api.js'

vi.mock('../api.js', () => ({
  getTestCases: vi.fn(),
}))

const mockCases = [
  { id: '1', title: 'Login smoke test', test_type: 'smoke', is_automated: true, priority: 1, status: 'active' },
  { id: '2', title: 'Signup e2e flow', test_type: 'e2e', is_automated: false, priority: 2, status: 'active' },
]

describe('TestCases', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('shows loading state initially', () => {
    api.getTestCases.mockReturnValue(new Promise(() => {}))
    render(<TestCases />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders all test case rows after load', async () => {
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    expect(await screen.findByText('Login smoke test')).toBeInTheDocument()
    expect(await screen.findByText('Signup e2e flow')).toBeInTheDocument()
  })

  it('shows automated badge as "yes" for automated tests', async () => {
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    expect(screen.getByText('yes')).toBeInTheDocument()
    expect(screen.getByText('no')).toBeInTheDocument()
  })

  it('filters by test_type', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    const typeSelect = screen.getAllByRole('combobox')[0]
    await user.selectOptions(typeSelect, 'smoke')
    expect(screen.getByText('Login smoke test')).toBeInTheDocument()
    expect(screen.queryByText('Signup e2e flow')).not.toBeInTheDocument()
  })

  it('filters by automated status', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    const automatedSelect = screen.getAllByRole('combobox')[1]
    await user.selectOptions(automatedSelect, 'manual')
    expect(screen.queryByText('Login smoke test')).not.toBeInTheDocument()
    expect(screen.getByText('Signup e2e flow')).toBeInTheDocument()
  })

  it('shows empty state message when no results match', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    const typeSelect = screen.getAllByRole('combobox')[0]
    await user.selectOptions(typeSelect, 'integration')
    expect(screen.getByText('No test cases match filters.')).toBeInTheDocument()
  })

  it('shows error on API failure', async () => {
    api.getTestCases.mockRejectedValue(new Error('HTTP 503'))
    render(<TestCases />)
    expect(await screen.findByText(/Error: HTTP 503/)).toBeInTheDocument()
  })
})
