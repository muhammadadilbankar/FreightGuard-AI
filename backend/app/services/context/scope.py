"""Deterministic route-scope compilation for context notes."""

import re

from ...domain.context_notes import RouteScope, ScopeStatus, ScopeType
from .errors import ScopeCompilationError

_ROUTE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z ]*-[A-Za-z][A-Za-z ]*$")
_DATASET_EXCLUSION = re.compile(
    r"\b(?:affected routes? (?:are|is) not part of this dataset|"
    r"outside this dataset|does not apply to routes? in this dataset)\b",
    re.IGNORECASE,
)


def compile_route_scope(
    applies_to: str,
    original_text: str,
    known_routes: frozenset[str],
) -> RouteScope:
    """Compile global or one-route applicability without fuzzy matching."""
    if not isinstance(applies_to, str) or not applies_to.strip():
        raise ScopeCompilationError("applies_to must contain non-blank text.")
    if not isinstance(original_text, str) or not original_text.strip():
        raise ScopeCompilationError("original_text must contain non-blank text.")
    if not known_routes:
        raise ScopeCompilationError("known_routes must not be empty.")

    value = applies_to.strip()
    warnings: set[str] = set()
    if value.casefold() == "all routes":
        scope_type = ScopeType.GLOBAL
        routes: tuple[str, ...] = ()
        status = ScopeStatus.IN_DATASET
    else:
        if _ROUTE_PATTERN.fullmatch(value) is None:
            raise ScopeCompilationError(
                "applies_to must be 'All Routes' or one directional route."
            )
        scope_type = ScopeType.ROUTE
        routes = (value,)
        if value in known_routes:
            status = ScopeStatus.IN_DATASET
        else:
            status = ScopeStatus.OUTSIDE_DATASET
            warnings.add("explicit_route_not_in_dataset")

    if _DATASET_EXCLUSION.search(original_text):
        status = ScopeStatus.OUTSIDE_DATASET
        warnings.add("text_excludes_dataset_scope")

    return RouteScope(
        scope_type=scope_type,
        applies_to_routes=routes,
        scope_status=status,
        warnings=tuple(sorted(warnings)),
    )
