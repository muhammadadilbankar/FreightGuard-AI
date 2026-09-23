import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { queryKeys } from '../api/queryKeys'

export interface SnapshotGuardResult {
  consistent: boolean
  reconciling: boolean
  persistentMismatch: boolean
}

export const compareSnapshotIds = (
  reference: string | null | undefined,
  observed: Array<string | null | undefined>,
): boolean => Boolean(reference) && observed.filter(Boolean).every((id) => id === reference)

export function useSnapshotGuard(
  reference: string | null | undefined,
  observed: Array<string | null | undefined>,
): SnapshotGuardResult {
  const client = useQueryClient()
  const [completedReference, setCompletedReference] = useState<string | null>(null)
  const attemptedReference = useRef<string | null>(null)
  const consistent = compareSnapshotIds(reference, observed)

  useEffect(() => {
    if (!reference || consistent || attemptedReference.current === reference) return
    attemptedReference.current = reference
    void Promise.all(
      queryKeys.snapshotRoots.map((queryKey) =>
        client.invalidateQueries({ queryKey }),
      ),
    ).then(() => setCompletedReference(reference))
  }, [client, consistent, reference])

  return {
    consistent,
    reconciling: Boolean(reference) && !consistent && completedReference !== reference,
    persistentMismatch:
      Boolean(reference) && !consistent && completedReference === reference,
  }
}
