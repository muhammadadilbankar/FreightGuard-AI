import { expect, test, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import {
  anomalyDetail,
  anomalyList,
  evaluation,
  healthReady,
  metrics,
  rootCause,
  runResponse,
  summary,
  timeline,
} from '../src/test/fixtures'

async function mockReadyApi(page: Page) {
  await page.route('**/health', (route) => route.fulfill({ json: healthReady }))
  await page.route('**/api/analysis/summary', (route) => route.fulfill({ json: summary }))
  await page.route('**/api/anomalies/*/*/root-cause', (route) => route.fulfill({ json: rootCause }))
  await page.route(/\/api\/anomalies\/[^/]+\/\d{4}-\d{2}-\d{2}$/, (route) => route.fulfill({ json: anomalyDetail }))
  await page.route('**/api/anomalies?*', (route) => route.fulfill({ json: anomalyList }))
  await page.route('**/api/routes/*/timeline*', (route) => route.fulfill({ json: timeline }))
  await page.route('**/api/evaluation/report?*', (route) => route.fulfill({ json: evaluation }))
  await page.route('**/api/run-metrics', (route) => route.fulfill({ json: metrics }))
  await page.route('**/api/analysis/run', async (route) => { await new Promise((resolve) => setTimeout(resolve, 1_000)); await route.fulfill({ json: runResponse }) })
  await page.route('**/api/analysis/export.csv', (route) => route.fulfill({ body: 'route,week_of\nTest-Route,2024-01-08\n', headers: { 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename="freightguard-test.csv"', 'Access-Control-Expose-Headers': 'Content-Disposition' } }))
}

test('investigation, deep-link, keyboard, rerun, and export flow', async ({ page }) => {
  await mockReadyApi(page)
  await page.goto('/?verdict=unexplained&selectedRoute=Test-Route&selectedWeek=2024-01-08')
  await expect(page.getByRole('heading', { name: 'Cost Courtroom' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'CHARGE' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'EVIDENCE' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Operational Leads' })).toBeVisible()
  await expect(page.getByRole('note')).toContainText('do not change the unexplained verdict')
  await page.getByRole('tab', { name: 'Material lens' }).click()
  await expect(page.getByText('Steel').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'VERDICT' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('heading', { name: 'Cost Courtroom' })).toBeHidden()
  await expect(page.getByRole('heading', { name: 'The freight network at a glance' })).toBeVisible()
  await page.getByRole('button', { name: 'Run analysis' }).click()
  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByText(/Running analytics and validation gates/)).toBeVisible()
  await expect(page.getByText('100', { exact: true })).toBeVisible()
  await expect(page.getByText(/Published trusted snapshot/)).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /Export CSV/ }).click()
  expect((await downloadPromise).suggestedFilename()).toBe('freightguard-test.csv')
})

test('ready dashboard and courtroom have no serious accessibility violations', async ({ page }) => {
  await mockReadyApi(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'The freight network at a glance' })).toBeVisible()
  let results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? ''))).toEqual([])
  await page.getByRole('button', { name: /Investigate (Test-Route|anomaly)/ }).first().click()
  await expect(page.getByRole('heading', { name: 'Cost Courtroom' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Operational Leads' })).toBeVisible()
  results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? ''))).toEqual([])
})

test('first run moves from guided not-ready state to dashboard', async ({ page }) => {
  let ready = false
  await mockReadyApi(page)
  await page.unroute('**/health')
  await page.unroute('**/api/analysis/run')
  await page.route('**/health', (route) => route.fulfill({ json: { ...healthReady, ready, has_snapshot: ready, snapshot_id: ready ? healthReady.snapshot_id : null, run_state: ready ? 'succeeded' : 'idle' } }))
  await page.route('**/api/analysis/run', async (route) => { ready = true; await route.fulfill({ json: runResponse }) })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Publish your first trusted/ })).toBeVisible()
  await page.getByRole('button', { name: /Run template analysis/ }).click()
  await page.getByRole('button', { name: 'Start analysis' }).click()
  await expect(page.getByRole('heading', { name: 'The freight network at a glance' })).toBeVisible()
})
