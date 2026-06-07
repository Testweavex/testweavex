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

export const getTestCase = (id) =>
  fetch(`${BASE}/api/test-cases/${id}`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const createTestCase = (body) =>
  fetch(`${BASE}/api/test-cases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const updateTestCase = (id, body) =>
  fetch(`${BASE}/api/test-cases/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const deleteTestCase = (id) =>
  fetch(`${BASE}/api/test-cases/${id}`, { method: 'DELETE' }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
  })

export const getRuns = (limit = 50) =>
  fetch(`${BASE}/api/runs?limit=${limit}`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const getRun = (runId) =>
  fetch(`${BASE}/api/runs/${runId}`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const getSettings = () =>
  fetch(`${BASE}/api/settings`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const updateSettings = (body) =>
  fetch(`${BASE}/api/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const executeTestCase = (id, body) =>
  fetch(`${BASE}/api/test-cases/${id}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })
