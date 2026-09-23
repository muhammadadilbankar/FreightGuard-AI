"""Context compilation regression checks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from collections.abc import Sequence

from ..domain.context_notes import CompiledContextNote
from ..domain.evaluation import EvaluationCheck, EvaluationDomain
from .contracts import check


def evaluate_compilation(
    notes: Sequence[CompiledContextNote], fixture_path: Path
) -> list[EvaluationCheck]:
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    actual = [
        {
            "note_id": note.note_id,
            "scope_type": note.scope_type.value,
            "scope_status": note.scope_status.value,
            "cost_impact_status": note.cost_impact_status.value,
            "effective_to_open": note.effective_to is None,
        }
        for note in sorted(notes, key=lambda item: item.note_id)
    ]
    scope = Counter(note.scope_type.value for note in notes)
    impacts = Counter(note.cost_impact_status.value for note in notes)
    domain = EvaluationDomain.CONTEXT_COMPILATION
    unsafe_positive = {
        note.note_id
        for note in notes
        if note.note_id in {"N005", "N006", "N008", "N009", "N010"}
        and note.cost_impact_status.value == "explicit_increase"
    }
    n007 = next(note for note in notes if note.note_id == "N007")
    return [
        check(
            "compilation.count",
            domain,
            "Exactly ten notes compile",
            len(notes) == 10,
            expected=10,
            actual=len(notes),
        ),
        check(
            "compilation.scope_counts",
            domain,
            "Four global and six route-scoped notes",
            scope == {"global": 4, "route": 6},
            expected={"global": 4, "route": 6},
            actual=dict(scope),
        ),
        check(
            "compilation.impact_counts",
            domain,
            "Impact classifications match supplied contract",
            impacts
            == {
                "explicit_increase": 3,
                "explicit_no_material_impact": 1,
                "normal_or_stable_operations": 3,
                "not_stated": 2,
                "explicit_no_rate_change": 1,
            },
            expected={
                "explicit_increase": 3,
                "explicit_no_material_impact": 1,
                "normal_or_stable_operations": 3,
                "not_stated": 2,
                "explicit_no_rate_change": 1,
            },
            actual=dict(impacts),
        ),
        check(
            "compilation.interval_counts",
            domain,
            "Five bounded and five open-ended intervals",
            sum(note.effective_to is None for note in notes) == 5,
            expected={"bounded": 5, "open": 5},
            actual={
                "bounded": sum(note.effective_to is not None for note in notes),
                "open": sum(note.effective_to is None for note in notes),
            },
        ),
        check(
            "compilation.fixture",
            domain,
            "Compiled note classifications match golden fixture",
            actual == expected,
            expected=expected,
            actual=actual,
        ),
        check(
            "compilation.no_false_positive_notes",
            domain,
            "No-impact/stable notes cannot become positive cost evidence",
            not unsafe_positive,
            expected=[],
            actual=sorted(unsafe_positive),
        ),
        check(
            "compilation.no_inferred_decrease",
            domain,
            "Improved roads do not infer a cost decrease",
            n007.impact_direction.value == "unknown",
            expected="unknown",
            actual=n007.impact_direction.value,
        ),
    ]
