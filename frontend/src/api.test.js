import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getDashboard, getTestCases, getGaps, generateForGap } from './api.js'

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
