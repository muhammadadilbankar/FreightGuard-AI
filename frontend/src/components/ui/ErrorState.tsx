import { AlertTriangle, RotateCcw } from 'lucide-react'
import { ApiError } from '../../api/errors'
import { Button } from './Button'

export function ErrorState({ error, onRetry, title = 'Unable to load this section' }: { error: unknown; onRetry?: () => void; title?: string }) {
  const apiError = error instanceof ApiError ? error : null
  return (
    <div className="state state--error" role="alert">
      <AlertTriangle aria-hidden="true" />
      <div>
        <h3>{title}</h3>
        <p>{apiError?.message ?? 'Check that the local API is running, then try again.'}</p>
        {apiError?.requestId && <small>Request ID: <code>{apiError.requestId}</code></small>}
      </div>
      {onRetry && <Button variant="secondary" onClick={onRetry}><RotateCcw size={16} /> Retry</Button>}
    </div>
  )
}
