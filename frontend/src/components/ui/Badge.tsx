import type { PropsWithChildren } from 'react'

export function Badge({ tone = 'neutral', children }: PropsWithChildren<{ tone?: string }>) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}
