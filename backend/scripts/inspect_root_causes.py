"""Read and inspect one deterministic operational root-cause artifact entry."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from backend.app.core.config import PROJECT_ROOT
from backend.app.domain.root_cause import RootCauseAnalysis
from backend.app.services.root_cause import ROOT_CAUSE_FILENAME


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", required=True)
    parser.add_argument("--week-of", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=PROJECT_ROOT / "backend" / "data" / "output" / ROOT_CAUSE_FILENAME,
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        payload = json.loads(args.artifact.read_text(encoding="utf-8"))
        results = tuple(
            RootCauseAnalysis.model_validate(item)
            for item in payload.get("analyses", ())
        )
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Root-cause artifact is invalid: {exc}", file=sys.stderr)
        return 2
    match = next(
        (
            item
            for item in results
            if item.route == args.route and item.week_of == args.week_of
        ),
        None,
    )
    if match is None:
        print("No root-cause analysis matches that route and week.", file=sys.stderr)
        return 1
    if args.as_json:
        print(match.model_dump_json())
        return 0
    print(f"Candidate: {match.candidate_key} ({match.canonical_verdict})")
    print(
        "Cost: "
        f"current {match.current_cost_per_tonne_km:.6f}; "
        f"baseline {match.own_history_baseline:.6f}; gap {match.target_gap:+.6f}"
    )
    print("Reference weeks: " + ", ".join(map(str, match.reference_weeks)))
    print(f"Support: {match.support_level.value}")
    for lens in (match.transporter, match.material):
        print(
            f"{lens.lens.title()}: {lens.reconstructed_gap:+.6f} "
            f"(error {lens.reconstruction_error:+.3e})"
        )
        for lead in (*lens.leads, *lens.offsets):
            print(f"  {lead.category}: {lead.effect:+.6f} [{lead.support_level.value}]")
    print("Operational metrics:")
    for metric in match.operational_metrics:
        print(
            f"  {metric.metric.value}: {metric.current_value:.4f} vs "
            f"{metric.reference_mean:.4f} ({metric.absolute_change:+.4f} {metric.unit})"
        )
    for caveat in match.caveats:
        print(f"Caveat: {caveat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
