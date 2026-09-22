"""Tests for compiler input boundaries, typed models, and invariants."""

from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from backend.app.domain.context_notes import (
    COMPILED_NOTE_FIELDS,
    CompiledContextNote,
    ContextNoteInput,
    CostImpactStatus,
    EventType,
    ImpactDirection,
    ScopeStatus,
    ScopeType,
    TemporalBasis,
)
from backend.app.services.context import ContextInputError, compile_context_notes
from backend.app.services.ingestion.contracts import CONTEXT_NOTE_COLUMNS

ROUTES = ("A-B", "B-A")


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "note_id": "N002",
                "date": pd.Timestamp("2025-01-20"),
                "applies_to": "A-B",
                "note": "Festival week caused a surcharge applied by transporters.",
            },
            {
                "note_id": "N001",
                "date": pd.Timestamp("2025-01-13"),
                "applies_to": "All Routes",
                "note": "Operations were reviewed locally.",
            },
        ]
    ).loc[:, CONTEXT_NOTE_COLUMNS]


def _valid_model_data() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "note_id": "N001",
        "source_date": date(2025, 1, 1),
        "source_applies_to": "A-B",
        "original_text": "Transport costs rose.",
        "scope_type": ScopeType.ROUTE,
        "applies_to_routes": ("A-B",),
        "scope_status": ScopeStatus.IN_DATASET,
        "effective_from": date(2025, 1, 1),
        "effective_to": date(2025, 1, 2),
        "temporal_basis": TemporalBasis.EXPLICIT_RANGE,
        "event_type": EventType.OTHER,
        "impact_direction": ImpactDirection.INCREASE,
        "cost_impact_status": CostImpactStatus.EXPLICIT_INCREASE,
        "affects_transport_cost": True,
        "negates_cost_increase": False,
        "magnitude_text": None,
        "compilation_warnings": (),
    }


def test_compile_preserves_inputs_and_sorts_deterministically() -> None:
    frame = _frame()
    original = frame.copy(deep=True)
    routes = list(ROUTES)

    first = compile_context_notes(frame, routes)
    repeated = compile_context_notes(frame, routes)
    shuffled = compile_context_notes(frame.sample(frac=1, random_state=7), routes)

    assert first == repeated == shuffled
    assert [note.note_id for note in first] == ["N001", "N002"]
    assert first[0].original_text == "Operations were reviewed locally."
    assert tuple(CompiledContextNote.model_fields) == COMPILED_NOTE_FIELDS
    pd.testing.assert_frame_equal(frame, original)
    assert routes == list(ROUTES)


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (lambda frame: frame.iloc[0:0], "must not be empty"),
        (lambda frame: frame.drop(columns="note"), "canonical Phase 2 order"),
        (lambda frame: frame.assign(note_id="N001"), "must be unique"),
        (lambda frame: frame.assign(note=" "), "non-blank"),
        (lambda frame: frame.assign(date="2025-01-01"), "valid date values"),
    ],
)
def test_invalid_note_frame_fails(transform: object, message: str) -> None:
    with pytest.raises(ContextInputError, match=message):
        compile_context_notes(transform(_frame()), ROUTES)


@pytest.mark.parametrize(
    "routes", [(), ("",), (" A-B",), ("A-B", "A-B"), "A-B"]
)
def test_invalid_route_universe_fails(routes: object) -> None:
    with pytest.raises(ContextInputError, match="known_routes"):
        compile_context_notes(_frame(), routes)


def test_models_are_immutable_and_enums_reject_arbitrary_values() -> None:
    note = ContextNoteInput(
        note_id="N1", date=date(2025, 1, 1), applies_to="A-B", note="Text"
    )
    with pytest.raises(ValidationError):
        note.note_id = "changed"
    with pytest.raises(ValidationError):
        CompiledContextNote(**(_valid_model_data() | {"scope_type": "invalid"}))


@pytest.mark.parametrize(
    "changes",
    [
        {"effective_to": date(2024, 12, 31)},
        {"scope_type": ScopeType.GLOBAL, "applies_to_routes": ("A-B",)},
        {"scope_type": ScopeType.ROUTE, "applies_to_routes": ()},
        {"affects_transport_cost": False},
        {
            "cost_impact_status": CostImpactStatus.NOT_STATED,
            "impact_direction": ImpactDirection.INCREASE,
            "affects_transport_cost": None,
        },
        {"compilation_warnings": ("z", "a", "a")},
    ],
)
def test_cross_field_invariant_failures(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CompiledContextNote(**(_valid_model_data() | changes))
