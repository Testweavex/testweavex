import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TestCases from './TestCases.jsx'
import * as api from '../api.js'

vi.mock('../api.js', () => ({
  getTestCases: vi.fn(),
  getTestCase: vi.fn(),
  createTestCase: vi.fn(),
  updateTestCase: vi.fn(),
  deleteTestCase: vi.fn(),
}))

const mockCases = [
  { id: 'tc-1', title: 'Login smoke test', test_type: 'smoke', is_automated: true, priority: 1, status: 'passed', tags: ['smoke'] },
  { id: 'tc-2', title: 'Signup e2e flow', test_type: 'e2e', is_automated: false, priority: 2, status: 'pending', tags: ['regression'] },
]

const mockDetail = {
  id: 'tc-1',
  title: 'Login smoke test',
  test_type: 'smoke',
  is_automated: true,
  priority: 1,
  status: 'passed',
  tags: ['smoke'],
  gherkin: 'Scenario: Login\n  Given I am on login page\n  When I submit valid credentials\n  Then I am logged in',
  source_file: 'features/auth/login.feature',
  recent_results: [
    { id: 'r-1', status: 'passed', duration_ms: 450 },
    { id: 'r-2', status: 'failed', duration_ms: 1200 },
  ],
}

describe('TestCases — list and filters', () => {
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
    expect(screen.getByText('Signup e2e flow')).toBeInTheDocument()
  })

  it('shows error on API failure', async () => {
    api.getTestCases.mockRejectedValue(new Error('HTTP 500'))
    render(<TestCases />)
    expect(await screen.findByText(/Error: HTTP 500/)).toBeInTheDocument()
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

  it('filters by automation status', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    const autoSelect = screen.getAllByRole('combobox')[1]
    await user.selectOptions(autoSelect, 'manual')
    expect(screen.queryByText('Login smoke test')).not.toBeInTheDocument()
    expect(screen.getByText('Signup e2e flow')).toBeInTheDocument()
  })

  it('filters by search text on title', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.type(screen.getByLabelText('Search test cases'), 'login')
    expect(screen.getByText('Login smoke test')).toBeInTheDocument()
    expect(screen.queryByText('Signup e2e flow')).not.toBeInTheDocument()
  })

  it('filters by search text on tag', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.type(screen.getByLabelText('Search test cases'), 'regression')
    expect(screen.queryByText('Login smoke test')).not.toBeInTheDocument()
    expect(screen.getByText('Signup e2e flow')).toBeInTheDocument()
  })

  it('shows empty state when no results match filters', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.type(screen.getByLabelText('Search test cases'), 'xxxxxxxx')
    expect(screen.getByText('No test cases match filters.')).toBeInTheDocument()
  })

  it('shows "+ New" button', async () => {
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    expect(screen.getByText('+ New')).toBeInTheDocument()
  })
})

describe('TestCases — detail panel', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('opens detail panel on row click', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    expect(await screen.findByTestId('detail-panel')).toBeInTheDocument()
    expect(api.getTestCase).toHaveBeenCalledWith('tc-1')
  })

  it('shows gherkin in detail panel', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    expect(await screen.findByText(/Given I am on login page/)).toBeInTheDocument()
  })

  it('shows recent results in detail panel', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    expect(await screen.findByText('Recent Results')).toBeInTheDocument()
    expect(screen.getAllByText('passed').length).toBeGreaterThan(0)
  })

  it('shows tags in detail panel', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    const panel = await screen.findByTestId('detail-panel')
    const tagElements = within(panel).getAllByText('smoke')
    // appears as both a type badge and a tag chip
    expect(tagElements.length).toBeGreaterThanOrEqual(1)
  })

  it('closes panel on X click', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByTestId('detail-panel')
    await user.click(screen.getByLabelText('Close panel'))
    expect(screen.queryByTestId('detail-panel')).not.toBeInTheDocument()
  })
})

describe('TestCases — edit', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('opens edit form on Edit button click', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByText('Edit')
    await user.click(screen.getByText('Edit'))
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
    expect(screen.getByLabelText('Title').value).toBe('Login smoke test')
  })

  it('calls updateTestCase on Save', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    api.updateTestCase.mockResolvedValue({ ...mockDetail, title: 'Updated title' })
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByText('Edit')
    await user.click(screen.getByText('Edit'))
    const titleInput = screen.getByLabelText('Title')
    await user.clear(titleInput)
    await user.type(titleInput, 'Updated title')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(api.updateTestCase).toHaveBeenCalledWith('tc-1', expect.objectContaining({ title: 'Updated title' }))
    expect((await screen.findAllByText('Updated title')).length).toBeGreaterThan(0)
  })

  it('Cancel from edit returns to view mode', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByText('Edit')
    await user.click(screen.getByText('Edit'))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByLabelText('Title')).not.toBeInTheDocument()
    expect(screen.getByText('Edit')).toBeInTheDocument()
  })

  it('Save is disabled when title is empty', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByText('Edit')
    await user.click(screen.getByText('Edit'))
    await user.clear(screen.getByLabelText('Title'))
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })
})

describe('TestCases — create', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('opens create form on "+ New" click', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('+ New'))
    expect(screen.getByTestId('detail-panel')).toBeInTheDocument()
    expect(screen.getByText('New Test Case')).toBeInTheDocument()
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
  })

  it('calls createTestCase on Save with form values', async () => {
    const user = userEvent.setup()
    const newTc = { id: 'tc-new', title: 'Brand new test', test_type: 'sanity', is_automated: false, priority: 2, status: 'pending', tags: [], gherkin: 'Scenario: New test\n  Given something', recent_results: [] }
    api.getTestCases.mockResolvedValue(mockCases)
    api.createTestCase.mockResolvedValue(newTc)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('+ New'))
    await user.type(screen.getByLabelText('Title'), 'Brand new test')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(api.createTestCase).toHaveBeenCalledWith(expect.objectContaining({ title: 'Brand new test' }))
    expect((await screen.findAllByText('Brand new test')).length).toBeGreaterThan(0)
  })

  it('Cancel from create closes panel', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('+ New'))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByTestId('detail-panel')).not.toBeInTheDocument()
  })
})

describe('TestCases — delete', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('requires confirmation before deleting', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByText('Delete')
    await user.click(screen.getByText('Delete'))
    expect(screen.getByText('Confirm delete')).toBeInTheDocument()
    expect(api.deleteTestCase).not.toHaveBeenCalled()
  })

  it('calls deleteTestCase on confirm and removes row', async () => {
    const user = userEvent.setup()
    api.getTestCases.mockResolvedValue(mockCases)
    api.getTestCase.mockResolvedValue(mockDetail)
    api.deleteTestCase.mockResolvedValue(undefined)
    render(<TestCases />)
    await screen.findByText('Login smoke test')
    await user.click(screen.getByText('Login smoke test'))
    await screen.findByText('Delete')
    await user.click(screen.getByText('Delete'))
    await user.click(screen.getByText('Confirm delete'))
    expect(api.deleteTestCase).toHaveBeenCalledWith('tc-1')
    expect(await screen.findByText('Signup e2e flow')).toBeInTheDocument()
    expect(screen.queryByText('Login smoke test')).not.toBeInTheDocument()
    expect(screen.queryByTestId('detail-panel')).not.toBeInTheDocument()
  })
})
