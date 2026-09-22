"""Compile validated source notes into deterministic typed JSONL claims."""

from collections import Counter
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT, Settings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.domain.context_notes import CostImpactStatus, ScopeStatus, ScopeType
from backend.app.services.context import (
    COMPILED_NOTES_FILENAME,
    ContextCompilationError,
    compile_context_notes,
    compiled_notes_sha256,
    validate_compiled_notes_jsonl,
    write_compiled_notes_jsonl,
)
from backend.app.services.ingestion import IngestionError, load_input_bundle
from backend.app.services.reporting import ReportingError


def main(settings: Settings | None = None) -> int:
    """Load Phase 2 inputs once, compile all notes, and validate JSONL output."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    print("FreightGuard context-note compilation")
    try:
        bundle = load_input_bundle(active_settings)
        known_routes = frozenset(bundle.shipments["route"].unique())
        compiled = compile_context_notes(bundle.context_notes, known_routes)
        destination = active_settings.output_data_dir / COMPILED_NOTES_FILENAME
        write_compiled_notes_jsonl(compiled, destination)
        validate_compiled_notes_jsonl(destination, compiled)
        digest = compiled_notes_sha256(destination)
    except IngestionError as exc:
        print(f"Result: FAIL (input validation): {exc}")
        return 2
    except ContextCompilationError as exc:
        print(f"Result: FAIL (context compilation): {exc}")
        return 1
    except ReportingError as exc:
        print(f"Result: FAIL (reporting): {exc}")
        return 1

    scope_counts = Counter(note.scope_type for note in compiled)
    impact_counts = Counter(note.cost_impact_status for note in compiled)
    warning_counts = Counter(
        warning for note in compiled for warning in note.compilation_warnings
    )
    bounded = sum(note.effective_to is not None for note in compiled)
    excluded = sum(
        note.scope_status == ScopeStatus.OUTSIDE_DATASET for note in compiled
    )
    try:
        display_path = destination.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = Path(destination)
    print(f"Notes compiled: {len(compiled)}")
    print(f"Global scope: {scope_counts[ScopeType.GLOBAL]}")
    print(f"Route scope: {scope_counts[ScopeType.ROUTE]}")
    print(
        "Explicit cost increases: "
        f"{impact_counts[CostImpactStatus.EXPLICIT_INCREASE]}"
    )
    print(
        "Explicit no-impact/no-rate-change: "
        f"{impact_counts[CostImpactStatus.EXPLICIT_NO_MATERIAL_IMPACT] + impact_counts[CostImpactStatus.EXPLICIT_NO_RATE_CHANGE]}"
    )
    print(
        "Normal or stable operations: "
        f"{impact_counts[CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS]}"
    )
    print(f"Cost impact not stated: {impact_counts[CostImpactStatus.NOT_STATED]}")
    print(f"Dataset-scope exclusions: {excluded}")
    print(f"Bounded intervals: {bounded}")
    print(f"Open-ended intervals: {len(compiled) - bounded}")
    warning_summary = ", ".join(
        f"{code}={count}" for code, count in sorted(warning_counts.items())
    )
    print(f"Compilation warnings: {warning_summary or 'none'}")
    print("Output contract: PASS")
    print(f"Output: {display_path.as_posix()}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
