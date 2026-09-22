"""Bundle-level error aggregation tests."""

import shutil
from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.services.ingestion.contracts import (
    CONTEXT_NOTES_FILENAME,
    OUTPUT_CONTRACT_FILENAME,
    SHIPMENTS_FILENAME,
)
from backend.app.services.ingestion.errors import DataValidationError, InputFileError
from backend.app.services.ingestion.loaders import load_input_bundle

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_bundle_collects_independent_dataset_errors(tmp_path: Path) -> None:
    shipment = (FIXTURES / "shipments_valid_minimal.csv").read_text(encoding="utf-8")
    notes = (FIXTURES / "context_notes_valid_minimal.csv").read_text(encoding="utf-8")
    (tmp_path / SHIPMENTS_FILENAME).write_text(
        shipment.replace("12.25", "0"), encoding="utf-8"
    )
    (tmp_path / CONTEXT_NOTES_FILENAME).write_text(
        notes.replace("2024-01-01", "01/01/2024"), encoding="utf-8"
    )
    shutil.copyfile(
        FIXTURES / "output_contract_valid.csv", tmp_path / OUTPUT_CONTRACT_FILENAME
    )

    with pytest.raises(DataValidationError) as caught:
        load_input_bundle(Settings(input_data_dir=tmp_path, _env_file=None))

    assert {issue.dataset for issue in caught.value.issues} == {
        "shipments",
        "context_notes",
    }
    assert {issue.code for issue in caught.value.issues} >= {
        "non_positive_value",
        "invalid_date",
    }


def test_bundle_uses_file_error_precedence_but_keeps_other_issues(tmp_path: Path) -> None:
    shipment = (FIXTURES / "shipments_valid_minimal.csv").read_text(encoding="utf-8")
    (tmp_path / SHIPMENTS_FILENAME).write_text(
        shipment.replace("12.25", "0"), encoding="utf-8"
    )
    shutil.copyfile(
        FIXTURES / "output_contract_valid.csv", tmp_path / OUTPUT_CONTRACT_FILENAME
    )

    with pytest.raises(InputFileError) as caught:
        load_input_bundle(Settings(input_data_dir=tmp_path, _env_file=None))

    assert {issue.code for issue in caught.value.issues} >= {
        "file_not_found",
        "non_positive_value",
    }
