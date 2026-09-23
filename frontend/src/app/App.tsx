import { useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ArrowRight, CheckCircle2, LoaderCircle, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { endpoints } from '../api/endpoints'
import { useHealth, useRunAnalysis } from '../api/hooks'
import { queryKeys } from '../api/queryKeys'
import { ApiError } from '../api/errors'
import { AppHeader } from '../components/layout/AppHeader'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ErrorState } from '../components/ui/ErrorState'
import { config } from '../config'
import { RunAnalysisDialog } from '../features/analysis-run/RunAnalysisDialog'
import { InvestigationAssistant } from '../features/assistant/InvestigationAssistant'
import { downloadBlob } from '../lib/download'
import { Dashboard } from './Dashboard'

export function App() {
  const health = useHealth()
  const run = useRunAnalysis()
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [notice, setNotice] = useState<string>()
  const [actionError, setActionError] = useState<unknown>()
  const [assistantOpen, setAssistantOpen] = useState(false)

  const startRun = () => {
    setActionError(undefined)
    run.mutate(
      { explanation_mode: config.defaultExplanationMode },
      {
        onSuccess: (result) => {
          setDialogOpen(false)
          setNotice(`Published trusted snapshot ${result.data.snapshot_id.slice(0, 8)} with ${result.data.candidate_count} candidates.`)
          void Promise.all([
            queryClient.invalidateQueries({ queryKey: queryKeys.health }),
            ...queryKeys.snapshotRoots.map((key) => queryClient.invalidateQueries({ queryKey: key })),
          ])
        },
        onError: (error) => setActionError(error),
      },
    )
  }

  const exportCsv = async () => {
    setExporting(true)
    setActionError(undefined)
    try {
      const result = await endpoints.exportCsv()
      downloadBlob(result)
      setNotice(`Downloaded ${result.filename} without transforming its bytes.`)
    } catch (error) {
      setActionError(error)
    } finally {
      setExporting(false)
    }
  }

  if (health.isLoading) return <div className="shell"><main className="not-ready container"><Card className="not-ready__card"><LoaderCircle aria-hidden="true" /><h1>Connecting to FreightGuard</h1><p>Checking API liveness and snapshot readiness.</p></Card></main></div>
  if (health.error) return <div className="shell"><main className="not-ready container"><ErrorState error={health.error} onRetry={() => void health.refetch()} title="FreightGuard API is unreachable" /></main></div>

  const hasOldSnapshot = Boolean(health.data?.ready)
  return <div className="shell"><a className="skip-link" href="#main-content">Skip to investigation dashboard</a><AppHeader health={health.data} running={run.isPending} exporting={exporting} onRun={() => setDialogOpen(true)} onExport={() => void exportCsv()} onAssistant={() => setAssistantOpen(true)} />
    <main id="main-content">
      {run.isPending && <div className="container banner" role="status"><LoaderCircle aria-hidden="true" /> <div><strong>Running analytics and validation gates.</strong><br /><small>{hasOldSnapshot ? 'The previous validated snapshot remains available while this run completes.' : 'The first snapshot will appear only after every gate passes.'}</small></div></div>}
      {notice && <div className="container banner" role="status"><CheckCircle2 aria-hidden="true" />{notice}<Button variant="ghost" onClick={() => setNotice(undefined)}>Dismiss</Button></div>}
      {Boolean(actionError) && <div className="container banner banner--warning" role="alert"><AlertCircle aria-hidden="true" /><div><strong>{actionError instanceof ApiError ? actionError.message : 'The requested action failed.'}</strong>{hasOldSnapshot && <><br /><small>The previous validated snapshot remains active.</small></>}{actionError instanceof ApiError && actionError.requestId && <><br /><small>Request ID: {actionError.requestId}</small></>}</div></div>}
      {!health.data?.ready ? <NotReady onRun={() => setDialogOpen(true)} running={run.isPending} /> : <Dashboard onRun={() => setDialogOpen(true)} />}
    </main>
    <RunAnalysisDialog open={dialogOpen} onOpenChange={setDialogOpen} onConfirm={startRun} running={run.isPending} />
    <InvestigationAssistant open={assistantOpen} onOpenChange={setAssistantOpen} snapshotId={health.data?.snapshot_id ?? undefined} />
  </div>
}

function NotReady({ onRun, running }: { onRun: () => void; running: boolean }) {
  return <div className="not-ready container"><Card className="not-ready__card"><p className="eyebrow"><ShieldCheck size={16} /> Service alive · analysis not ready</p><h1>Publish your first trusted freight-cost snapshot</h1><p className="hero-copy">The API is running, but FreightGuard will not display invented zeroes or partial results. Start the deterministic template pipeline to create a validated snapshot.</p><div className="steps"><div className="step"><strong>01 · Calculate</strong><p>Aggregate route-week costs and comparison baselines.</p></div><div className="step"><strong>02 · Validate</strong><p>Test context evidence against route, date, direction, impact, and scope.</p></div><div className="step"><strong>03 · Publish</strong><p>Expose results only after the formal evaluation gate passes.</p></div></div><Button onClick={onRun} disabled={running}>{running ? 'Analysis running…' : <>Run template analysis <ArrowRight size={17} /></>}</Button><p><small>The run may take time. No fabricated progress percentage is shown.</small></p></Card></div>
}
