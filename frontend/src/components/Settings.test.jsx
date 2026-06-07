import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Settings from './Settings.jsx'
import * as api from '../api.js'

vi.mock('../api.js', () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
}))

const mockSettings = {
  llm: { provider: 'anthropic', model: 'claude-sonnet-4-6', temperature: 0.3 },
  tcm: { provider: 'none' },
  gap_analysis: { top_gaps_default: 10, match_threshold: 0.65 },
}

describe('Settings', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('shows loading state initially', () => {
    api.getSettings.mockReturnValue(new Promise(() => {}))
    render(<Settings />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders LLM section by default after load', async () => {
    api.getSettings.mockResolvedValue(mockSettings)
    render(<Settings />)
    expect(await screen.findByText('LLM Configuration')).toBeInTheDocument()
    expect(screen.getByDisplayValue('anthropic')).toBeInTheDocument()
    expect(screen.getByDisplayValue('claude-sonnet-4-6')).toBeInTheDocument()
  })

  it('shows both nav sections', async () => {
    api.getSettings.mockResolvedValue(mockSettings)
    render(<Settings />)
    expect(await screen.findByText('LLM')).toBeInTheDocument()
    expect(screen.getByText('Gap Analysis')).toBeInTheDocument()
  })

  it('navigates to Gap Analysis section', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    render(<Settings />)
    await screen.findByText('LLM Configuration')
    await user.click(screen.getByText('Gap Analysis'))
    expect(screen.getByText('Top Gaps Default')).toBeInTheDocument()
    expect(screen.getByDisplayValue('10')).toBeInTheDocument()
  })

  it('shows match_threshold in Gap Analysis section', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    render(<Settings />)
    await screen.findByText('LLM')
    await user.click(screen.getByText('Gap Analysis'))
    expect(screen.getByText('0.65')).toBeInTheDocument()
  })

  it('shows TCM provider badge in Gap Analysis', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    render(<Settings />)
    await screen.findByText('LLM')
    await user.click(screen.getByText('Gap Analysis'))
    expect(screen.getByText('none (built-in)')).toBeInTheDocument()
  })

  it('shows connected badge when TCM is not none', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue({ ...mockSettings, tcm: { provider: 'testrail' } })
    render(<Settings />)
    await screen.findByText('LLM')
    await user.click(screen.getByText('Gap Analysis'))
    expect(screen.getByText(/testrail/)).toBeInTheDocument()
  })

  it('calls updateSettings with current form values on save', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    api.updateSettings.mockResolvedValue({ status: 'updated' })
    render(<Settings />)
    await screen.findByText('LLM Configuration')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(api.updateSettings).toHaveBeenCalledWith({
      llm_provider: 'anthropic',
      llm_model: 'claude-sonnet-4-6',
      temperature: 0.3,
    })
  })

  it('shows "Saved!" after successful save', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    api.updateSettings.mockResolvedValue({ status: 'updated' })
    render(<Settings />)
    await screen.findByText('LLM Configuration')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('Saved!')).toBeInTheDocument()
  })

  it('shows "Save failed." when updateSettings throws', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    api.updateSettings.mockRejectedValue(new Error('HTTP 500'))
    render(<Settings />)
    await screen.findByText('LLM Configuration')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('Save failed.')).toBeInTheDocument()
  })

  it('disables save button while saving', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    api.updateSettings.mockReturnValue(new Promise(() => {}))
    render(<Settings />)
    await screen.findByText('LLM Configuration')
    const btn = screen.getByRole('button', { name: 'Save Changes' })
    await user.click(btn)
    expect(btn).toBeDisabled()
  })

  it('updates model input on change', async () => {
    const user = userEvent.setup()
    api.getSettings.mockResolvedValue(mockSettings)
    api.updateSettings.mockResolvedValue({ status: 'updated' })
    render(<Settings />)
    await screen.findByText('LLM Configuration')
    const modelInput = screen.getByDisplayValue('claude-sonnet-4-6')
    await user.clear(modelInput)
    await user.type(modelInput, 'claude-opus-4-7')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))
    expect(api.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ llm_model: 'claude-opus-4-7' })
    )
  })

  it('updates temperature on slider change', async () => {
    api.getSettings.mockResolvedValue(mockSettings)
    api.updateSettings.mockResolvedValue({ status: 'updated' })
    render(<Settings />)
    expect(await screen.findByLabelText('Temperature')).toBeInTheDocument()
    const slider = screen.getByLabelText('Temperature')
    fireEvent.change(slider, { target: { value: '0.7' } })
    expect(screen.getByText('0.70')).toBeInTheDocument()
  })

  it('shows error on load failure', async () => {
    api.getSettings.mockRejectedValue(new Error('HTTP 503'))
    render(<Settings />)
    expect(await screen.findByText(/Error: HTTP 503/)).toBeInTheDocument()
  })
})
