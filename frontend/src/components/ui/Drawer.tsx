import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { PropsWithChildren } from 'react'

export function Drawer({ open, onOpenChange, title, description, closeLabel = 'Close panel', children }: PropsWithChildren<{ open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; closeLabel?: string }>) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="drawer-content">
          <div className="drawer-heading">
            <div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div>
            <Dialog.Close className="icon-button" aria-label={closeLabel}><X /></Dialog.Close>
          </div>
          <div className="drawer-scroll">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
