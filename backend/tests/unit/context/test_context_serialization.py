"""Tests for stable JSONL writing, reading, and round-trip validation."""

from datetime import date
import json
from pathlib import Path

import pytest

from backend.app.domain.context_notes import (
    COMPILED_NOTE_FIELDS,
    CompiledContextNote,
    CostImpactStatus,
    EventType,
    ImpactDirection,
    ScopeStatus,
    ScopeType,
    TemporalBasis,
)
from backend.app.services.context import (
    compiled_notes_sha256,
    read_compiled_notes_jsonl,
    validate_compiled_notes_jsonl,
    write_compiled_notes_jsonl,
)
from backend.app.services.context import serialization
from backend.app.services.reporting import CompiledNotesSerializationError


def _note(note_id: str, text: str = "Café \"quoted\"\nnext line") -> CompiledContextNote:
    return CompiledContextNote(
        note_id=note_id,
        source_date=date(2025, 1, 1),
        source_applies_to="All Routes",
        original_text=text,
        scope_type=ScopeType.GLOBAL,
        applies_to_routes=(),
        scope_status=ScopeStatus.IN_DATASET,
        effective_from=date(2025, 1, 1),
        effective_to=None,
        temporal_basis=TemporalBasis.OPEN_ENDED_START,
        event_type=EventType.OTHER,
        impact_direction=ImpactDirection.UNKNOWN,
        cost_impact_status=CostImpactStatus.NOT_STATED,
        affects_transport_cost=None,
        negates_cost_increase=False,
        magnitude_text=None,
        compilation_warnings=("transport_cost_impact_not_stated",),
    )


def test_jsonl_preserves_schema_order_types_unicode_and_embedded_text(
    tmp_path: Path,
) -> None:
    notes = (_note("N002"), _note("N001", "Plain"))
    path = write_compiled_notes_jsonl(notes, tmp_path / "notes.jsonl")

    raw = path.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    first = json.loads(lines[0])

    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert len(lines) == 2
    assert list(first) == list(COMPILED_NOTE_FIELDS)
    assert first["note_id"] == "N001"
    assert first["effective_to"] is None
    assert isinstance(first["applies_to_routes"], list)
    assert isinstance(first["negates_cost_increase"], bool)
    assert "Café" in raw.decode("utf-8")
    assert read_compiled_notes_jsonl(path) == tuple(sorted(notes, key=lambda n: n.note_id))


def test_two_writes_are_byte_identical_and_validate(tmp_path: Path) -> None:
    notes = (_note("N001"), _note("N002"))
    first = write_compiled_notes_jsonl(notes, tmp_path / "one.jsonl")
    second = write_compiled_notes_jsonl(notes, tmp_path / "two.jsonl")

    assert validate_compiled_notes_jsonl(first, notes) == notes
    assert first.read_bytes() == second.read_bytes()
    assert compiled_notes_sha256(first) == compiled_notes_sha256(second)


@pytest.mark.parametrize("content", [b"", b"{}", b"{}\n\n", b"not-json\n"])
def test_invalid_jsonl_contract_fails(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_bytes(content)

    with pytest.raises(CompiledNotesSerializationError):
        read_compiled_notes_jsonl(path)


def test_empty_note_output_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CompiledNotesSerializationError, match="must not be empty"):
        write_compiled_notes_jsonl((), tmp_path / "empty.jsonl")


def test_failed_replace_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "notes.jsonl"
    destination.write_text("existing\n", encoding="utf-8")

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("simulated failure")

    monkeypatch.setattr(serialization.os, "replace", fail_replace)

    with pytest.raises(CompiledNotesSerializationError, match="Unable to write"):
        write_compiled_notes_jsonl((_note("N001"),), destination)

    assert destination.read_text(encoding="utf-8") == "existing\n"
    assert not list(tmp_path.glob("*.tmp"))
