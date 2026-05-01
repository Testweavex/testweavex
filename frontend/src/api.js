const BASE = '/api'

export async function getDashboard() {
  const res = await fetch(`${BASE}/dashboard`)
  return res.json()
}

export async function getTestCases() {
  const res = await fetch(`${BASE}/test-cases`)
  return res.json()
}

export async function getGaps() {
  const res = await fetch(`${BASE}/gaps`)
  return res.json()
}

export async function generateForGap(gapId) {
  const res = await fetch(`${BASE}/gaps/${gapId}/generate`, { method: 'POST' })
  return res.json()
}
