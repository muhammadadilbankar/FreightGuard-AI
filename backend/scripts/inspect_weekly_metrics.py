"""Read-only inspection command for canonical weekly route metrics."""

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.services.analytics import (
    AnalyticsError,
    calculate_weekly_route_metrics,
    summarize_weekly_metrics,
)
from backend.app.services.ingestion import IngestionError, load_input_bundle


def main(settings: Settings | None = None) -> int:
    """Run ingestion and weekly analytics, printing a concise audit summary."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    print("FreightGuard weekly analytics")
    try:
        bundle = load_input_bundle(active_settings)
        weekly = calculate_weekly_route_metrics(bundle.shipments)
        summary = summarize_weekly_metrics(bundle.shipments, weekly)
    except IngestionError as exc:
        print(f"Result: FAIL (input validation): {exc}")
        return 2
    except AnalyticsError as exc:
        print(f"Result: FAIL (analytics): {exc}")
        return 1

    print(f"Validated shipments: {summary.validated_shipments}")
    print(f"Weekly route groups: {summary.weekly_route_groups}")
    print(f"Directional routes: {summary.directional_routes}")
    print(f"Route types: {summary.route_types}")
    print(f"Distinct weeks: {summary.distinct_weeks}")
    print(
        "week_of range: "
        f"{summary.earliest_week_of.isoformat()} to "
        f"{summary.latest_week_of.isoformat()}"
    )
    print(f"Reconciliation: {summary.reconciliation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
