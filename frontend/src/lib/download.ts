import type { BlobResult } from '../api/client'

export const downloadBlob = ({ blob, filename }: BlobResult): void => {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}
