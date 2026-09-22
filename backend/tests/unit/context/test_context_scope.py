"""Tests for deterministic route-scope compilation."""

import pytest

from backend.app.domain.context_notes import ScopeStatus, ScopeType
from backend.app.services.context import ScopeCompilationError, compile_route_scope

ROUTES = frozenset({"Mumbai-Pune", "Pune-Mumbai", "Delhi-Jaipur"})


@pytest.mark.parametrize("value", ["All Routes", " all routes ", "ALL ROUTES"])
def test_global_scope_is_case_insensitive_and_has_no_route(value: str) -> None:
    result = compile_route_scope(value, "Nationwide condition.", ROUTES)

    assert result.scope_type == ScopeType.GLOBAL
    assert result.applies_to_routes == ()
    assert result.scope_status == ScopeStatus.IN_DATASET


def test_known_route_preserves_direction_and_input_set() -> None:
    original = frozenset(ROUTES)

    result = compile_route_scope("Mumbai-Pune", "Route condition.", ROUTES)

    assert result.scope_type == ScopeType.ROUTE
    assert result.applies_to_routes == ("Mumbai-Pune",)
    assert result.scope_status == ScopeStatus.IN_DATASET
    assert ROUTES == original


def test_reversed_and_unknown_routes_are_not_fuzzy_matched() -> None:
    reversed_result = compile_route_scope(
        "Pune-Mumbai", "Route condition.", frozenset({"Mumbai-Pune"})
    )
    unknown_result = compile_route_scope("Mumbai-Delhi", "Route condition.", ROUTES)

    assert reversed_result.scope_status == ScopeStatus.OUTSIDE_DATASET
    assert unknown_result.scope_status == ScopeStatus.OUTSIDE_DATASET
    assert reversed_result.warnings == ("explicit_route_not_in_dataset",)


def test_text_exclusion_overrides_global_in_dataset_status() -> None:
    result = compile_route_scope(
        "All Routes",
        "The affected routes are not part of this dataset.",
        ROUTES,
    )

    assert result.scope_type == ScopeType.GLOBAL
    assert result.scope_status == ScopeStatus.OUTSIDE_DATASET
    assert result.warnings == ("text_excludes_dataset_scope",)


@pytest.mark.parametrize("scope", ["", "   ", "Mumbai/Pune", "Mumbai-Pune;Delhi-Jaipur"])
def test_blank_or_malformed_scope_is_rejected(scope: str) -> None:
    with pytest.raises(ScopeCompilationError):
        compile_route_scope(scope, "Valid note.", ROUTES)


def test_empty_route_universe_is_rejected() -> None:
    with pytest.raises(ScopeCompilationError, match="must not be empty"):
        compile_route_scope("All Routes", "Valid note.", frozenset())
