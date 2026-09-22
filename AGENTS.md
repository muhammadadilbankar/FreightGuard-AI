# FreightGuard AI development instructions

- Read `docs/PROJECT_SPEC.md`, `docs/IMPLEMENTATION_PLAN.md`, and the applicable
  phase plan before editing.
- Work only on the requested phase and inspect existing code before changing it.
- Do not hardcode sample anomalies, routes, dates, or note IDs.
- Keep deterministic mathematics and decisions separate from AI-assisted wording.
- An LLM must never decide canonical numbers, matched note IDs, or final verdicts.
- Add focused tests for every phase and run them before handing work back.
- Run long-lived tools with sensible timeouts or in non-interactive batch mode.
- For servers, use bounded background execution and verify logs or health checks.
- Do not begin the next implementation phase automatically.
- Report changed files, test results, manual verification steps, limitations, and a
  suggested commit message.
- Never commit secrets or a real `.env` file.
- Preserve unrelated user changes.

The canonical mathematical and evidence contracts are in
`docs/PROJECT_SPEC.md`.
