import { fireEvent, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { RootCauseEnvelope } from '../../api/contracts'
import { renderApp } from '../../test/render'
import { OperationalLeads } from './OperationalLeads'

const contribution = {
  category: 'Carrier A', current_shipment_count: 2, reference_shipment_count: 8,
  reference_weeks_present: 4, current_tonne_km_share: 0.6,
  reference_mean_tonne_km_share: 0.4, current_cost_per_tonne_km: 3,
  reference_mean_cost_per_tonne_km: 2, mix_effect: 0.2, rate_effect: 0.4,
  entry_effect: 0, exit_effect: 0, net_contribution: 0.6,
  absolute_effect_share_pct: 100, direction: 'increases_gap' as const,
  support_level: 'strong' as const, caveats: [],
}
const lens = (name: 'transporter' | 'material') => ({
  lens: name, target_gap: 0.6, reconstructed_gap: 0.6, reconstruction_error: 0,
  contributions: [{ ...contribution, category: name === 'transporter' ? 'Carrier A' : 'Steel' }],
  leads: [], offsets: [],
})
const data: RootCauseEnvelope = {
  data: {
    schema_version: '1.0', candidate_key: 'R|2024-01-08', route: 'R', route_type: 'Short',
    week_of: '2024-01-08', canonical_verdict: 'unexplained', availability: 'available',
    reference_weeks: ['2024-01-01'], reference_week_count: 1, support_level: 'limited',
    current_cost_per_tonne_km: 2.6, own_history_baseline: 2, target_gap: 0.6,
    transporter: lens('transporter'), material: lens('material'),
    operational_metrics: [{ metric: 'shipment_count', unit: 'shipments', current_value: 3, reference_mean: 2, absolute_change: 1, percentage_change: 50, highlighted: true, interpretation: 'Descriptive only.' }],
    caveats: ['The lenses must not be added together.'],
  },
  meta: { schema_version: '1.0', snapshot_id: 'snapshot-a', pagination: null },
}

test('renders boundary and keeps independent keyboard-accessible lenses', () => {
  renderApp(<OperationalLeads data={data} error={null} loading={false} onRetry={() => undefined} />)
  expect(screen.getByRole('note')).toHaveTextContent('do not change the unexplained verdict')
  expect(screen.getAllByText('Carrier A')).toHaveLength(2)
  const transporter = screen.getByRole('tab', { name: 'Transporter lens' })
  fireEvent.keyDown(transporter, { key: 'ArrowRight' })
  expect(screen.getByRole('tab', { name: 'Material lens' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getAllByText('Steel')).toHaveLength(2)
  expect(screen.getByText(/independently partitions/)).toBeInTheDocument()
})
