"""Named input, output, grouping, and precision contracts for weekly analytics."""

ANALYTICS_REQUIRED_COLUMNS = (
    "shipment_id",
    "route",
    "route_type",
    "week_of",
    "quantity_tonnes",
    "distance_km",
    "freight_cost_inr",
    "tonne_km",
)

ANALYTICS_GROUP_COLUMNS = ("route", "route_type", "week_of")
ANALYTICS_NUMERIC_COLUMNS = (
    "quantity_tonnes",
    "distance_km",
    "freight_cost_inr",
    "tonne_km",
)

WEEKLY_METRIC_COLUMNS = (
    "route",
    "route_type",
    "week_of",
    "shipment_count",
    "total_freight_cost_inr",
    "total_quantity_tonnes",
    "total_tonne_km",
    "cost_per_tonne_km",
)

HISTORY_PARTITION_COLUMNS = ("route", "route_type")
PEER_GROUP_COLUMNS = ("route_type", "week_of")
HISTORY_WINDOW_SIZE = 8

BASELINE_COLUMNS = (
    "own_history_avg_cost_per_tonne_km",
    "history_weeks_used",
    "similar_routes_avg_cost_per_tonne_km",
    "peer_routes_used",
)

BASELINE_METRIC_COLUMNS = WEEKLY_METRIC_COLUMNS + BASELINE_COLUMNS

COMPARISON_COLUMNS = (
    "vs_own_history_pct",
    "vs_similar_routes_pct",
)

COMPARISON_METRIC_COLUMNS = BASELINE_METRIC_COLUMNS + COMPARISON_COLUMNS

CANDIDATE_RULE_COLUMNS = (
    "is_rising",
    "own_threshold_breached",
    "peer_threshold_breached",
    "candidate_anomaly",
)

CANDIDATE_METRIC_COLUMNS = COMPARISON_METRIC_COLUMNS + CANDIDATE_RULE_COLUMNS

RELATIVE_TOLERANCE = 1e-12
ABSOLUTE_TOLERANCE = 1e-12
