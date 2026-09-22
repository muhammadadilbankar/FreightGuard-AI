"""Public deterministic context-note compilation services."""

from .compiler import compile_context_note, compile_context_notes
from .errors import (
    CompiledNoteContractError,
    ContextCompilationError,
    ContextInputError,
    ImpactCompilationError,
    ScopeCompilationError,
    TemporalCompilationError,
)
from .impact import compile_impact_claim
from .scope import compile_route_scope
from .serialization import (
    COMPILED_NOTES_FILENAME,
    compiled_notes_sha256,
    read_compiled_notes_jsonl,
    validate_compiled_notes_jsonl,
    write_compiled_notes_jsonl,
)
from .temporal import resolve_effective_interval

__all__ = [
    "COMPILED_NOTES_FILENAME",
    "CompiledNoteContractError",
    "ContextCompilationError",
    "ContextInputError",
    "ImpactCompilationError",
    "ScopeCompilationError",
    "TemporalCompilationError",
    "compile_context_note",
    "compile_context_notes",
    "compile_impact_claim",
    "compile_route_scope",
    "compiled_notes_sha256",
    "read_compiled_notes_jsonl",
    "resolve_effective_interval",
    "validate_compiled_notes_jsonl",
    "write_compiled_notes_jsonl",
]
