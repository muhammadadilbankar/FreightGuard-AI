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

RELATIVE_TOLERANCE = 1e-12
ABSOLUTE_TOLERANCE = 1e-12
