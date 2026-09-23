import { describe, expect, it } from 'vitest'
import { safeFilename } from './client'
import { parseApiError } from './errors'

describe('API transport safety', () => {
  it('parses the standard error envelope and request ID', async () => {
    const response = new Response(JSON.stringify({ error: { code: 'analysis_not_ready', message: 'Run analysis.', details: {}, request_id: 'request-1' } }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    await expect(parseApiError(response)).resolves.toMatchObject({ status: 503, code: 'analysis_not_ready', requestId: 'request-1' })
  })

  it('sanitizes server filenames and falls back safely', () => {
    expect(safeFilename('attachment; filename="analysis.csv"')).toBe('analysis.csv')
    expect(safeFilename('attachment; filename="../unsafe.csv"')).toBe('.._unsafe.csv')
    expect(safeFilename(null)).toBe('freightguard-analysis.csv')
  })
})
