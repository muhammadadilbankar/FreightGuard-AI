import axe from 'axe-core'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { App } from './App'
import { healthReady } from '../test/fixtures'
import { renderApp } from '../test/render'
import { server } from '../test/server'

describe('FreightGuard dashboard', () => {
  it('shows guided not-ready state and completes the first-run flow', async () => {
    let ready = false
    server.use(
      http.get('http://127.0.0.1:8000/health', () => HttpResponse.json({ ...healthReady, ready, has_snapshot: ready, snapshot_id: ready ? healthReady.snapshot_id : null, run_state: ready ? 'succeeded' : 'idle' })),
      http.post('http://127.0.0.1:8000/api/analysis/run', () => { ready = true; return HttpResponse.json({ data: { snapshot_id: healthReady.snapshot_id, candidate_count: 1 }, meta: { schema_version: '1.0', snapshot_id: healthReady.snapshot_id } }) }),
    )
    renderApp(<App />)
    expect(await screen.findByRole('heading', { name: /publish your first trusted/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /run template analysis/i }))
    await userEvent.click(screen.getByRole('button', { name: /start analysis/i }))
    expect(await screen.findByRole('heading', { name: /freight network at a glance/i })).toBeInTheDocument()
  })

  it('renders backend counts and opens the Cost Courtroom', async () => {
    renderApp(<App />)
    await screen.findByRole('heading', { name: /freight network at a glance/i }, { timeout: 10_000 })
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    const actions = await screen.findAllByRole('button', { name: /investigate test-route/i })
    await userEvent.click(actions[0]!)
    expect(await screen.findByRole('heading', { name: 'Cost Courtroom' })).toBeInTheDocument()
    expect(screen.getByText('CHARGE')).toBeInTheDocument()
    expect(screen.getByText('EVIDENCE')).toBeInTheDocument()
    expect(screen.getByText('VERDICT')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Cost Courtroom' })).not.toBeInTheDocument())
  })

  it('has no critical or serious axe violations in the ready state', async () => {
    const { container } = renderApp(<App />)
    await screen.findByRole('heading', { name: /freight network at a glance/i })
    const result = await axe.run(container)
    expect(result.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? ''))).toEqual([])
  })

  it('opens the grounded investigation assistant and renders a cited answer', async () => {
    renderApp(<App />)
    await screen.findByRole('heading', { name: /freight network at a glance/i })
    await userEvent.click(screen.getByRole('button', { name: /open investigation assistant/i }))
    expect(await screen.findByRole('heading', { name: /investigation assistant/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /how many anomalies/i }))
    expect(await screen.findByText(/20 weekly route records and 1 anomaly/i)).toBeInTheDocument()
    expect(screen.getByText(/template planner/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /analysis summary/i })).toBeDisabled()
  })
})
