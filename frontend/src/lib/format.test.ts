import { describe, expect, it } from 'vitest'
import { formatCostPerTonneKm, formatDate, formatInteger, formatPercent } from './format'

describe('presentation formatting', () => {
  it('formats numeric values without changing percentage-point semantics', () => {
    expect(formatInteger(2940)).toBe('2,940')
    expect(formatCostPerTonneKm(2.3456)).toContain('2.35')
    expect(formatPercent(23.4)).toContain('+23.40%')
    expect(formatPercent(-2)).toContain('-2.00%')
    expect(formatPercent(null)).toBe('Not available')
  })

  it('parses date-only values as local calendar dates', () => {
    expect(formatDate('2024-01-01')).toContain('01 Jan 2024')
    expect(formatDate(undefined)).toBe('Not available')
  })
})
