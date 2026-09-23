# Trade-offs and limitations

| Current limitation | Why acceptable here | Sensible production evolution |
|---|---|---|
| Pandas and one in-memory snapshot | Clear and sufficient for 2,940 rows | Partitioned storage, database-backed metadata, and queued jobs |
| Configurable 20% candidate threshold | Transparent challenge heuristic; the brief gives no threshold | Calibrate by segment with reviewed outcomes while retaining auditability |
| Only ten supplied context notes | Enforces the allowed evidence universe | Governed connectors with provenance, access control, and immutable source snapshots |
| Evidence Gate favors precision | False clearance is riskier than leaving a case open | Human feedback and labeled evaluation to tune recall without weakening gates |
| Template mode is less expressive | Fully offline, reproducible, and grounded | Optional constrained provider with replay cache and the same deterministic validation |
| Partial explanations do not clear candidates | Honest representation of insufficient scope | Reviewer workflow for adding or correcting source evidence |
| Operational decomposition is descriptive | Useful investigation clue without claiming causality | Add controlled external covariates and causal analysis only with appropriate data |
| Assistant has bounded intents | Prevents arbitrary tools and unsupported claims | Expand only through new typed tools, fixtures, and policy checks |
| Local application has no authentication | Appropriate for a local evaluator demo | Identity, authorization, tenant isolation, rate limits, and security review |
| No external fuel, weather, traffic, or toll data | Such data was not supplied | Versioned, licensed connectors whose records pass provenance and scope checks |
| No forecasting | The product investigates observed anomalies | Separate forecasting service with time-split evaluation and uncertainty reporting |
| No distributed processing | Unnecessary at challenge scale | Idempotent tasks, durable queues, and horizontal workers |
| First-time model preparation needs internet | Runtime can be local after preparation | Approved offline artifact registry and integrity-verified deployment bundle |
| Optional provider behavior and pricing vary | Default evaluation avoids that uncertainty | Pin model/prompt, retain validated replay data, and record dated pricing evidence |

The system identifies unusual costs and evaluates supplied context. It does not
determine fraud, prove operational causation, or claim full production readiness.
