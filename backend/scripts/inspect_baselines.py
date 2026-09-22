"""Read-only inspection command for history and peer baseline metrics."""

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.services.analytics import (
    AnalyticsError,
    add_comparison_baselines,
    calculate_weekly_route_metrics,
    summarize_baselines,
)
from backend.app.services.ingestion import IngestionError, load_input_bundle


def main(settings: Settings | None = None) -> int:
    """Run Phases 2 through 4 and print a concise baseline audit summary."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    print("FreightGuard baseline engine")
    try:
        bundle = load_input_bundle(active_settings)
        weekly = calculate_weekly_route_metrics(bundle.shipments)
        enriched = add_comparison_baselines(weekly)
        summary = summarize_baselines(enriched)
    except IngestionError as exc:
        print(f"Result: FAIL (input validation): {exc}")
        return 2
    except AnalyticsError as exc:
        print(f"Result: FAIL (analytics): {exc}")
        return 1

    print(f"Weekly route groups: {summary.weekly_route_groups}")
    print(f"Own-history baselines available: {summary.own_history_available}")
    print(f"Own-history baselines unavailable: {summary.own_history_unavailable}")
    print(f"Rows using full 8-week history: {summary.full_history_rows}")
    print(f"Peer baselines available: {summary.peer_baselines_available}")
    print(f"Peer baselines unavailable: {summary.peer_baselines_unavailable}")
    print(
        "Peer routes used: "
        f"min {summary.minimum_peers_used}, max {summary.maximum_peers_used}"
    )
    print(f"No-look-ahead checks: {summary.no_look_ahead_checks}")
    print(f"Self-exclusion checks: {summary.self_exclusion_checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
