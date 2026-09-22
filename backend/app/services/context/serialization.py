"""Deterministic JSONL persistence and independent compiled-note validation."""

from collections.abc import Sequence
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile

from pydantic import ValidationError

from ...core.logging import LOGGER_NAME
from ...domain.context_notes import CompiledContextNote
from ..reporting.errors import CompiledNotesSerializationError

logger = logging.getLogger(f"{LOGGER_NAME}.context_serialization")

COMPILED_NOTES_FILENAME = "compiled_context_notes.jsonl"


def write_compiled_notes_jsonl(
    notes: Sequence[CompiledContextNote], destination: Path
) -> Path:
    """Atomically write stable, compact, schema-versioned JSONL bytes."""
    ordered = _validated_notes(notes)
    destination = Path(destination)
    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        ) as temporary:
            temporary_path = Path(temporary.name)
            for note in ordered:
                payload = note.model_dump(mode="json")
                temporary.write(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )
        os.replace(temporary_path, destination)
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise CompiledNotesSerializationError(
            f"Unable to write compiled-note JSONL: {exc}"
        ) from exc
    logger.info("Wrote compiled notes path=%s notes=%d", destination, len(ordered))
    return destination


def read_compiled_notes_jsonl(path: Path) -> tuple[CompiledContextNote, ...]:
    """Read each physical JSONL line independently through the typed model."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise CompiledNotesSerializationError(
            f"Unable to read compiled-note JSONL: {exc}"
        ) from exc
    if not raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise CompiledNotesSerializationError(
            "Compiled-note JSONL must end with exactly one newline."
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CompiledNotesSerializationError(
            "Compiled-note JSONL must use UTF-8."
        ) from exc
    parsed: list[CompiledContextNote] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise CompiledNotesSerializationError(
                "Compiled-note JSONL must not contain blank lines."
            )
        try:
            payload = json.loads(line)
            parsed.append(CompiledContextNote.model_validate(payload))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CompiledNotesSerializationError(
                f"Compiled-note JSONL line {line_number} is invalid."
            ) from exc
    return _validated_notes(parsed)


def validate_compiled_notes_jsonl(
    path: Path, expected_notes: Sequence[CompiledContextNote]
) -> tuple[CompiledContextNote, ...]:
    """Validate serialized order, count, schema, and full model equality."""
    expected = _validated_notes(expected_notes)
    actual = read_compiled_notes_jsonl(path)
    if actual != expected:
        raise CompiledNotesSerializationError(
            "Compiled-note JSONL does not equal the in-memory contract."
        )
    logger.info(
        "Validated compiled notes path=%s notes=%d contract=PASS", path, len(actual)
    )
    return actual


def compiled_notes_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of the compiled-note artifact."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise CompiledNotesSerializationError(
            f"Unable to hash compiled-note JSONL: {exc}"
        ) from exc


def _validated_notes(
    notes: Sequence[CompiledContextNote],
) -> tuple[CompiledContextNote, ...]:
    if not notes:
        raise CompiledNotesSerializationError("Compiled notes must not be empty.")
    if any(not isinstance(note, CompiledContextNote) for note in notes):
        raise CompiledNotesSerializationError(
            "Every serialized item must be a CompiledContextNote."
        )
    ordered = tuple(sorted(notes, key=lambda item: item.note_id))
    if len({note.note_id for note in ordered}) != len(ordered):
        raise CompiledNotesSerializationError("Compiled note IDs must be unique.")
    return ordered
