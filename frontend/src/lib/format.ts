const integer = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const decimal = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export const formatInteger = (value: number | null | undefined) =>
  value == null ? 'Not available' : integer.format(value)

export const formatCostPerTonneKm = (value: number | null | undefined) =>
  value == null ? 'Not available' : `₹${decimal.format(value)}`

export const formatPercent = (value: number | null | undefined) =>
  value == null ? 'Not available' : `${value > 0 ? '+' : ''}${decimal.format(value)}%`

export const formatDate = (value: string | null | undefined) => {
  if (!value) return 'Not available'
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return 'Not available'
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(year, month - 1, day))
}

export const formatDateRange = (from?: string | null, to?: string | null) =>
  from && to ? `${formatDate(from)} – ${formatDate(to)}` : 'Not available'

export const formatDuration = (milliseconds: number | null | undefined) => {
  if (milliseconds == null) return 'Not available'
  return milliseconds >= 1000
    ? `${(milliseconds / 1000).toFixed(1)} s`
    : `${integer.format(milliseconds)} ms`
}

export const formatCurrency = (value: number | string | null | undefined) =>
  value == null
    ? 'Not available'
    : new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 4,
      }).format(Number(value))

export const formatFingerprint = (value: string | null | undefined) =>
  value ? `${value.slice(0, 8)}…${value.slice(-6)}` : 'Not available'

export const sentenceCase = (value: string) =>
  value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
