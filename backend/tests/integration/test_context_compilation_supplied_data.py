"""Supplied-data regression and Phase 5 isolation tests for Phase 6."""

from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.domain.context_notes import (
    CostImpactStatus,
    EventType,
    ImpactDirection,
    ScopeStatus,
    ScopeType,
    TemporalBasis,
)
from backend.app.services.analytics import (
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from backend.app.services.context import (
    compile_context_notes,
    compiled_notes_sha256,
    validate_compiled_notes_jsonl,
    write_compiled_notes_jsonl,
)
from backend.app.services.ingestion import load_input_bundle
from backend.app.services.reporting import (
    build_candidate_output,
    write_candidate_csv,
)

EXPECTED = {
    "N001": (ScopeType.ROUTE, ("Chennai-Bangalore",), ScopeStatus.IN_DATASET, date(2025, 2, 24), date(2025, 3, 8), TemporalBasis.EXPLICIT_RANGE, EventType.WEATHER_DISRUPTION, CostImpactStatus.EXPLICIT_INCREASE, ImpactDirection.INCREASE, False, None, ()),
    "N002": (ScopeType.ROUTE, ("Ahmedabad-Mumbai",), ScopeStatus.IN_DATASET, date(2025, 1, 20), date(2025, 1, 26), TemporalBasis.CALENDAR_WEEK, EventType.FESTIVAL_DEMAND, CostImpactStatus.EXPLICIT_INCREASE, ImpactDirection.INCREASE, False, None, ()),
    "N003": (ScopeType.GLOBAL, (), ScopeStatus.IN_DATASET, date(2025, 5, 5), None, TemporalBasis.OPEN_ENDED_START, EventType.FUEL_PRICE_CHANGE, CostImpactStatus.EXPLICIT_INCREASE, ImpactDirection.INCREASE, False, "roughly 5-7%", ()),
    "N004": (ScopeType.GLOBAL, (), ScopeStatus.OUTSIDE_DATASET, date(2024, 3, 11), None, TemporalBasis.OPEN_ENDED_START, EventType.TOLL_OR_INFRASTRUCTURE, CostImpactStatus.NOT_STATED, ImpactDirection.UNKNOWN, False, None, ("text_excludes_dataset_scope", "transport_cost_impact_not_stated")),
    "N005": (ScopeType.ROUTE, ("Mumbai-Delhi",), ScopeStatus.IN_DATASET, date(2024, 7, 29), date(2024, 8, 4), TemporalBasis.APPROXIMATE_WEEK, EventType.ROAD_MAINTENANCE, CostImpactStatus.EXPLICIT_NO_MATERIAL_IMPACT, ImpactDirection.NO_CHANGE, True, None, ()),
    "N006": (ScopeType.GLOBAL, (), ScopeStatus.IN_DATASET, date(2025, 7, 1), date(2025, 9, 30), TemporalBasis.CALENDAR_QUARTER, EventType.CAPACITY_OR_DEMAND_CONDITION, CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS, ImpactDirection.NO_CHANGE, True, None, ()),
    "N007": (ScopeType.ROUTE, ("Delhi-Jaipur",), ScopeStatus.IN_DATASET, date(2024, 5, 20), None, TemporalBasis.STATE_AFTER_COMPLETION, EventType.ROAD_IMPROVEMENT, CostImpactStatus.NOT_STATED, ImpactDirection.UNKNOWN, False, None, ("transport_cost_impact_not_stated",)),
    "N008": (ScopeType.ROUTE, ("Kolkata-Bhubaneswar",), ScopeStatus.IN_DATASET, date(2025, 4, 1), date(2025, 6, 30), TemporalBasis.CALENDAR_QUARTER, EventType.NORMAL_OPERATIONS, CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS, ImpactDirection.NO_CHANGE, True, None, ()),
    "N009": (ScopeType.ROUTE, ("Chennai-Bangalore",), ScopeStatus.IN_DATASET, date(2025, 3, 17), None, TemporalBasis.STATE_AFTER_COMPLETION, EventType.RECOVERY_OR_NORMALIZATION, CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS, ImpactDirection.NO_CHANGE, True, None, ()),
    "N010": (ScopeType.GLOBAL, (), ScopeStatus.IN_DATASET, date(2025, 10, 27), None, TemporalBasis.OPEN_ENDED_START, EventType.REGULATORY_COMPLIANCE, CostImpactStatus.EXPLICIT_NO_RATE_CHANGE, ImpactDirection.NO_CHANGE, True, None, ()),
}


@pytest.fixture(scope="module")
def supplied_compilation() -> tuple[object, frozenset[str], tuple[object, ...]]:
    bundle = load_input_bundle(Settings(_env_file=None))
    routes = frozenset(bundle.shipments["route"].unique())
    compiled = compile_context_notes(bundle.context_notes, routes)
    return bundle, routes, compiled


def test_supplied_notes_match_every_regression_field(
    supplied_compilation: tuple[object, frozenset[str], tuple[object, ...]],
) -> None:
    bundle, routes, compiled = supplied_compilation
    source = bundle.context_notes.set_index("note_id")

    assert len(routes) == 7
    assert len(compiled) == len(EXPECTED) == 10
    assert [note.note_id for note in compiled] == sorted(EXPECTED)
    for note in compiled:
        (
            scope_type,
            applies_to_routes,
            scope_status,
            effective_from,
            effective_to,
            temporal_basis,
            event_type,
            impact_status,
            direction,
            negates,
            magnitude,
            warnings,
        ) = EXPECTED[note.note_id]
        assert note.schema_version == "1.0"
        assert note.source_date == source.loc[note.note_id, "date"].date()
        assert note.source_applies_to == source.loc[note.note_id, "applies_to"]
        assert note.original_text == source.loc[note.note_id, "note"]
        assert note.scope_type == scope_type
        assert note.applies_to_routes == applies_to_routes
        assert note.scope_status == scope_status
        assert note.effective_from == effective_from
        assert note.effective_to == effective_to
        assert note.temporal_basis == temporal_basis
        assert note.event_type == event_type
        assert note.cost_impact_status == impact_status
        assert note.impact_direction == direction
        assert note.negates_cost_increase is negates
        assert note.magnitude_text == magnitude
        assert note.compilation_warnings == warnings
        expected_affects = (
            True
            if impact_status in {
                CostImpactStatus.EXPLICIT_INCREASE,
                CostImpactStatus.EXPLICIT_DECREASE,
            }
            else False
            if direction == ImpactDirection.NO_CHANGE
            else None
        )
        assert note.affects_transport_cost is expected_affects


def test_supplied_summary_counts(
    supplied_compilation: tuple[object, frozenset[str], tuple[object, ...]],
) -> None:
    _, _, compiled = supplied_compilation
    scopes = Counter(note.scope_type for note in compiled)
    impacts = Counter(note.cost_impact_status for note in compiled)

    assert scopes == {ScopeType.ROUTE: 6, ScopeType.GLOBAL: 4}
    assert impacts == {
        CostImpactStatus.EXPLICIT_INCREASE: 3,
        CostImpactStatus.EXPLICIT_NO_MATERIAL_IMPACT: 1,
        CostImpactStatus.EXPLICIT_NO_RATE_CHANGE: 1,
        CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS: 3,
        CostImpactStatus.NOT_STATED: 2,
    }
    assert sum(note.effective_to is not None for note in compiled) == 5
    assert sum(note.effective_to is None for note in compiled) == 5
    assert sum(note.scope_status == ScopeStatus.OUTSIDE_DATASET for note in compiled) == 1
    assert [note.note_id for note in compiled if note.magnitude_text] == ["N003"]


def test_jsonl_round_trip_and_phase_five_bytes_are_isolated(
    supplied_compilation: tuple[object, frozenset[str], tuple[object, ...]],
    tmp_path: Path,
) -> None:
    bundle, _, compiled = supplied_compilation
    weekly = calculate_weekly_route_metrics(bundle.shipments)
    baselines = add_comparison_baselines(weekly)
    comparisons = add_percentage_comparisons(baselines)
    detected = detect_candidate_anomalies(comparisons, 20.0)
    candidate_output = build_candidate_output(detected, bundle.output_columns)
    candidate_path = write_candidate_csv(candidate_output, tmp_path / "candidates.csv")
    candidate_bytes = candidate_path.read_bytes()

    context_path = write_compiled_notes_jsonl(compiled, tmp_path / "notes.jsonl")
    round_trip = validate_compiled_notes_jsonl(context_path, compiled)

    assert round_trip == compiled
    assert len(compiled_notes_sha256(context_path)) == 64
    assert candidate_path.read_bytes() == candidate_bytes
    assert len(candidate_output) == 19
