# FreightGuard AI implementation plan

This is the repository-facing summary of the canonical
`FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md`. That roadmap and the applicable
phase plan remain authoritative for detailed completion gates.

1. **Repository foundation:** FastAPI bootstrap, typed settings, logging, tests,
   directories, and documentation.
2. **Data ingestion and validation:** Strict loaders and normalized route, week,
   and tonne-kilometre fields.
3. **Weekly cost analytics:** Weighted route-week aggregation with full precision.
4. **Baseline engine:** Prior-eight-available-week history and same-week peer
   baselines with audit fields.
5. **Candidate detection and CSV (complete):** Full-precision comparisons,
   configurable deterministic rule, and validated preliminary eight-column output.
6. **Context-note compiler (complete):** Deterministic typed claims, inclusive
   effective intervals, preserved source text, and validated versioned JSONL.
7. **Hybrid retrieval and Evidence Gate:** Semantic candidates followed by strict
   route, date, direction, impact, and scope validation.
8. **Grounded explanation generation:** Provider-independent constrained wording,
   schema checks, fallback templates, and usage logging.
9. **Evaluation and reproducibility:** Adversarial cases, regressions, three-run
   byte identity, recorded hashes, and a readable report.
10. **FastAPI service layer:** Thin typed endpoints around stable services.
11. **React investigation dashboard:** Overview, queue, trends, evidence drawer,
    validation checklist, export, and metrics.
12. **Operational root-cause analysis:** Investigative mix and pricing clues that
    never alter the canonical evidence verdict.
13. **Natural-language assistant:** Grounded questions over stored results that
    cannot override results.
14. **Packaging and demo hardening:** Final docs, diagrams, reports, optional
    containers, walkthrough, and backup assets.

For every phase: inspect first, implement only that phase, add focused tests, run
bounded verification and linting, update its checklist, report manual commands and
limitations, suggest one commit message, and stop before the next phase.
