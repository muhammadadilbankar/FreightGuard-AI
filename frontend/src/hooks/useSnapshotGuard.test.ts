import { createElement, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createQueryClient } from '../app/queryClient'
import { queryKeys } from '../api/queryKeys'
import { compareSnapshotIds, useSnapshotGuard } from './useSnapshotGuard'

describe('snapshot consistency', () => {
  it('accepts only resources from the reference snapshot', () => {
    expect(compareSnapshotIds('A', ['A', 'A', undefined])).toBe(true)
    expect(compareSnapshotIds('A', ['A', 'B'])).toBe(false)
    expect(compareSnapshotIds(undefined, [])).toBe(false)
  })

  it('invalidates the snapshot queries once, then exposes a persistent mismatch', async () => {
    const client = createQueryClient()
    const invalidate = vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children)
    const { result, rerender } = renderHook(
      ({ observed }) => useSnapshotGuard('snapshot-a', observed),
      { wrapper, initialProps: { observed: ['snapshot-b'] as Array<string | undefined> } },
    )

    expect(result.current.reconciling).toBe(true)
    await waitFor(() => expect(result.current.persistentMismatch).toBe(true))
    rerender({ observed: ['snapshot-b'] })
    expect(invalidate).toHaveBeenCalledTimes(queryKeys.snapshotRoots.length)
  })

  it('recovers when refreshed resources converge on the reference snapshot', async () => {
    const client = createQueryClient()
    vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children)
    const { result, rerender } = renderHook(
      ({ observed }) => useSnapshotGuard('snapshot-a', observed),
      { wrapper, initialProps: { observed: ['snapshot-b'] as Array<string | undefined> } },
    )

    rerender({ observed: ['snapshot-a'] })
    await waitFor(() => expect(result.current.consistent).toBe(true))
    expect(result.current.persistentMismatch).toBe(false)
  })
})
