"""Deterministic atomic JSON serialization for operational analyses."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from ...domain.root_cause import RootCauseAnalysis

ROOT_CAUSE_FILENAME = "operational_root_causes.json"


def serialize_root_causes(results: tuple[RootCauseAnalysis, ...]) -> bytes:
    ordered = sorted(
        results,
        key=lambda item: (item.week_of, item.route, item.route_type, item.candidate_key),
    )
    payload = {
        "schema_version": "1.0",
        "analyses": [item.model_dump(mode="json") for item in ordered],
    }
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_root_cause_artifact(
    results: tuple[RootCauseAnalysis, ...], path: Path
) -> str:
    content = serialize_root_causes(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return hashlib.sha256(content).hexdigest()
