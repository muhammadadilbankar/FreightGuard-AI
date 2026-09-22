"""Regression coverage for the untouched supplied challenge inputs."""

import hashlib
import math
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.services.ingestion.contracts import (
    CONTEXT_NOTE_COLUMNS,
    CONTEXT_NOTES_FILENAME,
    OUTPUT_COLUMNS,
    OUTPUT_CONTRACT_FILENAME,
    SHIPMENT_COLUMNS,
    SHIPMENT_DERIVED_COLUMNS,
    SHIPMENTS_FILENAME,
)
from backend.app.services.ingestion.loaders import load_input_bundle


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_supplied_inputs_validate_normalize_and_remain_unchanged() -> None:
    settings = Settings(_env_file=None)
    paths = tuple(
        settings.input_data_dir / filename
        for filename in (
            SHIPMENTS_FILENAME,
            CONTEXT_NOTES_FILENAME,
            OUTPUT_CONTRACT_FILENAME,
        )
    )
    hashes_before = tuple(_sha256(path) for path in paths)

    bundle = load_input_bundle(settings)

    shipments = bundle.shipments
    notes = bundle.context_notes
    assert len(shipments) == 2940
    assert len(notes) == 10
    assert tuple(shipments.columns) == SHIPMENT_COLUMNS + SHIPMENT_DERIVED_COLUMNS
    assert tuple(notes.columns) == CONTEXT_NOTE_COLUMNS
    assert bundle.output_columns == OUTPUT_COLUMNS
    assert shipments["shipment_id"].nunique() == 2940
    assert not shipments.loc[:, SHIPMENT_COLUMNS].isna().any().any()
    assert (shipments["week_of"].dt.weekday == 0).all()
    assert shipments["route"].nunique() == 7
    assert shipments["week_of"].nunique() == 104
    assert shipments["shipment_date"].min().date().isoformat() == "2024-01-01"
    assert shipments["shipment_date"].max().date().isoformat() == "2025-12-28"
    assert shipments["tonne_km"].map(math.isfinite).all()
    assert (shipments["tonne_km"] > 0).all()
    assert tuple(_sha256(path) for path in paths) == hashes_before
