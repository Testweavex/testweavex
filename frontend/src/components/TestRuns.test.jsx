import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TestRuns from './TestRuns.jsx'
import * as api from '../api.js'

vi.mock('../api.js', () => ({
  getRuns: vi.fn(),
  getRun: vi.fn(),
}))

const mockRuns = [
  {
    id: 'run-uuid-1111-aaaa',
    suite: 'smoke',
    environment: 'local',
    started_at: '2026-06-01T10:00:00',
    result_ids: ['r1', 'r2', 'r3'],
  },
  {
    id: 'run-uuid-2222-bbbb',
    suite: 'e2e',
    environment: 'staging',
    started_at: '2026-06-02T14:30:00',
    result_ids: [],
  },
]

const mockRunDetail = {
  id: 'run-uuid-1111-aaaa',
  suite: 'smoke',
  environment: 'local',
  browser: 'chromium',
  started_at: '2026-06-01T10:00:00',
  result_ids: ['r1', 'r2', 'r3'],
  results: [
    { id: 'r1', test_case_id: 'tc-aabbccdd11223344', status: 'passed', duration_ms: 450, error_message: null },
    { id: 'r2', test_case_id: 'tc-eeff00112233aabb', status: 'failed', duration_ms: 1200, error_message: 'AssertionError' },
    { id: 'r3', test_case_id: 'tc-99887766554433aa', status: 'skipped', duration_ms: 0, error_message: null },
  ],
}

describe('TestRuns', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('shows loading state initially', () => {
    api.getRuns.mockReturnValue(new Promise(() => {}))
    render(<TestRuns />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders run rows after load', async () => {
    api.getRuns.mockResolvedValue(mockRuns)
    render(<TestRuns />)
    expect(await screen.findByText('smoke')).toBeInTheDocument()
    expect(await screen.findByText('e2e')).toBeInTheDocument()
    expect(screen.getByText('local')).toBeInTheDocument()
    expect(screen.getByText('staging')).toBeInTheDocument()
  })

  it('shows truncated run IDs', async () => {
    api.getRuns.mockResolvedValue(mockRuns)
    render(<TestRuns />)
    const cells = await screen.findAllByText('run-uuid…')
    expect(cells).toHaveLength(2)
  })

  it('shows result count from result_ids', async () => {
    api.getRuns.mockResolvedValue(mockRuns)
    render(<TestRuns />)
    await screen.findByText('smoke')
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('shows empty state when no runs', async () => {
    api.getRuns.mockResolvedValue([])
    render(<TestRuns />)
    expect(await screen.findByText('No test runs yet.')).toBeInTheDocument()
  })

  it('shows error on API load failure', async () => {
    api.getRuns.mockRejectedValue(new Error('HTTP 500'))
    render(<TestRuns />)
    expect(await screen.findByText(/Error: HTTP 500/)).toBeInTheDocument()
  })

  it('calls getRun on row click and shows detail', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockResolvedValue(mockRunDetail)
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    expect(api.getRun).toHaveBeenCalledWith('run-uuid-1111-aaaa')
    expect(await screen.findByText('passed')).toBeInTheDocument()
    expect(await screen.findByText('failed')).toBeInTheDocument()
    expect(await screen.findByText('AssertionError')).toBeInTheDocument()
  })

  it('shows pass/fail/skip counts in detail', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockResolvedValue(mockRunDetail)
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    expect(await screen.findByText('Passed')).toBeInTheDocument()
    expect(await screen.findByText('Failed')).toBeInTheDocument()
    expect(await screen.findByText('Skipped')).toBeInTheDocument()
  })

  it('collapses detail on second click', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockResolvedValue(mockRunDetail)
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    expect(await screen.findByText('passed')).toBeInTheDocument()
    await user.click(rows[1])
    expect(screen.queryByText('passed')).not.toBeInTheDocument()
  })

  it('does not re-fetch detail on second expand', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockResolvedValue(mockRunDetail)
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    await screen.findByText('passed')
    await user.click(rows[1])
    await user.click(rows[1])
    expect(api.getRun).toHaveBeenCalledTimes(1)
  })

  it('shows detail loading state while fetching run', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockReturnValue(new Promise(() => {}))
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    expect(await screen.findByText('Loading…')).toBeInTheDocument()
  })

  it('shows detail error when getRun fails', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockRejectedValue(new Error('HTTP 404'))
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    expect(await screen.findByText(/Error: HTTP 404/)).toBeInTheDocument()
  })

  it('shows "No results for this run." when results array is empty', async () => {
    const user = userEvent.setup()
    api.getRuns.mockResolvedValue(mockRuns)
    api.getRun.mockResolvedValue({ ...mockRunDetail, results: [] })
    render(<TestRuns />)
    await screen.findByText('smoke')
    const rows = screen.getAllByRole('row')
    await user.click(rows[1])
    expect(await screen.findByText('No results for this run.')).toBeInTheDocument()
  })
})
