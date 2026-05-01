import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import GapReport from './GapReport.jsx'
import * as api from '../api.js'

vi.mock('../api.js', () => ({
  getGaps: vi.fn(),
  generateForGap: vi.fn(),
}))

const mockGaps = [
  {
    id: 'gap-1',
    priority_score: 0.85,
    gap_reason: 'Never automated',
    test_case_id: 'tc-abc123def456789',
    status: 'open',
  },
]

const mockGenerateResponse = {
  scenarios: [
    {
      title: 'Login success flow',
      gherkin: 'Scenario: Login\n  Given I am on login page\n  When I submit valid credentials\n  Then I see the dashboard',
      confidence: 0.9,
      rationale: 'Core happy path',
      suggested_tags: ['@smoke'],
      skill_used: 'smoke',
    },
  ],
}

describe('GapReport', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('shows loading state initially', () => {
    api.getGaps.mockReturnValue(new Promise(() => {}))
    render(<GapReport />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders gap rows after load', async () => {
    api.getGaps.mockResolvedValue(mockGaps)
    render(<GapReport />)
    expect(await screen.findByText('Never automated')).toBeInTheDocument()
    expect(await screen.findByText('0.85')).toBeInTheDocument()
  })

  it('shows "No open gaps found." when list is empty', async () => {
    api.getGaps.mockResolvedValue([])
    render(<GapReport />)
    expect(await screen.findByText('No open gaps found.')).toBeInTheDocument()
  })

  it('calls getGaps with limit=20', async () => {
    api.getGaps.mockResolvedValue([])
    render(<GapReport />)
    await screen.findByText('No open gaps found.')
    expect(api.getGaps).toHaveBeenCalledWith(20)
  })

  it('generate button triggers API call and shows scenario title', async () => {
    const user = userEvent.setup()
    api.getGaps.mockResolvedValue(mockGaps)
    api.generateForGap.mockResolvedValue(mockGenerateResponse)
    render(<GapReport />)
    await screen.findByText('Never automated')
    await user.click(screen.getByRole('button', { name: 'Generate' }))
    expect(await screen.findByText('Login success flow')).toBeInTheDocument()
    expect(api.generateForGap).toHaveBeenCalledWith('gap-1')
  })

  it('shows error row when generate fails', async () => {
    const user = userEvent.setup()
    api.getGaps.mockResolvedValue(mockGaps)
    api.generateForGap.mockRejectedValue(new Error('HTTP 503'))
    render(<GapReport />)
    await screen.findByText('Never automated')
    await user.click(screen.getByRole('button', { name: 'Generate' }))
    expect(await screen.findByText(/Generation failed: HTTP 503/)).toBeInTheDocument()
  })

  it('disables button while generating', async () => {
    const user = userEvent.setup()
    api.getGaps.mockResolvedValue(mockGaps)
    api.generateForGap.mockReturnValue(new Promise(() => {}))
    render(<GapReport />)
    await screen.findByText('Never automated')
    const btn = screen.getByRole('button', { name: 'Generate' })
    await user.click(btn)
    expect(btn).toBeDisabled()
  })

  it('shows error on API load failure', async () => {
    api.getGaps.mockRejectedValue(new Error('HTTP 500'))
    render(<GapReport />)
    expect(await screen.findByText(/Error: HTTP 500/)).toBeInTheDocument()
  })

  it('can generate on multiple gaps independently', async () => {
    const user = userEvent.setup()
    const twoGaps = [
      { id: 'gap-1', priority_score: 0.85, gap_reason: 'Never automated', test_case_id: 'tc-abc123def456789', status: 'open' },
      { id: 'gap-2', priority_score: 0.60, gap_reason: 'Rarely run', test_case_id: 'tc-xyz000111222333', status: 'open' },
    ]
    api.getGaps.mockResolvedValue(twoGaps)
    api.generateForGap.mockResolvedValue(mockGenerateResponse)
    render(<GapReport />)
    await screen.findByText('Never automated')
    const buttons = screen.getAllByRole('button', { name: 'Generate' })
    expect(buttons).toHaveLength(2)
    await user.click(buttons[0])
    expect(await screen.findByText('Login success flow')).toBeInTheDocument()
    expect(api.generateForGap).toHaveBeenCalledWith('gap-1')
    expect(buttons[1]).not.toBeDisabled()
  })
})
