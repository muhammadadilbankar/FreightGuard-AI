import * as Dialog from '@radix-ui/react-dialog'
import { ShieldCheck } from 'lucide-react'
import { config } from '../../config'
import { Button } from '../../components/ui/Button'

export function RunAnalysisDialog({ open, onOpenChange, onConfirm, running }: { open: boolean; onOpenChange: (open: boolean) => void; onConfirm: () => void; running: boolean }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay">
          <Dialog.Content className="dialog">
            <Dialog.Title>Run trusted analysis</Dialog.Title>
            <Dialog.Description>
              FreightGuard will calculate route-week costs, apply deterministic evidence gates, and publish only after evaluation passes.
            </Dialog.Description>
            <div className="banner"><ShieldCheck aria-hidden="true" /><div><strong>Template mode · offline and deterministic</strong><br /><small>The current validated snapshot remains available until the new run passes every gate.</small></div></div>
            <p>Mode: <code>{config.defaultExplanationMode}</code>. This operation may take time; stage percentages are not available.</p>
            <div className="dialog-actions">
              <Dialog.Close asChild><Button variant="secondary">Cancel</Button></Dialog.Close>
              <Button onClick={onConfirm} disabled={running}>{running ? 'Running analytics…' : 'Start analysis'}</Button>
            </div>
          </Dialog.Content>
        </Dialog.Overlay>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
