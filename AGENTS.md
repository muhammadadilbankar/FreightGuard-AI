# FreightGuard AI contributor guardrails

- Read `docs/PROJECT_SPEC.md` and the evaluator-facing technical documentation
  before changing business logic.
- Inspect existing code and tests before changing it.
- Do not hardcode sample anomalies, routes, dates, or note IDs.
- Keep deterministic mathematics and decisions separate from AI-assisted wording.
- An LLM must never decide canonical numbers, matched note IDs, or final verdicts.
- Add focused tests for every behavior change and run them before handing work back.
- Run long-lived tools with sensible timeouts or in non-interactive batch mode.
- For servers, use bounded background execution and verify logs or health checks.
- Report changed files, test results, manual verification steps, and limitations.
- Never commit secrets or a real `.env` file.
- Preserve unrelated user changes.

The canonical mathematical and evidence contracts are in
`docs/PROJECT_SPEC.md`.
