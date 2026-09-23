import { Download, MessageCircle, Play, ShieldCheck, Truck } from 'lucide-react'
import type { Health } from '../../api/contracts'
import { formatFingerprint } from '../../lib/format'
import { Button } from '../ui/Button'

export function AppHeader({ health, running, exporting, onRun, onExport, onAssistant }: { health?: Health; running: boolean; exporting: boolean; onRun: () => void; onExport: () => void; onAssistant: () => void }) {
  return (
    <header className="app-header">
      <div className="container app-header__inner">
        <div className="brand">
          <span className="brand-mark"><Truck aria-hidden="true" /></span>
          <div><h1>FreightGuard AI</h1><p>Freight cost investigation control tower</p></div>
        </div>
        <div className="header-actions">
          <div className="snapshot-status" title={health?.snapshot_id ?? 'No active snapshot'}>
            <span className={`status-dot ${health?.ready ? 'status-dot--ready' : ''}`} />
            <span>{health?.ready ? <>Trusted snapshot <code>{formatFingerprint(health.snapshot_id)}</code></> : 'Awaiting analysis'}</span>
            {health?.ready && <ShieldCheck size={16} aria-label="Validated" />}
          </div>
          <Button variant="secondary" onClick={onExport} disabled={!health?.ready || exporting} aria-label={exporting ? 'Preparing CSV export' : 'Export CSV'}>
            <Download size={17} /><span className="export-label">{exporting ? 'Preparing…' : 'Export CSV'}</span>
          </Button>
          <Button variant="secondary" onClick={onAssistant} disabled={!health?.ready} aria-label="Open investigation assistant">
            <MessageCircle size={17} /><span className="export-label">Ask</span>
          </Button>
          <Button onClick={onRun} disabled={running}><Play size={17} />{running ? 'Running…' : 'Run analysis'}</Button>
        </div>
      </div>
    </header>
  )
}
