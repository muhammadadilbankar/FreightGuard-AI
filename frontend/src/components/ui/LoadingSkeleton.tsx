export function LoadingSkeleton({ label = 'Loading content' }: { label?: string }) {
  return <div className="skeleton" role="status" aria-label={label}><span /></div>
}
