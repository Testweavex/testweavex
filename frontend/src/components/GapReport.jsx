import { useEffect } from 'react'
import { getGaps } from '../api.js'

export default function GapReport() {
  useEffect(() => {
    getGaps()
  }, [])
  return <div data-testid="gap-report-view" />
}
