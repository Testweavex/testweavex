import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getDashboard, getTestCases, getGaps, generateForGap, getRuns, getRun, getSettings, updateSettings, getTestCase, createTestCase, updateTestCase, deleteTestCase } from './api.js'

function mockFetch(data, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    json: () => Promise.resolve(data),
  })
}

beforeEach(() => { vi.resetAllMocks() })

describe('getDashboard', () => {
  it('fetches /api/dashboard', async () => {
    const data = { coverage_percentage: 75, total_test_cases: 10, automated: 7, open_gaps: 3, last_run_id: 'abc' }
    mockFetch(data)
    const result = await getDashboard()
    expect(global.fetch).toHaveBeenCalledWith('/api/dashboard')
    expect(result).toEqual(data)
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getDashboard()).rejects.toThrow('HTTP')
  })
})

describe('getTestCases', () => {
  it('fetches /api/test-cases', async () => {
    mockFetch([])
    await getTestCases()
    expect(global.fetch).toHaveBeenCalledWith('/api/test-cases')
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getTestCases()).rejects.toThrow('HTTP')
  })
})

describe('getGaps', () => {
  it('fetches /api/gaps with default limit=20', async () => {
    mockFetch([])
    await getGaps()
    expect(global.fetch).toHaveBeenCalledWith('/api/gaps?limit=20')
  })

  it('fetches /api/gaps with custom limit', async () => {
    mockFetch([])
    await getGaps(50)
    expect(global.fetch).toHaveBeenCalledWith('/api/gaps?limit=50')
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getGaps()).rejects.toThrow('HTTP')
  })
})

describe('generateForGap', () => {
  it('POSTs to /api/gaps/:id/generate', async () => {
    mockFetch({ scenarios: [] })
    await generateForGap('gap-123')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/gaps/gap-123/generate',
      { method: 'POST' }
    )
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(generateForGap('x')).rejects.toThrow('HTTP')
  })
})

describe('getRuns', () => {
  it('fetches /api/runs with default limit=50', async () => {
    mockFetch([])
    await getRuns()
    expect(global.fetch).toHaveBeenCalledWith('/api/runs?limit=50')
  })

  it('fetches /api/runs with custom limit', async () => {
    mockFetch([])
    await getRuns(10)
    expect(global.fetch).toHaveBeenCalledWith('/api/runs?limit=10')
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getRuns()).rejects.toThrow('HTTP')
  })
})

describe('getRun', () => {
  it('fetches /api/runs/:id', async () => {
    const data = { id: 'run-123', results: [] }
    mockFetch(data)
    const result = await getRun('run-123')
    expect(global.fetch).toHaveBeenCalledWith('/api/runs/run-123')
    expect(result).toEqual(data)
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getRun('run-404')).rejects.toThrow('HTTP')
  })
})

describe('getSettings', () => {
  it('fetches /api/settings', async () => {
    const data = { llm: { provider: 'anthropic', model: 'claude-sonnet-4-6', temperature: 0.3 }, tcm: { provider: 'none' }, gap_analysis: { top_gaps_default: 10, match_threshold: 0.65 } }
    mockFetch(data)
    const result = await getSettings()
    expect(global.fetch).toHaveBeenCalledWith('/api/settings')
    expect(result).toEqual(data)
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getSettings()).rejects.toThrow('HTTP')
  })
})

describe('updateSettings', () => {
  it('PUTs to /api/settings with JSON body', async () => {
    mockFetch({ status: 'updated' })
    const body = { llm_provider: 'openai', llm_model: 'gpt-4o', temperature: 0.5 }
    await updateSettings(body)
    expect(global.fetch).toHaveBeenCalledWith('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(updateSettings({})).rejects.toThrow('HTTP')
  })
})

describe('getTestCase', () => {
  it('fetches /api/test-cases/:id', async () => {
    const data = { id: 'tc-1', title: 'Login test', recent_results: [] }
    mockFetch(data)
    const result = await getTestCase('tc-1')
    expect(global.fetch).toHaveBeenCalledWith('/api/test-cases/tc-1')
    expect(result).toEqual(data)
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(getTestCase('tc-404')).rejects.toThrow('HTTP')
  })
})

describe('createTestCase', () => {
  it('POSTs to /api/test-cases with JSON body', async () => {
    const body = { title: 'New test', test_type: 'smoke' }
    mockFetch({ id: 'tc-new', ...body })
    await createTestCase(body)
    expect(global.fetch).toHaveBeenCalledWith('/api/test-cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(createTestCase({})).rejects.toThrow('HTTP')
  })
})

describe('updateTestCase', () => {
  it('PATCHes /api/test-cases/:id with JSON body', async () => {
    const body = { title: 'Updated', priority: 1 }
    mockFetch({ id: 'tc-1', ...body })
    await updateTestCase('tc-1', body)
    expect(global.fetch).toHaveBeenCalledWith('/api/test-cases/tc-1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  })

  it('throws on non-ok response', async () => {
    mockFetch({}, false)
    await expect(updateTestCase('tc-1', {})).rejects.toThrow('HTTP')
  })
})

describe('deleteTestCase', () => {
  it('DELETEs /api/test-cases/:id', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true })
    await deleteTestCase('tc-1')
    expect(global.fetch).toHaveBeenCalledWith('/api/test-cases/tc-1', { method: 'DELETE' })
  })

  it('throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 })
    await expect(deleteTestCase('tc-1')).rejects.toThrow('HTTP')
  })
})
