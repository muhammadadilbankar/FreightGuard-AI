"""Independent weekly and baseline mathematical regression checks."""

from __future__ import annotations

import math

import pandas as pd

from ..domain.evaluation import EvaluationCheck, EvaluationDomain, NumericTolerance
from .contracts import check

WEEKLY_GOLDEN = (
    (
        "Mumbai-Pune",
        "2024-01-01",
        5,
        34849,
        70.7,
        10556.220000000001,
        3.3012764038642617,
    ),
    ("Delhi-Jaipur", "2024-11-11", 4, 84388, 72.0, 20222.59, 4.1729570742422215),
    ("Ahmedabad-Mumbai", "2025-01-20", 5, 134631, 76.7, 40916.71, 3.290367187391166),
    (
        "Chennai-Bangalore",
        "2025-02-24",
        5,
        120133,
        95.5,
        33530.229999999996,
        3.5828266015473207,
    ),
    ("Mumbai-Pune", "2025-09-15", 4, 34203, 57.5, 8591.97, 3.9808099888616932),
)

BASELINE_GOLDEN = (
    ("Mumbai-Pune", "2024-01-01", None, 0, 3.000124589086287, 1),
    ("Mumbai-Pune", "2024-01-08", 3.3012764038642617, 1, 3.053238844499479, 1),
    ("Mumbai-Pune", "2024-02-26", 3.3380877267885767, 8, 3.0959226120172616, 1),
    ("Delhi-Jaipur", "2024-11-11", 3.079216557951722, 8, 3.447745798728505, 1),
    ("Ahmedabad-Mumbai", "2025-01-20", 2.541351823620185, 8, 2.6861515905915425, 2),
    ("Chennai-Bangalore", "2025-02-24", 2.7253267565207007, 8, 2.5837434925863763, 2),
    ("Mumbai-Pune", "2025-09-15", 3.643772458181048, 8, 3.220063126502312, 1),
)


def evaluate_mathematics(
    shipments: pd.DataFrame,
    weekly: pd.DataFrame,
    baselines: pd.DataFrame,
    *,
    rel_tolerance: float = 1e-12,
    abs_tolerance: float = 1e-12,
) -> list[EvaluationCheck]:
    tol = NumericTolerance(relative=rel_tolerance, absolute=abs_tolerance)
    checks: list[EvaluationCheck] = []
    independent = (
        shipments.assign(_freight=shipments["freight_cost_inr"].astype(float))
        .groupby(["route", "route_type", "week_of"], sort=True, observed=True)
        .agg(
            shipment_count=("shipment_id", "size"),
            total_freight_cost_inr=("_freight", "sum"),
            total_quantity_tonnes=("quantity_tonnes", "sum"),
            total_tonne_km=("tonne_km", "sum"),
        )
        .reset_index()
    )
    independent["cost_per_tonne_km"] = (
        independent["total_freight_cost_inr"] / independent["total_tonne_km"]
    )
    domain = EvaluationDomain.WEEKLY_ANALYTICS
    observations = {
        "groups": len(independent),
        "routes": independent["route"].nunique(),
        "route_types": independent["route_type"].nunique(),
        "weeks": independent["week_of"].nunique(),
        "earliest": independent["week_of"].min().date().isoformat(),
        "latest": independent["week_of"].max().date().isoformat(),
        "shipments": int(independent["shipment_count"].sum()),
    }
    expected = {
        "groups": 728,
        "routes": 7,
        "route_types": 3,
        "weeks": 104,
        "earliest": "2024-01-01",
        "latest": "2025-12-22",
        "shipments": 2940,
    }
    for name, value in expected.items():
        checks.append(
            check(
                f"weekly.{name}",
                domain,
                f"Weekly {name} regression",
                observations[name] == value,
                expected=value,
                actual=observations[name],
            )
        )
    checks.append(
        check(
            "weekly.shipment_count_range",
            domain,
            "Group shipment counts range from 3 through 5",
            (
                int(independent.shipment_count.min()),
                int(independent.shipment_count.max()),
            )
            == (3, 5),
            expected=[3, 5],
            actual=[
                int(independent.shipment_count.min()),
                int(independent.shipment_count.max()),
            ],
        )
    )
    for column in ("total_freight_cost_inr", "total_quantity_tonnes", "total_tonne_km"):
        left = float(independent[column].sum())
        right = float(weekly[column].sum())
        checks.append(
            _numeric_check(
                f"weekly.reconcile.{column}",
                domain,
                f"Independent {column} reconciliation",
                left,
                right,
                tol,
            )
        )
    formula_ok = all(
        math.isclose(
            row.cost_per_tonne_km,
            row.total_freight_cost_inr / row.total_tonne_km,
            rel_tol=rel_tolerance,
            abs_tol=abs_tolerance,
        )
        for row in weekly.itertuples()
    )
    checks.append(
        check(
            "weekly.formula",
            domain,
            "Every weekly rate equals aggregate freight divided by aggregate tonne-km",
            formula_ok,
        )
    )
    for route, week, count, freight, quantity, tonne_km, rate in WEEKLY_GOLDEN:
        row = weekly[
            (weekly.route == route) & (weekly.week_of == pd.Timestamp(week))
        ].iloc[0]
        values = (
            int(row.shipment_count) == count
            and float(row.total_freight_cost_inr) == freight
            and math.isclose(
                float(row.total_quantity_tonnes),
                quantity,
                rel_tol=rel_tolerance,
                abs_tol=abs_tolerance,
            )
            and math.isclose(
                float(row.total_tonne_km),
                tonne_km,
                rel_tol=rel_tolerance,
                abs_tol=abs_tolerance,
            )
            and math.isclose(
                float(row.cost_per_tonne_km),
                rate,
                rel_tol=rel_tolerance,
                abs_tol=abs_tolerance,
            )
        )
        item = check(
            f"weekly.golden.{route}.{week}",
            domain,
            "Weekly golden row",
            values,
            expected=rate,
            actual=float(row.cost_per_tonne_km),
        )
        checks.append(item.model_copy(update={"tolerance": tol}))

    bdomain = EvaluationDomain.BASELINE_CORRECTNESS
    history_counts = baselines.history_weeks_used.value_counts().to_dict()
    peer_counts = baselines.peer_routes_used.value_counts().to_dict()
    summary_ok = (
        len(baselines) == 728
        and int(baselines.own_history_avg_cost_per_tonne_km.isna().sum()) == 7
        and history_counts == {8: 672, 0: 7, 1: 7, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 7}
        and peer_counts == {1: 416, 2: 312}
    )
    checks.append(
        check(
            "baseline.summary",
            bdomain,
            "Baseline summary counts",
            summary_ok,
            expected="728 rows; history 7 missing; peer 416/312",
            actual={
                "rows": len(baselines),
                "history_missing": int(
                    baselines.own_history_avg_cost_per_tonne_km.isna().sum()
                ),
                "history_counts": history_counts,
                "peer_counts": peer_counts,
            },
        )
    )
    for route, week, own, history_count, peer, peer_count in BASELINE_GOLDEN:
        row = baselines[
            (baselines.route == route) & (baselines.week_of == pd.Timestamp(week))
        ].iloc[0]
        own_ok = (
            pd.isna(row.own_history_avg_cost_per_tonne_km)
            if own is None
            else math.isclose(
                float(row.own_history_avg_cost_per_tonne_km),
                own,
                rel_tol=rel_tolerance,
                abs_tol=abs_tolerance,
            )
        )
        passed = (
            own_ok
            and int(row.history_weeks_used) == history_count
            and math.isclose(
                float(row.similar_routes_avg_cost_per_tonne_km),
                peer,
                rel_tol=rel_tolerance,
                abs_tol=abs_tolerance,
            )
            and int(row.peer_routes_used) == peer_count
        )
        item = check(
            f"baseline.golden.{route}.{week}",
            bdomain,
            "Baseline golden row",
            passed,
            expected={"own": own, "peer": peer},
            actual={
                "own": None
                if pd.isna(row.own_history_avg_cost_per_tonne_km)
                else float(row.own_history_avg_cost_per_tonne_km),
                "peer": float(row.similar_routes_avg_cost_per_tonne_km),
            },
        )
        checks.append(item.model_copy(update={"tolerance": tol}))
    return checks


def _numeric_check(
    check_id: str,
    domain: EvaluationDomain,
    description: str,
    expected: float,
    actual: float,
    tolerance: NumericTolerance,
) -> EvaluationCheck:
    result = check(
        check_id,
        domain,
        description,
        math.isclose(
            actual, expected, rel_tol=tolerance.relative, abs_tol=tolerance.absolute
        ),
        expected=expected,
        actual=actual,
    )
    return result.model_copy(update={"tolerance": tolerance})
