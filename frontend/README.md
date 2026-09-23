# FreightGuard investigation dashboard

Phase 11 is a React 19 + TypeScript + Vite investigation interface over the
Phase 10 API. The browser renders backend-owned calculations, Evidence Gate
decisions, evaluation results, and exact CSV exports; it does not recalculate
canonical values or verdicts.

## Local setup

Prerequisites: Node.js 20.19 or newer and the FreightGuard API on
`http://127.0.0.1:8000`.

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local  # optional
npm run dev
```

Open <http://127.0.0.1:5173>. `VITE_API_BASE_URL` may point to another API
origin. Do not put secrets in Vite variables because they are browser-visible.

Run the production preview with:

```powershell
npm run build
npm run preview -- --host 127.0.0.1
```

## Verification

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright covers Chromium desktop, an 820 x 1180 tablet, and a Pixel 7 viewport. API-facing tests use
MSW with synthetic records; production components contain no sample anomalies.
OpenAPI types can be refreshed while the API is running with `npm run api:types`.

## Main flows

- Guided first analysis and refresh confirmation, with the last trusted snapshot
  retained while a rerun is in progress or fails.
- Trusted overview, precisely labelled attention spotlight, URL-backed queue
  filters/sort/pagination, and shareable selected route-week deep links.
- Route trend chart with a text alternative and a Cost Courtroom showing Charge,
  Evidence, deterministic validation gates, Operational Leads for unexplained
  anomalies, and Verdict. Operational Leads load lazily and remain separate from
  accepted evidence.
- Evaluation/run diagnostics and byte-preserving CSV download.
- Snapshot-ID guard that invalidates all snapshot query families once and refuses
  to combine resources if they still disagree.

The dashboard is intentionally read-only. Phase 13 assistant behavior,
authentication, uploads, and verdict overrides are not included.
