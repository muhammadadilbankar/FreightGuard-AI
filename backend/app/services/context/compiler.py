"""Top-level deterministic context-note compilation and invariants."""

from collections.abc import Collection
from datetime import date, datetime
import logging

import pandas as pd
from pydantic import ValidationError

from ...core.logging import LOGGER_NAME
from ...domain.context_notes import (
    CompiledContextNote,
    ContextNoteInput,
    ScopeStatus,
    ScopeType,
)
from ..ingestion.contracts import CONTEXT_NOTE_COLUMNS
from .errors import (
    CompiledNoteContractError,
    ContextInputError,
)
from .impact import compile_impact_claim
from .scope import compile_route_scope
from .temporal import resolve_effective_interval

logger = logging.getLogger(f"{LOGGER_NAME}.context_compiler")


def compile_context_note(
    note: ContextNoteInput, known_routes: frozenset[str]
) -> CompiledContextNote:
    """Compile one canonical note into a traceable typed claim."""
    scope = compile_route_scope(note.applies_to, note.note, known_routes)
    interval = resolve_effective_interval(note.date, note.note)
    impact = compile_impact_claim(note.note)
    warnings = tuple(
        sorted(set(scope.warnings + interval.warnings + impact.warnings))
    )
    try:
        compiled = CompiledContextNote(
            note_id=note.note_id,
            source_date=note.date,
            source_applies_to=note.applies_to,
            original_text=note.note,
            scope_type=scope.scope_type,
            applies_to_routes=scope.applies_to_routes,
            scope_status=scope.scope_status,
            effective_from=interval.effective_from,
            effective_to=interval.effective_to,
            temporal_basis=interval.temporal_basis,
            event_type=impact.event_type,
            impact_direction=impact.impact_direction,
            cost_impact_status=impact.cost_impact_status,
            affects_transport_cost=impact.affects_transport_cost,
            negates_cost_increase=impact.negates_cost_increase,
            magnitude_text=impact.magnitude_text,
            compilation_warnings=warnings,
        )
    except ValidationError as exc:
        raise CompiledNoteContractError(
            f"Compiled note {note.note_id} violates the domain contract."
        ) from exc
    if (
        compiled.scope_type == ScopeType.ROUTE
        and compiled.scope_status == ScopeStatus.IN_DATASET
        and not set(compiled.applies_to_routes).issubset(known_routes)
    ):
        raise CompiledNoteContractError(
            f"Compiled note {note.note_id} marks an unknown route in-dataset."
        )
    return compiled


def compile_context_notes(
    context_notes: pd.DataFrame,
    known_routes: Collection[str],
) -> tuple[CompiledContextNote, ...]:
    """Compile canonical Phase 2 notes, sorted deterministically by note ID."""
    working = _validated_context_frame_copy(context_notes)
    frozen_routes = _validated_route_universe(known_routes)
    compiled: list[CompiledContextNote] = []
    for row in working.itertuples(index=False):
        try:
            note = ContextNoteInput(
                note_id=row.note_id,
                date=row.date.date() if isinstance(row.date, datetime) else row.date,
                applies_to=row.applies_to,
                note=row.note,
            )
        except ValidationError as exc:
            raise ContextInputError("Context-note row has invalid typed values.") from exc
        compiled.append(compile_context_note(note, frozen_routes))

    result = tuple(sorted(compiled, key=lambda item: item.note_id))
    if len({note.note_id for note in result}) != len(result):
        raise CompiledNoteContractError("Compiled note IDs must remain unique.")
    if len(result) != len(working):
        raise CompiledNoteContractError(
            "Compilation must return exactly one model per source note."
        )
    logger.info(
        "Compiled context notes loaded=%d compiled=%d global=%d route=%d warnings=%d",
        len(working),
        len(result),
        sum(note.scope_type == ScopeType.GLOBAL for note in result),
        sum(note.scope_type == ScopeType.ROUTE for note in result),
        sum(len(note.compilation_warnings) for note in result),
    )
    return result


def _validated_context_frame_copy(context_notes: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(context_notes, pd.DataFrame):
        raise ContextInputError("Context-note input must be a Pandas DataFrame.")
    duplicates = sorted(
        {
            column
            for column in CONTEXT_NOTE_COLUMNS
            if list(context_notes.columns).count(column) > 1
        }
    )
    if duplicates:
        raise ContextInputError(
            "Context-note input contains duplicate columns: "
            + ", ".join(duplicates)
            + "."
        )
    if tuple(context_notes.columns) != CONTEXT_NOTE_COLUMNS:
        raise ContextInputError(
            "Context-note columns must match the canonical Phase 2 order exactly."
        )
    if context_notes.empty:
        raise ContextInputError("Context-note input must not be empty.")
    working = context_notes.loc[:, CONTEXT_NOTE_COLUMNS].copy(deep=True)
    for column in ("note_id", "applies_to", "note"):
        if working[column].isna().any() or not working[column].map(
            lambda value: isinstance(value, str) and bool(value.strip())
        ).all():
            raise ContextInputError(f"{column} must contain non-blank strings.")
    if working["note_id"].duplicated().any():
        raise ContextInputError("note_id values must be unique.")
    if working["note_id"].map(lambda value: value != value.strip()).any():
        raise ContextInputError("note_id values must already be normalized.")
    if working["applies_to"].map(lambda value: value != value.strip()).any():
        raise ContextInputError("applies_to values must already be normalized.")
    working["date"] = working["date"].map(_validated_source_date)
    return working


def _validated_source_date(value: object) -> date:
    if isinstance(value, pd.Timestamp):
        if value.tz is not None or value != value.normalize():
            raise ContextInputError(
                "Context-note dates must be timezone-naive normalized dates."
            )
        return value.date()
    if isinstance(value, datetime):
        if value.tzinfo is not None or value.time() != datetime.min.time():
            raise ContextInputError(
                "Context-note dates must be timezone-naive normalized dates."
            )
        return value.date()
    if isinstance(value, date):
        return value
    raise ContextInputError("Context-note dates must be valid date values.")


def _validated_route_universe(known_routes: Collection[str]) -> frozenset[str]:
    if isinstance(known_routes, (str, bytes)):
        raise ContextInputError("known_routes must be a collection of routes.")
    routes = tuple(known_routes)
    if not routes:
        raise ContextInputError("known_routes must not be empty.")
    if any(not isinstance(route, str) or not route.strip() for route in routes):
        raise ContextInputError("known_routes must contain non-blank strings.")
    if any(route != route.strip() for route in routes):
        raise ContextInputError("known_routes must already be normalized.")
    if len(set(routes)) != len(routes):
        raise ContextInputError("known_routes must contain unique routes.")
    return frozenset(routes)
