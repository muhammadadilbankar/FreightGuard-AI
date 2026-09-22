"""Generate and validate the deterministic preliminary candidate CSV."""

from pathlib import Path

from backend.app.core.config import PROJECT_ROOT, Settings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.services.analytics import (
    AnalyticsError,
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from backend.app.services.ingestion import IngestionError, load_input_bundle
from backend.app.services.reporting import (
    CANDIDATE_OUTPUT_FILENAME,
    ReportingError,
    build_candidate_output,
    candidate_csv_sha256,
    validate_candidate_csv,
    write_candidate_csv,
)


def main(settings: Settings | None = None) -> int:
    """Run Phases 2 through 5 once and persist the preliminary output."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    print("FreightGuard candidate detection")
    try:
        bundle = load_input_bundle(active_settings)
        weekly = calculate_weekly_route_metrics(bundle.shipments)
        baselines = add_comparison_baselines(weekly)
        comparisons = add_percentage_comparisons(baselines)
        detected = detect_candidate_anomalies(
            comparisons, active_settings.anomaly_threshold_percent
        )
        output = build_candidate_output(detected, bundle.output_columns)
        destination = active_settings.output_data_dir / CANDIDATE_OUTPUT_FILENAME
        write_candidate_csv(output, destination)
        validate_candidate_csv(destination, expected_rows=len(output))
        digest = candidate_csv_sha256(destination)
    except IngestionError as exc:
        print(f"Result: FAIL (input validation): {exc}")
        return 2
    except AnalyticsError as exc:
        print(f"Result: FAIL (analytics): {exc}")
        return 1
    except ReportingError as exc:
        print(f"Result: FAIL (reporting): {exc}")
        return 1

    candidates = detected.loc[detected["candidate_anomaly"]]
    own_triggered = int(candidates["own_threshold_breached"].sum())
    peer_triggered = int(candidates["peer_threshold_breached"].sum())
    both_triggered = int(
        (
            candidates["own_threshold_breached"]
            & candidates["peer_threshold_breached"]
        ).sum()
    )
    try:
        display_path = destination.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = Path(destination)
    print(f"Weekly route groups evaluated: {len(detected)}")
    print(f"Threshold: {active_settings.anomaly_threshold_percent}%")
    print(f"Candidates detected: {len(candidates)}")
    print(f"Triggered by own history: {own_triggered}")
    print(f"Triggered by peers: {peer_triggered}")
    print(f"Triggered by both: {both_triggered}")
    print(f"Output rows: {len(output)}")
    print("Output contract: PASS")
    print(f"Output: {display_path.as_posix()}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
