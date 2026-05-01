const BASE = ''

export const getDashboard = () =>
  fetch(`${BASE}/api/dashboard`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const getTestCases = () =>
  fetch(`${BASE}/api/test-cases`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const getGaps = (limit = 20) =>
  fetch(`${BASE}/api/gaps?limit=${limit}`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const generateForGap = (gapId) =>
  fetch(`${BASE}/api/gaps/${gapId}/generate`, { method: 'POST' }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })
