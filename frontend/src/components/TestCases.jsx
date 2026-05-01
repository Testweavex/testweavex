import { useEffect } from 'react'
import { getTestCases } from '../api.js'

export default function TestCases() {
  useEffect(() => {
    getTestCases()
  }, [])
  return <div data-testid="test-cases-view" />
}
