import { describe, expect, it } from 'vitest'
import { parseInvestigationState, serializeInvestigationState } from './urlState'

describe('investigation URL state', () => {
  it('normalizes invalid enum and page values', () => {
    const state = parseInvestigationState('?verdict=wrong&sortBy=secret&page=-3')
    expect(state.filters.verdict).toBeUndefined()
    expect(state.filters.sortBy).toBe('vs_own_history_pct')
    expect(state.filters.page).toBe(1)
  })

  it('round-trips safe filters and selection', () => {
    const state = parseInvestigationState('?verdict=unexplained&selectedRoute=A-B&selectedWeek=2024-01-08')
    expect(serializeInvestigationState(state)).toContain('selectedRoute=A-B')
    expect(state.filters.verdict).toBe('unexplained')
  })
})
