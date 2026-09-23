# Token and cost report

This report covers one complete run over all 2,940 supplied shipment records. It is
derived from the explanation-generation audit by:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.report_run_usage
```

| Field | Observed value |
|---|---|
| Run identifier | `7b6bf86d92062362` |
| Run mode | `template` |
| Provider identity | Template; no hosted provider |
| Model identity | Not applicable |
| Pricing snapshot date | Not available; no pricing was required/configured |
| Eligible explanation requests | 15 |
| Provider calls | 0 |
| Input / cached input / output tokens | 0 / 0 / 0 |
| Failed or refused calls | 0 |
| Cache hits / misses | 0 / 0 |
| Fallback count | 0 |
| Estimated input/output cost | Not available |
| Estimated total hosted cost | Not applicable because no hosted calls occurred |
| Currency | USD |

All 19 final reasons were generated directly by deterministic templates. This is
not a claim that compute is free; it means there was no provider-billed token usage.
The machine-readable report is
[`run_usage_report.json`](../backend/data/output/run_usage_report.json), and the
underlying audit hash is
`62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea`.

The assistant's formal 40-case template evaluation also made zero provider calls.
Optional live explanation and planner modes are not part of this cost result. A
future live report must identify its provider/model, configured price rates and
date, tokens, retries, cache behavior, and estimated cost separately.
